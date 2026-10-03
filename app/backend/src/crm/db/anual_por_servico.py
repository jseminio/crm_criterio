"""Recalcula o preço anual das oportunidades já gravadas pelo serviço — 03/10/2026.

Regra de Eduardo: contábil e DP têm 13 mensalidades no ano (o 13º honorário) e o BPO Financeiro 12;
o anual é mensal × isso. A tela e a API já seguem a regra; este módulo corrige o que foi gravado
antes (autorizado por Eduardo em 03/10/2026). Cada mudança deixa linha no Histórico de preço e entra
em `campos_do_crm`, para a recarga da planilha não desfazer. Sem preço mensal, ou com serviço fora
da regra, nada muda. Contratos ficam como estão.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import HistoricoDePreco, Oportunidade
from crm.domain.listas import ORIGEM_DA_MUDANCA_NO_CRM
from crm.domain.servicos import meses_no_ano

__all__ = ["MOTIVO", "Mudanca", "planejar", "aplicar", "resumir"]

MOTIVO = "Regra de 03/10/2026: anual = mensal × 13 (contábil e DP) ou × 12 (financeiro)"


@dataclass(frozen=True)
class Mudanca:
    oportunidade_id: int
    servico: str
    meses: int
    mensal: Decimal
    antes: Decimal | None
    depois: Decimal


def planejar(sessao: Session) -> list[Mudanca]:
    """O que mudaria, sem gravar nada."""
    mudancas = []
    for id_, servico, mensal, anual in sessao.execute(
        sa.select(Oportunidade.id, Oportunidade.servico, Oportunidade.preco_mensal, Oportunidade.preco_anual)
        .order_by(Oportunidade.id)
    ):
        meses = meses_no_ano(servico)
        if meses is None or mensal is None:
            continue
        novo = mensal * meses
        if anual != novo:
            mudancas.append(Mudanca(id_, servico, meses, mensal, anual, novo))
    return mudancas


def aplicar(sessao: Session, mudancas: list[Mudanca]) -> None:
    for m in mudancas:
        o = sessao.get(Oportunidade, m.oportunidade_id)
        sessao.add(HistoricoDePreco(
            oportunidade_id=o.id, origem=ORIGEM_DA_MUDANCA_NO_CRM, motivo=MOTIVO,
            preco_mensal_anterior=o.preco_mensal, preco_mensal_novo=o.preco_mensal,
            preco_anual_anterior=o.preco_anual, preco_anual_novo=m.depois,
        ))
        o.preco_anual, o.quantidade_parcelas = m.depois, m.meses
        # Nova lista, não mutação: o SQLAlchemy não enxerga alteração no lugar de um valor JSON.
        o.campos_do_crm = sorted(set(o.campos_do_crm or []) | {"preco_anual"})


def resumir(mudancas: list[Mudanca]) -> list[str]:
    """Uma linha por (serviço, × meses), com a contagem e quantas não tinham anual."""
    contagem = Counter((m.servico, m.meses) for m in mudancas)
    sem_anual = Counter((m.servico, m.meses) for m in mudancas if m.antes is None)
    return [
        f"{n:>4}  {servico}: × {meses}" + (f" ({sem_anual[(servico, meses)]} sem anual antes)" if sem_anual[(servico, meses)] else "")
        for (servico, meses), n in sorted(contagem.items())
    ]
