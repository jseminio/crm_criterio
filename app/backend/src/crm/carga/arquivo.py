"""Leitura da planilha de performance comercial em disco.

Fica separado de :mod:`crm.carga.planilha_2026` de propósito: a normalização é
lógica pura e testável sem arquivo; aqui mora o que sabe de ``.xlsx``.

A aba ``Propostas`` tem **duas colunas chamadas "Responsável"** — a primeira é
a linha de serviço (C1/C2), a segunda é o captador. O leitor desambigua,
renomeando a segunda para ``Responsável 2``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

__all__ = ["ler_aba_propostas", "ABA"]

ABA = "Propostas"


def _cabecalho(linha: tuple[Any, ...]) -> list[str | None]:
    """Nomes de coluna, com os repetidos numerados a partir da segunda vez."""
    vistos: dict[str, int] = {}
    nomes: list[str | None] = []
    for celula in linha:
        if celula is None:
            nomes.append(None)
            continue
        nome = str(celula).strip()
        vistos[nome] = vistos.get(nome, 0) + 1
        nomes.append(nome if vistos[nome] == 1 else f"{nome} {vistos[nome]}")
    return nomes


def ler_aba_propostas(caminho: str | Path) -> Iterator[dict[str, Any]]:
    """Gera uma linha de cada vez, já com os nomes de coluna resolvidos."""
    import openpyxl  # dependência só desta camada

    livro = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    try:
        aba = livro[ABA]
        linhas = aba.iter_rows(values_only=True)
        nomes = _cabecalho(next(linhas))
        for valores in linhas:
            if not any(v is not None for v in valores):
                continue
            yield {
                nome: valor
                for nome, valor in zip(nomes, valores)
                if nome is not None
            }
    finally:
        livro.close()
