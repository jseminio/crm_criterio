"""Conversões devolvidas às plataformas de anúncio — 14/10/2026.

Amostra aprovada por Eduardo em 14/10/2026. O CRM avisa ao Meta Ads e ao Google Ads quando um lead de tráfego
pago é **qualificado**, **marca reunião** ou **fecha contrato** (com o valor em MRR, parcela × 13 ÷ 12). Assim as
plataformas otimizam para lead que vira reunião e contrato, não para formulário preenchido.

Lógica pura, sem banco nem rede. Regras:

- só lead de tráfego pago; **nunca** lead marcado "não contatar";
- e-mail e telefone saem **só criptografados** (SHA-256 do texto normalizado), decisão de Eduardo em 14/10/2026;
- cada lead, evento e plataforma sai **uma vez**: o que já foi aceito ou recusado de vez não sai de novo; o que
  falhou por rede tenta de novo, até `TENTATIVAS` vezes;
- o Meta recusa evento com mais de 7 dias: o CRM nem envia, e registra o porquê;
- o Google só reconhece lead com gclid (o clique no anúncio).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Protocol
from zoneinfo import ZoneInfo

from crm.domain.listas import Situacao, TipoCanal
from crm.domain.mrr import mensalizar

__all__ = ["EVENTOS", "Envio", "MAX_IDADE_NO_META", "TENTATIVAS", "eventos_do_lead", "hash_email", "hash_telefone",
           "pendentes", "telefone_e164"]

FUSO = ZoneInfo("America/Sao_Paulo")
TENTATIVAS = 5
MAX_IDADE_NO_META = timedelta(days=7)
META, GOOGLE = "Meta Ads", "Google Ads"

EVENTOS = {
    "lead_qualificado": "Lead qualificado",
    "reuniao_marcada": "Reunião marcada",
    "contrato_fechado": "Contrato fechado",
}
"""Chave guardada no banco → rótulo da tela."""


class OportunidadeLida(Protocol):
    situacao: Situacao
    data_aceite: object
    preco_mensal: Decimal | None


class LeadLido(Protocol):
    id: int
    tipo_canal: TipoCanal | None
    nao_contatar: bool
    email: str | None
    telefone: str | None
    gclid: str | None
    fbclid: str | None
    criado_em: datetime
    qualificado_em: datetime | None
    reuniao_marcada_para: datetime | None
    convertido_em: OportunidadeLida | None


class JaEnviada(Protocol):
    lead_id: int
    evento: str
    plataforma: str
    situacao: str
    tentativas: int
    momento_do_evento: datetime


@dataclass(frozen=True)
class Envio:
    lead_id: int
    evento: str
    plataforma: str
    momento: datetime
    valor: Decimal | None
    hash_email: str | None
    hash_telefone_meta: str | None
    """SHA-256 dos dígitos com o 55, sem o + (o formato do Meta)."""
    hash_telefone_google: str | None
    """SHA-256 do E.164, com o + (o formato do Google)."""
    gclid: str | None
    fbclid: str | None
    tentativas: int = 0
    """Quantas vezes já falhou por rede: o envio de agora é a tentativa seguinte."""
    recusa_previa: str | None = None
    """Preenchido quando o CRM já sabe que a plataforma vai recusar (ex.: mais de 7 dias no Meta): não envia."""


def _utc(m: datetime) -> datetime:
    return m if m.tzinfo else m.replace(tzinfo=timezone.utc)


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def hash_email(email: str | None) -> str | None:
    """SHA-256 do e-mail em minúsculas, sem espaços (o formato que o Meta e o Google pedem)."""
    limpo = (email or "").strip().lower()
    return _sha(limpo) if "@" in limpo else None


def telefone_e164(telefone: str | None) -> str | None:
    """+55DDNÚMERO. Telefone brasileiro sem o 55 ganha o 55; o que não parece telefone fica de fora."""
    digitos = re.sub(r"\D", "", telefone or "")
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return f"+{digitos}" if 12 <= len(digitos) <= 13 else None


def hash_telefone(telefone: str | None, *, com_mais: bool) -> str | None:
    """SHA-256 do telefone: com o + (E.164, o Google) ou só os dígitos com o 55 (o Meta)."""
    e164 = telefone_e164(telefone)
    if not e164:
        return None
    return _sha(e164 if com_mais else e164[1:])


def eventos_do_lead(lead: LeadLido, agora: datetime) -> list[tuple[str, datetime, Decimal | None]]:
    """Os eventos que o lead já gerou, com o momento e o valor. Reunião sem data de marcação usa o
    momento em que o CRM a viu (`agora`), limitado ao horário da própria reunião."""
    eventos: list[tuple[str, datetime, Decimal | None]] = []
    op = lead.convertido_em
    if lead.qualificado_em is not None:
        eventos.append(("lead_qualificado", _utc(lead.qualificado_em), None))
    elif lead.convertido_em is not None:
        eventos.append(("lead_qualificado", _utc(lead.criado_em), None))
    if lead.reuniao_marcada_para is not None:
        eventos.append(("reuniao_marcada", min(_utc(lead.reuniao_marcada_para), agora), None))
    if op is not None and op.situacao is Situacao.ACEITA:
        dia = op.data_aceite
        momento = datetime.combine(dia, time(12), FUSO).astimezone(timezone.utc) if dia else agora
        eventos.append(("contrato_fechado", min(momento, agora), mensalizar(op.preco_mensal)))
    return eventos


def pendentes(leads: Iterable[LeadLido], ja: Iterable[JaEnviada], plataformas: Iterable[str],
              agora: datetime) -> tuple[list[Envio], dict[tuple[str, str], int]]:
    """O que falta enviar, e quantos eventos ficaram sem como ser reconhecidos (por evento e plataforma).

    Para cada evento já registrado, vale o momento gravado na primeira vez: a nova tentativa não muda o horário.
    """
    feitos = {(j.lead_id, j.evento, j.plataforma): j for j in ja}
    plataformas = list(plataformas)
    envios: list[Envio] = []
    sem_identificador: dict[tuple[str, str], int] = {}
    for lead in leads:
        if lead.tipo_canal is not TipoCanal.TRAFEGO_PAGO or lead.nao_contatar:
            continue
        email = hash_email(lead.email)
        tel_meta = hash_telefone(lead.telefone, com_mais=False)
        tel_google = hash_telefone(lead.telefone, com_mais=True)
        for evento, momento, valor in eventos_do_lead(lead, agora):
            for plataforma in plataformas:
                antes = feitos.get((lead.id, evento, plataforma))
                if antes is not None and (antes.situacao != "falhou" or antes.tentativas >= TENTATIVAS):
                    continue
                reconhece = bool(lead.gclid) if plataforma == GOOGLE else bool(email or tel_meta or lead.fbclid)
                if not reconhece:
                    sem_identificador[(evento, plataforma)] = sem_identificador.get((evento, plataforma), 0) + 1
                    continue
                quando = _utc(antes.momento_do_evento) if antes is not None else momento
                recusa = None
                if plataforma == META and agora - quando > MAX_IDADE_NO_META:
                    recusa = "O evento tem mais de 7 dias: o Meta não aceita."
                envios.append(Envio(lead.id, evento, plataforma, quando, valor, email, tel_meta, tel_google,
                                    lead.gclid, lead.fbclid, antes.tentativas if antes else 0, recusa))
    return envios, sem_identificador
