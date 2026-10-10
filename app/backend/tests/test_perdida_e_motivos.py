"""Perdida e motivos (decisões de Eduardo, 10/10/2026): "Recusada" e "Perdido" viram a etapa única "Perdida",
com o motivo obrigatório ("Outro" pede a descrição); as listas de motivos de perda e de churn foram aprovadas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import Contrato, GrupoEconomico, Oportunidade
from crm.domain.listas import MotivoRecusa, Origem, Situacao, SituacaoContrato
from crm.manutencao.tarefas import perdida_e_motivos


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        g = GrupoEconomico(nome="Beta")
        s.add(g)
        s.flush()
        aberta = Oportunidade(grupo_id=g.id, nome="aberta", situacao=Situacao.EM_AVALIACAO, origem=Origem.CRM, chave_origem="a")
        perdida = Oportunidade(grupo_id=g.id, nome="perdida", situacao=Situacao.PERDIDA, origem=Origem.CRM, chave_origem="p",
                               motivo_recusa=MotivoRecusa.PRECO)
        antiga = Oportunidade(grupo_id=g.id, nome="antiga", situacao=Situacao.PERDIDA, origem=Origem.CRM, chave_origem="x")
        c = Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("1200"), data_inicio=date(2026, 1, 1),
                     escopo="Contábil")
        s.add_all([aberta, perdida, antiga, c])
        s.commit()
        return {"aberta": aberta.id, "contrato": c.id}


@pytest.fixture
def cliente(engine, ids):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def test_perdida_exige_o_motivo_e_outro_exige_a_descricao(cliente, ids):
    url = f"/api/oportunidades/{ids['aberta']}"
    r = cliente.patch(url, json={"situacao": "Perdida"})
    assert r.status_code == 422 and "motivo da perda" in r.json()["detail"]
    r = cliente.patch(url, json={"situacao": "Perdida", "motivo_recusa": "Outro"})
    assert r.status_code == 422 and "descreva" in r.json()["detail"]
    r = cliente.patch(url, json={"situacao": "Perdida", "motivo_recusa": "Outro", "motivo_recusa_detalhe": " fechou a empresa "})
    assert r.status_code == 200, r.text
    assert r.json()["motivo_recusa_detalhe"] == "fechou a empresa"


def test_a_lista_tem_perdida_e_nao_tem_recusada_nem_perdido(cliente):
    listas = cliente.get("/api/listas").json()
    assert "Perdida" in listas["situacoes"] and not {"Recusada", "Perdido"} & set(listas["situacoes"])
    assert "Sem retorno do cliente" in listas["motivos_de_recusa"]


def test_card_de_motivos_de_perda_e_a_composicao(cliente):
    motivos = cliente.get("/api/indicadores").json()["motivos_de_perda"]
    assert motivos == [["Preço", 1], ["Sem motivo informado", 1]]
    itens = cliente.get("/api/indicadores/composicao", params={"indicador": "motivos_de_perda"}).json()["itens"]
    assert {(i["nome"], i["parte"], i["entra"]) for i in itens} == {("perdida", "Preço", True), ("antiga", "Sem motivo informado", False)}


def test_motivo_de_churn_vem_no_movimento(cliente, ids):
    r = cliente.post(f"/api/contratos/{ids['contrato']}/eventos", json={
        "tipo": "Encerramento", "data_do_evento": date.today().isoformat(), "iniciativa": "Cliente",
        "motivo_categoria": "Migrou para concorrente"})
    assert r.status_code == 201, r.text
    itens = cliente.get("/api/mrr/movimento", params={"de": date.today().replace(day=1).isoformat()}).json()["itens"]
    churn = [i for i in itens if i["categoria"] == "churn_cliente"]
    assert churn and churn[0]["motivo"] == "Migrou para concorrente" and churn[0]["iniciativa"] == "Cliente"


def test_tarefa_leva_recusada_e_perdido_para_perdida_e_renomeia_os_motivos(engine, ids):
    with Session(engine) as s:
        s.execute(sa.text("UPDATE oportunidade SET situacao='Recusada', motivo_recusa='Sem retorno' WHERE nome='perdida'"))
        s.execute(sa.text("UPDATE oportunidade SET situacao='Perdido' WHERE nome='antiga'"))
        s.commit()
        assert perdida_e_motivos.executar(s) == "2 oportunidade(s) para Perdida e 1 motivo(s) com o nome aprovado"
        s.commit()
        p = s.scalars(sa.select(Oportunidade).where(Oportunidade.nome == "perdida")).one()
        assert p.situacao is Situacao.PERDIDA and p.motivo_recusa is MotivoRecusa.SEM_RETORNO
        assert perdida_e_motivos.executar(s) == "nada a mudar"
