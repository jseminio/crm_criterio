"""O tipo dos contratos de antes da tabela de serviços (13/10/2026): recorrente ou não.

Pela ordem: o serviço da oportunidade no catálogo; a linha (C1/C2) gravada na oportunidade; o escopo do contrato, se
for nome de serviço do catálogo; sem nada disso, o preço (com mensal é recorrente; só com o total, não). Sem preço
nenhum, fica vazio. Só mexe no que está vazio: rodar de novo não muda nada.
"""

from __future__ import annotations

from collections import Counter

import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from crm.db.modelos import Contrato
from crm.domain.listas import LinhaServico
from crm.domain.servicos import linha_do_servico


def tipo_provavel(contrato: Contrato) -> tuple[bool | None, str]:
    op = contrato.oportunidade
    for linha, origem in (
        (linha_do_servico(op.servico) if op else None, "pelo serviço"),
        (op.linha_servico if op else None, "pela linha da oportunidade"),
        (linha_do_servico(contrato.escopo), "pelo escopo"),
    ):
        if linha is not None:
            return linha is LinhaServico.C1, origem
    if contrato.preco_mensal is not None:
        return True, "pelo preço mensal"
    if contrato.preco_anual is not None:
        return False, "pelo preço total, sem mensal"
    return None, "sem dado"


def executar(sessao: Session) -> str:
    contratos = sessao.scalars(
        sa.select(Contrato).where(Contrato.recorrente.is_(None)).options(selectinload(Contrato.oportunidade))
    ).all()
    if not contratos:
        return "nada a mudar: todo contrato já tem o tipo"
    origens: Counter[str] = Counter()
    for c in contratos:
        recorrente, origem = tipo_provavel(c)
        if recorrente is not None:
            c.recorrente = recorrente
        origens[origem] += 1
    sessao.flush()
    partes = ", ".join(f"{n} {o}" if o != "sem dado" else f"{n} sem dado (ficam vazios)" for o, n in origens.most_common())
    return f"{len(contratos)} contrato(s) sem tipo: {partes}"
