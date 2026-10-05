"""Entrada com e-mail e senha no próprio CRM (#89, 05/10/2026)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import jwt
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.catalogo import PERMISSOES, permissoes_do_comercial
from crm.acesso.entrada import (
    ConfiguracaoDeEntrada, ConfiguracaoDeSenha, EntradaMalConfigurada, ler_configuracao,
)
from crm.acesso.senha import Tentativas, confere, gerar_hash
from crm.api.app import criar_app
from crm.db.modelos import Perfil, RegistroDeAlteracao, Usuario

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"
ADMIN_EMAIL = "admin@crmcs.com.br"
CONFIG = ConfiguracaoDeSenha(ADMIN_EMAIL, SEGREDO, "Admin@123")
SENHA_ERRADA = {"detail": "E-mail ou senha incorretos."}
SESSAO_INVALIDA = {"detail": "Sessão expirada ou inválida. Entre de novo."}


class Relogio:
    def __init__(self) -> None:
        self.agora = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.agora


@pytest.fixture
def base(engine):
    """Os dois perfis da migração e a Karine no Comercial, já com senha."""
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        comercial = Perfil(nome="Comercial", permissoes=permissoes_do_comercial())
        s.add(comercial)
        s.flush()
        karine = Usuario(email="karine@grupocriterio.com.br", nome="Karine", perfil_id=comercial.id,
                         senha_hash=gerar_hash("karine-123"))
        s.add(karine)
        s.commit()
        return {"comercial": comercial.id, "karine": karine.id}


@pytest.fixture
def relogio():
    return Relogio()


def _app(engine, config=CONFIG, relogio=None):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return criar_app(fabrica, entrada=config, tentativas=Tentativas(relogio) if relogio else None)


@pytest.fixture
def cliente(engine, base, relogio):
    with TestClient(_app(engine, relogio=relogio)) as c:
        yield c


def entrar(c: TestClient, email: str, senha: str):
    return c.post("/api/acesso/login", json={"email": email, "senha": senha})


def cab(c: TestClient, email: str, senha: str) -> dict:
    r = entrar(c, email, senha)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ------------------------------------------------------------------ configuração e modos

def test_precedencia_dos_modos_pelo_env():
    microsoft = {"CRM_ENTRA_TENANT_ID": "t", "CRM_ENTRA_CLIENT_ID": "c"}
    senha = {"CRM_ADMIN_EMAIL": " Admin@CRMCS.com.br ", "CRM_SEGREDO_SESSAO": SEGREDO, "CRM_ADMIN_SENHA_INICIAL": "Admin@123"}
    c = ler_configuracao({**microsoft, **senha})
    assert isinstance(c, ConfiguracaoDeSenha) and c.admin_email == ADMIN_EMAIL and c.modo == "senha"
    assert isinstance(ler_configuracao(microsoft), ConfiguracaoDeEntrada)
    assert ler_configuracao({}) is None
    assert SEGREDO not in repr(c) and "Admin@123" not in repr(c)


def test_modo_senha_sem_segredo_nao_sobe():
    with pytest.raises(EntradaMalConfigurada, match="falta CRM_SEGREDO_SESSAO") as erro:
        ler_configuracao({"CRM_ADMIN_EMAIL": ADMIN_EMAIL, "CRM_ADMIN_SENHA_INICIAL": "Admin@123"})
    assert "Admin@123" not in str(erro.value)


def test_hash_com_sal_e_conferencia():
    h = gerar_hash("Admin@123")
    assert h.startswith("scrypt$16384$8$1$") and "Admin@123" not in h
    assert h != gerar_hash("Admin@123")  # sal aleatório
    assert confere("Admin@123", h) and not confere("admin@123", h)
    assert not confere("Admin@123", None) and not confere("Admin@123", "lixo") and not confere("x", "scrypt$1$2$3$!!$!!")


def test_health_responde_sem_login_e_nao_aparece_no_mapa(cliente):
    """O healthcheck do container não tem token: `/health` fica fora de `/api` e do login."""
    r = cliente.get("/health")
    assert (r.status_code, r.json()) == (200, {"status": "healthy"})
    assert cliente.get("/api/listas").status_code == 401  # o resto continua fechado
    assert cliente.get("/openapi.json").status_code == 404


def test_health_nao_depende_do_banco(engine, base):
    """Não consulta o banco: a fábrica que explode não muda a resposta."""
    def fabrica_quebrada():
        raise AssertionError("o /health não pode abrir sessão")

    app = criar_app(fabrica_quebrada, entrada=None)
    with TestClient(app) as c:
        r = c.get("/health")
    assert (r.status_code, r.json()) == (200, {"status": "healthy"})


def test_entrada_publica_diz_o_modo(cliente):
    assert cliente.get("/api/acesso/entrada").json() == {"modo": "senha"}


# ------------------------------------------------------------------ administrador semeado pelo .env

def test_administrador_nasce_ao_subir_e_entra(cliente, engine):
    with Session(engine) as s:
        u = s.scalar(sa.select(Usuario).where(Usuario.email == ADMIN_EMAIL))
        assert u.perfil.administrador and u.liberado_por == "CRM_ADMIN_EMAIL"
        assert u.senha_hash.startswith("scrypt$") and "Admin@123" not in u.senha_hash
    r = entrar(cliente, "  Admin@CRMCS.com.br ", "Admin@123")
    assert r.status_code == 200
    doc = r.json()
    assert {k: doc[k] for k in ("email", "nome", "perfil", "administrador")} == {
        "email": ADMIN_EMAIL, "nome": None, "perfil": "Administrador", "administrador": True}
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?(Z|[+-]\d\d:\d\d)", doc["expira_em"]), doc["expira_em"]  # fuso explícito
    expira = datetime.fromisoformat(doc["expira_em"])
    assert expira.tzinfo is not None
    assert timedelta(hours=11, minutes=59) < expira - datetime.now(timezone.utc) <= timedelta(hours=12)
    assert jwt.decode(doc["token"], SEGREDO, algorithms=["HS256"])["sub"] == ADMIN_EMAIL

    h = {"Authorization": f"Bearer {doc['token']}"}
    eu = cliente.get("/api/eu", headers=h).json()
    assert eu["modo"] == "senha" == cliente.get("/api/acesso/entrada").json()["modo"]  # a tela mostra "Trocar senha" por ele
    assert eu["email"] == ADMIN_EMAIL and set(eu["permissoes"]) == PERMISSOES
    pessoas = cliente.get("/api/acesso/usuarios", headers=h).json()
    assert all("senha" not in k for p in pessoas for k in p)


def test_semente_nao_sobrescreve_a_senha(engine, base):
    with TestClient(_app(engine)) as c:
        h = cab(c, ADMIN_EMAIL, "Admin@123")
        assert c.post("/api/acesso/senha", headers=h, json={"senha_atual": "Admin@123", "senha_nova": "outra-senha"}).status_code == 200
    with TestClient(_app(engine)) as c:  # reiniciou: o .env ainda diz Admin@123
        assert entrar(c, ADMIN_EMAIL, "Admin@123").status_code == 401
        assert entrar(c, ADMIN_EMAIL, "outra-senha").status_code == 200
    with Session(engine) as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(Usuario).where(Usuario.email == ADMIN_EMAIL)) == 1


def test_conta_sem_senha_do_tempo_da_microsoft_recebe_a_inicial(engine, base):
    with Session(engine) as s:
        s.add(Usuario(email=ADMIN_EMAIL, nome="Eduardo", perfil_id=base["comercial"]))
        s.commit()
    with TestClient(_app(engine)) as c:
        doc = entrar(c, ADMIN_EMAIL, "Admin@123").json()
        assert doc["nome"] == "Eduardo" and doc["perfil"] == "Comercial"  # só a senha; o resto fica


@pytest.mark.parametrize("senha, frase", [(None, "falta CRM_ADMIN_SENHA_INICIAL"), ("curta", "pelo menos 8 caracteres")])
def test_sem_senha_inicial_boa_a_api_nao_sobe(engine, base, senha, frase):
    with pytest.raises(EntradaMalConfigurada, match=frase):
        with TestClient(_app(engine, ConfiguracaoDeSenha(ADMIN_EMAIL, SEGREDO, senha))):
            pass


# ------------------------------------------------------------------ login

def test_email_inexistente_e_senha_errada_dao_a_mesma_resposta(cliente):
    a, b = entrar(cliente, "ninguem@crmcs.com.br", "Admin@123"), entrar(cliente, ADMIN_EMAIL, "errada-123")
    assert (a.status_code, a.json()) == (b.status_code, b.json()) == (401, SENHA_ERRADA)


def test_cinco_erros_seguidos_bloqueiam_o_email_por_15_minutos(cliente, relogio):
    for _ in range(5):
        assert entrar(cliente, ADMIN_EMAIL, "errada-123").status_code == 401
    r = entrar(cliente, ADMIN_EMAIL, "Admin@123")  # nem a senha certa passa no bloqueio
    assert (r.status_code, r.json()) == (429, {"detail": "Muitas tentativas. Tente de novo em 15 minutos."})
    assert entrar(cliente, "karine@grupocriterio.com.br", "karine-123").status_code == 200  # outro e-mail segue
    relogio.agora += timedelta(minutes=14, seconds=30)
    assert entrar(cliente, ADMIN_EMAIL, "Admin@123").json()["detail"] == "Muitas tentativas. Tente de novo em 1 minuto."
    relogio.agora += timedelta(seconds=30)
    assert entrar(cliente, ADMIN_EMAIL, "Admin@123").status_code == 200


def test_acertar_zera_e_erros_antigos_saem_da_conta(cliente, relogio):
    for _ in range(4):
        entrar(cliente, ADMIN_EMAIL, "errada-123")
    assert entrar(cliente, ADMIN_EMAIL, "Admin@123").status_code == 200
    for _ in range(4):
        entrar(cliente, ADMIN_EMAIL, "errada-123")
    relogio.agora += timedelta(minutes=16)  # os 4 erros ficaram para trás da janela
    assert entrar(cliente, ADMIN_EMAIL, "errada-123").status_code == 401
    assert entrar(cliente, ADMIN_EMAIL, "Admin@123").status_code == 200


def test_conta_desativada_nao_entra_e_perde_a_sessao_aberta(cliente, base):
    karine = cab(cliente, "karine@grupocriterio.com.br", "karine-123")
    assert cliente.get("/api/oportunidades", headers=karine).status_code == 200
    admin = cab(cliente, ADMIN_EMAIL, "Admin@123")
    assert cliente.patch(f"/api/acesso/usuarios/{base['karine']}", headers=admin, json={"ativo": False}).status_code == 200
    r = cliente.get("/api/oportunidades", headers=karine)
    assert r.status_code == 401 and "desativada" in r.json()["detail"]
    assert entrar(cliente, "karine@grupocriterio.com.br", "errada-123").json() == SENHA_ERRADA  # sem a senha, nada se revela
    r = entrar(cliente, "karine@grupocriterio.com.br", "karine-123")
    assert r.status_code == 403 and "desativada" in r.json()["detail"]


# ------------------------------------------------------------------ sessão nas rotas protegidas

def test_rota_protegida_sem_sessao_ou_com_sessao_que_nao_vale(cliente):
    r = cliente.get("/api/listas")
    assert r.status_code == 401 and r.json() == {"detail": "Entre com e-mail e senha para usar o CRM."}
    vencido = jwt.encode({"sub": ADMIN_EMAIL, "exp": datetime.now(timezone.utc) - timedelta(seconds=1)}, SEGREDO, algorithm="HS256")
    outro_segredo = jwt.encode({"sub": ADMIN_EMAIL, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, "x" * 40, algorithm="HS256")
    sem_validade = jwt.encode({"sub": ADMIN_EMAIL}, SEGREDO, algorithm="HS256")
    sem_carimbo = jwt.encode({"sub": ADMIN_EMAIL, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}, SEGREDO, algorithm="HS256")
    carimbo_errado = jwt.encode({"sub": ADMIN_EMAIL, "sv": "0" * 16, "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                                SEGREDO, algorithm="HS256")
    for token in (vencido, outro_segredo, sem_validade, sem_carimbo, carimbo_errado, "lixo", "karine@grupocriterio.com.br|Karine"):
        r = cliente.get("/api/listas", headers={"Authorization": f"Bearer {token}"})
        assert (r.status_code, r.json()) == (401, SESSAO_INVALIDA), token


def test_o_perfil_vale_no_modo_senha(cliente):
    karine = cab(cliente, "karine@grupocriterio.com.br", "karine-123")
    eu = cliente.get("/api/eu", headers=karine).json()
    assert eu["modo"] == "senha" and eu["perfil"] == "Comercial" and not eu["administrador"]
    assert cliente.get("/api/acesso/perfis", headers=karine).status_code == 403


# ------------------------------------------------------------------ senhas

def test_trocar_a_propria_senha(cliente, engine):
    karine = cab(cliente, "karine@grupocriterio.com.br", "karine-123")
    r = cliente.post("/api/acesso/senha", headers=karine, json={"senha_atual": "errada-123", "senha_nova": "nova-senha-1"})
    assert (r.status_code, r.json()) == (400, {"detail": "A senha atual não confere."})
    r = cliente.post("/api/acesso/senha", headers=karine, json={"senha_atual": "karine-123", "senha_nova": "curta"})
    assert (r.status_code, r.json()) == (422, {"detail": "A senha precisa ter pelo menos 8 caracteres."})
    outra_aba = cab(cliente, "karine@grupocriterio.com.br", "karine-123")
    r = cliente.post("/api/acesso/senha", headers=karine, json={"senha_atual": "karine-123", "senha_nova": "nova-senha-1"})
    assert r.status_code == 200
    doc = r.json()  # sessão nova, no formato do login, que a tela guarda no lugar da antiga
    assert set(doc) == {"token", "expira_em", "email", "nome", "perfil", "administrador"}
    assert (doc["email"], doc["perfil"]) == ("karine@grupocriterio.com.br", "Comercial")
    for velha in (karine, outra_aba):  # a senha mudou: as sessões abertas com a antiga caem
        assert (cliente.get("/api/eu", headers=velha).status_code, cliente.get("/api/eu", headers=velha).json()) == (401, SESSAO_INVALIDA)
    assert cliente.get("/api/eu", headers={"Authorization": f"Bearer {doc['token']}"}).status_code == 200
    assert entrar(cliente, "karine@grupocriterio.com.br", "karine-123").status_code == 401
    assert entrar(cliente, "karine@grupocriterio.com.br", "nova-senha-1").status_code == 200
    with Session(engine) as s:  # o histórico diz que mudou, sem o valor
        linha = s.scalar(sa.select(RegistroDeAlteracao).where(RegistroDeAlteracao.campo == "senha_hash"))
        assert (linha.usuario_email, linha.antes, linha.depois) == ("karine@grupocriterio.com.br", None, "(alterada)")
        assert not s.scalar(sa.select(sa.func.count()).select_from(RegistroDeAlteracao).where(
            sa.or_(RegistroDeAlteracao.antes.like("scrypt$%"), RegistroDeAlteracao.depois.like("scrypt$%"))))


def test_quem_administra_redefine_a_senha_de_alguem(cliente, base, relogio):
    aberta = cab(cliente, "karine@grupocriterio.com.br", "karine-123")
    for _ in range(5):
        entrar(cliente, "karine@grupocriterio.com.br", "errada-123")
    assert entrar(cliente, "karine@grupocriterio.com.br", "karine-123").status_code == 429
    admin = cab(cliente, ADMIN_EMAIL, "Admin@123")
    url = f"/api/acesso/usuarios/{base['karine']}/senha"
    assert cliente.post(url, headers=admin, json={"senha": "curta"}).status_code == 422
    assert cliente.post("/api/acesso/usuarios/999/senha", headers=admin, json={"senha": "provisoria-1"}).status_code == 404
    assert cliente.post(url, headers=admin, json={"senha": "provisoria-1"}).status_code == 204
    assert cliente.get("/api/eu", headers=aberta).json() == SESSAO_INVALIDA  # a sessão dela caiu
    assert cliente.get("/api/eu", headers=admin).status_code == 200  # a de quem redefiniu, não
    karine = cab(cliente, "karine@grupocriterio.com.br", "provisoria-1")  # e o bloqueio saiu
    r = cliente.post(url, headers=karine, json={"senha": "outra-senha"})
    assert r.status_code == 403 and r.json()["detail"] == "O seu perfil não libera esta ação."


def test_pessoa_cadastrada_com_senha_nasce_administrador(cliente, base):
    admin = cab(cliente, ADMIN_EMAIL, "Admin@123")
    r = cliente.post("/api/acesso/usuarios", headers=admin, json={"email": "Ana@CRMCS.com.br"})
    assert r.status_code == 422 and "senha provisória" in r.json()["detail"]
    r = cliente.post("/api/acesso/usuarios", headers=admin, json={"email": "ana@crmcs.com.br", "senha": "1234567"})
    assert (r.status_code, r.json()) == (422, {"detail": "A senha precisa ter pelo menos 8 caracteres."})
    r = cliente.post("/api/acesso/usuarios", headers=admin, json={"email": "Ana@CRMCS.com.br", "senha": "provisoria-1"})
    assert r.status_code == 200, r.text
    doc = r.json()
    assert (doc["email"], doc["perfil"], doc["liberado_por"]) == ("ana@crmcs.com.br", "Administrador", ADMIN_EMAIL)
    assert not any("senha" in k for k in doc)
    assert entrar(cliente, "ana@crmcs.com.br", "provisoria-1").json()["administrador"] is True
    # Como a tela manda: sempre com o perfil pré-selecionado, nunca com nome.
    r = cliente.post("/api/acesso/usuarios", headers=admin,
                     json={"email": "bruno@crmcs.com.br", "senha": "provisoria-2", "perfil_id": base["comercial"]})
    assert r.status_code == 200 and (r.json()["perfil"], r.json()["nome"]) == ("Comercial", None)
    assert entrar(cliente, "bruno@crmcs.com.br", "provisoria-2").json()["perfil"] == "Comercial"


# ------------------------------------------------------------------ os outros modos seguem como antes

def test_sem_login_as_rotas_de_senha_nao_existem_e_a_entrada_segue_igual(engine, base):
    with TestClient(_app(engine, config=None)) as c:
        assert c.get("/api/acesso/entrada").json() == {"modo": "local", "tenant_id": None, "client_id": None, "escopo": None}
        assert c.get("/api/eu").json()["modo"] == "local"
        assert entrar(c, ADMIN_EMAIL, "Admin@123").status_code == 404
        assert c.post("/api/acesso/senha", json={"senha_atual": "a", "senha_nova": "nova-senha-1"}).status_code == 404
        r = c.post("/api/acesso/usuarios", json={"email": "ana@crmcs.com.br"})  # sem login, senha não é obrigatória
        assert r.status_code == 200 and r.json()["perfil"] == "Administrador"
    with Session(engine) as s:
        assert s.scalar(sa.select(Usuario).where(Usuario.email == ADMIN_EMAIL)) is None  # nada semeado


def test_no_modo_microsoft_o_login_com_senha_nao_existe(engine, base):
    config = ConfiguracaoDeEntrada("t", "c", frozenset())
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=config, validar_token=lambda t: {"preferred_username": t})) as c:
        assert c.get("/api/acesso/entrada").json()["modo"] == "microsoft"
        assert entrar(c, "karine@grupocriterio.com.br", "karine-123").status_code == 404
        r = c.get("/api/listas")
        assert r.status_code == 401 and "conta Microsoft" in r.json()["detail"]
        eu = c.get("/api/eu", headers={"Authorization": "Bearer karine@grupocriterio.com.br"}).json()
        assert eu["modo"] == "microsoft" and eu["perfil"] == "Comercial"


# ------------------------------------------------------------------ endurecimento antes da internet (05/10/2026)

def test_bloqueio_e_por_ip_e_nao_tranca_o_admin_de_outro_ip(engine, base, relogio):
    app = _app(engine, relogio=relogio)
    with TestClient(app, client=("203.0.113.9", 1)) as atacante, TestClient(app, client=("10.0.0.2", 1)) as escritorio:
        for _ in range(5):
            assert entrar(atacante, ADMIN_EMAIL, "errada-123").status_code == 401
        assert entrar(atacante, ADMIN_EMAIL, "Admin@123").status_code == 429
        assert entrar(escritorio, ADMIN_EMAIL, "Admin@123").status_code == 200  # o admin segue entrando


def test_limite_por_ip_com_emails_variados(engine, base, relogio):
    app = _app(engine, relogio=relogio)
    with TestClient(app, client=("203.0.113.9", 1)) as atacante, TestClient(app, client=("10.0.0.2", 1)) as escritorio:
        for i in range(20):  # 1 erro por e-mail: nunca chega aos 5 de um par, mas soma 20 no IP
            assert entrar(atacante, f"pessoa{i}@crmcs.com.br", "Senha@2026").status_code == 401
        r = entrar(atacante, "karine@grupocriterio.com.br", "karine-123")
        assert (r.status_code, r.json()) == (429, {"detail": "Muitas tentativas. Tente de novo em 15 minutos."})
        assert entrar(escritorio, "karine@grupocriterio.com.br", "karine-123").status_code == 200
        relogio.agora += timedelta(minutes=15)
        assert entrar(atacante, "karine@grupocriterio.com.br", "karine-123").status_code == 200


def test_trocar_senha_conta_como_tentativa_e_respeita_o_bloqueio(cliente):
    karine = cab(cliente, "karine@grupocriterio.com.br", "karine-123")
    errada = {"senha_atual": "errada-123", "senha_nova": "nova-senha-1"}
    for _ in range(5):
        assert cliente.post("/api/acesso/senha", headers=karine, json=errada).status_code == 400
    r = cliente.post("/api/acesso/senha", headers=karine, json={"senha_atual": "karine-123", "senha_nova": "nova-senha-1"})
    assert r.status_code == 429 and r.json()["detail"].startswith("Muitas tentativas.")
    assert entrar(cliente, "karine@grupocriterio.com.br", "karine-123").status_code == 429  # mesmo IP, mesmo e-mail


def test_com_login_a_documentacao_da_api_some(engine, base):
    with TestClient(_app(engine)) as c:
        for caminho in ("/docs", "/redoc", "/openapi.json"):
            assert c.get(caminho).status_code == 404, caminho
    with TestClient(criar_app(sessionmaker(bind=engine), entrada=ConfiguracaoDeEntrada("t", "c", frozenset()))) as c:
        assert c.get("/openapi.json").status_code == 404 and c.get("/docs").status_code == 404
    with TestClient(_app(engine, config=None)) as c:  # modo livre, só na máquina: seguem
        assert c.get("/docs").status_code == 200 and c.get("/openapi.json").status_code == 200


def test_redefinir_senha_fora_do_modo_senha_nao_existe(engine, base):
    with TestClient(_app(engine, config=None)) as c:
        r = c.post(f"/api/acesso/usuarios/{base['karine']}/senha", json={"senha": "provisoria-1"})
        assert r.status_code == 404


# ------------------------------------------------------------------ revisão de segurança (AppSec, 05/10/2026)

def test_segredo_curto_nao_sobe_em_nenhuma_forma_de_subir_a_api():
    """Não só no `servir_producao.py`: `ler_configuracao` também recusa, e a frase não mostra o segredo."""
    with pytest.raises(EntradaMalConfigurada, match="pelo menos 32 caracteres") as erro:
        ler_configuracao({"CRM_ADMIN_EMAIL": ADMIN_EMAIL, "CRM_SEGREDO_SESSAO": "curto-demais"})
    assert "curto-demais" not in str(erro.value)


@pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")
def test_token_sem_assinatura_ou_com_outro_algoritmo_nao_vale():
    from crm.acesso.senha import email_da_sessao, emitir_sessao

    agora = datetime.now(timezone.utc)
    corpo = {"sub": ADMIN_EMAIL, "exp": agora + timedelta(hours=1)}
    assert email_da_sessao(jwt.encode(corpo, None, algorithm="none"), SEGREDO) is None
    assert email_da_sessao(jwt.encode(corpo, SEGREDO, algorithm="HS512"), SEGREDO) is None
    assert email_da_sessao(jwt.encode({"sub": ADMIN_EMAIL}, SEGREDO, algorithm="HS256"), SEGREDO) is None  # sem exp
    assert email_da_sessao(jwt.encode({**corpo, "exp": agora - timedelta(seconds=1)}, SEGREDO, algorithm="HS256"), SEGREDO) is None
    assert email_da_sessao(emitir_sessao(ADMIN_EMAIL, SEGREDO)[0], "outro-segredo-de-teste-com-32-caracteres") is None
    assert email_da_sessao(emitir_sessao(ADMIN_EMAIL, SEGREDO)[0], SEGREDO) == ADMIN_EMAIL


def test_bloqueios_vencidos_saem_da_memoria(relogio):
    t = Tentativas(relogio)
    for i in range(1100):
        for _ in range(5):
            t.errou("10.0.0.1", f"x{i}@exemplo.com")
    relogio.agora += timedelta(minutes=16)
    t.errou("10.0.0.1", "novo@exemplo.com")
    assert len(t._bloqueado_ate) <= 1
