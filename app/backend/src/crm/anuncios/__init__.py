"""Leitura das plataformas de anúncio (13/10/2026). Só lê: nada aqui cria ou muda campanha.

O que vale para todas: o gasto de uma campanha no mês e a falha com frase para a pessoa ler.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

__all__ = ["GastoDaCampanha", "LeituraFalhou", "intervalo"]


class LeituraFalhou(RuntimeError):
    """A leitura não deu certo. A mensagem é para a pessoa ler; nunca leva token ou segredo."""


@dataclass(frozen=True)
class GastoDaCampanha:
    id: str
    nome: str
    valor: Decimal


def intervalo(mes: str, hoje: date) -> tuple[date, date] | None:
    """Do dia 1 ao último dia do mês, ou até hoje no mês corrente. `None` para mês futuro."""
    ano, numero = (int(p) for p in mes.split("-"))
    inicio = date(ano, numero, 1)
    if inicio > hoje:
        return None
    fim = date(ano + (numero == 12), numero % 12 + 1, 1) - timedelta(days=1)
    return inicio, min(fim, hoje)
