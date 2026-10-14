"""Leitura das plataformas de anúncio (13/10/2026). Só lê: nada aqui cria ou muda campanha.

O que vale para todas: o gasto de uma campanha no mês e a falha com frase para a pessoa ler.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

__all__ = ["AcessoNegado", "GastoDaCampanha", "LeituraFalhou", "Recusado", "intervalo"]


class LeituraFalhou(RuntimeError):
    """A leitura ou o envio não deu certo agora (rede, instabilidade). A mensagem é para a pessoa ler;
    nunca leva token, segredo ou dado do lead. No envio de conversão, tenta de novo na próxima rodada."""


class AcessoNegado(LeituraFalhou):
    """A plataforma recusou a credencial ou falta configuração (14/10/2026). O envio para na rodada e não
    gasta tentativa: depois de corrigir em Integrações, sai normalmente."""


class Recusado(RuntimeError):
    """A plataforma recusou o evento de vez (dado inválido, fora do prazo): não adianta reenviar."""


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
