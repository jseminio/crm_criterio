"""Excluir uma oportunidade pela tela (04/10/2026, amostra aprovada por Eduardo).

Para o que entrou errado: duplicada, teste, cadastrada no grupo errado. Sai junto o que só existe
por causa dela (propostas, pendências da proposta, histórico de preço). Fica o que tem vida própria:
o grupo, as empresas, os contatos, as reuniões, o questionário do site e o lead de origem; esses só
deixam de apontar para ela.

Recusa a oportunidade **Aceita** ou **Recusada** (é o desfecho do funil e conta na taxa de conversão:
se a venda não aconteceu, o certo é mudar para Perdido) e a que **virou contrato**.

O motivo vai para o histórico de alterações numa linha própria, mesmo sem login (quem fica
"sem login"): a exclusão não se desfaz pela tela, e o porquê é o que sobra dela.
"""

from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.acesso.auditoria import usuario_atual
from crm.db.modelos import (
    Contrato, HistoricoDePreco, Lead, Oportunidade, OportunidadeDaReuniao, PendenciaDaProposta, Proposta,
    QuestionarioRecebido, RegistroDeAlteracao,
)
from crm.domain.listas import Situacao

__all__ = ["ExclusaoRecusada", "OQueSai", "o_que_sai", "excluir"]


class ExclusaoRecusada(ValueError):
    """A oportunidade não pode sair pela tela; a mensagem diz o que fazer no lugar."""


@dataclass(frozen=True)
class OQueSai:
    recusa: str | None
    propostas: int
    pendencias: int
    precos: int
    questionarios: int
    """Ficam, sem apontar para ela."""
    leads: int
    vendas_da_reuniao: int
    sai_da_conversao: bool
    """Perdido conta na taxa de conversão: excluir muda o número."""


def _recusa(sessao: Session, op: Oportunidade) -> str | None:
    if sessao.scalar(sa.select(Contrato.id).where(Contrato.oportunidade_id == op.id).limit(1)) is not None:
        return "Não dá para excluir: esta oportunidade virou contrato. Resolva o contrato em Gestão de contratos."
    if op.situacao in (Situacao.ACEITA, Situacao.RECUSADA):
        return (f"Não dá para excluir uma oportunidade {op.situacao.value}: ela conta na taxa de conversão. "
                "Se a venda não aconteceu, mude a situação para Perdido.")
    return None


def _contar(sessao: Session, coluna, *onde) -> int:
    return sessao.scalar(sa.select(sa.func.count(coluna)).where(*onde)) or 0


def o_que_sai(sessao: Session, op: Oportunidade) -> OQueSai:
    return OQueSai(
        recusa=_recusa(sessao, op),
        propostas=_contar(sessao, Proposta.id, Proposta.oportunidade_id == op.id),
        pendencias=_contar(sessao, PendenciaDaProposta.id, PendenciaDaProposta.oportunidade_id == op.id),
        precos=_contar(sessao, HistoricoDePreco.id, HistoricoDePreco.oportunidade_id == op.id),
        questionarios=_contar(sessao, QuestionarioRecebido.id, (QuestionarioRecebido.oportunidade_id == op.id)
                              | (QuestionarioRecebido.oportunidade_em_aberto_id == op.id)),
        leads=_contar(sessao, Lead.id, Lead.convertido_em_id == op.id),
        vendas_da_reuniao=_contar(sessao, OportunidadeDaReuniao.id, OportunidadeDaReuniao.oportunidade_id == op.id),
        sai_da_conversao=op.situacao is Situacao.PERDIDO,
    )


def excluir(sessao: Session, op: Oportunidade, motivo: str) -> None:
    """Apaga a oportunidade e o que é só dela; desliga o resto. Não faz commit."""
    motivo = " ".join((motivo or "").split())
    if not motivo:
        raise ExclusaoRecusada("Diga o motivo da exclusão.")
    recusa = _recusa(sessao, op)
    if recusa:
        raise ExclusaoRecusada(recusa)
    sessao.execute(sa.update(Lead).where(Lead.convertido_em_id == op.id).values(convertido_em_id=None))
    sessao.execute(sa.update(QuestionarioRecebido).where(QuestionarioRecebido.oportunidade_id == op.id)
                   .values(oportunidade_id=None))
    sessao.execute(sa.update(QuestionarioRecebido).where(QuestionarioRecebido.oportunidade_em_aberto_id == op.id)
                   .values(oportunidade_em_aberto_id=None))
    sessao.execute(sa.update(OportunidadeDaReuniao).where(OportunidadeDaReuniao.oportunidade_id == op.id)
                   .values(oportunidade_id=None))
    for modelo in (PendenciaDaProposta, Proposta, HistoricoDePreco):
        for x in sessao.scalars(sa.select(modelo).where(modelo.oportunidade_id == op.id)):
            sessao.delete(x)
        sessao.flush()
    quem = usuario_atual.get()
    sessao.add(RegistroDeAlteracao(
        usuario_email=quem.email if quem else "sem login", usuario_nome=quem.nome if quem else None,
        acao="excluiu", tabela="oportunidade", registro_id=op.id, descricao=(op.nome or "")[:200] or None,
        campo="motivo", depois=motivo[:1000], rota=quem.rota if quem else None,
    ))
    sessao.delete(op)
    sessao.flush()
