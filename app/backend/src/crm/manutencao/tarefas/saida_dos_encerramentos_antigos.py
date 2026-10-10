"""Os encerramentos registrados antes de 10/10/2026 não tinham saída efetiva: o contrato saía na data do
evento. Aqui a saída fica igual à data do evento — nada muda no MRR nem no churn de quem já saiu."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import EventoDeContrato
from crm.domain.listas import TipoDeEventoDeContrato


def executar(sessao: Session) -> str:
    eventos = list(sessao.scalars(sa.select(EventoDeContrato).where(
        EventoDeContrato.tipo == TipoDeEventoDeContrato.ENCERRAMENTO, EventoDeContrato.data_da_saida.is_(None),
    )))
    for e in eventos:
        e.data_da_saida = e.data_do_evento
    return f"{len(eventos)} encerramento(s) antigo(s) com a saída igual à data do evento" if eventos else "nada a preencher"
