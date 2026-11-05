"""Excluir contrato pela tela, com motivo (30/10/2026, amostra aprovada por Karine)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.catalogo import permissoes_da_rota, permissoes_do_comercial
from crm.api.app import criar_app
from crm.db.modelos import (
    Contrato, DocumentoAnexado, EventoDeContrato, GrupoEconomico, Oportunidade, PedidoDeAprovacao,
    RegistroDeAlteracao,
)
from crm.domain.listas import Situacao, SituacaoContrato, TipoDeEventoDeContrato


@pytest.fixture
def cliente(engine):
    with TestClient(criar_app(sessionmaker(bind=engine, expire_on_commit=False, future=True))) as c:
        yield c


@pytest.fixture
def ids(engine) -> dict:
    with Session(engine) as s:
        g = GrupoEconomico(nome="Grupo Delta")
        s.add(g)
        s.flush()
        op = Oportunidade(grupo_id=g.id, nome="BPO", situacao=Situacao.ACEITA, preco_mensal=D("4500"))
        s.add(op)
        s.flush()
        ativo = Contrato(grupo_id=g.id, oportunidade_id=op.id, escopo="BPO Financeiro", situacao=SituacaoContrato.ATIVO,
                         preco_mensal=D("4500"), data_inicio=date(2026, 3, 1))
        outro = Contrato(grupo_id=g.id, escopo="DP", situacao=SituacaoContrato.ATIVO, preco_mensal=D("800"))
        s.add_all([ativo, outro])
        s.flush()
        evento = EventoDeContrato(contrato_id=ativo.id, tipo=TipoDeEventoDeContrato.REAJUSTE, data_do_evento=date(2026, 9, 1))
        s.add(evento)
        s.flush()
        s.add_all([
            EventoDeContrato(contrato_id=outro.id, tipo=TipoDeEventoDeContrato.REAJUSTE, data_do_evento=date(2026, 9, 1)),
            PedidoDeAprovacao(contrato_id=ativo.id, tipo=TipoDeEventoDeContrato.REAJUSTE, data_do_evento=date(2026, 9, 1),
                              motivo="redução", pedido_por="t", evento_id=evento.id),
            DocumentoAnexado(grupo_id=g.id, contrato_id=ativo.id, tipo="contrato", nome_arquivo="a.pdf", tamanho=1,
                             sha256="0" * 64, conteudo_base64="", enviado_por="t"),
        ])
        s.commit()
        return {"ativo": ativo.id, "outro": outro.id, "op": op.id, "grupo": g.id}


def test_mostra_o_que_sai_e_o_que_so_se_desliga(cliente, ids):
    r = cliente.get(f"/api/contratos/{ids['ativo']}/exclusao")
    assert r.status_code == 200
    assert r.json() == {"eventos": 1, "pedidos_de_aprovacao": 1, "documentos_gerados": 0, "anexos": 1, "envelopes": 0}


def test_exclui_ate_o_ativo_com_motivo_e_deixa_o_resto(cliente, engine, ids):
    r = cliente.post(f"/api/contratos/{ids['ativo']}/excluir", json={"motivo": "  Cadastrado   em duplicidade "})
    assert r.status_code == 204, r.text
    with Session(engine) as s:
        assert s.get(Contrato, ids["ativo"]) is None and s.get(Contrato, ids["outro"]) is not None
        assert s.get(Oportunidade, ids["op"]).situacao is Situacao.ACEITA
        assert s.get(GrupoEconomico, ids["grupo"]) is not None
        assert [e.contrato_id for e in s.scalars(sa.select(EventoDeContrato))] == [ids["outro"]]
        assert s.scalar(sa.select(sa.func.count(PedidoDeAprovacao.id))) == 0
        assert s.scalar(sa.select(DocumentoAnexado)).contrato_id is None
        reg = s.scalar(sa.select(RegistroDeAlteracao).where(RegistroDeAlteracao.campo == "motivo"))
        assert (reg.acao, reg.tabela, reg.registro_id, reg.descricao, reg.depois, reg.usuario_email) == (
            "excluiu", "contrato", ids["ativo"], "Grupo Delta · BPO Financeiro", "Cadastrado em duplicidade", "sem login")


def test_a_oportunidade_pode_virar_contrato_de_novo(cliente, ids):
    assert cliente.post(f"/api/contratos/{ids['ativo']}/excluir", json={"motivo": "errado"}).status_code == 204
    r = cliente.post(f"/api/oportunidades/{ids['op']}/converter-em-contrato", json={"recorrente": True})
    assert r.status_code == 201, r.text


@pytest.mark.parametrize("motivo", ["", "   "])
def test_sem_motivo_nao_exclui(cliente, engine, ids, motivo):
    r = cliente.post(f"/api/contratos/{ids['ativo']}/excluir", json={"motivo": motivo})
    assert r.status_code in (409, 422)
    with Session(engine) as s:
        assert s.get(Contrato, ids["ativo"]) is not None


def test_contrato_que_nao_existe(cliente):
    assert cliente.get("/api/contratos/999/exclusao").status_code == 404
    assert cliente.post("/api/contratos/999/excluir", json={"motivo": "x"}).status_code == 404


def test_permissao_vale_para_o_comercial():
    assert permissoes_da_rota("POST", "/api/contratos/5/excluir") == ("contratos.excluir",)
    assert permissoes_da_rota("GET", "/api/contratos/5/exclusao") == ("contratos.excluir",)
    assert "contratos.excluir" in permissoes_do_comercial()
