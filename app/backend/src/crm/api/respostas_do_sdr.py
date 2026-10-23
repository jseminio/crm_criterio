"""As respostas do SDR de IA no WhatsApp — fase 1 (amostra aprovada por Eduardo em 23/10/2026).

- O **laço**: enquanto o CRM está ligado, a cada `INTERVALO` segundos responde as conversas pendentes
  (`crm.agente.respostas_do_sdr.rodar_uma_vez`), conforme o modo da aba Respostas do SDR em Integrações.
  Desligado (o padrão), não faz nada.
- As **ações da equipe** na conversa do lead: responder pelo CRM, enviar ou descartar o rascunho da IA,
  devolver a conversa à IA. O número da Critério está na API da Meta, então é pelo CRM que a equipe escreve.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload, sessionmaker

import sqlalchemy as sa

from crm.agente import respostas_do_sdr as respostas
from crm.agente.config import ler_configuracao
from crm.agente.ia import montar_cliente
from crm.agente.roteador_do_sdr import Clientes, ConfiguracaoDasRespostas, ler_configuracao_das_respostas
from crm.agente.whatsapp import enviar_texto
from crm.api import esquemas as e
from crm.api.acesso import quem_fez
from crm.db.base import agora
from crm.db.modelos import ConversaDoSdr, MensagemDoSdr

__all__ = ["ESTADO_DAS_RESPOSTAS", "INTERVALO", "clientes_reais", "envio_real", "laco_das_respostas",
           "roteador_das_respostas"]

INTERVALO = 10.0
"""Segundos entre as rodadas. Com a espera de 20 segundos, o lead tem a resposta em meio minuto."""


def clientes_reais(cfg: ConfiguracaoDasRespostas) -> Callable[[], Clientes]:
    """Os clientes da tela de Integrações: o principal (aba IA) e o leve (o mesmo fornecedor, com o modelo
    leve), cada um com a reserva atrás. Sem chave, `AgenteFalhou`: a conversa vai para a equipe."""
    def montar() -> Clientes:
        config = ler_configuracao()
        principal, modelo_principal = montar_cliente(config)
        leve, modelo_leve = montar_cliente(replace(config, modelo=cfg.modelo_leve, openai_modelo=cfg.modelo_leve_openai))
        return Clientes(leve=leve, modelo_leve=modelo_leve, principal=principal, modelo_principal=modelo_principal)
    return montar


def envio_real() -> respostas.Enviar | None:
    """O envio de texto livre pelo WhatsApp da tela. `None` sem token ou número."""
    config = ler_configuracao().whatsapp
    if config is None:
        return None
    return lambda para, texto: enviar_texto(config, para=para, texto=texto)


class EstadoDasRespostas:
    """A última rodada, em memória: some ao reiniciar o CRM."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self.ultima_em: datetime | None = None
        self._erro: tuple[datetime, str] | None = None

    def registrar(self, rodada: respostas.Rodada) -> None:
        with self._trava:
            self.ultima_em = agora()
            if rodada.erros:
                self._erro = (self.ultima_em, rodada.erros[-1])

    def erro(self) -> str | None:
        """A última falha, com a hora de Brasília. Fica até a próxima falha ou até o CRM reiniciar."""
        with self._trava:
            if self._erro is None:
                return None
            em, texto = self._erro
            return f"{texto} ({em.astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m às %H:%M')})"


ESTADO_DAS_RESPOSTAS = EstadoDasRespostas()


def _rodar(fabrica: sessionmaker[Session], clientes: Callable[[ConfiguracaoDasRespostas], Callable[[], Clientes]],
           envio: Callable[[], respostas.Enviar | None], estado: EstadoDasRespostas) -> respostas.Rodada:
    cfg = ler_configuracao_das_respostas()
    if not cfg.ligado:
        return respostas.Rodada()
    rodada = respostas.rodar_uma_vez(fabrica, cfg, clientes(cfg), None if cfg.supervisionado else envio(),
                                     ler_configuracao().link_do_questionario, agora)
    estado.registrar(rodada)
    return rodada


async def laco_das_respostas(
    fabrica: sessionmaker[Session],
    clientes: Callable[[ConfiguracaoDasRespostas], Callable[[], Clientes]] = clientes_reais,
    envio: Callable[[], respostas.Enviar | None] = envio_real,
    intervalo: float = INTERVALO, estado: EstadoDasRespostas = ESTADO_DAS_RESPOSTAS,
) -> None:
    """Roda já e depois a cada `intervalo`, fora do laço de eventos, até o CRM desligar."""
    while True:
        try:
            await asyncio.to_thread(_rodar, fabrica, clientes, envio, estado)
        except Exception as falha:  # noqa: BLE001 — o laço nunca derruba o CRM
            estado.registrar(respostas.Rodada(erros=[f"Falha inesperada na rodada ({type(falha).__name__})."]))
        await asyncio.sleep(intervalo)


class TextoDaEquipe(BaseModel):
    texto: str = Field(min_length=1, max_length=4096)


class AjusteDoRascunho(BaseModel):
    texto: str | None = Field(default=None, max_length=4096)
    """Vazio ou igual: sai como a IA escreveu."""


class ModoDasRespostas(BaseModel):
    modo: str


def roteador_das_respostas(
    obter_sessao: Callable[[], Iterator[Session]],
    envio: Callable[[], respostas.Enviar | None] = envio_real,
) -> APIRouter:
    r = APIRouter(prefix="/api/sdr", tags=["sdr"])

    def _conversa_resposta(sessao: Session, conversa_id: int) -> e.ConversaResposta:
        sessao.expire_all()
        conversa = sessao.scalar(sa.select(ConversaDoSdr).where(ConversaDoSdr.id == conversa_id)
                                 .options(selectinload(ConversaDoSdr.mensagens)))
        return e.ConversaResposta.model_validate(conversa)

    def _conversa(sessao: Session, conversa_id: int) -> ConversaDoSdr:
        conversa = sessao.get(ConversaDoSdr, conversa_id, with_for_update=True)
        if conversa is None:
            raise HTTPException(404, "conversa não encontrada")
        return conversa

    def _mensagem(sessao: Session, mensagem_id: int) -> MensagemDoSdr:
        mensagem = sessao.get(MensagemDoSdr, mensagem_id, with_for_update=True)
        if mensagem is None:
            raise HTTPException(404, "mensagem não encontrada")
        return mensagem

    def _executar(sessao: Session, acao: Callable[[], int]) -> e.ConversaResposta:
        try:
            conversa_id = acao()
        except respostas.RegraDaResposta as regra:
            raise HTTPException(regra.status, str(regra)) from regra
        sessao.flush()
        return _conversa_resposta(sessao, conversa_id)

    @r.get("/respostas", response_model=ModoDasRespostas)
    def modo_das_respostas():
        """O modo das respostas da IA, para a conversa do lead dizer quem responde."""
        return ModoDasRespostas(modo=ler_configuracao_das_respostas().modo)

    @r.post("/conversas/{conversa_id}/responder", response_model=e.ConversaResposta)
    def responder(conversa_id: int, corpo: TextoDaEquipe, sessao: Session = Depends(obter_sessao, scope="function")):
        """A equipe escreve ao lead. A IA para de responder nesta conversa."""
        conversa = _conversa(sessao, conversa_id)
        return _executar(sessao, lambda: respostas.responder_pela_equipe(
            sessao, conversa, corpo.texto, quem_fez(None), envio(), agora()).conversa_id)

    @r.post("/conversas/{conversa_id}/devolver", response_model=e.ConversaResposta)
    def devolver(conversa_id: int, sessao: Session = Depends(obter_sessao, scope="function")):
        """A conversa volta para a IA (na mesma conversa, ou numa nova se a passagem a encerrou)."""
        conversa = _conversa(sessao, conversa_id)
        return _executar(sessao, lambda: respostas.devolver_para_a_ia(sessao, conversa, agora()).id)

    @r.post("/mensagens/{mensagem_id}/enviar", response_model=e.ConversaResposta)
    def enviar(mensagem_id: int, corpo: AjusteDoRascunho, sessao: Session = Depends(obter_sessao, scope="function")):
        """Envia o rascunho da IA (modo supervisionado), como está ou ajustado."""
        mensagem = _mensagem(sessao, mensagem_id)
        return _executar(sessao, lambda: respostas.enviar_rascunho(
            sessao, mensagem, corpo.texto, quem_fez(None), envio(), agora()).conversa_id)

    @r.post("/mensagens/{mensagem_id}/descartar", response_model=e.ConversaResposta)
    def descartar(mensagem_id: int, sessao: Session = Depends(obter_sessao, scope="function")):
        """Descarta o rascunho da IA e passa a conversa para a equipe."""
        mensagem = _mensagem(sessao, mensagem_id)
        return _executar(sessao, lambda: respostas.descartar_rascunho(
            sessao, mensagem, quem_fez(None), agora()).conversa_id)

    return r
