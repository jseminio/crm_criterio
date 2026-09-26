"""Recortes do funil por serviço, canal e captador, e os cenários de ticket.

**Recorrente** = aceita com preço mensal **maior que zero**, a mesma definição do
`TicketRecorrente` em `crm.domain.indicadores`.

Os cenários de ticket saem de uma regra estatística, não de escolha manual de quem
tirar da conta (pedido de Eduardo, 25/09/2026):

- **atípico** = contrato recorrente acima de **3 × a mediana**;
- **comum** — *conservador* = mediana de todos; *base* = média dos que não são
  atípicos; *otimista* = terceiro quartil dos que não são atípicos;
- **atípico** — o menor, a média e o maior observados.

São **hipóteses de trabalho**, não meta. Com poucos contratos, o número mexe muito.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median, quantiles
from typing import Iterable, Protocol

from crm.domain.listas import Situacao

__all__ = ["CenariosDeTicket", "LinhaDeRecorte", "DIMENSOES", "recortar", "cenarios_de_ticket"]

ZERO = Decimal("0.00")
CENTAVOS = Decimal("0.01")
FATOR_DO_ATIPICO = Decimal("3")
MINIMO_PARA_CENARIOS = 4
SEM_VALOR = "(não informado)"

#: dimensão → como ler o valor da oportunidade.
DIMENSOES = ("servico", "tipo_canal", "captador")


class _Oportunidade(Protocol):
    situacao: Situacao
    servico: str | None
    captador: str | None
    preco_mensal: Decimal | None


@dataclass(frozen=True)
class LinhaDeRecorte:
    chave: str
    propostas: int
    em_aberto: int
    aceitas: int
    decididas: int
    conversao: Decimal | None
    """Aceitas ÷ decididas, como no cartão de conversão. `None` sem nenhuma decidida."""
    recorrentes: int
    valor_mensal: Decimal
    ticket_medio: Decimal | None
    mediana: Decimal | None


@dataclass(frozen=True)
class CenariosDeTicket:
    contratos: int
    atipicos: int
    limite_do_atipico: Decimal
    conservador: Decimal
    base: Decimal
    otimista: Decimal
    atipico_minimo: Decimal | None
    atipico_medio: Decimal | None
    atipico_maximo: Decimal | None


def _valor(o, dimensao: str) -> str:
    v = getattr(o, dimensao)
    v = getattr(v, "value", v)
    return v if v else SEM_VALOR


def _mensal(o) -> Decimal | None:
    return o.preco_mensal if o.situacao.ganha and o.preco_mensal is not None and o.preco_mensal > 0 else None


def recortar(oportunidades: Iterable[_Oportunidade], dimensao: str) -> list[LinhaDeRecorte]:
    if dimensao not in DIMENSOES:
        raise ValueError(f"dimensão desconhecida: {dimensao}")
    grupos: dict[str, list] = {}
    for o in oportunidades:
        grupos.setdefault(_valor(o, dimensao), []).append(o)
    linhas = []
    for chave, itens in grupos.items():
        aceitas = [o for o in itens if o.situacao.ganha]
        decididas = [o for o in itens if o.situacao.decidida]
        mensais = [m for o in itens if (m := _mensal(o)) is not None]
        linhas.append(
            LinhaDeRecorte(
                chave=chave,
                propostas=len(itens),
                em_aberto=sum(1 for o in itens if not o.situacao.decidida),
                aceitas=len(aceitas),
                decididas=len(decididas),
                conversao=(Decimal(len(aceitas)) / len(decididas) * 100).quantize(Decimal("0.1")) if decididas else None,
                recorrentes=len(mensais),
                valor_mensal=sum(mensais, ZERO),
                ticket_medio=(sum(mensais, ZERO) / len(mensais)).quantize(CENTAVOS) if mensais else None,
                mediana=Decimal(median(mensais)).quantize(CENTAVOS) if mensais else None,
            )
        )
    linhas.sort(key=lambda l: (-l.propostas, l.chave))
    return linhas


def cenarios_de_ticket(oportunidades: Iterable[_Oportunidade]) -> CenariosDeTicket | None:
    """`None` com menos de 4 contratos recorrentes: não há base para cenário."""
    mensais = sorted(m for o in oportunidades if (m := _mensal(o)) is not None)
    if len(mensais) < MINIMO_PARA_CENARIOS:
        return None
    mediana = Decimal(median(mensais))
    limite = mediana * FATOR_DO_ATIPICO
    comuns = [m for m in mensais if m <= limite]
    atipicos = [m for m in mensais if m > limite]
    media_comum = sum(comuns, ZERO) / len(comuns)
    q3 = Decimal(quantiles(comuns, n=4, method="inclusive")[2]) if len(comuns) >= 2 else comuns[0]
    return CenariosDeTicket(
        contratos=len(mensais),
        atipicos=len(atipicos),
        limite_do_atipico=limite.quantize(CENTAVOS),
        conservador=mediana.quantize(CENTAVOS),
        base=media_comum.quantize(CENTAVOS),
        otimista=q3.quantize(CENTAVOS),
        atipico_minimo=min(atipicos) if atipicos else None,
        atipico_medio=(sum(atipicos, ZERO) / len(atipicos)).quantize(CENTAVOS) if atipicos else None,
        atipico_maximo=max(atipicos) if atipicos else None,
    )
