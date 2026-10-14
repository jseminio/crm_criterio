"""Devolução das conversões ao Meta Ads e ao Google Ads — amostra aprovada por Eduardo em 14/10/2026.

Uma rodada (`rodar_uma_vez`) olha os leads de tráfego pago, vê o que ainda não saiu (`crm.domain.conversoes`)
e manda a cada plataforma com a devolução ligada em Configurações › Integrações. Roda sozinha a cada 10 minutos
(`laco_das_conversoes`) e também pelo botão "Enviar agora" da aba Campanhas.

- Cada envio fica registrado em `conversao_enviada`, com a frase da resposta: o que foi aceito não sai de novo.
- Credencial recusada para a plataforma na rodada, sem gastar tentativa: corrigida a tela, sai normalmente.
- E-mail e telefone só em SHA-256 (decisão de Eduardo em 14/10/2026). Lead "não contatar" nunca sai.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload, sessionmaker

from crm.anuncios import AcessoNegado, LeituraFalhou, Recusado
from crm.anuncios import google as google_ads
from crm.anuncios import meta as meta_ads
from crm.db.base import agora
from crm.db.modelos import ConversaoEnviada, Lead
from crm.domain import conversoes as regras
from crm.domain import sdr as regras_do_sdr
from crm.domain.listas import TipoCanal

__all__ = ["Enviador", "enviadores_reais", "laco_das_conversoes", "roteador_de_conversoes", "rodar_uma_vez"]

_log = logging.getLogger(__name__)

INTERVALO = timedelta(minutes=10)
JANELA = timedelta(days=120)
"""Só leads que chegaram nos últimos 120 dias entram na rodada: o Google aceita até 90 dias depois do clique."""


@dataclass(frozen=True)
class Enviador:
    """Uma plataforma que recebe conversões. `preparar` devolve a função de envio da rodada, ou `None`
    com a devolução desligada; o teste troca por falsos."""

    plataforma: str
    preparar: Callable[[], Callable[[regras.Envio], str] | None]


def _preparar_meta():
    config = meta_ads.ler_envio()
    if config is None:
        return None
    return lambda envio: meta_ads.enviar_evento(config, envio)


def _preparar_google():
    config = google_ads.ler_envio()
    if config is None:
        return None
    acesso: dict[str, str] = {}

    def enviar(envio):
        if "token" not in acesso:  # um token de acesso por rodada
            import httpx2 as httpx
            with httpx.Client(timeout=30.0) as cliente:
                try:
                    acesso["token"] = google_ads._acesso(cliente, config.credenciais)
                except LeituraFalhou as falha:
                    raise AcessoNegado(str(falha)) from falha
        return google_ads.enviar_conversao(config, envio, acesso=acesso["token"])

    return enviar


def enviadores_reais() -> list[Enviador]:
    return [Enviador(regras.META, _preparar_meta), Enviador(regras.GOOGLE, _preparar_google)]


# ------------------------------------------------------------------- a rodada
class ResultadoDaPlataforma(BaseModel):
    plataforma: str
    ligada: bool
    enviados: int = 0
    recusados: int = 0
    falhas: int = 0
    aviso: str | None = None
    """Credencial recusada ou configuração faltando: a rodada parou nesta plataforma."""


class Rodada(BaseModel):
    em: datetime
    plataformas: list[ResultadoDaPlataforma]


@dataclass
class EstadoDasConversoes:
    """A última rodada, para a tela. Uma rodada por vez."""

    ultima: Rodada | None = None
    trava: threading.Lock = field(default_factory=threading.Lock)


ESTADO = EstadoDasConversoes()


def rodar_uma_vez(sessao: Session, enviadores: list[Enviador], momento: datetime) -> Rodada:
    preparados = [(e.plataforma, e.preparar()) for e in enviadores]
    ligados = {p: f for p, f in preparados if f is not None}
    resultados = {p: ResultadoDaPlataforma(plataforma=p, ligada=p in ligados) for p, _ in preparados}
    if ligados:
        leads = sessao.scalars(
            sa.select(Lead)
            .where(Lead.tipo_canal == TipoCanal.TRAFEGO_PAGO, Lead.criado_em >= momento - JANELA)
            .options(selectinload(Lead.convertido_em))
        ).all()
        ja = {(c.lead_id, c.evento, c.plataforma): c for c in sessao.scalars(
            sa.select(ConversaoEnviada).where(ConversaoEnviada.lead_id.in_([l.id for l in leads] or [-1])))}
        envios, _ = regras.pendentes(leads, ja.values(), ligados, momento)
        parados: set[str] = set()
        for envio in envios:
            if envio.plataforma in parados:
                continue
            r = resultados[envio.plataforma]
            if envio.recusa_previa:
                situacao, resposta = "recusado", envio.recusa_previa
            else:
                try:
                    situacao, resposta = "enviado", ligados[envio.plataforma](envio)
                except AcessoNegado as falha:
                    parados.add(envio.plataforma)
                    r.aviso = str(falha)
                    continue
                except Recusado as falha:
                    situacao, resposta = "recusado", str(falha)
                except LeituraFalhou as falha:
                    situacao, resposta = "falhou", str(falha)
            linha = ja.get((envio.lead_id, envio.evento, envio.plataforma))
            if linha is None:
                linha = ConversaoEnviada(lead_id=envio.lead_id, evento=envio.evento, plataforma=envio.plataforma,
                                         momento_do_evento=envio.momento, valor=envio.valor, tentativas=0)
                sessao.add(linha)
            linha.situacao, linha.resposta, linha.enviado_em = situacao, resposta[:500], momento
            linha.tentativas = (linha.tentativas or 0) + 1
            r.enviados += situacao == "enviado"
            r.recusados += situacao == "recusado"
            r.falhas += situacao == "falhou"
        sessao.flush()
    return Rodada(em=momento, plataformas=list(resultados.values()))


def _rodar_com_sessao(fabrica: sessionmaker[Session], enviadores: list[Enviador],
                      estado: EstadoDasConversoes) -> Rodada | None:
    if not estado.trava.acquire(blocking=False):
        return None  # já tem uma rodada em curso
    try:
        with fabrica() as sessao:
            rodada = rodar_uma_vez(sessao, enviadores, agora())
            sessao.commit()
        estado.ultima = rodada
        return rodada
    finally:
        estado.trava.release()


async def laco_das_conversoes(fabrica: sessionmaker[Session], enviadores: Callable[[], list[Enviador]] = enviadores_reais,
                              intervalo: timedelta = INTERVALO, estado: EstadoDasConversoes = ESTADO) -> None:
    """Roda já e depois a cada `intervalo`, até o CRM desligar. Desligada a devolução, a rodada não envia nada."""
    while True:
        try:
            await asyncio.to_thread(_rodar_com_sessao, fabrica, enviadores(), estado)
        except Exception:  # noqa: BLE001 — uma rodada que quebra não derruba o laço
            _log.exception("a rodada de devolução de conversões falhou")
        await asyncio.sleep(intervalo.total_seconds())


# ------------------------------------------------------------------- as rotas
class LinhaDoResumo(BaseModel):
    evento: str
    rotulo: str
    plataforma: str
    enviados: int
    recusados: int
    falhas: int
    sem_identificador: int
    valor_enviado: float | None


class Recusa(BaseModel):
    lead: str
    evento: str
    plataforma: str
    motivo: str
    em: datetime


class ResumoDasConversoes(BaseModel):
    mes: str
    ligadas: dict[str, bool]
    linhas: list[LinhaDoResumo]
    recusas: list[Recusa]
    ultima_rodada: Rodada | None


def roteador_de_conversoes(obter_sessao: Callable[[], Iterator[Session]],
                           enviadores: Callable[[], list[Enviador]] = enviadores_reais,
                           estado: EstadoDasConversoes = ESTADO) -> APIRouter:
    r = APIRouter(prefix="/api/sdr/conversoes", tags=["sdr"])

    @r.get("", response_model=ResumoDasConversoes)
    def resumo(mes: str = Query(pattern=regras_do_sdr.MES.pattern),
               sessao: Session = Depends(obter_sessao, scope="function")) -> ResumoDasConversoes:
        """O que saiu, o que foi recusado e o que não tem como ser reconhecido, dos leads de tráfego pago do mês."""
        inicio, fim = regras_do_sdr.intervalo_do_mes(mes)
        leads = sessao.scalars(
            sa.select(Lead).where(Lead.tipo_canal == TipoCanal.TRAFEGO_PAGO, Lead.criado_em >= inicio,
                                  Lead.criado_em < fim).options(selectinload(Lead.convertido_em))
        ).all()
        por_id = {l.id: l for l in leads}
        enviadas = list(sessao.scalars(sa.select(ConversaoEnviada).where(
            ConversaoEnviada.lead_id.in_(list(por_id) or [-1]))))
        plataformas = [e.plataforma for e in enviadores()]
        ligadas = {e.plataforma: e.preparar() is not None for e in enviadores()}
        _, sem = regras.pendentes(leads, enviadas, plataformas, agora())
        linhas = []
        for evento, rotulo in regras.EVENTOS.items():
            for p in plataformas:
                daqui = [c for c in enviadas if c.evento == evento and c.plataforma == p]
                ok = [c for c in daqui if c.situacao == "enviado"]
                valor = sum((float(c.valor) for c in ok if c.valor is not None), 0.0)
                linhas.append(LinhaDoResumo(
                    evento=evento, rotulo=rotulo, plataforma=p, enviados=len(ok),
                    recusados=sum(1 for c in daqui if c.situacao == "recusado"),
                    falhas=sum(1 for c in daqui if c.situacao == "falhou"),
                    sem_identificador=sem.get((evento, p), 0),
                    valor_enviado=round(valor, 2) if evento == "contrato_fechado" and ok else None,
                ))
        recusas = sorted((Recusa(lead=por_id[c.lead_id].empresa_texto or por_id[c.lead_id].nome,
                                 evento=regras.EVENTOS[c.evento], plataforma=c.plataforma, motivo=c.resposta or "",
                                 em=c.enviado_em)
                          for c in enviadas if c.situacao == "recusado"), key=lambda x: x.em, reverse=True)[:20]
        return ResumoDasConversoes(mes=mes, ligadas=ligadas, linhas=linhas, recusas=recusas,
                                   ultima_rodada=estado.ultima)

    @r.post("/enviar", response_model=Rodada)
    def enviar_agora(sessao: Session = Depends(obter_sessao, scope="function")) -> Rodada:
        """Uma rodada agora, sem esperar os 10 minutos."""
        lista = enviadores()
        if not any(e.preparar() is not None for e in lista):
            raise HTTPException(409, "a devolução de conversões está desligada: ligue em Configurações › Integrações")
        if not estado.trava.acquire(blocking=False):
            raise HTTPException(409, "já tem uma rodada de envio em curso: tente em instantes")
        try:
            rodada = rodar_uma_vez(sessao, lista, agora())
        finally:
            estado.trava.release()
        estado.ultima = rodada
        return rodada

    return r
