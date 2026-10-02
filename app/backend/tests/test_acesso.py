"""Entrada pela conta Microsoft, perfis por funcionalidade e histórico de alterações (E1, 02/10/2026)."""

from __future__ import annotations

import re

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.catalogo import PERMISSOES, PUBLICAS, permissoes_da_rota, permissoes_do_comercial
from crm.acesso.entrada import ConfiguracaoDeEntrada, EntradaRecusada
from crm.api.app import criar_app
from crm.db.modelos import GrupoEconomico, Oportunidade, Perfil, RegistroDeAlteracao, Usuario
from crm.domain.listas import Situacao

CONFIG = ConfiguracaoDeEntrada("tenant-teste", "cliente-teste", frozenset({"eduardo@grupocriterio.com.br"}))


def validar(token: str) -> dict:
    """Token de mentira do teste: "email|Nome". A assinatura de verdade é conferida pela PyJWT."""
    if "|" not in token:
        raise EntradaRecusada(401, "A entrada expirou ou não vale. Entre de novo.")
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


def cab(email: str, nome: str = "Pessoa") -> dict:
    return {"Authorization": f"Bearer {email}|{nome}"}


ADMIN = cab("eduardo@grupocriterio.com.br", "Eduardo Luiz")
KARINE = cab("karine@grupocriterio.com.br", "Karine Nascimento")


@pytest.fixture
def base(engine):
    """Os dois perfis que a migração cria, uma oportunidade e a Karine no Comercial."""
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        comercial = Perfil(nome="Comercial", permissoes=permissoes_do_comercial())
        s.add(comercial)
        g = GrupoEconomico(nome="Grupo Alfa")
        s.add(g)
        s.flush()
        o = Oportunidade(grupo_id=g.id, nome="Alfa BPO", situacao=Situacao.ENVIAR_PROPOSTA)
        s.add(o)
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=comercial.id))
        s.commit()
        return {"oportunidade": o.id, "comercial": comercial.id}


@pytest.fixture
def cliente(engine, base):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


def test_toda_rota_da_api_tem_permissao_definida():
    app = criar_app(sessionmaker(bind=sa.create_engine("sqlite://")))
    for caminho, operacoes in app.openapi()["paths"].items():
        if caminho in PUBLICAS:
            continue
        exemplo = re.sub(r"\{(tipo|chave)\}", "x", re.sub(r"\{[a-z_]*id\}", "7", caminho))
        for metodo in operacoes:
            exigidas = permissoes_da_rota(metodo.upper(), exemplo)
            assert exigidas is not None, f"{metodo.upper()} {caminho} está fora do mapa de permissões"
            assert set(exigidas) <= PERMISSOES


def test_sem_entrada_recusa_e_a_configuracao_e_publica(cliente):
    assert cliente.get("/api/oportunidades").status_code == 401
    assert cliente.get("/api/oportunidades", headers={"Authorization": "Bearer lixo"}).status_code == 401
    r = cliente.get("/api/acesso/entrada")
    assert r.status_code == 200 and r.json() == {
        "modo": "microsoft", "tenant_id": "tenant-teste", "client_id": "cliente-teste", "escopo": "api://cliente-teste/acesso",
    }


def test_primeiro_administrador_nasce_do_env_e_conta_sem_perfil_e_recusada(cliente):
    eu = cliente.get("/api/eu", headers=ADMIN).json()
    assert eu["administrador"] and eu["nome"] == "Eduardo Luiz" and set(eu["permissoes"]) == PERMISSOES
    r = cliente.get("/api/oportunidades", headers=cab("bruno@grupocriterio.com.br"))
    assert r.status_code == 403 and "bruno@grupocriterio.com.br ainda não tem perfil" in r.json()["detail"]


def test_perfil_libera_funcionalidade_dentro_do_menu(cliente, base):
    oid = base["oportunidade"]
    eu = cliente.get("/api/eu", headers=KARINE).json()
    assert eu["perfil"] == "Comercial" and "funil.converter" not in eu["permissoes"]
    assert cliente.get("/api/oportunidades", headers=KARINE).status_code == 200
    assert cliente.patch(f"/api/oportunidades/{oid}", headers=KARINE, json={"nome": "Alfa BPO Full"}).status_code == 200
    r = cliente.post(f"/api/oportunidades/{oid}/converter-em-contrato", headers=KARINE, json={})
    assert r.status_code == 403 and r.json()["detail"] == "O seu perfil não libera esta ação."
    assert cliente.get("/api/carteira/classificacao", headers=KARINE).status_code == 403
    assert cliente.get("/api/acesso/perfis", headers=KARINE).status_code == 403


def test_toda_alteracao_vai_para_o_historico_com_quem_fez(cliente, base, engine):
    oid = base["oportunidade"]
    cliente.patch(f"/api/oportunidades/{oid}", headers=KARINE, json={"nome": "Alfa BPO Full"})
    with Session(engine) as s:
        linhas = list(s.scalars(sa.select(RegistroDeAlteracao).where(RegistroDeAlteracao.campo == "nome")))
    assert len(linhas) == 1
    l = linhas[0]
    assert (l.usuario_email, l.usuario_nome, l.tabela, l.registro_id) == (
        "karine@grupocriterio.com.br", "Karine Nascimento", "oportunidade", oid)
    assert (l.acao, l.antes, l.depois) == ("alterou", "Alfa BPO", "Alfa BPO Full")
    assert l.rota == f"PATCH /api/oportunidades/{oid}"

    # Geral, só com a funcionalidade; o de um registro, com o "ver" do menu dono dele.
    assert cliente.get("/api/historico", headers=KARINE).status_code == 403
    doc = cliente.get("/api/historico", headers=KARINE, params={"tabela": "oportunidade", "registro_id": oid}).json()
    assert [x["campo"] for x in doc] == ["nome"]
    por_pessoa = cliente.get("/api/historico", headers=ADMIN, params={"usuario": "KARINE@grupocriterio.com.br"}).json()
    assert {x["usuario_nome"] for x in por_pessoa} == {"Karine Nascimento"}


def test_periodo_do_historico_e_o_dia_de_brasilia(cliente, base, engine):
    from datetime import datetime, timezone
    with Session(engine) as s:
        for quando in (datetime(2026, 10, 2, 2, 30, tzinfo=timezone.utc),   # 01/10, 23h30 em Brasília
                       datetime(2026, 10, 2, 13, 0, tzinfo=timezone.utc)):  # 02/10, 10h em Brasília
            s.add(RegistroDeAlteracao(quando=quando, usuario_email="eduardo@grupocriterio.com.br", acao="alterou",
                                      tabela="oportunidade", registro_id=base["oportunidade"], campo="nome"))
        s.commit()
    dia = cliente.get("/api/historico", headers=ADMIN, params={"de": "2026-10-02", "ate": "2026-10-02"}).json()
    assert [x["quando"][:13] for x in dia] == ["2026-10-02T13"]
    vespera = cliente.get("/api/historico", headers=ADMIN, params={"de": "2026-10-01", "ate": "2026-10-01"}).json()
    assert [x["quando"][:13] for x in vespera] == ["2026-10-02T02"]


def test_perfis_e_pessoas_pela_tela(cliente, base):
    r = cliente.post("/api/acesso/perfis", headers=ADMIN, json={"nome": "Customer Success", "permissoes": ["carteira.ver", "agenda.ver"]})
    assert r.status_code == 200 and r.json()["permissoes"] == ["agenda.ver", "carteira.ver"]
    cs = r.json()["id"]
    assert cliente.post("/api/acesso/perfis", headers=ADMIN, json={"nome": "customer success"}).status_code == 422
    assert cliente.post("/api/acesso/perfis", headers=ADMIN, json={"nome": "X", "permissoes": ["funil.voar"]}).status_code == 422
    admin = next(p for p in cliente.get("/api/acesso/perfis", headers=ADMIN).json() if p["administrador"])
    assert cliente.patch(f"/api/acesso/perfis/{admin['id']}", headers=ADMIN, json={"permissoes": []}).status_code == 422
    assert cliente.patch(f"/api/acesso/perfis/{cs}", headers=ADMIN, json={"permissoes": ["carteira.ver"]}).json()["permissoes"] == ["carteira.ver"]

    nova = cliente.post("/api/acesso/usuarios", headers=ADMIN, json={"email": "Ana@GrupoCriterio.com.br", "perfil_id": cs})
    assert nova.status_code == 200 and nova.json()["email"] == "ana@grupocriterio.com.br"
    assert nova.json()["liberado_por"] == "Eduardo Luiz"
    assert cliente.get("/api/carteira/classificacao", headers=cab("ana@grupocriterio.com.br")).status_code != 403
    cliente.patch(f"/api/acesso/usuarios/{nova.json()['id']}", headers=ADMIN, json={"ativo": False})
    assert cliente.get("/api/eu", headers=cab("ana@grupocriterio.com.br")).status_code == 403

    eduardo = next(u for u in cliente.get("/api/acesso/usuarios", headers=ADMIN).json() if u["email"].startswith("eduardo"))
    r = cliente.patch(f"/api/acesso/usuarios/{eduardo['id']}", headers=ADMIN, json={"perfil_id": base["comercial"]})
    assert r.status_code == 422 and "pelo menos um Administrador" in r.json()["detail"]


def test_com_entrada_quem_fez_e_quem_entrou(cliente, base):
    """O seletor "Quem preenche" deixa de valer: a ficha grava o nome da conta."""
    oid = base["oportunidade"]
    r = cliente.put(f"/api/oportunidades/{oid}/ficha/auditada", headers=KARINE, json={"valor": "Sim", "por": "Eduardo"})
    assert r.status_code == 200, r.text
    campo = next(c for s in r.json()["secoes"] for c in s["campos"] if c["chave"] == "auditada")
    assert campo["por"] == "Karine Nascimento"


def test_sem_configuracao_segue_sem_login_e_sem_historico(engine, base):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        assert c.get("/api/acesso/entrada").json()["modo"] == "local"
        eu = c.get("/api/eu").json()
        assert eu["modo"] == "local" and eu["administrador"]
        assert c.patch(f"/api/oportunidades/{base['oportunidade']}", json={"nome": "Sem login"}).status_code == 200
    with Session(engine) as s:
        assert s.scalar(sa.select(sa.func.count()).select_from(RegistroDeAlteracao)) == 0
