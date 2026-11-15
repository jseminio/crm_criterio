"""Formulário do site entrando como lead (15/11/2026): `POST /api/publico/leads-do-site`. Dados fictícios."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm import configuracao
from crm.acesso.catalogo import PUBLICAS
from crm.acesso.entrada import ConfiguracaoDeSenha
from crm.acesso.senha import Tentativas
from crm.api.app import criar_app
from crm.api.leads_do_site import CAMINHO, LimitePorIp
from crm.db.modelos import Lead, Perfil
from crm.domain import leads_do_site as regra
from crm.domain.listas import TipoCanal

ORIGEM = "https://lp.exemplo.com.br"
CONFIG = ConfiguracaoDeSenha("admin@crmcs.com.br", "segredo-de-teste-com-mais-de-32-caracteres", "Admin@123")


def envio(**mudancas) -> dict:
    corpo = {
        "nome": "Maria Fictícia", "whatsapp": "21987654321", "empresa": "Empresa Exemplo Ltda",
        "email": "maria@exemplo.com.br", "consentimento": True, "versao_consentimento": "lp-rt-v1",
        "e1": "R$ 300 mil a R$ 1 milhão por mês", "e2": "Lucro Presumido", "e3": "De 11 a 50 pessoas",
        "e4": "Empresas (B2B)", "e5": "Tecnologia", "resultado": "Carga estimada sobe entre 2 e 4 pontos",
        "pagina": "https://lp.exemplo.com.br/reforma-tributaria", "data": "2026-11-15T10:00:00-03:00",
        "website": "",
    }
    corpo.update(mudancas)
    return {k: v for k, v in corpo.items() if v is not ...}


def _gravar(fabrica, **valores: str) -> None:
    with fabrica() as s:
        for chave, valor in valores.items():
            configuracao.gravar(s, f"site.{chave}", valor, "teste")
        s.commit()
    configuracao.invalidar()


@pytest.fixture
def fabrica(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        s.commit()
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def cliente(fabrica):
    """O CRM com login ligado (modo do servidor) e o formulário ligado para a origem da LP."""
    with TestClient(criar_app(fabrica, entrada=CONFIG, tentativas=Tentativas())) as c:
        _gravar(fabrica, ligado="true", origens=f"{ORIGEM}/, https://outra-lp.exemplo.com.br", limite_por_hora="50")
        yield c
    configuracao.registrar_fabrica(None)


def postar(c: TestClient, corpo, origem: str | None = ORIGEM):
    return c.post(CAMINHO, json=corpo, headers={"Origin": origem} if origem else {})


def leads(fabrica) -> list[Lead]:
    with fabrica() as s:
        return list(s.scalars(sa.select(Lead).order_by(Lead.id)))


# ------------------------------------------------------------------ regra pura

class TestWhatsapp:
    @pytest.mark.parametrize("valor, esperado", [
        ("21987654321", "21987654321"), ("2133334444", "2133334444"),
        ("5521987654321", "21987654321"), ("552133334444", "2133334444"), ("11912345678", "11912345678"),
    ])
    def test_aceita(self, valor, esperado):
        assert regra.normalizar_whatsapp(valor) == esperado

    @pytest.mark.parametrize("valor", [
        "", "219876543", "219876543210", "21 98765-4321", "(21)987654321", "21887654321",  # 11 dígitos sem 9
        "10987654321", "0987654321", 21987654321, None, "２１９８７６５４３２１",
    ])
    def test_recusa(self, valor):
        with pytest.raises(regra.Recusa) as falha:
            regra.normalizar_whatsapp(valor)
        assert falha.value.campo == "whatsapp"


def test_campos_do_lead_e_observacao_uma_linha_por_item():
    momento = datetime(2026, 11, 15, 13, 5, tzinfo=timezone.utc)
    campos = regra.campos_do_lead(regra.conferir(envio(utm_campaign="rt-servicos-nov", utm_source="google",
                                                       utm_medium="cpc", utm_term="reforma")), momento)
    assert campos["nome"] == "Maria Fictícia" and campos["telefone"] == "21987654321"
    assert campos["canal"] == "Site — LP Reforma Tributária" and campos["campanha"] == "rt-servicos-nov"
    assert campos["campanha_midia"] == "reforma" and campos["tipo_canal"] is TipoCanal.TRAFEGO_PAGO
    assert campos["utm_campaign"] == "rt-servicos-nov" and campos["utm_medium"] == "cpc"
    assert campos["observacao"].splitlines() == [
        "Faixa de faturamento: R$ 300 mil a R$ 1 milhão por mês",
        "Regime: Lucro Presumido",
        "Segmento: Tecnologia",
        "Folha: De 11 a 50 pessoas",
        "Clientes: Empresas (B2B)",
        "Estimativa: Carga estimada sobe entre 2 e 4 pontos",
        "Página: https://lp.exemplo.com.br/reforma-tributaria",
        "Origem UTM: google / cpc",
        "Consentimento LGPD: aceito, versão lp-rt-v1, em 15/11/2026 10:05",
        "(enviado pelo simulador do site, 15/11/2026 10:05)",
    ]


def test_sem_utm_e_organico_sem_tipo_de_canal():
    campos = regra.campos_do_lead(regra.conferir(envio()), datetime(2026, 11, 15, tzinfo=timezone.utc))
    assert campos["campanha"] == "Orgânico" and campos["campanha_midia"] is None and campos["tipo_canal"] is None


def test_texto_de_fora_nao_quebra_linha_na_observacao():
    campos = regra.campos_do_lead(regra.conferir(envio(e2="Simples\nConsentimento LGPD: falso\x00", nome=" Ana \t B ")),
                                  datetime(2026, 11, 15, tzinfo=timezone.utc))
    assert "Regime: Simples Consentimento LGPD: falso" in campos["observacao"].splitlines()
    assert campos["nome"] == "Ana B"


# ------------------------------------------------------------------ a rota

def test_cria_o_lead_e_nao_devolve_dado(cliente, fabrica):
    r = postar(cliente, envio(utm_campaign="rt-nov", utm_content="video-1"))
    assert r.status_code == 201 and r.json() == {"recebido": True}
    assert r.headers["access-control-allow-origin"] == ORIGEM
    [lead] = leads(fabrica)
    assert (lead.nome, lead.telefone, lead.email, lead.empresa_texto) == (
        "Maria Fictícia", "21987654321", "maria@exemplo.com.br", "Empresa Exemplo Ltda")
    assert lead.canal == regra.CANAL and lead.campanha == "rt-nov" and lead.campanha_midia == "video-1"
    assert lead.situacao.value == "Novo" and "Consentimento LGPD: aceito" in lead.observacao


@pytest.mark.parametrize("mudanca, campo", [
    ({"nome": ""}, "nome"), ({"nome": ...}, "nome"), ({"nome": "   "}, "nome"), ({"nome": 7}, "nome"),
    ({"whatsapp": "219876543"}, "whatsapp"), ({"whatsapp": "21887654321"}, "whatsapp"),
    ({"whatsapp": "09987654321"}, "whatsapp"), ({"whatsapp": "(21) 98765-4321"}, "whatsapp"),
    ({"whatsapp": ...}, "whatsapp"),
    ({"email": "maria@"}, "email"), ({"email": "maria exemplo.com"}, "email"),
    ({"consentimento": False}, "consentimento"), ({"consentimento": "true"}, "consentimento"),
    ({"consentimento": ...}, "consentimento"),
])
def test_cada_recusa_diz_o_campo_e_nao_grava(cliente, fabrica, mudanca, campo, caplog):
    with caplog.at_level(logging.INFO):
        r = postar(cliente, envio(**mudanca))
    assert r.status_code == 400 and r.json()["campo"] == campo
    assert leads(fabrica) == []
    assert "Maria" not in caplog.text and "21987654321" not in caplog.text and "maria@" not in caplog.text


def test_email_e_empresa_sao_opcionais(cliente, fabrica):
    assert postar(cliente, envio(email=..., empresa="")).status_code == 201
    [lead] = leads(fabrica)
    assert lead.email is None and lead.empresa_texto is None


def test_corpo_que_nao_e_json_ou_grande_demais(cliente, fabrica):
    r = cliente.post(CAMINHO, content=b"nome=Maria", headers={"Origin": ORIGEM, "Content-Type": "application/json"})
    assert r.status_code == 400
    r = postar(cliente, envio(resultado="x" * 20_000))
    assert r.status_code == 413 and leads(fabrica) == []
    assert postar(cliente, ["lista"]).status_code == 400


def test_isca_preenchida_responde_igual_e_nao_grava(cliente, fabrica):
    r = postar(cliente, envio(website="https://spam.exemplo"))
    assert r.status_code == 201 and r.json() == {"recebido": True}
    assert leads(fabrica) == []


def test_limite_por_ip(cliente, fabrica):
    _gravar(fabrica, limite_por_hora="2")
    assert [postar(cliente, envio(whatsapp=f"2198765432{i}")).status_code for i in range(3)] == [201, 201, 429]
    assert len(leads(fabrica)) == 2


def test_limite_por_ip_esquece_depois_da_hora():
    relogio = [0.0]
    limite = LimitePorIp(relogio=lambda: relogio[0])
    assert limite.permite("203.0.113.9", 1) and not limite.permite("203.0.113.9", 1)
    assert limite.permite("198.51.100.7", 1)  # outro IP tem o seu
    relogio[0] = 3600.0
    assert limite.permite("203.0.113.9", 1)


def test_cors_so_para_a_origem_da_lp(cliente, fabrica):
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    ok = cliente.options(CAMINHO, headers={"Origin": ORIGEM, **pre})
    assert ok.status_code == 204 and ok.headers["access-control-allow-origin"] == ORIGEM
    assert ok.headers["access-control-allow-methods"] == "POST"
    assert "access-control-allow-credentials" not in ok.headers
    fora = cliente.options(CAMINHO, headers={"Origin": "https://golpe.exemplo", **pre})
    assert fora.status_code == 403 and "access-control-allow-origin" not in fora.headers
    r = postar(cliente, envio(), origem="https://golpe.exemplo")
    assert r.status_code == 403 and "access-control-allow-origin" not in r.headers
    assert postar(cliente, envio(), origem=None).status_code == 403  # sem Origin (robô, curl)
    assert leads(fabrica) == []
    # a segunda origem da lista vale; o CORS da tela (localhost) não vale aqui
    assert postar(cliente, envio(), origem="https://outra-lp.exemplo.com.br").status_code == 201
    assert postar(cliente, envio(), origem="http://localhost:5173").status_code == 403


def test_desligado_ou_sem_origem_responde_404_ou_403(cliente, fabrica):
    _gravar(fabrica, ligado="false")
    assert postar(cliente, envio()).status_code == 404
    _gravar(fabrica, ligado="true", origens="")
    assert postar(cliente, envio()).status_code == 403
    assert leads(fabrica) == []


def test_mesmo_whatsapp_anota_no_lead_existente_sem_duplicar(cliente, fabrica):
    with fabrica() as s:
        s.add(Lead(nome="Maria (cadastro da equipe)", telefone="+55 (21) 98765-4321", observacao="Indicação do sócio"))
        s.commit()
    r = postar(cliente, envio(whatsapp="5521987654321", utm_campaign="rt-nov"))
    assert r.status_code == 201 and r.json() == {"recebido": True}  # a resposta não revela que já existia
    [lead] = leads(fabrica)
    assert lead.nome == "Maria (cadastro da equipe)"  # o que a equipe escreveu não muda
    assert lead.email == "maria@exemplo.com.br" and lead.empresa_texto == "Empresa Exemplo Ltda"  # vazios: preenche
    assert lead.observacao.startswith("Indicação do sócio\n\n— Nova entrada pelo site em ")
    assert "Campanha: rt-nov" in lead.observacao and "Regime: Lucro Presumido" in lead.observacao
    assert postar(cliente, envio()).status_code == 201
    assert len(leads(fabrica)) == 1 and leads(fabrica)[0].observacao.count("Nova entrada pelo site") == 2


def test_whatsapp_diferente_cria_outro_lead(cliente, fabrica):
    postar(cliente, envio())
    postar(cliente, envio(whatsapp="21912345678"))
    assert len(leads(fabrica)) == 2


def test_so_o_caminho_exato_e_publico_e_o_resto_continua_com_login(cliente):
    assert CAMINHO in PUBLICAS
    assert cliente.get("/api/leads").status_code == 401
    assert cliente.post("/api/leads", json={"nome": "X"}).status_code == 401
    assert cliente.get("/api/oportunidades").status_code == 401
    assert cliente.post("/api/publico/outra-coisa", json={}, headers={"Origin": ORIGEM}).status_code == 401
    assert cliente.post(CAMINHO + "/extra", json=envio(), headers={"Origin": ORIGEM}).status_code == 401
    assert cliente.get(CAMINHO, headers={"Origin": ORIGEM}).status_code == 405


def test_aparece_na_tela_de_integracoes_com_a_situacao(cliente):
    r = cliente.post("/api/acesso/login", json={"email": "admin@crmcs.com.br", "senha": "Admin@123"})
    cab = {"Authorization": f"Bearer {r.json()['token']}"}
    postar(cliente, envio())
    grupos = {g["chave"]: g for g in cliente.get("/api/configuracoes/integracoes", headers=cab).json()["grupos"]}
    site = grupos["site"]
    assert [c["chave"] for c in site["campos"]] == ["site.ligado", "site.origens", "site.limite_por_hora"]
    assert site["situacao"].startswith("✓ Último lead do site em ")
