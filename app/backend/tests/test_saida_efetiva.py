"""Aviso de saída (decisão de Eduardo, 10/10/2026): o cliente anuncia e sai de fato 30 ou 60 dias depois. Até a
saída o contrato segue Ativo, faturando e no MRR; o MRR cai e o churn conta na saída efetiva; na saída o cliente
paga a 13ª proporcional junto com a última parcela."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import Contrato, EventoDeContrato, GrupoEconomico
from crm.db.saidas import efetivar_saidas
from crm.domain.listas import SituacaoContrato, TipoDeEventoDeContrato as T
from crm.manutencao.tarefas import saida_dos_encerramentos_antigos

HOJE = date.today()


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        g = GrupoEconomico(nome="Beta")
        s.add(g)
        s.flush()
        c = Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("3600"), escopo="Contábil",
                     data_inicio=date(2025, 1, 1), anterior_ao_crm=True)
        s.add(c)
        s.commit()
        return {"contrato": c.id, "grupo": g.id}


@pytest.fixture
def cliente(engine, ids):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def _encerrar(cliente, cid, saida, anuncio=HOJE):
    return cliente.post(f"/api/contratos/{cid}/eventos", json={
        "tipo": "Encerramento", "data_do_evento": anuncio.isoformat(), "data_da_saida": saida.isoformat() if saida else None,
        "iniciativa": "Cliente", "motivo_categoria": "Preço",
    })


def test_em_aviso_segue_ativo_no_mrr_e_aparece_a_parte(cliente, ids):
    saida = HOJE + timedelta(days=60)
    r = _encerrar(cliente, ids["contrato"], saida)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["situacao"] == "Ativo" and c["saida_em"] == saida.isoformat() and c["data_fim"] == saida.isoformat()
    mrr = cliente.get("/api/mrr").json()
    assert D(mrr["atual"]["valor"]) == D("3900.00") and D(mrr["movimento"]["churn_cliente"]) == 0
    carteira = cliente.get("/api/mrr/carteira").json()
    assert D(carteira["em_aviso"]) == D("3900.00") and carteira["em_aviso_contratos"] == 1
    assert carteira["itens"][0]["itens"][0]["saida_em"] == saida.isoformat()


def test_em_aviso_so_recebe_correcao_novo_encerramento_ou_desistencia(cliente, ids):
    _encerrar(cliente, ids["contrato"], HOJE + timedelta(days=30))
    r = cliente.post(f"/api/contratos/{ids['contrato']}/eventos", json={"tipo": "Reajuste", "preco_mensal_novo": "4000"})
    assert r.status_code == 409 and "aviso de saída" in r.json()["detail"]
    # Novo encerramento troca a saída (negociou 60 dias).
    r = _encerrar(cliente, ids["contrato"], HOJE + timedelta(days=60))
    assert r.json()["saida_em"] == (HOJE + timedelta(days=60)).isoformat()
    # Desistiu: volta a ser um contrato sem saída, com o fim de antes.
    r = cliente.post(f"/api/contratos/{ids['contrato']}/eventos", json={"tipo": "Desistência da saída"})
    assert r.status_code == 201, r.text
    assert r.json()["saida_em"] is None and r.json()["data_fim"] is None and r.json()["situacao"] == "Ativo"
    r = cliente.post(f"/api/contratos/{ids['contrato']}/eventos", json={"tipo": "Desistência da saída"})
    assert r.status_code == 409


def test_saida_que_ja_chegou_encerra_na_hora(cliente, ids):
    r = _encerrar(cliente, ids["contrato"], HOJE, anuncio=HOJE - timedelta(days=30))
    assert r.json()["situacao"] == "Encerrado"


def test_a_saida_chega_e_o_contrato_encerra_sozinho_com_o_churn_na_data_da_saida(engine, cliente, ids):
    saida = HOJE + timedelta(days=30)
    _encerrar(cliente, ids["contrato"], saida)
    with Session(engine) as s:
        assert efetivar_saidas(s, HOJE) == 0
        assert efetivar_saidas(s, saida) == 1
        s.commit()
        c = s.get(Contrato, ids["contrato"])
        assert c.situacao is SituacaoContrato.ENCERRADO and c.data_fim == saida


def test_o_churn_conta_na_saida_e_nao_no_anuncio(engine, ids):
    from crm.domain import mrr

    with Session(engine) as s:
        c = s.get(Contrato, ids["contrato"])
        s.add(EventoDeContrato(contrato_id=c.id, tipo=T.ENCERRAMENTO, data_do_evento=date(2026, 10, 10),
                               data_da_saida=date(2026, 12, 9)))
        c.situacao = SituacaoContrato.ENCERRADO
        s.commit()
        s.refresh(c)
        bruto = mrr.em_bruto([c], D("0"))
        assert mrr.movimento(bruto, date(2026, 10, 1), date(2026, 10, 31), date(2026, 12, 20)).churn == 0
        assert mrr.movimento(bruto, date(2026, 12, 1), date(2026, 12, 20), date(2026, 12, 20)).churn == D("3900.00")
        assert mrr.mrr_em(bruto, date(2026, 11, 30), date(2026, 12, 20)) == D("3900.00")


def test_encerramentos_antigos_ganham_a_saida_igual_a_data(engine, ids):
    with Session(engine) as s:
        s.add(EventoDeContrato(contrato_id=ids["contrato"], tipo=T.ENCERRAMENTO, data_do_evento=date(2026, 9, 1)))
        s.commit()
        assert "1 encerramento" in saida_dos_encerramentos_antigos.executar(s)
        assert s.query(EventoDeContrato).one().data_da_saida == date(2026, 9, 1)
        assert saida_dos_encerramentos_antigos.executar(s) == "nada a preencher"
