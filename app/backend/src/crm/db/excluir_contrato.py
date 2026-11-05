"""Excluir um contrato pela tela (30/10/2026, amostra aprovada por Karine).

Qualquer situação — inclusive Ativo e Encerrado (decisão de Karine): o contrato some da carteira, do
MRR e dos indicadores como se nunca tivesse existido. Para encerrar um contrato que existiu, o caminho
continua sendo o evento de encerramento, que guarda a história.

Sai junto o que só existe por causa dele: os eventos, os pedidos de aprovação e os documentos gerados
pelo CRM. Fica o que tem vida própria: a oportunidade de origem (continua Aceita e pode ser convertida
de novo), o grupo, a empresa, os PDFs anexados e os envelopes do Clicksign; esses só deixam de apontar
para ele.

O motivo vai para o histórico de alterações numa linha própria, mesmo sem login: a exclusão não se
desfaz pela tela, e o porquê é o que sobra dela.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.acesso.auditoria import usuario_atual
from crm.db.modelos import (
    Contrato, DocumentoAnexado, DocumentoDeContrato, EnvelopeDoClicksign, EventoDeContrato, PedidoDeAprovacao,
    RegistroDeAlteracao,
)

__all__ = ["ExclusaoRecusada", "OQueSai", "o_que_sai", "excluir"]


class ExclusaoRecusada(ValueError):
    """O pedido de exclusão não fecha; a mensagem diz o que falta."""


@dataclass(frozen=True)
class OQueSai:
    eventos: int
    pedidos_de_aprovacao: int
    documentos_gerados: int
    anexos: int
    """Ficam, sem apontar para ele."""
    envelopes: int
    """Ficam, sem apontar para ele."""


def _contar(sessao: Session, coluna, *onde) -> int:
    return sessao.scalar(sa.select(sa.func.count(coluna)).where(*onde)) or 0


def o_que_sai(sessao: Session, contrato: Contrato) -> OQueSai:
    return OQueSai(
        eventos=_contar(sessao, EventoDeContrato.id, EventoDeContrato.contrato_id == contrato.id),
        pedidos_de_aprovacao=_contar(sessao, PedidoDeAprovacao.id, PedidoDeAprovacao.contrato_id == contrato.id),
        documentos_gerados=_contar(sessao, DocumentoDeContrato.id, DocumentoDeContrato.contrato_id == contrato.id),
        anexos=_contar(sessao, DocumentoAnexado.id, DocumentoAnexado.contrato_id == contrato.id),
        envelopes=_contar(sessao, EnvelopeDoClicksign.id, EnvelopeDoClicksign.contrato_id == contrato.id),
    )


def excluir(sessao: Session, contrato: Contrato, motivo: str) -> None:
    """Apaga o contrato e o que é só dele; desliga o resto. Não faz commit."""
    motivo = " ".join((motivo or "").split())
    if not motivo:
        raise ExclusaoRecusada("Diga o motivo da exclusão.")
    for modelo in (DocumentoAnexado, EnvelopeDoClicksign):
        sessao.execute(sa.update(modelo).where(modelo.contrato_id == contrato.id).values(contrato_id=None))
    # O pedido aponta para o evento que nasceu dele: sai antes do evento.
    for modelo in (PedidoDeAprovacao, EventoDeContrato, DocumentoDeContrato):
        for x in sessao.scalars(sa.select(modelo).where(modelo.contrato_id == contrato.id)):
            sessao.delete(x)
        sessao.flush()
    quem = usuario_atual.get()
    descricao = " · ".join(p for p in (contrato.grupo.nome if contrato.grupo else None, contrato.escopo) if p)
    sessao.add(RegistroDeAlteracao(
        usuario_email=quem.email if quem else "sem login", usuario_nome=quem.nome if quem else None,
        acao="excluiu", tabela="contrato", registro_id=contrato.id, descricao=descricao[:200] or None,
        campo="motivo", depois=motivo[:1000], rota=quem.rota if quem else None,
    ))
    sessao.expire(contrato, ["eventos"])  # a lista carregada ainda traria os eventos já apagados
    sessao.delete(contrato)
    sessao.flush()
