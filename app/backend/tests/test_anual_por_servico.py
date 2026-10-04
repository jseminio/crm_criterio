"""Recalcular o anual já gravado: contábil e DP × 13, financeiro × 12 (Eduardo, 03/10/2026)."""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.anual_por_servico import MOTIVO, aplicar, planejar, resumir
from crm.db.modelos import GrupoEconomico, HistoricoDePreco, Oportunidade
from crm.domain.listas import Situacao

D = Decimal


def _oportunidade(s: Session, g: GrupoEconomico, servico: str | None, mensal: str | None, anual: str | None) -> Oportunidade:
    o = Oportunidade(grupo_id=g.id, nome=servico or "sem serviço", situacao=Situacao.ENVIAR_PROPOSTA, servico=servico,
                     preco_mensal=D(mensal) if mensal else None, preco_anual=D(anual) if anual else None)
    s.add(o)
    return o


def test_planeja_so_o_que_a_regra_cobre_e_aplica_com_historico(sessao: Session):
    g = GrupoEconomico(nome="Grupo Delta")
    sessao.add(g)
    sessao.flush()
    contabil = _oportunidade(sessao, g, "BPO Contábil", "5000", "60000")  # nome antigo também vale
    financeiro = _oportunidade(sessao, g, "BPO Financeiro", "3000", None)
    certo = _oportunidade(sessao, g, "Dep. Pessoal", "1000", "13000")
    sem_mensal = _oportunidade(sessao, g, "BPO Contábil e Fiscal", None, "9000")
    fora = _oportunidade(sessao, g, "Auditoria", "1000", "4000")
    sessao.flush()

    mudancas = planejar(sessao)
    assert {m.oportunidade_id: m.depois for m in mudancas} == {contabil.id: D(65000), financeiro.id: D(36000)}
    assert resumir(mudancas) == ["   1  BPO Contábil: × 13", "   1  BPO Financeiro: × 12 (1 sem anual antes)"]

    aplicar(sessao, mudancas)
    sessao.commit()
    assert (contabil.preco_anual, contabil.quantidade_parcelas) == (D(65000), 13)
    assert (financeiro.preco_anual, financeiro.quantidade_parcelas) == (D(36000), 12)
    assert "preco_anual" in contabil.campos_do_crm
    assert (certo.preco_anual, sem_mensal.preco_anual, fora.preco_anual) == (D(13000), D(9000), D(4000))
    h = sessao.scalars(sa.select(HistoricoDePreco).where(HistoricoDePreco.oportunidade_id == contabil.id)).one()
    assert (h.preco_anual_anterior, h.preco_anual_novo, h.motivo) == (D(60000), D(65000), MOTIVO)
    assert planejar(sessao) == []  # rodar de novo não muda nada
