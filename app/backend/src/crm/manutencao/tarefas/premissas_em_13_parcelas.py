"""Leva as premissas do plano de MRR para a base de 13 parcelas (decisão de Eduardo, 09/10/2026).

O MRR do CRM passou a ser a parcela × 13 ÷ 12. As premissas em reais do plano tinham sido escritas
pela parcela; aqui viram MRR, ao centavo: a meta (R$ 250 mil → R$ 270.833,33, o mesmo esforço), o ponto
e o MRR de partida, os tickets (BPO, contábil por cenário), os acréscimos da escada e o valor dos
contratos previstos. Contagens, percentuais e prazos não mudam.

Rodar de novo não converte duas vezes: a linha convertida fica marcada em `alterado_por` (`QUEM`).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.base import agora
from crm.db.modelos import ContratoPrevistoDoPlano, PlanoDeMrr

QUEM = "atualizador (premissas em 13 parcelas)"
CAMPOS = (
    "meta_liquida", "ponto_de_partida", "mrr_de_partida", "bpo_ticket", "plus_acrescimo", "cfo_acrescimo",
    "alerta_ticket_contabil", "previsto_ticket_contabil", "otimista_ticket_contabil",
)


def em_mrr(v: Decimal) -> Decimal:
    return (Decimal(v) * 13 / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def executar(sessao: Session) -> str:
    planos = [p for p in sessao.scalars(sa.select(PlanoDeMrr)) if p.alterado_por != QUEM]
    if not planos:
        return "nada a converter: o plano usa o padrão do código, já em 13 parcelas"
    for p in planos:
        for campo in CAMPOS:
            valor = getattr(p, campo)
            if valor is not None:
                setattr(p, campo, em_mrr(valor))
        p.alterado_por, p.alterado_em = QUEM, agora()
    previstos = list(sessao.scalars(sa.select(ContratoPrevistoDoPlano)))
    for c in previstos:
        c.valor = em_mrr(c.valor)
    return f"{len(planos)} plano(s) e {len(previstos)} contrato(s) previsto(s) convertidos para 13 parcelas"
