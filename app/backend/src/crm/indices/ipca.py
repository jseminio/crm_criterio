"""O IPCA guardado no CRM: buscar no Banco Central o que falta e devolver a série (13/10/2026).

**Nada manual** (regra do projeto, 05/10/2026): a série se completa sozinha quando a tela de reajuste abre e
o último mês publicado ainda não está aqui. Se o Banco Central não responder, a tela segue com o que já está
guardado e avisa; nada é apagado.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.base import agora
from crm.db.modelos import IpcaDoMes
from crm.indices.bcb import BuscaDoIpcaFalhou, buscar_ipca

__all__ = ["BuscarIpca", "INICIO_DA_SERIE", "Atualizacao", "atualizar", "precisa_atualizar", "serie"]

BuscarIpca = Callable[[date, date], dict[date, Decimal]]
INICIO_DA_SERIE = date(2016, 1, 1)
"""Dez anos antes do primeiro reajuste pelo CRM: cobre a assinatura de qualquer contrato da carteira atual."""
INTERVALO = timedelta(hours=12)
"""Entre uma busca e outra. O IBGE publica uma vez por mês; buscar a cada abertura da tela seria desperdício."""


@dataclass(frozen=True)
class Atualizacao:
    novos: int
    revistos: int
    ultimo_mes: date | None
    erro: str | None = None


def _mes_anterior(hoje: date) -> date:
    primeiro = hoje.replace(day=1)
    return (primeiro - timedelta(days=1)).replace(day=1)


def serie(sessao: Session) -> dict[date, Decimal]:
    return dict(sessao.execute(sa.select(IpcaDoMes.mes, IpcaDoMes.variacao).order_by(IpcaDoMes.mes)).all())


def precisa_atualizar(sessao: Session, hoje: date, momento: datetime | None = None) -> bool:
    """Falta o mês anterior a `hoje` e a última busca foi há mais de 12 horas (ou nunca houve)."""
    ultimo, buscado = sessao.execute(sa.select(sa.func.max(IpcaDoMes.mes), sa.func.max(IpcaDoMes.buscado_em))).one()
    if ultimo is not None and ultimo >= _mes_anterior(hoje):
        return False
    if buscado is None:
        return True
    if buscado.tzinfo is None:
        buscado = buscado.replace(tzinfo=(momento or agora()).tzinfo)
    return (momento or agora()) - buscado >= INTERVALO


def atualizar(sessao: Session, hoje: date, buscar: BuscarIpca = buscar_ipca) -> Atualizacao:
    """Busca do último mês guardado (ou de 2016) até hoje e grava o que é novo ou mudou. Não faz commit."""
    guardada = serie(sessao)
    de = max(guardada) if guardada else INICIO_DA_SERIE
    try:
        meses = buscar(de, hoje)
    except BuscaDoIpcaFalhou as erro:
        # Marca a tentativa para não bater no Banco Central a cada abertura da tela enquanto ele estiver fora.
        if guardada:
            sessao.execute(sa.update(IpcaDoMes).where(IpcaDoMes.mes == max(guardada)).values(buscado_em=agora()))
        return Atualizacao(0, 0, max(guardada) if guardada else None, str(erro))
    novos = revistos = 0
    momento = agora()
    for mes, variacao in sorted(meses.items()):
        mes = mes.replace(day=1)
        if mes not in guardada:
            sessao.add(IpcaDoMes(mes=mes, variacao=variacao, buscado_em=momento))
            novos += 1
        elif guardada[mes] != variacao:
            sessao.execute(sa.update(IpcaDoMes).where(IpcaDoMes.mes == mes).values(variacao=variacao, buscado_em=momento))
            revistos += 1
    ultimo = max([*guardada, *meses], default=None)
    if ultimo is not None and not novos and not revistos and guardada:
        sessao.execute(sa.update(IpcaDoMes).where(IpcaDoMes.mes == max(guardada)).values(buscado_em=momento))
    sessao.flush()
    return Atualizacao(novos, revistos, ultimo)
