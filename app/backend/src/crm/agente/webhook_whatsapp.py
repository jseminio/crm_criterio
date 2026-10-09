"""O webhook da Meta: o CRM recebe as respostas do lead no WhatsApp (09/10/2026).

Decisão de Eduardo em 09/10/2026: o webhook mora no servidor, que passa a ser o oficial para as
conversas do WhatsApp (a Meta só entrega num endereço público com HTTPS).

Regras:

- **Assinatura antes de tudo.** A Meta assina cada aviso com a chave secreta do app
  (`X-Hub-Signature-256`, HMAC-SHA256 do corpo cru). Sem chave cadastrada ou com assinatura errada,
  nada é lido nem gravado.
- **Todo aviso fica registrado** em `EventoDoWhatsapp`, uma vez só (a Meta reenvia).
- **Mensagem de lead conhecido entra na conversa do SDR**, com autor "Lead": a conversa aberta, se
  houver; senão, uma nova pelo WhatsApp. Lead que já virou oportunidade não ganha conversa do SDR.
- **Número desconhecido não vira lead sozinho**: fica como evento "sem lead".
- **A IA não responde.** Este módulo só registra; ligar a resposta é outra demanda, depois dos ensaios.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import ConversaDoSdr, EventoDoWhatsapp, Lead, MensagemDoSdr
from crm.domain.abordagem import normalizar_destino
from crm.domain.listas import AutorDaMensagem, CanalDeAbordagem, SituacaoLead

__all__ = ["Resumo", "assinatura_confere", "desafio_da_verificacao", "processar", "variantes_do_numero"]

NA_CONVERSA = "na conversa"
SEM_LEAD = "sem lead"
JA_E_OPORTUNIDADE = "lead já é oportunidade"
SO_AVISO = "só aviso"

_SEM_TEXTO = {
    "image": "[imagem recebida]",
    "audio": "[áudio recebido]",
    "video": "[vídeo recebido]",
    "document": "[documento recebido]",
    "sticker": "[figurinha recebida]",
    "location": "[localização recebida]",
    "contacts": "[contato recebido]",
}


def assinatura_confere(corpo: bytes, cabecalho: str | None, chave_do_app: str | None) -> bool:
    """Confere o `X-Hub-Signature-256` (`sha256=<hex>`) com a chave secreta do app."""
    if not chave_do_app or not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperada = hmac.new(chave_do_app.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, cabecalho[len("sha256="):].strip().lower())


def desafio_da_verificacao(modo: str | None, token: str | None, desafio: str | None, esperado: str | None) -> str | None:
    """O teste que a Meta faz ao cadastrar o endereço. Devolve o desafio, ou `None` se não confere."""
    if not esperado or modo != "subscribe" or not token or desafio is None:
        return None
    return desafio if hmac.compare_digest(token.encode(), esperado.encode()) else None


def variantes_do_numero(numero: str | None) -> set[str]:
    """O mesmo celular brasileiro com e sem o nono dígito: a Meta às vezes manda o `wa_id` sem ele."""
    digitos = normalizar_destino(CanalDeAbordagem.WHATSAPP, numero)
    if not digitos:
        return set()
    variantes = {digitos}
    if digitos.startswith("55") and len(digitos) == 13 and digitos[4] == "9":
        variantes.add(digitos[:4] + digitos[5:])
    elif digitos.startswith("55") and len(digitos) == 12 and digitos[4] in "6789":
        variantes.add(digitos[:4] + "9" + digitos[4:])
    return variantes


@dataclass
class Resumo:
    """O que um aviso trouxe. Vai para o log, nunca com o texto da mensagem."""

    novos: int = 0
    repetidos: int = 0
    na_conversa: int = 0
    sem_lead: int = 0
    situacoes: list[str] = field(default_factory=list)


def _texto(mensagem: dict[str, Any]) -> str | None:
    """O texto que entra na conversa; `None` para o que não é mensagem do lead (reação, por exemplo)."""
    tipo = mensagem.get("type")
    if tipo == "text":
        return (mensagem.get("text") or {}).get("body") or ""
    if tipo == "button":
        return (mensagem.get("button") or {}).get("text") or ""
    if tipo == "interactive":
        interativo = mensagem.get("interactive") or {}
        resposta = interativo.get("button_reply") or interativo.get("list_reply") or {}
        return resposta.get("title") or "[resposta de botão]"
    if tipo in _SEM_TEXTO:
        legenda = (mensagem.get(tipo) or {}).get("caption")
        return f"{_SEM_TEXTO[tipo]} {legenda}".strip() if legenda else _SEM_TEXTO[tipo]
    if tipo == "reaction":
        return None
    return "[mensagem que o CRM não lê]"


def _momento(mensagem: dict[str, Any], padrao: datetime) -> datetime:
    try:
        return datetime.fromtimestamp(int(mensagem["timestamp"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError):
        return padrao


class _Leads:
    """Os leads com telefone, indexados pelas variantes do número. Lido uma vez por aviso."""

    def __init__(self, sessao: Session) -> None:
        self._por_numero: dict[str, list[Lead]] = {}
        for lead in sessao.scalars(sa.select(Lead).where(Lead.telefone.is_not(None)).order_by(Lead.id)):
            for numero in variantes_do_numero(lead.telefone):
                self._por_numero.setdefault(numero, []).append(lead)

    def de(self, sessao: Session, numero: str) -> Lead | None:
        """O lead do número. Mais de um: o que tem conversa aberta; senão, o mais recente."""
        achados = {l.id: l for n in variantes_do_numero(numero) for l in self._por_numero.get(n, [])}
        if not achados:
            return None
        com_conversa = sessao.scalars(
            sa.select(ConversaDoSdr.lead_id).where(
                ConversaDoSdr.lead_id.in_(achados), ConversaDoSdr.desfecho.is_(None)
            )
        ).all()
        if com_conversa:
            return achados[max(com_conversa)]
        return achados[max(achados)]


def _ja_existe(sessao: Session, externo_id: str) -> bool:
    return sessao.scalar(sa.select(EventoDoWhatsapp.id).where(EventoDoWhatsapp.externo_id == externo_id)) is not None


def _conversa_aberta(sessao: Session, lead: Lead, momento: datetime) -> ConversaDoSdr:
    aberta = sessao.scalar(
        sa.select(ConversaDoSdr).where(ConversaDoSdr.lead_id == lead.id, ConversaDoSdr.desfecho.is_(None))
    )
    if aberta is not None:
        return aberta
    nova = ConversaDoSdr(lead_id=lead.id, canal=CanalDeAbordagem.WHATSAPP, iniciada_em=momento)
    sessao.add(nova)
    sessao.flush()
    return nova


def _mensagem(sessao: Session, leads: _Leads, mensagem: dict[str, Any], agora: datetime, resumo: Resumo) -> None:
    externo_id = str(mensagem.get("id") or "")
    numero = normalizar_destino(CanalDeAbordagem.WHATSAPP, str(mensagem.get("from") or ""))
    if not externo_id or not numero:
        return
    if _ja_existe(sessao, externo_id):
        resumo.repetidos += 1
        return
    lead = leads.de(sessao, numero)
    texto = _texto(mensagem)
    evento = EventoDoWhatsapp(
        externo_id=externo_id[:200], recebido_em=agora, tipo="mensagem", telefone=numero[:20],
        lead_id=lead.id if lead else None, conteudo=mensagem,
    )
    if lead is None:
        evento.situacao = SEM_LEAD
        resumo.sem_lead += 1
    elif lead.convertido_em_id is not None:
        evento.situacao = JA_E_OPORTUNIDADE
    elif texto is None:
        evento.situacao = SO_AVISO
    else:
        momento = _momento(mensagem, agora)
        conversa = _conversa_aberta(sessao, lead, momento)
        registrada = MensagemDoSdr(conversa_id=conversa.id, autor=AutorDaMensagem.LEAD, enviada_em=momento, texto=texto)
        sessao.add(registrada)
        sessao.flush()
        evento.mensagem_id = registrada.id
        evento.situacao = NA_CONVERSA
        if lead.situacao is SituacaoLead.NOVO:
            lead.situacao = SituacaoLead.EM_CONTATO
        resumo.na_conversa += 1
    sessao.add(evento)
    sessao.flush()
    resumo.novos += 1
    resumo.situacoes.append(evento.situacao)


def _status(sessao: Session, leads: _Leads, status: dict[str, Any], agora: datetime, resumo: Resumo) -> None:
    id_da_mensagem, qual = str(status.get("id") or ""), str(status.get("status") or "")
    numero = normalizar_destino(CanalDeAbordagem.WHATSAPP, str(status.get("recipient_id") or ""))
    if not id_da_mensagem or not qual:
        return
    externo_id = f"{id_da_mensagem}:{qual}"[:200]
    if _ja_existe(sessao, externo_id):
        resumo.repetidos += 1
        return
    lead = leads.de(sessao, numero) if numero else None
    sessao.add(EventoDoWhatsapp(
        externo_id=externo_id, recebido_em=agora, tipo="status", telefone=numero[:20], situacao=qual[:40],
        lead_id=lead.id if lead else None, conteudo=status,
    ))
    sessao.flush()
    resumo.novos += 1
    resumo.situacoes.append(qual)


def processar(sessao: Session, aviso: dict[str, Any], agora: datetime) -> Resumo:
    """Grava o que o aviso trouxe (sem commit). Aviso que não é do WhatsApp é ignorado."""
    resumo = Resumo()
    if not isinstance(aviso, dict) or aviso.get("object") != "whatsapp_business_account":
        return resumo
    leads: _Leads | None = None
    for entrada in aviso.get("entry") or []:
        for mudanca in (entrada or {}).get("changes") or []:
            if (mudanca or {}).get("field") != "messages":
                continue
            valor = mudanca.get("value") or {}
            if leads is None:
                leads = _Leads(sessao)
            for mensagem in valor.get("messages") or []:
                if isinstance(mensagem, dict):
                    _mensagem(sessao, leads, mensagem, agora, resumo)
            for status in valor.get("statuses") or []:
                if isinstance(status, dict):
                    _status(sessao, leads, status, agora, resumo)
    return resumo
