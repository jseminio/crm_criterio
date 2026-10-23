"""Notas do Granola no CRM (amostra aprovada por Eduardo em 23/10/2026).

- A busca roda logo ao subir e a cada 10 minutos (`laco_do_granola`), com a busca ligada em Configurações ›
  Integrações › Granola, e pelo botão "Buscar agora" da mesma tela.
- `GET /api/granola`: a situação da busca e a fila "Precisa de você", com as oportunidades em aberto e os grupos
  para escolher. Escolher manda a nota para "A usar" no lugar escolhido; descartar tira o resumo e a transcrição.
- A aba Granola da oportunidade e a reunião do cliente no Funil do Sucesso leem as suas notas "A usar". Quem usa
  é a pessoa: a nota marca "Usada" quando a reunião é guardada com ela (`usar_nota`).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import httpx2 as httpx
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from crm.api.acesso import quem_fez
from crm.db.base import agora
from crm.db.modelos import GrupoEconomico, NotaDoGranola, Oportunidade
from crm.domain.granola import SituacaoDaNota, TipoDaNota
from crm.domain.listas import SituacaoGrupo
from crm.granola import cliente as g
from crm.granola.busca import EM_ABERTO, buscar_uma_vez

__all__ = ["ESTADO", "EstadoDoGranola", "laco_do_granola", "roteador_do_granola", "usar_nota"]

_log = logging.getLogger(__name__)

INTERVALO = timedelta(minutes=10)


class ResultadoDaBusca(BaseModel):
    em: datetime
    lidas: int = 0
    novas: int = 0
    a_usar: int = 0
    precisam: int = 0
    erro: str | None = None
    aviso: str | None = None


@dataclass
class EstadoDoGranola:
    ultima: ResultadoDaBusca | None = None
    proxima: datetime | None = None
    trava: threading.Lock = field(default_factory=threading.Lock)


ESTADO = EstadoDoGranola()


def _rodar(sessao: Session, http: Callable[[], httpx.Client], config: g.ConfiguracaoDoGranola) -> ResultadoDaBusca:
    momento = agora()
    try:
        with http() as cliente:
            r = buscar_uma_vez(sessao, cliente, config, date.today())
    except g.FalhaNoGranola as falha:
        sessao.rollback()
        return ResultadoDaBusca(em=momento, erro=str(falha))
    sessao.commit()
    return ResultadoDaBusca(em=momento, lidas=r.lidas, novas=r.novas, a_usar=r.a_usar, precisam=r.precisam, aviso=r.aviso)


def _uma_rodada(fabrica: sessionmaker[Session], http: Callable[[], httpx.Client], estado: EstadoDoGranola) -> None:
    config = g.ler_configuracao()
    if config is None or not estado.trava.acquire(blocking=False):
        return
    try:
        with fabrica() as sessao:
            estado.ultima = _rodar(sessao, http, config)
    finally:
        estado.trava.release()


async def laco_do_granola(fabrica: sessionmaker[Session], http: Callable[[], httpx.Client] = g.novo_http,
                          intervalo: timedelta = INTERVALO, estado: EstadoDoGranola = ESTADO) -> None:
    """Roda já e depois a cada `intervalo`. Desligada a busca, a rodada não pede nada ao Granola."""
    try:
        while True:
            try:
                await asyncio.to_thread(_uma_rodada, fabrica, http, estado)
            except Exception:  # noqa: BLE001 — uma rodada que quebra não derruba o laço
                _log.exception("a busca das notas do Granola falhou")
            estado.proxima = agora() + intervalo
            await asyncio.sleep(intervalo.total_seconds())
    finally:
        estado.proxima = None


# ------------------------------------------------------------------ esquemas
class NotaResposta(BaseModel):
    id: int
    tipo: str
    titulo: str
    data: date
    participantes: str | None
    link: str | None
    motivo: str | None
    resumo: str | None
    transcricao: str | None = None
    chegou_em: datetime


class Opcao(BaseModel):
    id: int
    nome: str


class SituacaoDoGranola(BaseModel):
    ligada: bool
    ultima: ResultadoDaBusca | None
    proxima: datetime | None
    precisam: list[NotaResposta]
    oportunidades: list[Opcao]
    """As oportunidades em aberto, para escolher onde entra uma nota de reunião com o lead."""
    grupos: list[Opcao]
    """Os grupos clientes, para escolher onde entra uma nota de Reunião de Resultado."""


class Destino(BaseModel):
    oportunidade_id: int | None = None
    grupo_id: int | None = None


def _resposta(n: NotaDoGranola, *, com_transcricao: bool = False) -> NotaResposta:
    return NotaResposta(
        id=n.id, tipo=n.tipo.value, titulo=n.titulo, data=n.data, participantes=n.participantes, link=n.link,
        motivo=n.motivo, resumo=n.resumo, transcricao=n.transcricao if com_transcricao else None, chegou_em=n.criado_em,
    )


def usar_nota(sessao: Session, nota_id: int | None, *, oportunidade_id: int | None = None,
              grupo_id: int | None = None) -> None:
    """Marca "Usada" a nota com que a pessoa guardou a reunião. A nota precisa ser daquele lugar e estar "A usar"."""
    if nota_id is None:
        return
    n = sessao.get(NotaDoGranola, nota_id)
    lugar_certo = n is not None and (
        (oportunidade_id is not None and n.tipo is TipoDaNota.LEAD and n.oportunidade_id == oportunidade_id)
        or (grupo_id is not None and n.tipo is TipoDaNota.RESULTADO and n.grupo_id == grupo_id))
    if not lugar_certo or n.situacao is not SituacaoDaNota.A_USAR:
        raise HTTPException(422, "Esta nota do Granola não está à espera de uso aqui. Recarregue a tela.")
    n.situacao = SituacaoDaNota.USADA
    n.resolvida_por = quem_fez("") or None
    n.resolvida_em = agora()


def _descartar(n: NotaDoGranola) -> None:
    n.situacao = SituacaoDaNota.DESCARTADA
    n.resumo = None
    n.transcricao = None
    n.participantes = None
    n.resolvida_por = quem_fez("") or None
    n.resolvida_em = agora()


def roteador_do_granola(obter_sessao: Callable[[], Iterator[Session]],
                        http: Callable[[], httpx.Client] = g.novo_http,
                        estado: EstadoDoGranola = ESTADO) -> APIRouter:
    r = APIRouter(tags=["granola"])

    def _situacao(sessao: Session) -> SituacaoDoGranola:
        fila = list(sessao.scalars(sa.select(NotaDoGranola).where(
            NotaDoGranola.situacao == SituacaoDaNota.PRECISA_DE_VOCE).order_by(NotaDoGranola.data.desc(), NotaDoGranola.id)))
        oportunidades: list[Opcao] = []
        grupos: list[Opcao] = []
        if any(n.tipo is TipoDaNota.LEAD for n in fila):
            oportunidades = [Opcao(id=i, nome=f"{nome} · {servico}" if servico else nome) for i, nome, servico in sessao.execute(
                sa.select(Oportunidade.id, Oportunidade.nome, Oportunidade.servico)
                .where(Oportunidade.situacao.in_(EM_ABERTO)).order_by(Oportunidade.nome, Oportunidade.id))]
        if any(n.tipo is TipoDaNota.RESULTADO for n in fila):
            grupos = [Opcao(id=i, nome=nome) for i, nome in sessao.execute(
                sa.select(GrupoEconomico.id, GrupoEconomico.nome)
                .where(GrupoEconomico.situacao == SituacaoGrupo.CLIENTE).order_by(GrupoEconomico.nome))]
        return SituacaoDoGranola(
            ligada=g.ler_configuracao() is not None, ultima=estado.ultima, proxima=estado.proxima,
            precisam=[_resposta(n) for n in fila], oportunidades=oportunidades, grupos=grupos,
        )

    def _nota(sessao: Session, nota_id: int) -> NotaDoGranola:
        n = sessao.get(NotaDoGranola, nota_id)
        if n is None:
            raise HTTPException(404, "nota do Granola não encontrada")
        return n

    @r.get("/api/granola", response_model=SituacaoDoGranola)
    def situacao(sessao: Session = Depends(obter_sessao, scope="function")) -> SituacaoDoGranola:
        return _situacao(sessao)

    @r.post("/api/granola/buscar", response_model=ResultadoDaBusca)
    def buscar_agora(sessao: Session = Depends(obter_sessao, scope="function")) -> ResultadoDaBusca:
        """Uma busca agora, sem esperar os 10 minutos."""
        config = g.ler_configuracao()
        if config is None:
            raise HTTPException(409, "A busca do Granola está desligada ou sem chave: ligue e salve em "
                                     "Configurações › Integrações › Granola.")
        if not estado.trava.acquire(blocking=False):
            raise HTTPException(409, "Já tem uma busca em curso: tente em instantes.")
        try:
            estado.ultima = _rodar(sessao, http, config)
        finally:
            estado.trava.release()
        return estado.ultima

    @r.get("/api/granola/pastas", response_model=list[str])
    def pastas() -> list[str]:
        """Os nomes das pastas que a chave salva enxerga, para escolher na tela. Não precisa da busca ligada."""
        config = g.ler_configuracao(exigir_ligada=False)
        if config is None:
            raise HTTPException(409, "Salve a chave da API do Granola para ver as pastas.")
        try:
            with http() as cliente:
                return sorted({p.nome for p in g.listar_pastas(cliente, config) if p.nome}, key=str.casefold)
        except g.FalhaNoGranola as falha:
            raise HTTPException(502, str(falha)) from falha

    @r.post("/api/granola/notas/{nota_id}/destino", response_model=SituacaoDoGranola)
    def escolher_destino(nota_id: int, corpo: Destino,
                         sessao: Session = Depends(obter_sessao, scope="function")) -> SituacaoDoGranola:
        n = _nota(sessao, nota_id)
        if n.situacao is not SituacaoDaNota.PRECISA_DE_VOCE:
            raise HTTPException(409, "Esta nota já saiu da fila. Recarregue a tela.")
        if n.tipo is TipoDaNota.LEAD:
            o = sessao.get(Oportunidade, corpo.oportunidade_id) if corpo.oportunidade_id else None
            if o is None or o.situacao not in EM_ABERTO:
                raise HTTPException(422, "Escolha uma oportunidade em aberto.")
            n.oportunidade_id = o.id
        else:
            grupo = sessao.get(GrupoEconomico, corpo.grupo_id) if corpo.grupo_id else None
            if grupo is None:
                raise HTTPException(422, "Escolha o grupo do cliente.")
            n.grupo_id = grupo.id
        n.situacao = SituacaoDaNota.A_USAR
        n.motivo = None
        n.resolvida_por = quem_fez("") or None
        n.resolvida_em = agora()
        sessao.flush()
        return _situacao(sessao)

    @r.post("/api/granola/notas/{nota_id}/descartar", response_model=SituacaoDoGranola)
    def descartar_da_fila(nota_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> SituacaoDoGranola:
        n = _nota(sessao, nota_id)
        if n.situacao is not SituacaoDaNota.PRECISA_DE_VOCE:
            raise HTTPException(409, "Esta nota já saiu da fila. Recarregue a tela.")
        _descartar(n)
        sessao.flush()
        return _situacao(sessao)

    # ------------------------------------------------ onde a nota é usada
    def _a_usar(sessao: Session, **onde: int) -> list[NotaDoGranola]:
        filtro = [getattr(NotaDoGranola, k) == v for k, v in onde.items()]
        return list(sessao.scalars(sa.select(NotaDoGranola).where(
            NotaDoGranola.situacao == SituacaoDaNota.A_USAR, *filtro).order_by(NotaDoGranola.data.desc(), NotaDoGranola.id)))

    @r.get("/api/oportunidades/{oportunidade_id}/granola", response_model=list[NotaResposta])
    def da_oportunidade(oportunidade_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> list[NotaResposta]:
        """As notas de reunião com o lead que chegaram para esta oportunidade. Só o resumo: do lead não há transcrição."""
        return [_resposta(n) for n in _a_usar(sessao, oportunidade_id=oportunidade_id, tipo=TipoDaNota.LEAD)]

    @r.post("/api/oportunidades/{oportunidade_id}/granola/{nota_id}/descartar", response_model=list[NotaResposta])
    def descartar_da_oportunidade(oportunidade_id: int, nota_id: int,
                                  sessao: Session = Depends(obter_sessao, scope="function")) -> list[NotaResposta]:
        n = _nota(sessao, nota_id)
        if n.oportunidade_id != oportunidade_id or n.situacao is not SituacaoDaNota.A_USAR:
            raise HTTPException(409, "Esta nota já saiu daqui. Recarregue a tela.")
        _descartar(n)
        sessao.flush()
        return [_resposta(x) for x in _a_usar(sessao, oportunidade_id=oportunidade_id, tipo=TipoDaNota.LEAD)]

    @r.get("/api/sucesso/grupos/{grupo_id}/granola", response_model=list[NotaResposta])
    def do_grupo(grupo_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> list[NotaResposta]:
        """As notas de Reunião de Resultado que chegaram para este cliente, com a transcrição para montar a ata."""
        return [_resposta(n, com_transcricao=True)
                for n in _a_usar(sessao, grupo_id=grupo_id, tipo=TipoDaNota.RESULTADO)]

    @r.post("/api/sucesso/grupos/{grupo_id}/granola/{nota_id}/descartar", response_model=list[NotaResposta])
    def descartar_do_grupo(grupo_id: int, nota_id: int,
                           sessao: Session = Depends(obter_sessao, scope="function")) -> list[NotaResposta]:
        n = _nota(sessao, nota_id)
        if n.grupo_id != grupo_id or n.situacao is not SituacaoDaNota.A_USAR:
            raise HTTPException(409, "Esta nota já saiu daqui. Recarregue a tela.")
        _descartar(n)
        sessao.flush()
        return [_resposta(x, com_transcricao=True)
                for x in _a_usar(sessao, grupo_id=grupo_id, tipo=TipoDaNota.RESULTADO)]

    return r
