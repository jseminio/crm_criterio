"""Smarthis e CS Brasil voltam para "Aguardando assinatura" (decisão de Eduardo em 29/10/2026).

Os dois contratos entraram como Ativos, mas a assinatura na Clicksign não foi concluída: a Smarthis ainda espera a
assinatura do cliente e a CS Brasil, a da testemunha. A tela não deixa um contrato assinado voltar (destravaria o preço
sem evento), por isso a correção vem por aqui, uma vez só.

Só muda o contrato que ainda está Ativo e sem nenhum evento: se alguém já mexeu, fica como está. A data de assinatura
que estava gravada fica; quando a assinatura sair, ela é trocada pela real. Rodar de novo não muda nada."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Contrato, Empresa, EventoDeContrato
from crm.domain.listas import SituacaoContrato

CNPJS = ("29862205000168", "45216559000191")  # Smarthis Consultoria; CS Brasil


def executar(sessao: Session) -> str:
    com_evento = sa.select(EventoDeContrato.contrato_id)
    contratos = sessao.scalars(
        sa.select(Contrato).join(Empresa, Empresa.id == Contrato.empresa_id)
        .where(Empresa.cnpj.in_(CNPJS), Contrato.situacao == SituacaoContrato.ATIVO, Contrato.id.not_in(com_evento))
    ).all()
    for c in contratos:
        c.situacao = SituacaoContrato.AGUARDANDO_ASSINATURA
    sessao.flush()
    if not contratos:
        return "nada a mudar: nenhum contrato Ativo e sem evento da Smarthis ou da CS Brasil"
    return f"{len(contratos)} contrato(s) da Smarthis/CS Brasil voltaram para Aguardando assinatura"
