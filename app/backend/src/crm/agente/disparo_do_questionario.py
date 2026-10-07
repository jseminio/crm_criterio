"""O disparo do lembrete e do agradecimento do questionário — pedido de Eduardo em 06/10/2026.

A cada rodada, em horário comercial, o CRM pega a lista de pendentes (`crm.db.questionario_do_lead`)
e envia pelo canal da conversa:

- **WhatsApp:** o modelo aprovado pela Meta (`sdr-ia-modelos-whatsapp.md`), com o nome e o serviço.
- **E-mail:** o mesmo texto, pelo Microsoft 365, com o link escrito no corpo.

Texto fixo, igual ao modelo aprovado: o disparo não chama a IA, não custa token e não improvisa.
Cada mensagem enviada é registrada na conversa e carimbada no lead **logo depois do envio**, uma por
vez: se o envio falha, nada é carimbado e a próxima rodada tenta de novo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

from sqlalchemy.orm import Session

from crm.agente.envio import EnvioFalhou
from crm.db import questionario_do_lead as do_lead
from crm.db.modelos import Lead
from crm.domain.abordagem import normalizar_destino
from crm.domain.listas import CanalDeAbordagem
from crm.domain.questionario_do_lead import MensagemDoQuestionario, em_horario_comercial
from crm.domain.sdr import problema_na_mensagem

__all__ = ["Modelo", "MODELOS", "Canais", "Resultado", "parametros", "texto", "disparar"]

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Modelo:
    nome: str
    """O nome do modelo no WhatsApp Manager."""
    assunto: str
    """Só no e-mail."""
    corpo: str
    com_link: bool


MODELOS: dict[MensagemDoQuestionario, Modelo] = {
    MensagemDoQuestionario.LEMBRETE: Modelo(
        nome="criterio_lembrete_questionario",
        assunto="O questionário para a sua proposta",
        corpo=(
            "Olá, {nome}! Aqui é a assistente virtual da Critério. Para a nossa equipe preparar a "
            "proposta de {servico} que você pediu, ainda falta o questionário de volumetria: é por ele "
            "que a proposta fica do tamanho da sua operação. Se alguma pergunta gerar dúvida, é só "
            "responder esta mensagem que eu ajudo."
        ),
        com_link=True,
    ),
    MensagemDoQuestionario.AGRADECIMENTO: Modelo(
        nome="criterio_agradecimento_questionario",
        assunto="Recebemos o seu questionário",
        corpo=(
            "Olá, {nome}! Aqui é a assistente virtual da Critério. Recebemos as respostas do "
            "questionário de volumetria, obrigada pelo envio. A nossa equipe vai preparar a proposta "
            "de {servico} e alguém do time entra em contato com você para apresentá-la."
        ),
        com_link=False,
    ),
}
"""Os textos aprovados para a Meta. Mudar aqui pede nova aprovação do modelo no WhatsApp Manager."""

RODAPE = "Critério Consultores"
BOTAO = "Responder o questionário"
SERVICO_SEM_INTERESSE = "BPO"


def parametros(lead: Lead) -> dict[str, str]:
    """Os dois parâmetros nomeados dos modelos: o primeiro nome e o serviço de interesse."""
    nome = (lead.nome or "").strip().split()
    return {"nome": nome[0] if nome else "tudo bem", "servico": (lead.interesse or "").strip() or SERVICO_SEM_INTERESSE}


def texto(modelo: Modelo, lead: Lead, link: str) -> str:
    """O texto como o lead lê: é o que fica registrado na conversa e o que vai no e-mail."""
    partes = [modelo.corpo.format(**parametros(lead))]
    if modelo.com_link:
        partes.append(f"{BOTAO}: {link}")
    partes.append(RODAPE)
    return "\n\n".join(partes)


@dataclass(frozen=True)
class Canais:
    """Como enviar. Canal `None` é canal não configurado: a pendência fica para depois, com aviso."""

    whatsapp: Callable[[str, str, dict[str, str]], None] | None = None
    """(número com 55, nome do modelo, parâmetros)"""
    email: Callable[[str, str, str], None] | None = None
    """(e-mail, assunto, corpo)"""


@dataclass
class Resultado:
    enviados: int = 0
    avisos: list[str] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)


def _rotulo(lead: Lead) -> str:
    """Quem, sem telefone nem e-mail: o que aparece no painel e no log."""
    return f"{lead.nome} (lead {lead.id})"


def disparar(sessao: Session, canais: Canais, momento: datetime, link: str) -> Resultado:
    """Uma rodada. Só em horário comercial, para o agradecimento também não chegar de madrugada."""
    resultado = Resultado()
    if not em_horario_comercial(momento):
        resultado.avisos.append("Fora do horário comercial: nada enviado.")
        return resultado

    for pendencia in do_lead.pendentes(sessao, momento):
        lead, conversa, mensagem = pendencia.lead, pendencia.conversa, pendencia.mensagem
        modelo = MODELOS[mensagem]
        corpo = texto(modelo, lead, link)
        problema = problema_na_mensagem(corpo)
        if problema:
            resultado.erros.append(f"{_rotulo(lead)}: {problema}.")
            continue
        try:
            if conversa.canal is CanalDeAbordagem.WHATSAPP:
                numero = normalizar_destino(CanalDeAbordagem.WHATSAPP, lead.telefone)
                if canais.whatsapp is None:
                    resultado.avisos.append(f"{_rotulo(lead)}: WhatsApp não configurado (Configurações › Integrações).")
                    continue
                if len(numero) not in (12, 13):
                    resultado.avisos.append(f"{_rotulo(lead)}: sem celular válido no cadastro.")
                    continue
                canais.whatsapp(numero, modelo.nome, parametros(lead))
            else:
                if canais.email is None:
                    resultado.avisos.append(f"{_rotulo(lead)}: e-mail não configurado (Configurações › Integrações).")
                    continue
                if not (lead.email or "").strip():
                    resultado.avisos.append(f"{_rotulo(lead)}: sem e-mail no cadastro.")
                    continue
                canais.email(lead.email.strip(), modelo.assunto, corpo)
        except EnvioFalhou as falha:
            resultado.erros.append(f"{_rotulo(lead)}: {falha}")
            continue

        do_lead.marcar(sessao, lead, conversa, corpo, mensagem, momento)
        sessao.commit()
        resultado.enviados += 1
        _log.info("questionário: %s enviado ao lead %s", mensagem.value.lower(), lead.id)
    return resultado
