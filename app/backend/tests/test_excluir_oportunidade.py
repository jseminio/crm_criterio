"""Excluir oportunidade do Funil — irreversível, com travas. Pedido de Karine em 02/10/2026.

Contrato ou proposta enviada impedem. Vão junto as propostas não enviadas e o histórico de preço;
o questionário fica, sem o vínculo. A da planilha é lembrada e a recarga não a recria.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.carga.persistencia import importar
from crm.db.modelos import (
    Contrato, GrupoEconomico, HistoricoDePreco, MatrizDeProposta, Oportunidade, OportunidadeExcluida, Proposta,
    QuestionarioRecebido,
)
from crm.domain.listas import Situacao, SituacaoContrato, SituacaoDoQuestionario, TipoDeMatriz
from test_persistencia import proposta as linha_da_planilha


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def _oportunidade(sessao: Session, nome="Delta") -> Oportunidade:
    g = GrupoEconomico(nome=f"Grupo {nome}")
    sessao.add(g)
    sessao.flush()
    o = Oportunidade(grupo_id=g.id, nome=nome, situacao=Situacao.ENVIAR_PROPOSTA)
    sessao.add(o)
    sessao.flush()
    return o


def _proposta(sessao: Session, o: Oportunidade, numero=154, enviada=False) -> Proposta:
    m = MatrizDeProposta(tipo=TipoDeMatriz.CONTABIL, nome_arquivo="m.pptx", conteudo_base64="", enviada_em=datetime.now(),
                         enviada_por="Karine", faltando=[], desconhecidos=[])
    sessao.add(m)
    sessao.flush()
    p = Proposta(oportunidade_id=o.id, numero=numero, ano=2026, matriz_id=m.id, valores={},
                 enviada_em=date(2026, 10, 1) if enviada else None)
    sessao.add(p)
    sessao.flush()
    return p


def test_exclui_e_leva_proposta_nao_enviada_e_historico(cliente, sessao: Session):
    o = _oportunidade(sessao)
    _proposta(sessao, o)
    sessao.add(HistoricoDePreco(oportunidade_id=o.id, origem="CRM", preco_mensal_novo=Decimal("100")))
    q = QuestionarioRecebido(externo_id="q1", recebido_em=datetime.now(), versao="v", razao_social="Delta", cnpj="1" * 14,
                             contato_nome="Ana", respostas={}, situacao=SituacaoDoQuestionario.IMPORTADO, o_que_fez="",
                             grupo_id=o.grupo_id, oportunidade_id=o.id)
    sessao.add(q)
    sessao.commit()
    oid, grupo_id = o.id, o.grupo_id

    antes = cliente.get(f"/api/oportunidades/{o.id}/exclusao").json()
    assert antes == {"pode_excluir": True, "motivo": None, "propostas": ["154.2026"], "questionarios": 1, "da_planilha": False}

    assert cliente.delete(f"/api/oportunidades/{oid}").status_code == 204
    assert cliente.get(f"/api/oportunidades/{oid}").status_code == 404
    sessao.expire_all()
    assert sessao.scalar(sa.select(sa.func.count()).select_from(Proposta)) == 0
    assert sessao.scalar(sa.select(sa.func.count()).select_from(HistoricoDePreco)) == 0
    assert sessao.get(QuestionarioRecebido, q.id).oportunidade_id is None  # o questionário fica
    assert sessao.get(GrupoEconomico, grupo_id) is not None  # o grupo fica
    assert cliente.delete(f"/api/oportunidades/{oid}").status_code == 404


def test_contrato_impede(cliente, sessao: Session):
    o = _oportunidade(sessao)
    sessao.add(Contrato(grupo_id=o.grupo_id, oportunidade_id=o.id, situacao=SituacaoContrato.ATIVO))
    sessao.commit()
    r = cliente.delete(f"/api/oportunidades/{o.id}")
    assert r.status_code == 409 and "contrato" in r.json()["detail"]
    assert cliente.get(f"/api/oportunidades/{o.id}/exclusao").json()["pode_excluir"] is False


def test_proposta_enviada_impede(cliente, sessao: Session):
    o = _oportunidade(sessao)
    _proposta(sessao, o, enviada=True)
    sessao.commit()
    r = cliente.delete(f"/api/oportunidades/{o.id}")
    assert r.status_code == 409 and "154.2026" in r.json()["detail"]


def test_a_da_planilha_e_lembrada_e_a_recarga_nao_recria(cliente, sessao: Session):
    linha = linha_da_planilha(nome_oportunidade="Sogamax")
    importar(sessao, [linha])
    sessao.commit()
    o = sessao.scalar(sa.select(Oportunidade).where(Oportunidade.nome == "Sogamax"))
    assert cliente.get(f"/api/oportunidades/{o.id}/exclusao").json()["da_planilha"] is True

    assert cliente.delete(f"/api/oportunidades/{o.id}").status_code == 204
    sessao.expire_all()
    assert sessao.scalar(sa.select(OportunidadeExcluida.nome)) == "Sogamax"

    resultado = importar(sessao, [linha])
    sessao.flush()
    assert sessao.scalar(sa.select(Oportunidade).where(Oportunidade.nome == "Sogamax")) is None
    assert resultado.criadas == 0 and resultado.inalteradas == 1  # a conta da conferência fecha
    assert any("excluída no CRM" in o.texto for o in resultado.ocorrencias)
