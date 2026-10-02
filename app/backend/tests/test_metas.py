"""Configurações › Metas (02/10/2026): meta e alerta do MRR e da conversão editáveis na tela."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import Contrato, GrupoEconomico, Oportunidade, Perfil, Usuario
from crm.domain.listas import Situacao, SituacaoContrato

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


@pytest.fixture
def base(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        comercial = Perfil(nome="Comercial", permissoes=["funil.ver", "contratos.ver"])
        s.add(comercial)
        g = GrupoEconomico(nome="Grupo Alfa")
        s.add(g)
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=comercial.id))
        s.add(Contrato(grupo_id=g.id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("250000")))
        for situacao in (Situacao.ACEITA, Situacao.ACEITA, Situacao.RECUSADA, Situacao.PERDIDO):  # 50% de conversão
            s.add(Oportunidade(grupo_id=g.id, nome="x", situacao=situacao))
        s.commit()


@pytest.fixture
def cliente(engine, base):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


def test_sem_nada_gravado_valem_os_padroes_do_kpi_oficial(cliente):
    m = cliente.get("/api/metas", headers=ADMIN).json()
    assert (m["mrr"]["meta"], m["mrr"]["alerta"]) == ("400000", "200000")
    assert (m["conversao"]["meta"], m["conversao"]["alerta"]) == ("50", "30")
    mrr = cliente.get("/api/mrr", headers=ADMIN, params={"hoje": "2026-10-02"}).json()
    assert (mrr["contra_a_meta"], mrr["falta_para_a_meta"]) == ("entre", "150000.00")
    tx = cliente.get("/api/indicadores", headers=ADMIN).json()["taxa_de_conversao"]
    assert (tx["percentual"], tx["atingiu_a_meta"], tx["meta"]) == ("50.0", True, "50")


def test_mudar_a_meta_muda_a_comparacao_e_registra_quem(cliente):
    r = cliente.put("/api/metas", headers=ADMIN, json={"mrr": {"meta": "240000", "alerta": "150000"},
                                                        "conversao": {"meta": "60", "alerta": "40"}})
    assert r.status_code == 200, r.text
    assert r.json()["mrr"]["alterado_por"] == "Eduardo Luiz"
    mrr = cliente.get("/api/mrr", headers=ADMIN, params={"hoje": "2026-10-02"}).json()
    assert (mrr["meta"], mrr["contra_a_meta"], mrr["falta_para_a_meta"]) == ("240000.00", "na_meta", "0")
    tx = cliente.get("/api/indicadores", headers=ADMIN).json()["taxa_de_conversao"]
    assert (tx["atingiu_a_meta"], tx["abaixo_do_alerta"], tx["meta"]) == (False, False, "60.00")
    # A primeira gravação cria a linha (no banco real, a migração já a cria); a seguinte altera.
    cliente.put("/api/metas", headers=ADMIN, json={"mrr": {"meta": "300000", "alerta": "150000"}})
    hist = cliente.get("/api/historico", headers=ADMIN, params={"tabela": "meta_de_indicador"}).json()
    assert {h["acao"] for h in hist} == {"criou", "alterou"}
    mudou = [h for h in hist if h["acao"] == "alterou" and h["campo"] == "meta"]
    assert (mudou[0]["antes"], mudou[0]["depois"], mudou[0]["usuario_nome"]) == ("240000.00", "300000", "Eduardo Luiz")


def test_so_muda_o_que_veio(cliente):
    cliente.put("/api/metas", headers=ADMIN, json={"conversao": {"meta": "55", "alerta": "35"}})
    m = cliente.get("/api/metas", headers=ADMIN).json()
    assert m["mrr"]["meta"] == "400000" and m["conversao"]["meta"] == "55.00"


@pytest.mark.parametrize("corpo, trecho", [
    ({"mrr": {"meta": "200000", "alerta": "200000"}}, "alerta precisa ficar abaixo da meta"),
    ({"conversao": {"meta": "120", "alerta": "30"}}, "vai até 100%"),
])
def test_valida_antes_de_gravar(cliente, corpo, trecho):
    r = cliente.put("/api/metas", headers=ADMIN, json=corpo)
    assert r.status_code == 422 and trecho in r.json()["detail"]
    assert cliente.get("/api/metas", headers=ADMIN).json()["mrr"]["meta"] == "400000"


def test_so_quem_tem_a_funcionalidade_ve_e_muda(cliente):
    assert cliente.get("/api/metas", headers=KARINE).status_code == 403
    assert cliente.put("/api/metas", headers=KARINE, json={"mrr": {"meta": "1", "alerta": "0.5"}}).status_code == 403
