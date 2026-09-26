"""Backup automático: exporta, confere o arquivo e apaga só os automáticos antigos.

Regras que existem para o backup **não virar esperança** (planejamento, E1):

- o arquivo só conta depois de **conferido** (`verificar`); se falhar, é descartado
  e a execução termina com erro;
- a **retenção** só apaga arquivos `crm-auto-*.zip` — nunca um backup manual nem o
  `antes-de-importar-*`;
- a retenção só roda **depois** de um backup novo e conferido: se hoje falhou, nenhum
  antigo é apagado;
- o log **nunca** guarda dado de cliente: só data, tamanho e contagem de registros.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import sqlalchemy as sa

from crm.backup.formato import ErroDeBackup, exportar, verificar

__all__ = ["PREFIXO", "Resultado", "executar"]

PREFIXO = "crm-auto-"


@dataclass(frozen=True)
class Resultado:
    arquivo: Path
    registros: int
    bytes: int
    apagados: list[Path]


def executar(engine: sa.Engine, pasta: Path, *, manter: int = 14, agora: datetime | None = None) -> Resultado:
    if manter < 1:
        raise ValueError("manter precisa ser pelo menos 1")
    pasta.mkdir(parents=True, exist_ok=True)
    os.chmod(pasta, 0o700)
    instante = agora or datetime.now()
    destino = pasta / f"{PREFIXO}{instante:%Y%m%d-%H%M%S}.zip"

    try:
        exportar(engine, destino)
        resumo = verificar(destino)
    except Exception:
        destino.unlink(missing_ok=True)  # arquivo pela metade não pode ficar parecendo backup
        raise
    os.chmod(destino, 0o600)

    automaticos = sorted(pasta.glob(f"{PREFIXO}*.zip"))
    antigos = automaticos[:-manter] if len(automaticos) > manter else []
    for arquivo in antigos:
        arquivo.unlink()
    return Resultado(destino, resumo.total, destino.stat().st_size, antigos)
