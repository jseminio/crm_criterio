"""Data de envio da proposta (decisão de Eduardo, 10/10/2026): pedida ao mover de "Enviar proposta" para
"Em avaliação"; o follow-up conta dela; o ciclo de vendas se divide em originação → envio e envio → aceite. Na
planilha de 2026, a originação já era o envio."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import GrupoEconomico, Oportunidade
from crm.domain.listas import Origem, Situacao
from crm.manutencao.tarefas import data_de_envio_da_proposta

HOJE = date.today()


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        g = GrupoEconomico(nome="Hospital")
        s.add(g)
        s.flush()
        nova = Oportunidade(grupo_id=g.id, nome="nova", situacao=Situacao.ENVIAR_PROPOSTA, origem=Origem.CRM,
                            chave_origem="nova", data_colocacao=HOJE - timedelta(days=20))
        aceita = Oportunidade(grupo_id=g.id, nome="aceita", situacao=Situacao.ACEITA, origem=Origem.CRM, chave_origem="aceita",
                              data_colocacao=date(2026, 9, 1), data_envio_proposta=date(2026, 9, 13),
                              data_aceite=date(2026, 10, 9), preco_mensal=D("1000"))
        da_planilha = Oportunidade(grupo_id=g.id, nome="planilha", situacao=Situacao.EM_AVALIACAO, origem=Origem.CARGA_2026,
                                   chave_origem="planilha", data_colocacao=date(2026, 5, 4))
        ainda_nao = Oportunidade(grupo_id=g.id, nome="ainda", situacao=Situacao.ENVIAR_PROPOSTA, origem=Origem.CARGA_2026,
                                 chave_origem="ainda", data_colocacao=date(2026, 6, 1))
        s.add_all([nova, aceita, da_planilha, ainda_nao])
        s.commit()
        return {"nova": nova.id, "aceita": aceita.id, "planilha": da_planilha.id, "ainda": ainda_nao.id}


@pytest.fixture
def cliente(engine, ids):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def test_mover_para_em_avaliacao_pede_a_data_de_envio(cliente, ids):
    url = f"/api/oportunidades/{ids['nova']}"
    r = cliente.patch(url, json={"situacao": "Em avaliação pela empresa"})
    assert r.status_code == 422 and "data de envio" in r.json()["detail"]
    r = cliente.patch(url, json={"situacao": "Em avaliação pela empresa", "data_envio_proposta": HOJE.isoformat()})
    assert r.status_code == 200, r.text
    assert r.json()["data_envio_proposta"] == HOJE.isoformat()


def test_data_de_envio_nao_pode_ser_futura_nem_antes_da_originacao(cliente, ids):
    url = f"/api/oportunidades/{ids['nova']}"
    assert cliente.patch(url, json={"data_envio_proposta": (HOJE + timedelta(days=1)).isoformat()}).status_code == 422
    assert cliente.patch(url, json={"data_envio_proposta": (HOJE - timedelta(days=30)).isoformat()}).status_code == 422


def test_ciclo_em_duas_partes(cliente):
    ciclo = cliente.get("/api/indicadores").json()["ciclo_medio"]
    assert D(ciclo["dias"]) == D("38.0")  # 01/09 → 09/10
    assert (D(ciclo["dias_ate_o_envio"]), D(ciclo["dias_do_envio_ao_aceite"])) == (D("12.0"), D("26.0"))
    assert (ciclo["amostra_ate_o_envio"], ciclo["amostra_do_envio_ao_aceite"]) == (1, 1)


def test_planilha_de_2026_recebe_a_originacao_como_envio(engine, ids):
    with Session(engine) as s:
        assert "1 da planilha" in data_de_envio_da_proposta.executar(s)
        assert s.get(Oportunidade, ids["planilha"]).data_envio_proposta == date(2026, 5, 4)
        assert s.get(Oportunidade, ids["ainda"]).data_envio_proposta is None  # ainda em Enviar proposta
        assert s.get(Oportunidade, ids["nova"]).data_envio_proposta is None  # nasceu no CRM
        assert data_de_envio_da_proposta.executar(s) == "nada a preencher"


def test_follow_up_da_agenda_conta_do_envio(cliente, ids):
    cliente.patch(f"/api/oportunidades/{ids['nova']}", json={
        "situacao": "Em avaliação pela empresa", "data_envio_proposta": (HOJE - timedelta(days=3)).isoformat(),
        "proxima_acao": "cobrar retorno", "proxima_acao_em": HOJE.isoformat()})
    itens = cliente.get("/api/agenda").json()["itens"]
    item = next(i for i in itens if i["tipo"] == "oportunidade" and i["id"] == ids["nova"])
    assert item["dias_desde_o_envio"] == 3  # e não 20, da originação
