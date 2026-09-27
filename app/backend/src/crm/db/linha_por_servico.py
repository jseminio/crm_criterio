"""Reclassifica a linha (C1/C2) das oportunidades pelo serviço — 27/09/2026.

Regra de Eduardo: C1 é recorrente, C2 não é recorrente, e a linha sai do
serviço, **também no passado**. A carga e a tela já seguem a regra; este
módulo corrige o que foi gravado antes. Serviço fora do catálogo não muda.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Oportunidade
from crm.domain.listas import LinhaServico
from crm.domain.servicos import linha_do_servico

__all__ = ["Mudanca", "planejar", "aplicar", "resumir"]


@dataclass(frozen=True)
class Mudanca:
    oportunidade_id: int
    servico: str
    antes: LinhaServico | None
    depois: LinhaServico


def planejar(sessao: Session) -> list[Mudanca]:
    """O que mudaria, sem gravar nada."""
    mudancas = []
    for id_, servico, linha in sessao.execute(
        sa.select(Oportunidade.id, Oportunidade.servico, Oportunidade.linha_servico).order_by(Oportunidade.id)
    ):
        nova = linha_do_servico(servico)
        if nova is not None and nova is not linha:
            mudancas.append(Mudanca(id_, servico, linha, nova))
    return mudancas


def aplicar(sessao: Session, mudancas: list[Mudanca]) -> None:
    for linha in LinhaServico:
        ids = [m.oportunidade_id for m in mudancas if m.depois is linha]
        if ids:
            sessao.execute(sa.update(Oportunidade).where(Oportunidade.id.in_(ids)).values(linha_servico=linha))


def resumir(mudancas: list[Mudanca]) -> list[str]:
    """Uma linha por (serviço, antes → depois), com a contagem."""
    contagem = Counter(
        (m.servico, m.antes.value if m.antes else "vazio", m.depois.value) for m in mudancas
    )
    return [f"{n:>4}  {servico}: {antes} → {depois}" for (servico, antes, depois), n in sorted(contagem.items())]
