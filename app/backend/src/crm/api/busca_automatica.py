"""Busca automática dos questionários do site (aprovado por Eduardo em 02/10/2026): enquanto o CRM
estiver ligado, ele busca sozinho logo ao subir e depois a cada 10 minutos, sem ninguém apertar botão.
O questionário novo vira oportunidade (ou "precisa de você") como na busca do botão. O resultado de
cada busca, inclusive a falha, fica no painel Questionários (`ESTADO_DA_BUSCA`)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy.orm import Session, sessionmaker

from crm.api.questionarios import (
    ESTADO_DA_BUSCA, INTERVALO_DA_BUSCA, BuscaNaoConfigurada, EstadoDaBusca, executar_busca,
)
from crm.db.base import agora
from crm.questionario.endereco import BuscaDeEndereco
from crm.questionario.fonte import BuscaFalhou, FonteDeQuestionarios

__all__ = ["buscar_uma_vez", "laco_da_busca"]

_log = logging.getLogger(__name__)


def buscar_uma_vez(
    fabrica: sessionmaker[Session], fonte: Callable[[], FonteDeQuestionarios | None],
    buscar_endereco: BuscaDeEndereco | None, estado: EstadoDaBusca = ESTADO_DA_BUSCA,
) -> None:
    """Uma busca, sem nunca derrubar o CRM: qualquer falha vai para o painel, com o motivo."""
    with fabrica() as sessao:
        try:
            novos, avisos = executar_busca(sessao, fonte(), buscar_endereco)
        except (BuscaNaoConfigurada, BuscaFalhou) as falha:
            sessao.rollback()
            estado.registrar(manual=False, novos=0, erro=str(falha))
            return
        except Exception as falha:  # noqa: BLE001 — o laço continua; o motivo vai para o painel e o log
            sessao.rollback()
            _log.exception("busca automática de questionários falhou")
            estado.registrar(manual=False, novos=0, erro=f"Falha inesperada na busca ({type(falha).__name__}). Tente \"Buscar agora\".")
            return
        estado.registrar(manual=False, novos=len(novos), erro=None, avisos=avisos)


async def laco_da_busca(
    fabrica: sessionmaker[Session], fonte: Callable[[], FonteDeQuestionarios | None],
    buscar_endereco: BuscaDeEndereco | None, intervalo: timedelta = INTERVALO_DA_BUSCA,
    estado: EstadoDaBusca = ESTADO_DA_BUSCA,
) -> None:
    """Busca já e depois a cada `intervalo`, até o CRM desligar. A busca roda fora do laço de eventos
    (banco e rede são bloqueantes), para a tela não travar enquanto ela acontece."""
    estado.ligar(agora())
    try:
        while True:
            await asyncio.to_thread(buscar_uma_vez, fabrica, fonte, buscar_endereco, estado)
            estado.agendar(agora() + intervalo)
            await asyncio.sleep(intervalo.total_seconds())
    finally:
        estado.desligar()
