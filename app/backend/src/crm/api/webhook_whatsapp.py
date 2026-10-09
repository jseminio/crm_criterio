"""Rota pública do webhook do WhatsApp (09/10/2026): `GET|POST /api/whatsapp/webhook`.

Fica fora do login (`crm.acesso.catalogo.PUBLICAS`) porque quem chama é a Meta, não uma pessoa. A
proteção é outra: o GET só devolve o desafio a quem sabe o token de verificação, e o POST só é lido
com a assinatura da chave secreta do app (`crm.agente.webhook_whatsapp`). Os dois se cadastram na
tela Configurações › Integrações › WhatsApp.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from crm import configuracao
from crm.agente.webhook_whatsapp import assinatura_confere, desafio_da_verificacao, processar
from crm.db.base import agora

__all__ = ["CAMINHO", "roteador_do_webhook_do_whatsapp"]

CAMINHO = "/api/whatsapp/webhook"
_log = logging.getLogger(__name__)


def roteador_do_webhook_do_whatsapp(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["whatsapp"])

    @r.get(CAMINHO, response_class=PlainTextResponse, include_in_schema=False)
    def verificar(request: Request) -> str:
        """A Meta confere o endereço uma vez, ao cadastrá-lo, com o token de verificação."""
        p = request.query_params
        desafio = desafio_da_verificacao(
            p.get("hub.mode"), p.get("hub.verify_token"), p.get("hub.challenge"),
            configuracao.valor("whatsapp.verificacao") or None,
        )
        if desafio is None:
            raise HTTPException(403, "token de verificação não confere")
        return desafio

    @r.post(CAMINHO, include_in_schema=False)
    async def receber(request: Request, sessao: Session = Depends(obter_sessao, scope="function")) -> dict[str, int]:
        corpo = await request.body()
        if not assinatura_confere(corpo, request.headers.get("x-hub-signature-256"),
                                  configuracao.valor("whatsapp.chave_do_app") or None):
            raise HTTPException(403, "assinatura não confere")
        try:
            aviso = json.loads(corpo)
        except ValueError:
            raise HTTPException(400, "aviso não é JSON") from None
        resumo = processar(sessao, aviso, agora())
        _log.info("webhook do WhatsApp: %s novo(s), %s repetido(s), %s na conversa, %s sem lead",
                  resumo.novos, resumo.repetidos, resumo.na_conversa, resumo.sem_lead)
        return {"novos": resumo.novos, "repetidos": resumo.repetidos}

    return r
