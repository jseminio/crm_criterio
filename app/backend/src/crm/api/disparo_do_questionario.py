"""O disparo automático do lembrete e do agradecimento do questionário (06/10/2026).

Como a busca automática dos questionários: enquanto o CRM estiver ligado, roda logo ao subir e
depois a cada 10 minutos. **Só envia com `CRM_DISPARO_DO_QUESTIONARIO=true`**; desligado, cada
rodada só anota "desligado". O resultado da última rodada, inclusive a falha, fica em
`GET /api/sdr/questionario/disparo`.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy.orm import Session, sessionmaker

from crm.agente.config import ler_configuracao
from crm.agente.disparo_do_questionario import Canais, Resultado, disparar
from crm.agente.envio import enviar_email
from crm.agente.whatsapp import enviar_modelo
from crm.db.base import agora

__all__ = ["INTERVALO_DO_DISPARO", "EstadoDoDisparo", "ESTADO_DO_DISPARO", "canais_reais", "rodar_uma_vez",
           "laco_do_disparo"]

_log = logging.getLogger(__name__)

INTERVALO_DO_DISPARO = timedelta(minutes=10)


def canais_reais() -> Canais | None:
    """Os canais do `.env`. `None` quando o disparo está desligado: nada sai."""
    config = ler_configuracao()
    if not config.disparo_ligado:
        return None
    whatsapp = email = None
    if config.whatsapp is not None:
        cw = config.whatsapp
        whatsapp = lambda para, modelo, parametros: enviar_modelo(cw, para=para, modelo=modelo, parametros=parametros)  # noqa: E731
    if config.email is not None:
        ce = config.email
        email = lambda para, assunto, corpo: enviar_email(ce, para=para, assunto=assunto, corpo=corpo)  # noqa: E731
    return Canais(whatsapp=whatsapp, email=email)


class EstadoDoDisparo:
    """A última rodada e a próxima, em memória: some ao reiniciar o CRM, que roda logo ao subir."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._automatico = False
        self._ligado = False
        self._ultima_em: datetime | None = None
        self._resultado = Resultado()
        self._proxima_em: datetime | None = None

    def ligar_laco(self, proxima_em: datetime | None) -> None:
        with self._trava:
            self._automatico, self._proxima_em = True, proxima_em

    def desligar_laco(self) -> None:
        with self._trava:
            self._automatico, self._proxima_em = False, None

    def agendar(self, proxima_em: datetime) -> None:
        with self._trava:
            self._proxima_em = proxima_em

    def registrar(self, *, ligado: bool, resultado: Resultado) -> None:
        with self._trava:
            self._ligado, self._ultima_em, self._resultado = ligado, agora(), resultado

    def retrato(self) -> dict:
        with self._trava:
            return {
                "automatico": self._automatico, "ligado": self._ligado,
                "intervalo_minutos": int(INTERVALO_DO_DISPARO.total_seconds() // 60),
                "ultima_em": self._ultima_em, "enviados": self._resultado.enviados,
                "avisos": list(self._resultado.avisos), "erros": list(self._resultado.erros),
                "proxima_em": self._proxima_em,
            }


ESTADO_DO_DISPARO = EstadoDoDisparo()


def rodar_uma_vez(
    fabrica: Callable[[], Session], canais: Callable[[], Canais | None], estado: EstadoDoDisparo = ESTADO_DO_DISPARO,
) -> Resultado:
    """Uma rodada, sem nunca derrubar o CRM: qualquer falha vai para o estado, com o motivo."""
    atuais = canais()
    if atuais is None:
        resultado = Resultado(avisos=["Disparo desligado: CRM_DISPARO_DO_QUESTIONARIO não está true."])
        estado.registrar(ligado=False, resultado=resultado)
        return resultado
    with fabrica() as sessao:
        try:
            resultado = disparar(sessao, atuais, agora(), ler_configuracao().link_do_questionario)
        except Exception as falha:  # noqa: BLE001 — o laço continua; o motivo vai para o estado e o log
            sessao.rollback()
            _log.exception("disparo do questionário falhou")
            resultado = Resultado(erros=[f"Falha inesperada no disparo ({type(falha).__name__})."])
    estado.registrar(ligado=True, resultado=resultado)
    return resultado


async def laco_do_disparo(
    fabrica: sessionmaker[Session], canais: Callable[[], Canais | None] = canais_reais,
    intervalo: timedelta = INTERVALO_DO_DISPARO, estado: EstadoDoDisparo = ESTADO_DO_DISPARO,
) -> None:
    """Roda já e depois a cada `intervalo`, até o CRM desligar, fora do laço de eventos."""
    estado.ligar_laco(agora())
    try:
        while True:
            await asyncio.to_thread(rodar_uma_vez, fabrica, canais, estado)
            estado.agendar(agora() + intervalo)
            await asyncio.sleep(intervalo.total_seconds())
    finally:
        estado.desligar_laco()
