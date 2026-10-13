"""A série do IPCA no Banco Central: SGS, série 433 (variação mensal, em %), consulta pública sem chave.

`https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=dd/mm/aaaa&dataFinal=dd/mm/aaaa`
devolve `[{"data": "01/01/2026", "valor": "0.42"}, ...]`. O Banco Central limita cada consulta a 10 anos, então a
busca anda em janelas de 10 anos.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

import httpx2 as httpx

__all__ = ["SERIE_DO_IPCA", "BuscaDoIpcaFalhou", "buscar_ipca"]

SERIE_DO_IPCA = 433
URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
JANELA_EM_ANOS = 10


class BuscaDoIpcaFalhou(RuntimeError):
    """O Banco Central não respondeu, recusou ou devolveu algo que não é a série. Nada foi gravado."""


def _ler(itens: object) -> dict[date, Decimal]:
    if not isinstance(itens, list):
        raise BuscaDoIpcaFalhou("o Banco Central devolveu uma resposta que não é a série do IPCA")
    meses: dict[date, Decimal] = {}
    for item in itens:
        try:
            dia, mes, ano = (int(p) for p in str(item["data"]).split("/"))
            meses[date(ano, mes, 1)] = Decimal(str(item["valor"]))
        except (KeyError, TypeError, ValueError, InvalidOperation) as erro:
            raise BuscaDoIpcaFalhou(f"linha da série do IPCA ilegível: {item!r}") from erro
    return meses


def buscar_ipca(de: date, ate: date, *, timeout: float = 20.0) -> dict[date, Decimal]:
    """Os meses de `de` até `ate`, {dia 1 do mês: variação em %}."""
    meses: dict[date, Decimal] = {}
    inicio = de.replace(day=1)
    while inicio <= ate:
        fim = min(ate, date(inicio.year + JANELA_EM_ANOS, inicio.month, 1))
        try:
            resposta = httpx.get(
                URL.format(serie=SERIE_DO_IPCA),
                params={"formato": "json", "dataInicial": f"{inicio:%d/%m/%Y}", "dataFinal": f"{fim:%d/%m/%Y}"},
                timeout=timeout,
            )
        except httpx.HTTPError as erro:
            raise BuscaDoIpcaFalhou(f"o Banco Central não respondeu ({type(erro).__name__})") from erro
        if resposta.status_code == 404:
            # O SGS responde 404 quando a janela não tem nenhum mês publicado ainda.
            pass
        elif resposta.status_code != 200:
            raise BuscaDoIpcaFalhou(f"o Banco Central recusou a consulta (HTTP {resposta.status_code})")
        else:
            try:
                corpo = resposta.json()
            except ValueError as erro:
                raise BuscaDoIpcaFalhou("o Banco Central devolveu uma resposta que não é JSON") from erro
            meses.update(_ler(corpo))
        if fim >= ate:
            break
        inicio = date(fim.year + fim.month // 12, fim.month % 12 + 1, 1)
    return meses
