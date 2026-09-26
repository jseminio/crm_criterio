"""Regras dos eventos de contrato: o que cada um exige e o que muda no contrato.

**A vigência começa na assinatura** (decisão de Eduardo, 25/09/2026). Por isso:

- `data_inicio` do contrato é a **data da assinatura**; sem ela o contrato não vira Ativo;
- só contrato **Ativo ou Suspenso** recebe evento — antes da assinatura ainda não há o que
  aditar, e um encerrado não se mexe mais;
- um evento não pode ser anterior à assinatura.

Cada tipo:

| Tipo | Exige | Efeito no contrato |
|---|---|---|
| Aditivo | descrição | opcionalmente novo escopo e/ou preço |
| Reajuste | novo preço (mensal e/ou anual) | novo preço, para cima ou para baixo |
| Expansão | novo preço, **não menor** | novo preço |
| Contração | novo preço, **não maior** | novo preço |
| Renovação | nova data de fim, **depois** da atual | nova data de fim |
| Encerramento | **categoria do motivo** (`Outro` exige texto) | situação Encerrado; fim = data do evento |

Funções puras: não tocam no banco. Quem chama grava o evento e aplica o efeito.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from crm.domain.listas import MotivoDeEncerramento, SituacaoContrato, TipoDeEventoDeContrato

__all__ = ["ErroDeEvento", "Pedido", "efeito_do_evento"]

T = TipoDeEventoDeContrato
MINIMO_DO_TEXTO = 3


class ErroDeEvento(ValueError):
    """`status` diz se o problema é do estado do contrato (409) ou do pedido (422)."""

    def __init__(self, mensagem: str, status: int = 422):
        super().__init__(mensagem)
        self.status = status


class _Contrato(Protocol):
    situacao: SituacaoContrato
    escopo: str | None
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    data_inicio: date | None
    data_fim: date | None


@dataclass(frozen=True)
class Pedido:
    tipo: T
    data_do_evento: date
    descricao: str | None = None
    escopo_novo: str | None = None
    preco_mensal_novo: Decimal | None = None
    preco_anual_novo: Decimal | None = None
    data_fim_nova: date | None = None
    motivo_categoria: MotivoDeEncerramento | None = None


def _texto_obrigatorio(pedido: Pedido, o_que: str) -> None:
    if len((pedido.descricao or "").strip()) < MINIMO_DO_TEXTO:
        raise ErroDeEvento(f"{pedido.tipo.value}: informe {o_que}.")


def efeito_do_evento(contrato: _Contrato, pedido: Pedido) -> dict[str, object]:
    """Valida o pedido contra o contrato e devolve o que muda nele (campo → valor novo).

    Levanta `ErroDeEvento` sem alterar nada.
    """
    if contrato.situacao is SituacaoContrato.AGUARDANDO_ASSINATURA:
        raise ErroDeEvento("O contrato ainda não foi assinado: registre a assinatura antes de qualquer evento.", 409)
    if contrato.situacao is SituacaoContrato.ENCERRADO:
        raise ErroDeEvento("O contrato está encerrado e não recebe mais eventos.", 409)
    if contrato.data_inicio and pedido.data_do_evento < contrato.data_inicio:
        raise ErroDeEvento("O evento não pode ser anterior à assinatura do contrato.")

    tipo = pedido.tipo
    novos_precos = {
        campo: valor
        for campo, valor in (("preco_mensal", pedido.preco_mensal_novo), ("preco_anual", pedido.preco_anual_novo))
        if valor is not None
    }
    for campo, valor in novos_precos.items():
        if valor < 0:
            raise ErroDeEvento("Preço não pode ser negativo.")
    efeito: dict[str, object] = {}

    if tipo is T.ADITIVO:
        _texto_obrigatorio(pedido, "o que foi aditado")
        efeito.update(novos_precos)
        if pedido.escopo_novo is not None and pedido.escopo_novo != contrato.escopo:
            efeito["escopo"] = pedido.escopo_novo

    elif tipo in (T.REAJUSTE, T.EXPANSAO, T.CONTRACAO):
        if not novos_precos:
            raise ErroDeEvento(f"{tipo.value}: informe o novo preço mensal e/ou anual.")
        mudou = False
        for campo, novo in novos_precos.items():
            atual = getattr(contrato, campo)
            if atual is not None and novo != atual:
                mudou = True
                if tipo is T.EXPANSAO and novo < atual:
                    raise ErroDeEvento("Expansão aumenta o valor: o novo preço não pode ser menor. Para reduzir, use Contração.")
                if tipo is T.CONTRACAO and novo > atual:
                    raise ErroDeEvento("Contração reduz o valor: o novo preço não pode ser maior. Para aumentar, use Expansão.")
            elif atual is None:
                mudou = True
        if not mudou:
            raise ErroDeEvento(f"{tipo.value}: o novo preço é igual ao atual.")
        efeito.update(novos_precos)

    elif tipo is T.RENOVACAO:
        if pedido.data_fim_nova is None:
            raise ErroDeEvento("Renovação: informe a nova data de fim.")
        referencia = contrato.data_fim or pedido.data_do_evento
        if pedido.data_fim_nova <= referencia:
            raise ErroDeEvento("Renovação: a nova data de fim precisa ser depois da atual.")
        efeito["data_fim"] = pedido.data_fim_nova

    elif tipo is T.ENCERRAMENTO:
        if pedido.motivo_categoria is None:
            raise ErroDeEvento("Encerramento: escolha a categoria do motivo.")
        if pedido.motivo_categoria is MotivoDeEncerramento.OUTRO:
            _texto_obrigatorio(pedido, "o motivo (a categoria é “Outro”)")
        efeito["situacao"] = SituacaoContrato.ENCERRADO
        efeito["data_fim"] = pedido.data_do_evento

    return efeito
