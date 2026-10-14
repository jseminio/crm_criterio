"""Mensagens do WhatsApp que chegam ao CRM — fase 0 do SDR de IA (amostra aprovada em 14/10/2026).

A Meta entrega cada mensagem do lead no webhook do CRM (`crm.api.whatsapp_recebido`). Este módulo
só confere e grava; **ninguém responde sozinho nesta fase**. Regras:

- a entrega só vale com a assinatura `X-Hub-Signature-256` feita com a chave secreta do aplicativo
  (HMAC-SHA256 do corpo bruto, comparado em tempo constante). Sem ela, nada é gravado;
- só o número configurado em Integrações: entrega de outro número é ignorada;
- a Meta repete entregas; o ID da mensagem (`externo_id`) faz cada uma gravar uma vez;
- número que não está em nenhum lead vira **lead novo**, canal "WhatsApp" (decisão de Eduardo);
- a mensagem que é só "SAIR", "PARAR" e parecidas marca o lead como **não contatar** (decisão de
  Eduardo), e fica registrada na conversa para a equipe ver;
- foto, áudio, documento: registra o tipo ("[áudio]"), sem baixar o arquivo;
- a situação de entrega (enviada, entregue, lida, falhou) atualiza a mensagem da Critério que tem o
  mesmo ID. Nunca volta atrás: lida não vira entregue;
- nada de conteúdo, telefone ou nome no log: só contagens.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import ConversaDoSdr, Lead, MensagemDoSdr
from crm.domain.listas import AutorDaMensagem, CanalDeAbordagem

__all__ = ["LIMITE_DO_TEXTO", "Resumo", "assinatura_valida", "chave_do_telefone", "eh_pedido_de_saida", "processar"]

_log = logging.getLogger(__name__)

LIMITE_DO_TEXTO = 4096
"""O WhatsApp aceita até 4.096 caracteres por mensagem de texto."""

CANAL_DO_LEAD_NOVO = "WhatsApp"

_SAIDA = re.compile(r"^\s*(sair|parar|pare|stop|cancelar|descadastrar|n[ãa]o quero mais receber)\s*[.!]*\s*$", re.IGNORECASE)

_TIPOS = {
    "image": "[foto]", "audio": "[áudio]", "video": "[vídeo]", "document": "[documento]",
    "sticker": "[figurinha]", "location": "[localização]", "contacts": "[contato]", "reaction": "[reação]",
}

_ENTREGA = {"sent": "enviada", "delivered": "entregue", "read": "lida", "failed": "falhou"}
_ORDEM = {"enviada": 1, "entregue": 2, "lida": 3}


def assinatura_valida(corpo: bytes, cabecalho: str | None, segredo: str) -> bool:
    """`X-Hub-Signature-256: sha256=<hex>` = HMAC-SHA256(chave secreta do app, corpo bruto)."""
    if not segredo or not cabecalho or not cabecalho.startswith("sha256="):
        return False
    esperado = hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, cabecalho[len("sha256="):].strip().lower())


def chave_do_telefone(telefone: str | None) -> str:
    """Forma comparável do telefone. O WhatsApp entrega celular brasileiro às vezes sem o nono dígito
    (5511 8765 4321); a chave tira esse 9 dos dois lados para os dois jeitos casarem."""
    digitos = "".join(c for c in telefone or "" if c.isdigit())
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    if digitos.startswith("55") and len(digitos) == 13 and digitos[4] == "9":
        digitos = digitos[:4] + digitos[5:]
    return digitos


def eh_pedido_de_saida(texto: str) -> bool:
    """Só a mensagem que é o pedido inteiro: "SAIR", "parar.", "Não quero mais receber".
    "Quero sair do Simples" não é pedido de saída."""
    return bool(_SAIDA.match(texto or ""))


@dataclass
class Resumo:
    recebidas: int = 0
    repetidas: int = 0
    entregas: int = 0
    outro_numero: int = 0
    leads_novos: int = 0
    saidas: int = 0


def _texto(m: dict[str, Any]) -> str:
    tipo = m.get("type")
    if tipo == "text":
        texto = (m.get("text") or {}).get("body") or ""
    elif tipo == "button":
        texto = (m.get("button") or {}).get("text") or "[botão]"
    elif tipo == "interactive":
        i = m.get("interactive") or {}
        texto = (i.get("button_reply") or i.get("list_reply") or {}).get("title") or "[resposta de botão]"
    elif tipo in _TIPOS:
        legenda = (m.get(tipo) or {}).get("caption") if isinstance(m.get(tipo), dict) else None
        texto = f"{_TIPOS[tipo]} {legenda}".strip() if legenda else _TIPOS[tipo]
    else:
        texto = "[mensagem que o CRM ainda não lê]"
    return texto.strip()[:LIMITE_DO_TEXTO] or "[mensagem vazia]"


def _quando(m: dict[str, Any], padrao: datetime) -> datetime:
    try:
        return datetime.fromtimestamp(int(m["timestamp"]), tz=timezone.utc)
    except (KeyError, TypeError, ValueError, OverflowError):
        return padrao


def _lead_do_numero(sessao: Session, wa_id: str, nome: str | None, momento: datetime, resumo: Resumo) -> Lead:
    chave = chave_do_telefone(wa_id)
    candidatos = [l for l in sessao.scalars(sa.select(Lead).where(Lead.telefone.is_not(None)))
                  if chave and chave_do_telefone(l.telefone) == chave]
    if candidatos:
        # Mais de um lead com o mesmo número: o mais recente.
        return max(candidatos, key=lambda l: (l.criado_em or momento, l.id))
    lead = Lead(nome=(nome or "").strip()[:200] or f"WhatsApp +{wa_id}", telefone=f"+{wa_id}"[:30],
                canal=CANAL_DO_LEAD_NOVO)
    sessao.add(lead)
    sessao.flush()
    resumo.leads_novos += 1
    return lead


def _conversa_aberta(sessao: Session, lead: Lead, momento: datetime) -> ConversaDoSdr:
    conversa = sessao.scalar(
        sa.select(ConversaDoSdr)
        .where(ConversaDoSdr.lead_id == lead.id, ConversaDoSdr.canal == CanalDeAbordagem.WHATSAPP,
               ConversaDoSdr.encerrada_em.is_(None))
        .order_by(ConversaDoSdr.iniciada_em.desc(), ConversaDoSdr.id.desc())
        .limit(1)
    )
    if conversa is None:
        conversa = ConversaDoSdr(lead_id=lead.id, canal=CanalDeAbordagem.WHATSAPP, iniciada_em=momento)
        sessao.add(conversa)
        sessao.flush()
    return conversa


def _depois(a: datetime | None, b: datetime) -> datetime:
    if a is None:
        return b
    a = a if a.tzinfo else a.replace(tzinfo=timezone.utc)
    return max(a, b)


def processar(sessao: Session, payload: dict[str, Any], numero_id: str, momento: datetime) -> Resumo:
    """Grava o que a entrega traz para o número `numero_id`. Não faz commit."""
    resumo = Resumo()
    for entrada in payload.get("entry") or []:
        for mudanca in (entrada or {}).get("changes") or []:
            if (mudanca or {}).get("field") != "messages":
                continue
            valor = mudanca.get("value") or {}
            if str((valor.get("metadata") or {}).get("phone_number_id") or "") != numero_id:
                resumo.outro_numero += 1
                continue
            nomes = {str(c.get("wa_id")): ((c.get("profile") or {}).get("name"))
                     for c in valor.get("contacts") or [] if c.get("wa_id")}
            for m in valor.get("messages") or []:
                _gravar_mensagem(sessao, m, nomes, momento, resumo)
            for s in valor.get("statuses") or []:
                _atualizar_entrega(sessao, s, resumo)
    sessao.flush()
    _log.info("WhatsApp: %d recebidas, %d repetidas, %d entregas, %d leads novos, %d pedidos de saída, %d de outro número",
              resumo.recebidas, resumo.repetidas, resumo.entregas, resumo.leads_novos, resumo.saidas, resumo.outro_numero)
    return resumo


def _gravar_mensagem(sessao: Session, m: dict[str, Any], nomes: dict[str, str | None], momento: datetime,
                     resumo: Resumo) -> None:
    externo, de = str(m.get("id") or ""), str(m.get("from") or "")
    if not externo or not de.isdigit():
        return
    if sessao.scalar(sa.select(MensagemDoSdr.id).where(MensagemDoSdr.externo_id == externo)) is not None:
        resumo.repetidas += 1
        return
    quando = _quando(m, momento)
    texto = _texto(m)
    lead = _lead_do_numero(sessao, de, nomes.get(de), momento, resumo)
    conversa = _conversa_aberta(sessao, lead, quando)
    sessao.add(MensagemDoSdr(conversa_id=conversa.id, autor=AutorDaMensagem.LEAD, enviada_em=quando,
                             texto=texto, externo_id=externo[:128]))
    conversa.ultima_do_lead_em = _depois(conversa.ultima_do_lead_em, quando)
    resumo.recebidas += 1
    if m.get("type") == "text" and eh_pedido_de_saida(texto) and not lead.nao_contatar:
        lead.nao_contatar, lead.nao_contatar_em = True, quando
        resumo.saidas += 1
    sessao.flush()


def _atualizar_entrega(sessao: Session, s: dict[str, Any], resumo: Resumo) -> None:
    nova = _ENTREGA.get(str(s.get("status") or ""))
    externo = str(s.get("id") or "")
    if not nova or not externo:
        return
    mensagem = sessao.scalar(sa.select(MensagemDoSdr).where(MensagemDoSdr.externo_id == externo))
    if mensagem is None or mensagem.autor is AutorDaMensagem.LEAD:
        return
    if nova != "falhou" and _ORDEM.get(nova, 0) <= _ORDEM.get(mensagem.entrega or "", 0):
        return  # a Meta pode entregar fora de ordem: lida não volta a entregue
    mensagem.entrega = nova
    resumo.entregas += 1
