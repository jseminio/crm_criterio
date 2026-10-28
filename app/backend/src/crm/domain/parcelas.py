"""Datas de competência e de início do pagamento, e as parcelas do não recorrente (Eduardo, 28/10/2026).

- **Data de competência**: quando a Critério assume os serviços. A 13ª proporcional conta os avos a partir dela.
- **Início do pagamento**: o vencimento da 1ª parcela, a data do primeiro recebimento. O contrato entra no MRR
  (e conta como MRR novo) nela.
- Sem essas datas, vale a assinatura (`data_inicio`), como antes: não se inventa data.

**Parcelas do não recorrente**: uma lista de `{vencimento, valor}`, valores não necessariamente iguais. A soma tem
de bater com o valor total do serviço (o preço anual; sem ele, o mensal, como os KPIs leem o não recorrente).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

__all__ = ["Parcela", "inicio_do_mrr", "inicio_do_servico", "ler", "gravar", "problema_nas_parcelas", "total_do_servico",
           "no_mes"]

CENTAVOS = Decimal("0.01")
MAXIMO_DE_PARCELAS = 60


@dataclass(frozen=True)
class Parcela:
    vencimento: date
    valor: Decimal


def inicio_do_mrr(c: Any) -> date | None:
    """Onde o contrato começa a contar no MRR: o início do pagamento, senão a assinatura. A carteira anterior ao CRM
    sem assinatura conhecida segue sem data: existe desde sempre, nunca é MRR novo."""
    if getattr(c, "anterior_ao_crm", False) and getattr(c, "data_inicio", None) is None:
        return None
    return getattr(c, "data_inicio_pagamento", None) or getattr(c, "data_inicio", None)


def inicio_do_servico(c: Any) -> date | None:
    """De onde a 13ª proporcional conta os avos: a data de competência, senão a assinatura."""
    return getattr(c, "data_competencia", None) or getattr(c, "data_inicio", None)


def ler(guardado: Iterable[dict] | None) -> list[Parcela]:
    """As parcelas como estão no banco (JSON), em ordem de vencimento."""
    lista = [Parcela(date.fromisoformat(str(p["vencimento"])), Decimal(str(p["valor"]))) for p in (guardado or [])]
    return sorted(lista, key=lambda p: p.vencimento)


def gravar(parcelas: Iterable[Parcela]) -> list[dict] | None:
    """O JSON que vai para o banco; lista vazia vira `None` (sem parcelas)."""
    lista = sorted(parcelas, key=lambda p: p.vencimento)
    if not lista:
        return None
    return [{"vencimento": p.vencimento.isoformat(), "valor": str(p.valor.quantize(CENTAVOS, ROUND_HALF_UP))}
            for p in lista]


def total_do_servico(preco_anual: Decimal | None, preco_mensal: Decimal | None) -> Decimal | None:
    """O valor total do não recorrente: o preço anual; sem ele, o mensal."""
    total = preco_anual if preco_anual is not None else preco_mensal
    return Decimal(total).quantize(CENTAVOS, ROUND_HALF_UP) if total is not None else None


def problema_nas_parcelas(parcelas: list[Parcela], total: Decimal | None) -> str | None:
    """A frase de por que as parcelas não podem ser gravadas; `None` se podem."""
    if not parcelas:
        return None
    if len(parcelas) > MAXIMO_DE_PARCELAS:
        return f"no máximo {MAXIMO_DE_PARCELAS} parcelas"
    if any(p.valor <= 0 for p in parcelas):
        return "toda parcela precisa de valor maior que zero"
    if total is None:
        return "informe o valor total do serviço antes de dividir em parcelas"
    soma = sum((p.valor for p in parcelas), Decimal("0")).quantize(CENTAVOS, ROUND_HALF_UP)
    if soma != total:
        diferenca = total - soma
        quanto = f"R$ {abs(diferenca):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"a soma das parcelas não bate com o valor total: {'faltam' if diferenca > 0 else 'sobram'} {quanto}"
    return None


def no_mes(parcelas: Iterable[Parcela], competencia: date) -> Decimal:
    """Quanto das parcelas vence no mês da competência."""
    return sum((p.valor for p in parcelas if (p.vencimento.year, p.vencimento.month) == (competencia.year,
                                                                                         competencia.month)),
               Decimal("0"))
