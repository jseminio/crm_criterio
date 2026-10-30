"""Exporta a Gestão de contratos para Excel (pedido de Karine, 30/10/2026).

As seis colunas da tela (Grupo, Escopo, Situação, Preço mensal, Assinatura, Signatário) e os dados que
existem por trás de cada contrato (empresa, CNPJ, preço anual, recorrente, parcelas no ano, competência,
início do pagamento, fim e saída anunciada) — nos mesmos contratos e na mesma ordem que a tela mostra.
Valor sai como número e data como data; a última linha soma o preço mensal e o anual. Só leitura.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

__all__ = ["COLUNAS", "LinhaDeContrato", "gerar_planilha_de_contratos"]

COLUNAS = [
    "Grupo", "Empresa", "CNPJ", "Escopo", "Situação", "Recorrente", "Preço mensal", "Preço anual",
    "Parcelas no ano", "Assinatura", "Data de competência", "Início do pagamento", "Data de fim",
    "Saída anunciada", "Signatário",
]
_LARGURAS = [30, 40, 20, 36, 22, 11, 15, 15, 9, 13, 13, 13, 13, 13, 28]
_DINHEIRO = "R$ #,##0.00"
_DATA = "DD/MM/YYYY"
_CINZA_CLARO = "F2F2F2"
_COLUNAS_DE_DATA = (11, 12, 13, 14)  # competência, início do pagamento, fim, saída


@dataclass(frozen=True)
class LinhaDeContrato:
    grupo: str | None
    empresa: str | None
    cnpj: str | None
    escopo: str | None
    situacao: str
    recorrente: bool | None
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    parcelas_no_ano: int | None
    assinatura: date | None
    anterior_ao_crm: bool
    data_competencia: date | None
    data_inicio_pagamento: date | None
    data_fim: date | None
    saida_em: date | None
    signatario: str | None


def _cnpj(c: str | None) -> str | None:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if c and len(c) == 14 and c.isdigit() else c


def _dinheiro(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


def gerar_planilha_de_contratos(linhas: list[LinhaDeContrato]) -> bytes:
    """Devolve os bytes do `.xlsx`: uma aba, cabeçalho congelado, filtro ligado e a linha de soma."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Contratos"

    for col, titulo in enumerate(COLUNAS, start=1):
        c = ws.cell(row=1, column=col, value=titulo)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=_CINZA_CLARO)
        ws.column_dimensions[c.column_letter].width = _LARGURAS[col - 1]

    for linha, l in enumerate(linhas, start=2):
        recorrente = None if l.recorrente is None else ("Sim" if l.recorrente else "Não")
        assinatura: date | str | None = l.assinatura or ("anterior ao CRM" if l.anterior_ao_crm else None)
        valores = [
            l.grupo, l.empresa, _cnpj(l.cnpj), l.escopo, l.situacao, recorrente,
            _dinheiro(l.preco_mensal), _dinheiro(l.preco_anual), l.parcelas_no_ano, assinatura,
            l.data_competencia, l.data_inicio_pagamento, l.data_fim, l.saida_em, l.signatario,
        ]
        for col, valor in enumerate(valores, start=1):
            c = ws.cell(row=linha, column=col, value=valor)
            if col in (7, 8):
                c.number_format = _DINHEIRO
            elif col == 10 or col in _COLUNAS_DE_DATA:
                c.number_format = _DATA

    ultima = len(linhas) + 1
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{ws.cell(row=1, column=len(COLUNAS)).column_letter}{max(ultima, 1)}"

    # Soma no fim, fora do filtro: fórmula viva, para continuar certa se alguém editar um valor.
    total = ultima + 2
    ws.cell(row=total, column=1, value=f"Total ({len(linhas)} contrato{'s' if len(linhas) != 1 else ''})").font = Font(bold=True)
    for col, letra in ((7, "G"), (8, "H")):
        c = ws.cell(row=total, column=col, value=f"=SUM({letra}2:{letra}{max(ultima, 2)})" if linhas else 0)
        c.number_format = _DINHEIRO
        c.font = Font(bold=True)

    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()
