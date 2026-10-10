"""A saída efetiva chega (10/10/2026): o contrato em aviso de saída passa a Encerrado no dia anunciado.

Até a saída o contrato fica Ativo, faturando e no MRR. Quando a data chega, ninguém precisa voltar ao CRM para
encerrar: `efetivar_saidas` roda ao subir a API, a cada hora (`laco_das_saidas`) e antes das contas de MRR.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload, sessionmaker

from crm.db.modelos import Contrato, EventoDeContrato
from crm.domain.eventos_de_contrato import saida_vigente
from crm.domain.listas import SituacaoContrato, TipoDeEventoDeContrato

__all__ = ["efetivar_saidas", "laco_das_saidas"]

INTERVALO = timedelta(hours=1)
_log = logging.getLogger(__name__)


def efetivar_saidas(sessao: Session, hoje: date) -> int:
    """Passa a Encerrado os contratos ativos (ou suspensos) cuja saída efetiva já chegou. Devolve quantos."""
    candidatos = sessao.scalars(
        sa.select(Contrato)
        .where(Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
        .where(sa.exists().where(EventoDeContrato.contrato_id == Contrato.id,
                                 EventoDeContrato.tipo == TipoDeEventoDeContrato.ENCERRAMENTO))
        .options(selectinload(Contrato.eventos))
    ).all()
    feitos = 0
    for c in candidatos:
        saida = saida_vigente(c)
        if saida is not None and saida <= hoje:
            c.situacao = SituacaoContrato.ENCERRADO
            c.data_fim = saida
            feitos += 1
    if feitos:
        sessao.flush()
    return feitos


def _uma_vez(fabrica: sessionmaker[Session]) -> None:
    with fabrica() as sessao:
        if efetivar_saidas(sessao, date.today()):
            sessao.commit()


async def laco_das_saidas(fabrica: sessionmaker[Session], intervalo: timedelta = INTERVALO) -> None:
    """Roda já e depois a cada `intervalo`, até o CRM desligar, fora do laço de eventos."""
    while True:
        try:
            await asyncio.to_thread(_uma_vez, fabrica)
        except Exception:  # um banco fora do ar não derruba a API; tenta de novo na próxima hora
            _log.exception("não consegui efetivar as saídas de contrato; tento de novo na próxima hora")
        await asyncio.sleep(intervalo.total_seconds())
