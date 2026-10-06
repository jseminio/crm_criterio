"""O questionário de volumetria na conversa do SDR de IA — pedido de Eduardo em 06/10/2026.

A IA envia o link quando o lead mostra interesse em proposta. Depois, quem diz se o lead respondeu
é o **CRM**, não a memória da conversa: o questionário chega do site pela busca automática
(`QuestionarioRecebido`) e é ligado ao lead pelo CNPJ, pelo e-mail, pelo celular ou pela
oportunidade em que o lead virou.

- Respondeu: a IA agradece, uma vez.
- Não respondeu em 48 horas: a IA lembra, uma vez, de forma educada, profissional e persuasiva.
  Depois do lembrete ela não insiste: o lead segue com a equipe.

Lógica pura, sem banco: a rota lê as datas e pergunta aqui qual é o passo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable

__all__ = [
    "PRAZO_DO_LEMBRETE",
    "PassoDoQuestionario",
    "MensagemDoQuestionario",
    "PASSO_DA_MENSAGEM",
    "Contato",
    "passo_do_questionario",
    "por_que_nao",
    "mesmo_contato",
    "tem_o_link",
]

PRAZO_DO_LEMBRETE = timedelta(hours=48)
"""Do envio do link ao lembrete. Horas corridas (hipótese de 06/10/2026, a rever com o uso)."""


class PassoDoQuestionario(Enum):
    NAO_ENVIADO = "Não enviado"
    AGUARDANDO = "Aguardando resposta"
    LEMBRAR = "Lembrar"
    LEMBRADO = "Lembrete enviado"
    AGRADECER = "Agradecer"
    AGRADECIDO = "Agradecido"
    RESPONDIDO = "Respondido"
    """O lead respondeu sem que a IA tivesse enviado o link: nada a agradecer nem a lembrar."""


class MensagemDoQuestionario(Enum):
    """A mensagem da IA que o CRM pediu sobre o questionário. Marcada pela integração do canal."""

    LEMBRETE = "Lembrete"
    AGRADECIMENTO = "Agradecimento"


PASSO_DA_MENSAGEM: dict[MensagemDoQuestionario, PassoDoQuestionario] = {
    MensagemDoQuestionario.LEMBRETE: PassoDoQuestionario.LEMBRAR,
    MensagemDoQuestionario.AGRADECIMENTO: PassoDoQuestionario.AGRADECER,
}
"""Cada mensagem só sai no seu passo: lembrete a quem já respondeu, ou agradecimento a quem não
respondeu, o servidor recusa."""


def _utc(momento: datetime) -> datetime:
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def passo_do_questionario(
    *,
    enviado_em: datetime | None,
    respondido_em: datetime | None,
    lembrado_em: datetime | None,
    agradecido_em: datetime | None,
    agora: datetime,
) -> PassoDoQuestionario:
    """Em que passo está o questionário de um lead. Responder vence tudo: quem respondeu nunca
    recebe lembrete, nem que as 48 horas tenham passado."""
    if respondido_em is not None:
        if agradecido_em is not None:
            return PassoDoQuestionario.AGRADECIDO
        if enviado_em is None:
            return PassoDoQuestionario.RESPONDIDO
        return PassoDoQuestionario.AGRADECER
    if enviado_em is None:
        return PassoDoQuestionario.NAO_ENVIADO
    if lembrado_em is not None:
        return PassoDoQuestionario.LEMBRADO
    if _utc(agora) - _utc(enviado_em) >= PRAZO_DO_LEMBRETE:
        return PassoDoQuestionario.LEMBRAR
    return PassoDoQuestionario.AGUARDANDO


_MOTIVO: dict[PassoDoQuestionario, str] = {
    PassoDoQuestionario.NAO_ENVIADO: "a IA ainda não enviou o link do questionário a este lead",
    PassoDoQuestionario.AGUARDANDO: "ainda não passaram 48 horas desde o envio do link",
    PassoDoQuestionario.LEMBRAR: "o questionário ainda não foi respondido",
    PassoDoQuestionario.LEMBRADO: "o lembrete do questionário já foi enviado",
    PassoDoQuestionario.AGRADECER: "o lead já respondeu o questionário",
    PassoDoQuestionario.AGRADECIDO: "o agradecimento já foi enviado",
    PassoDoQuestionario.RESPONDIDO: "o lead respondeu sem que a IA tivesse enviado o link",
}


def por_que_nao(passo: PassoDoQuestionario) -> str:
    """Por que a mensagem pedida não cabe neste passo, para a resposta 409 da rota."""
    return _MOTIVO[passo]


# ------------------------------------------------------------ quem é quem
def _digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")


def _celular(valor: str | None) -> str:
    """Só DDD e número: o mesmo celular com ou sem o 55 do país é o mesmo celular."""
    digitos = _digitos(valor)
    if len(digitos) > 11 and digitos.startswith("55"):
        digitos = digitos[2:]
    return digitos if len(digitos) >= 10 else ""


@dataclass(frozen=True)
class Contato:
    """O que identifica um lead ou quem respondeu um questionário."""

    cnpj: str | None = None
    email: str | None = None
    celular: str | None = None
    oportunidade_id: int | None = None


def mesmo_contato(lead: Contato, questionario: Contato) -> bool:
    """O questionário é deste lead? Basta um dos quatro bater; vazio nunca bate com vazio."""
    cnpj = _digitos(lead.cnpj)
    if len(cnpj) == 14 and cnpj == _digitos(questionario.cnpj):
        return True
    email = (lead.email or "").strip().casefold()
    if email and email == (questionario.email or "").strip().casefold():
        return True
    celular = _celular(lead.celular)
    if celular and celular == _celular(questionario.celular):
        return True
    return lead.oportunidade_id is not None and lead.oportunidade_id == questionario.oportunidade_id


def tem_o_link(texto: str, links: Iterable[str]) -> bool:
    """A mensagem leva o link do questionário? Vale o endereço atual e os anteriores: a mudança
    para o domínio da Critério não apaga o envio feito com o link antigo."""
    return any(link and link.rstrip("/") in texto for link in links)
