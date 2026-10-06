"""O questionário de cada lead, lido do banco — usado pela rota do SDR e pelo disparo (06/10/2026).

As regras puras estão em `crm.domain.questionario_do_lead`; aqui só se junta o lead com os
questionários recebidos do site e se registra a mensagem que a IA mandou.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from crm.agente.config import LINK_DO_QUESTIONARIO_PADRAO, ler_configuracao
from crm.db.modelos import ConversaDoSdr, Lead, MensagemDoSdr, QuestionarioRecebido
from crm.domain import questionario_do_lead as questionario
from crm.domain.listas import AutorDaMensagem

__all__ = [
    "Situacao",
    "Pendencia",
    "links_do_questionario",
    "recebidos",
    "situacao",
    "pendentes",
    "marcar",
]


def links_do_questionario() -> tuple[str, ...]:
    """O link configurado e o padrão: quem recebeu o link antigo também recebeu o questionário."""
    return (ler_configuracao().link_do_questionario, LINK_DO_QUESTIONARIO_PADRAO)


def recebidos(sessao: Session) -> list[QuestionarioRecebido]:
    return list(sessao.scalars(sa.select(QuestionarioRecebido)).all())


def _respondido_em(lead: Lead, lista: list[QuestionarioRecebido]) -> datetime | None:
    do_lead = questionario.Contato(lead.cnpj, lead.email, lead.telefone, lead.convertido_em_id)
    datas = [
        q.recebido_em
        for q in lista
        if questionario.mesmo_contato(
            do_lead, questionario.Contato(q.cnpj, q.contato_email, q.contato_celular, q.oportunidade_id)
        )
    ]
    return min(datas) if datas else None


@dataclass(frozen=True)
class Situacao:
    passo: questionario.PassoDoQuestionario
    respondido_em: datetime | None
    lembrar_a_partir_de: datetime | None


def situacao(lead: Lead, lista: list[QuestionarioRecebido], momento: datetime) -> Situacao:
    respondido_em = _respondido_em(lead, lista)
    enviado = lead.questionario_enviado_em
    passo = questionario.passo_do_questionario(
        enviado_em=enviado,
        respondido_em=respondido_em,
        lembrado_em=lead.questionario_lembrado_em,
        agradecido_em=lead.questionario_agradecido_em,
        agora=momento,
    )
    return Situacao(passo, respondido_em, questionario.lembrar_a_partir_de(enviado) if enviado else None)


@dataclass(frozen=True)
class Pendencia:
    lead: Lead
    conversa: ConversaDoSdr
    """A conversa mais recente do lead: é nela que a mensagem fica registrada."""
    mensagem: questionario.MensagemDoQuestionario
    situacao: Situacao


def pendentes(sessao: Session, momento: datetime) -> list[Pendencia]:
    """A quem a IA deve lembrar ou agradecer agora. Fica fora quem pediu para não ser contatado."""
    leads = sessao.scalars(
        sa.select(Lead)
        .where(
            Lead.questionario_enviado_em.is_not(None),
            Lead.questionario_agradecido_em.is_(None),
            Lead.nao_contatar.is_(False),
        )
        .options(selectinload(Lead.conversas))
        .order_by(Lead.questionario_enviado_em)
    ).all()
    lista = recebidos(sessao) if leads else []
    mensagem_do_passo = {passo: msg for msg, passo in questionario.PASSO_DA_MENSAGEM.items()}
    resultado = []
    for lead in leads:
        atual = situacao(lead, lista, momento)
        if atual.passo in mensagem_do_passo and lead.conversas:
            resultado.append(Pendencia(lead, lead.conversas[-1], mensagem_do_passo[atual.passo], atual))
    return resultado


def marcar(
    sessao: Session,
    lead: Lead,
    conversa: ConversaDoSdr,
    texto: str,
    mensagem: questionario.MensagemDoQuestionario,
    momento: datetime,
) -> MensagemDoSdr:
    """Registra o lembrete ou o agradecimento já enviado e carimba o lead: não sai de novo."""
    registro = MensagemDoSdr(
        conversa_id=conversa.id, autor=AutorDaMensagem.IA, enviada_em=momento, texto=texto
    )
    sessao.add(registro)
    if mensagem is questionario.MensagemDoQuestionario.LEMBRETE:
        lead.questionario_lembrado_em = momento
    else:
        lead.questionario_agradecido_em = momento
    return registro
