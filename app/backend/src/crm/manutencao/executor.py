"""Aplica as tarefas de manutenção pendentes, cada uma na sua transação, e as registra (#93).

Usado por `scripts/manutencao.py`, que o `atualizador.sh` chama no Redeploy. Nada aqui imprime dado de
cliente nem a URL do banco: a mensagem de falha é só o tipo da exceção e a primeira linha dela (o
SQLAlchemy põe o SQL e os parâmetros nas linhas seguintes).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from crm.db.base import agora
from crm.db.modelos import ManutencaoAplicada

__all__ = ["TABELA", "FalhaNaTarefa", "Tarefa", "aplicar_pendentes", "estado", "problemas_do_registro"]

TABELA = ManutencaoAplicada.__tablename__
FORMATO_DO_ID = re.compile(r"^\d{4}_\d{2}_\d{2}_[a-z0-9]+(?:_[a-z0-9]+)*$")
TAMANHO_DO_ID = 120


@dataclass(frozen=True)
class Tarefa:
    id: str
    descricao: str
    executar: Callable[[Session], str | None]


class FalhaNaTarefa(RuntimeError):
    """Uma tarefa levantou exceção: nada dela ficou no banco. As seguintes não rodaram."""

    def __init__(self, tarefa: Tarefa, causa: BaseException) -> None:
        primeira = (str(causa).strip().splitlines() or [""])[0][:300]
        super().__init__(f"{tarefa.id}: {type(causa).__name__}" + (f": {primeira}" if primeira else ""))
        self.tarefa = tarefa


def problemas_do_registro(tarefas: Iterable[Tarefa]) -> list[str]:
    """O que impede o registro de valer: id repetido, fora do formato ou fora da ordem das datas."""
    problemas: list[str] = []
    vistos: set[str] = set()
    data_anterior = ""
    for t in tarefas:
        if t.id in vistos:
            problemas.append(f"id repetido: {t.id}")
        vistos.add(t.id)
        if not FORMATO_DO_ID.match(t.id) or len(t.id) > TAMANHO_DO_ID:
            problemas.append(f"id fora do formato AAAA_MM_DD_assunto (minúsculas, até {TAMANHO_DO_ID}): {t.id}")
            continue
        data = t.id[:10]
        if data < data_anterior:
            problemas.append(f"fora de ordem: {t.id} vem depois de uma tarefa de {data_anterior} (acrescente no fim)")
        data_anterior = max(data_anterior, data)
        if not t.descricao.strip():
            problemas.append(f"sem descrição: {t.id}")
    return problemas


def _tabela_existe(sessao: Session) -> bool:
    return sa.inspect(sessao.get_bind()).has_table(TABELA)


def estado(fabrica: sessionmaker[Session], tarefas: Iterable[Tarefa]) -> tuple[list[tuple[Tarefa, ManutencaoAplicada | None]], list[ManutencaoAplicada]]:
    """Cada tarefa com o seu registro (ou `None`, pendente) e os registros sem tarefa no código."""
    tarefas = list(tarefas)
    with fabrica() as sessao:
        if not _tabela_existe(sessao):
            raise RuntimeError(f"a tabela {TABELA} não existe: o banco está atrás do head (rode as migrações).")
        registros = {r.id: r for r in sessao.scalars(sa.select(ManutencaoAplicada))}
    ids = {t.id for t in tarefas}
    orfaos = sorted((r for r in registros.values() if r.id not in ids), key=lambda r: r.id)
    return [(t, registros.get(t.id)) for t in tarefas], orfaos


def aplicar_pendentes(
    fabrica: sessionmaker[Session],
    tarefas: Iterable[Tarefa],
    *,
    avisar: Callable[[str], None] = print,
    relogio: Callable[[], datetime] = agora,
) -> list[str]:
    """Aplica, em ordem, as tarefas ainda sem registro. Devolve os ids aplicados agora.

    Cada tarefa roda numa transação própria, junto com a sua linha em `manutencao_aplicada`. Na
    primeira falha, desfaz aquela tarefa e levanta `FalhaNaTarefa`: as seguintes **não** rodam (podem
    depender dela), e as anteriores, já confirmadas, ficam. A conferência "já aplicada?" é refeita
    dentro da transação; se dois processos corressem juntos, a chave primária barraria o segundo e
    desfaria o efeito dele junto.
    """
    tarefas = list(tarefas)
    problemas = problemas_do_registro(tarefas)
    if problemas:
        raise ValueError("registro de tarefas inválido: " + "; ".join(problemas))
    if not tarefas:
        return []
    aplicadas: list[str] = []
    with fabrica() as sessao:
        if not _tabela_existe(sessao):
            raise RuntimeError(f"a tabela {TABELA} não existe: o banco está atrás do head (rode as migrações).")
        ja = set(sessao.scalars(sa.select(ManutencaoAplicada.id)))
    for tarefa in tarefas:
        if tarefa.id in ja:
            continue
        avisar(f"aplicando {tarefa.id} — {tarefa.descricao}")
        sessao = fabrica()
        try:
            with sessao.begin():
                if sessao.get(ManutencaoAplicada, tarefa.id) is not None:
                    continue
                resultado = tarefa.executar(sessao)
                sessao.add(ManutencaoAplicada(
                    id=tarefa.id, descricao=tarefa.descricao[:300], aplicada_em=relogio(),
                    resultado=(resultado or None),
                ))
        except Exception as causa:  # noqa: BLE001 — qualquer falha da tarefa vira FalhaNaTarefa
            raise FalhaNaTarefa(tarefa, causa) from causa
        finally:
            sessao.close()
        avisar(f"ok: {tarefa.id}" + (f" — {resultado}" if resultado else ""))
        aplicadas.append(tarefa.id)
    return aplicadas
