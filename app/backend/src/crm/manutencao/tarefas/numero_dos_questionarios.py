"""Numera os questionários que já estavam no CRM e preenche a chave de quem preencheu (decisão de Eduardo, 11/11/2026).

Pela ordem de chegada, a partir do Q-1001. Só mexe em quem ainda não tem número ou chave; rodar de novo não muda nada.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import QuestionarioRecebido
from crm.questionario.importacao import PRIMEIRO_NUMERO, chave_do_preenchedor


def executar(sessao: Session) -> str:
    maior = sessao.scalar(sa.select(sa.func.max(QuestionarioRecebido.numero)))
    proximo = max(PRIMEIRO_NUMERO, (maior or 0) + 1)
    sem_numero = sessao.scalars(
        sa.select(QuestionarioRecebido).where(QuestionarioRecebido.numero.is_(None))
        .order_by(QuestionarioRecebido.recebido_em, QuestionarioRecebido.id)
    ).all()
    for q in sem_numero:
        q.numero, proximo = proximo, proximo + 1
    sem_chave = sessao.scalars(sa.select(QuestionarioRecebido).where(QuestionarioRecebido.chave_do_preenchedor.is_(None))).all()
    for q in sem_chave:
        q.chave_do_preenchedor = chave_do_preenchedor(q.cnpj, q.contato_nome)
    sessao.flush()
    return f"{len(sem_numero)} questionário(s) numerado(s), {len(sem_chave)} chave(s) preenchida(s)"
