"""O webhook do WhatsApp: o único endereço do CRM aberto sem login (amostra aprovada em 14/10/2026).

A Meta precisa alcançá-lo de fora, então a segurança está nas travas, não no login:

- **desligado por padrão** (`whatsapp.recebimento`): desligado, responde 404 e não grava nada;
- **GET** (a Meta confirmando o endereço): devolve o desafio só se o token de verificação bater,
  comparado em tempo constante, e só se o desafio for número (nada de refletir texto de fora);
- **POST** (as entregas): sem a chave secreta do aplicativo salva, recusa tudo; com ela, exige a
  assinatura `X-Hub-Signature-256` do corpo bruto. Corpo acima de `LIMITE_DO_CORPO` é recusado antes
  de ser lido inteiro. Só depois disso o JSON é aberto;
- a resposta nunca leva dado: só confirma o recebimento;
- a última recusa (sem conteúdo) fica em memória para a tela de Integrações explicar o que houve.

A configuração toda vem da tela Configurações › Integrações › WhatsApp (`crm.configuracao`).
"""

from __future__ import annotations

import hmac
import json
import logging
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from crm import configuracao
from crm.agente.recebimento import assinatura_valida, processar
from crm.db.base import agora
from crm.db.modelos import ConversaDoSdr, MensagemDoSdr
from crm.domain.listas import AutorDaMensagem, CanalDeAbordagem

__all__ = ["CAMINHO", "LIMITE_DO_CORPO", "roteador_do_whatsapp_recebido", "situacao_do_recebimento", "ultima_recusa"]

CAMINHO = "/api/whatsapp/webhook"
LIMITE_DO_CORPO = 1_000_000
"""1 MB. Uma entrega da Meta com mensagens de texto tem poucos KB."""

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Recusa:
    em: datetime
    motivo: str


_trava = threading.Lock()
_ultima_recusa: Recusa | None = None


def _recusar(motivo: str, status: int) -> Response:
    global _ultima_recusa
    with _trava:
        _ultima_recusa = Recusa(agora(), motivo)
    _log.warning("WhatsApp: entrega recusada (%s)", motivo)
    return Response(status_code=status)


def ultima_recusa() -> Recusa | None:
    with _trava:
        return _ultima_recusa


def _brasilia(momento: datetime) -> str:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y às %H:%M")


def _ligado() -> bool:
    return configuracao.valor("whatsapp.recebimento") == "true"


def situacao_do_recebimento(sessao: Session) -> str:
    """A frase da tela de Integrações sobre o recebimento. Estado nunca só por cor: vai em texto."""
    if not _ligado():
        return "Recebimento desligado: o CRM recusa o que a Meta entregar."
    if not configuracao.valor("whatsapp.app_secret"):
        return "⚠ Recebimento ligado, mas falta a chave secreta do aplicativo: o CRM recusa tudo até ela ser salva."
    ultima = sessao.scalar(
        sa.select(sa.func.max(MensagemDoSdr.enviada_em))
        .join(ConversaDoSdr, MensagemDoSdr.conversa_id == ConversaDoSdr.id)
        .where(MensagemDoSdr.autor == AutorDaMensagem.LEAD, MensagemDoSdr.externo_id.is_not(None),
               ConversaDoSdr.canal == CanalDeAbordagem.WHATSAPP)
    )
    partes = [f"✓ Última mensagem recebida em {_brasilia(ultima)}." if ultima else "⚠ Nenhuma mensagem recebida ainda."]
    recusa = ultima_recusa()
    if recusa is not None:
        partes.append(f"Última entrega recusada em {_brasilia(recusa.em)}: {recusa.motivo}.")
    return " ".join(partes)


def roteador_do_whatsapp_recebido(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["whatsapp"])

    @r.get(CAMINHO)
    def verificar(request: Request) -> Response:
        if not _ligado():
            return _recusar("recebimento desligado", 404)
        p = request.query_params
        token = configuracao.valor("whatsapp.token_verificacao")
        dado, desafio = p.get("hub.verify_token") or "", p.get("hub.challenge") or ""
        if p.get("hub.mode") != "subscribe" or not token or not hmac.compare_digest(dado.encode(), token.encode()):
            return _recusar("token de verificação diferente do salvo", 403)
        if not desafio.isdigit() or len(desafio) > 64:
            return _recusar("desafio fora do formato da Meta", 400)
        return Response(desafio, media_type="text/plain")

    @r.post(CAMINHO)
    async def receber(request: Request, sessao: Session = Depends(obter_sessao, scope="function")) -> Response:
        if not _ligado():
            return _recusar("recebimento desligado", 404)
        segredo = configuracao.valor("whatsapp.app_secret")
        if not segredo:
            return _recusar("falta a chave secreta do aplicativo", 403)
        tamanho = request.headers.get("content-length")
        if tamanho is not None and (not tamanho.isdigit() or int(tamanho) > LIMITE_DO_CORPO):
            return _recusar("entrega grande demais", 413)
        corpo = b""
        async for parte in request.stream():
            corpo += parte
            if len(corpo) > LIMITE_DO_CORPO:
                return _recusar("entrega grande demais", 413)
        if not assinatura_valida(corpo, request.headers.get("x-hub-signature-256"), segredo):
            return _recusar("assinatura ausente ou inválida", 401)
        try:
            payload = json.loads(corpo)
        except ValueError:
            return _recusar("corpo que não é JSON", 400)
        if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
            return _recusar("entrega que não é do WhatsApp", 400)
        numero = configuracao.valor("whatsapp.numero_id")
        try:
            await run_in_threadpool(processar, sessao, payload, numero, agora())
        except Exception as falha:  # noqa: BLE001 — o erro do banco traz os valores: no log, só o tipo
            sessao.rollback()
            _log.error("WhatsApp: falha ao gravar a entrega (%s); a Meta vai reenviar", type(falha).__name__)
            return Response(status_code=500)
        return Response(status_code=200)

    return r
