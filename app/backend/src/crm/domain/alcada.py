"""Alçada dos eventos de contrato (decisões de Eduardo em 02/10/2026).

Pedem aprovação, quando quem registra não tem a funcionalidade "aprovar eventos de contrato":

- **Contração** e **Reajuste para baixo** que reduzam o preço mensal ou o anual em **mais de 10%**;
- **Aditivo** que mude o escopo, ou que reduza o preço em mais de 10%.

Expansão, reajuste para cima, renovação, correção e encerramento entram direto. A absorção de horas
fora da política fica para a Etapa 2, junto do saldo de horas de conforto.

Função pura: não toca no banco. Quem chama decide se grava o evento ou o pedido de aprovação.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol

from crm.domain.listas import TipoDeEventoDeContrato

__all__ = ["LIMITE_DE_REDUCAO", "TIPOS_COM_ALCADA", "motivo_da_alcada"]

T = TipoDeEventoDeContrato
LIMITE_DE_REDUCAO = Decimal("0.10")
"""Redução acima disto (fração do preço atual) pede aprovação."""
TIPOS_COM_ALCADA = frozenset({T.CONTRACAO, T.REAJUSTE, T.ADITIVO})

_ROTULO = {"preco_mensal": "preço mensal", "preco_anual": "preço anual"}


class _Contrato(Protocol):
    escopo: str | None
    preco_mensal: Decimal | None
    preco_anual: Decimal | None


def _percentual(fracao: Decimal) -> str:
    return f"{(fracao * 100).quantize(Decimal('0.1'), ROUND_HALF_UP)}".replace(".", ",") + "%"


def motivo_da_alcada(contrato: _Contrato, tipo: TipoDeEventoDeContrato, efeito: dict[str, object]) -> str | None:
    """Por que o evento precisa de aprovação, em texto para a tela; `None` = entra direto.

    `efeito` é o que `efeito_do_evento` devolveu: o evento já foi validado."""
    if tipo not in TIPOS_COM_ALCADA:
        return None
    motivos: list[str] = []
    if tipo is T.ADITIVO and "escopo" in efeito:
        motivos.append("aditivo que muda o escopo")
    for campo, rotulo in _ROTULO.items():
        novo = efeito.get(campo)
        atual = getattr(contrato, campo)
        if not isinstance(novo, Decimal) or atual is None or atual <= 0 or novo >= atual:
            continue
        queda = (atual - novo) / atual
        if queda > LIMITE_DE_REDUCAO:
            motivos.append(f"redução de {_percentual(queda)} no {rotulo}")
    return "; ".join(motivos) or None
