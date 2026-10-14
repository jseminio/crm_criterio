"""Leads dos formulários do Meta e do Google entrando sozinhos no CRM — amostra aprovada por Eduardo em 14/10/2026;
o Google entrou no mesmo dia, pelo formulário de lead do próprio Google Ads (decisão de Eduardo).

Uma rodada (`buscar_uma_vez`) pede ao Meta os leads criados desde o último que entrou (na primeira vez, os dos
últimos 30 dias) e cria no CRM os que ainda não existem, pelo ID do lead no Meta. Roda a cada 10 minutos
(`laco_dos_leads_do_meta`) e pelo "Buscar leads agora" da aba Campanhas.

Lead que já existe no CRM com o mesmo e-mail entra assim mesmo (decisão de 14/10/2026): juntar os dois fica para a
fusão que o CRM já tem.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from crm.anuncios import LeituraFalhou
from crm.anuncios import google as google_ads
from crm.anuncios import leads_do_meta as meta_leads
from crm.db.base import agora
from crm.db.modelos import Lead
from crm.domain import leads_do_google
from crm.domain.leads_do_meta import campos_do_lead

__all__ = ["Busca", "buscador_do_google", "buscador_real", "buscar_uma_vez", "laco_dos_leads_do_meta",
           "roteador_de_leads_do_meta"]

_log = logging.getLogger(__name__)

INTERVALO = timedelta(minutes=10)
PRIMEIRA_VEZ = timedelta(days=30)
"""Na primeira busca, os leads dos últimos 30 dias (o Meta guarda 90)."""
FOLGA = timedelta(hours=1)
"""Pede uma hora antes do último lead que entrou: o ID evita entrar em dobro."""


@dataclass(frozen=True)
class Busca:
    """A busca de uma rodada: `preparar` devolve `None` com a entrada desligada; o teste troca por falsos.
    `coluna` = a coluna do lead com o ID na plataforma; `converter` = respostas → campos do lead."""

    preparar: Callable[[], Callable[[datetime], list] | None]
    coluna: str = "meta_lead_id"
    converter: Callable[[object], dict] = campos_do_lead


def buscador_real() -> Busca:
    def preparar():
        config = meta_leads.ler_configuracao()
        if config is None:
            return None
        return lambda desde: meta_leads.buscar_leads(config, desde)
    return Busca(preparar)


def buscador_do_google() -> Busca:
    def preparar():
        config = google_ads.ler_leads()
        if config is None:
            return None
        return lambda desde: google_ads.buscar_leads(config, desde)
    return Busca(preparar, coluna="google_lead_id", converter=leads_do_google.campos_do_lead)


class ResultadoDaBusca(BaseModel):
    em: datetime
    ligada: bool
    lidos: int = 0
    novos: int = 0
    erro: str | None = None


@dataclass
class EstadoDaBusca:
    ultima: ResultadoDaBusca | None = None
    trava: threading.Lock = field(default_factory=threading.Lock)


ESTADO = EstadoDaBusca()
ESTADO_DO_GOOGLE = EstadoDaBusca()


def _utc(m: datetime) -> datetime:
    return m if m.tzinfo else m.replace(tzinfo=timezone.utc)


def buscar_uma_vez(sessao: Session, busca: Busca, momento: datetime) -> ResultadoDaBusca:
    buscar = busca.preparar()
    if buscar is None:
        return ResultadoDaBusca(em=momento, ligada=False)
    coluna = getattr(Lead, busca.coluna)
    ultimo = sessao.scalar(sa.select(sa.func.max(Lead.criado_em)).where(coluna.is_not(None)))
    desde = _utc(ultimo) - FOLGA if ultimo else momento - PRIMEIRA_VEZ
    try:
        lidos = buscar(desde)
    except LeituraFalhou as falha:
        return ResultadoDaBusca(em=momento, ligada=True, erro=str(falha))
    ids = [l.id for l in lidos]
    existentes = set(sessao.scalars(sa.select(coluna).where(coluna.in_(ids or ["-"]))))
    novos = 0
    for lead in sorted(lidos, key=lambda l: l.criado_em):
        if lead.id in existentes:
            continue
        sessao.add(Lead(**busca.converter(lead)))
        existentes.add(lead.id)
        novos += 1
    sessao.flush()
    return ResultadoDaBusca(em=momento, ligada=True, lidos=len(lidos), novos=novos)


def _rodar(fabrica: sessionmaker[Session], busca: Busca, estado: EstadoDaBusca) -> None:
    if not estado.trava.acquire(blocking=False):
        return
    try:
        with fabrica() as sessao:
            resultado = buscar_uma_vez(sessao, busca, agora())
            sessao.commit()
        if resultado.ligada:
            estado.ultima = resultado
    finally:
        estado.trava.release()


async def laco_dos_leads_do_meta(fabrica: sessionmaker[Session], busca: Callable[[], Busca] = buscador_real,
                                 intervalo: timedelta = INTERVALO, estado: EstadoDaBusca = ESTADO) -> None:
    """Roda já e depois a cada `intervalo`. Desligada a entrada, a rodada não pede nada ao Meta."""
    while True:
        try:
            await asyncio.to_thread(_rodar, fabrica, busca(), estado)
        except Exception:  # noqa: BLE001 — uma rodada que quebra não derruba o laço
            _log.exception("a busca dos leads do Meta falhou")
        await asyncio.sleep(intervalo.total_seconds())


class SituacaoDaBusca(BaseModel):
    ligada: bool
    ultima: ResultadoDaBusca | None


def roteador_de_leads_do_meta(obter_sessao: Callable[[], Iterator[Session]],
                              busca: Callable[[], Busca] = buscador_real,
                              estado: EstadoDaBusca = ESTADO, *, prefixo: str = "/api/sdr/leads-do-meta",
                              plataforma: str = "Meta") -> APIRouter:
    r = APIRouter(prefix=prefixo, tags=["sdr"])

    @r.get("", response_model=SituacaoDaBusca)
    def situacao() -> SituacaoDaBusca:
        return SituacaoDaBusca(ligada=busca().preparar() is not None, ultima=estado.ultima)

    @r.post("/buscar", response_model=ResultadoDaBusca)
    def buscar_agora(sessao: Session = Depends(obter_sessao, scope="function")) -> ResultadoDaBusca:
        """Uma busca agora, sem esperar os 10 minutos."""
        b = busca()
        if b.preparar() is None:
            raise HTTPException(409, f"a entrada dos leads do {plataforma} está desligada: ligue em Configurações › Integrações")
        if not estado.trava.acquire(blocking=False):
            raise HTTPException(409, "já tem uma busca em curso: tente em instantes")
        try:
            resultado = buscar_uma_vez(sessao, b, agora())
        finally:
            estado.trava.release()
        estado.ultima = resultado
        return resultado

    return r
