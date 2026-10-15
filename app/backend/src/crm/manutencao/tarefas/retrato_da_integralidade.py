"""Guarda o retrato do Passado da integralidade do cadastro no dia da publicação (decisão de Eduardo em 15/10/2026):
quantas pendências os registros de antes do corte tinham, para a tela mostrar quantas já foram consertadas. Se o
retrato já existe, não mexe."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from crm.api import integralidade


def executar(sessao: Session) -> str:
    retrato = integralidade.guardar_retrato(sessao, date.today())
    if retrato is None:
        return "nada a fazer: o retrato do Passado já estava guardado"
    return (f"retrato do Passado em {retrato.em:%d/%m/%Y}: {retrato.pendencias} pendência(s), "
            f"{retrato.obrigatorios} obrigatória(s)")
