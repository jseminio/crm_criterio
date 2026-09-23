"""Leitura e gravação do arquivo de backup lógico."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, BinaryIO

import sqlalchemy as sa

from crm.db.base import Base, agora
from crm.db import modelos  # noqa: F401 — registra todas as tabelas em Base.metadata

__all__ = ["VERSAO_DO_FORMATO", "ErroDeBackup", "ResumoDeBackup", "exportar", "importar", "verificar"]

VERSAO_DO_FORMATO = 1
_MANIFESTO = "manifesto.json"
_LOTE = 500


class ErroDeBackup(RuntimeError):
    """Backup inválido, adulterado, de outra versão, ou destino que não aceita."""


@dataclass(frozen=True)
class ResumoDeBackup:
    criado_em: str
    revisao_do_esquema: str | None
    tabelas: dict[str, int]

    @property
    def total(self) -> int:
        return sum(self.tabelas.values())


# ---------------------------------------------------------------- conversão

def _para_json(valor: Any) -> Any:
    if valor is None or isinstance(valor, (bool, int, float, str)):
        return valor
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return str(valor)  # texto: float perderia centavo
    return valor  # JSON já é estrutura (dict/list)


def _do_json(coluna: sa.Column, valor: Any) -> Any:
    if valor is None:
        return None
    tipo = coluna.type
    if isinstance(tipo, sa.Enum):
        return tipo.enum_class(valor)
    if isinstance(tipo, sa.DateTime):
        return datetime.fromisoformat(valor)
    if isinstance(tipo, sa.Date):
        return date.fromisoformat(valor)
    if isinstance(tipo, sa.Numeric):
        return Decimal(valor)
    return valor


def _tabelas() -> list[sa.Table]:
    """Na ordem que respeita chaves estrangeiras: pai antes de filho."""
    return list(Base.metadata.sorted_tables)


def _revisao(conexao: sa.Connection) -> str | None:
    try:
        return conexao.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    except sa.exc.DBAPIError:
        return None


def _linha(tabela: sa.Table, registro: sa.Row) -> bytes:
    obj = {c.name: _para_json(registro._mapping[c.name]) for c in tabela.columns}
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")


# ----------------------------------------------------------------- exportar

def exportar(engine: sa.Engine, destino: Path | BinaryIO) -> ResumoDeBackup:
    """Grava o backup completo. Lê tudo numa transação só, para ser consistente."""
    tabelas_info: dict[str, dict] = {}
    with engine.connect() as conexao, conexao.begin():
        revisao = _revisao(conexao)
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
            for tabela in _tabelas():
                digest = hashlib.sha256()
                buffer = io.BytesIO()
                n = 0
                for registro in conexao.execute(sa.select(tabela).order_by(*tabela.primary_key.columns)):
                    linha = _linha(tabela, registro)
                    digest.update(linha)
                    buffer.write(linha)
                    n += 1
                zf.writestr(f"dados/{tabela.name}.jsonl", buffer.getvalue())
                tabelas_info[tabela.name] = {
                    "registros": n,
                    "sha256": digest.hexdigest(),
                    "colunas": [c.name for c in tabela.columns],
                }
            criado = agora().isoformat()
            zf.writestr(
                _MANIFESTO,
                json.dumps(
                    {
                        "formato": VERSAO_DO_FORMATO,
                        "criado_em": criado,
                        "revisao_do_esquema": revisao,
                        "tabelas": tabelas_info,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
    return ResumoDeBackup(criado, revisao, {k: v["registros"] for k, v in tabelas_info.items()})


# ---------------------------------------------------------------- verificar

def _abrir(origem: Path | BinaryIO) -> tuple[zipfile.ZipFile, dict]:
    try:
        zf = zipfile.ZipFile(origem)
        manifesto = json.loads(zf.read(_MANIFESTO))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as erro:
        raise ErroDeBackup("O arquivo não é um backup do CRM (ou está corrompido).") from erro
    if manifesto.get("formato") != VERSAO_DO_FORMATO:
        raise ErroDeBackup(
            f"Formato {manifesto.get('formato')} não é suportado; esta versão lê o {VERSAO_DO_FORMATO}."
        )
    return zf, manifesto


def verificar(origem: Path | BinaryIO) -> ResumoDeBackup:
    """Confere a integridade de cada tabela contra a impressão digital. Não toca no banco."""
    zf, manifesto = _abrir(origem)
    with zf:
        for nome, info in manifesto["tabelas"].items():
            try:
                bruto = zf.read(f"dados/{nome}.jsonl")
            except KeyError as erro:
                raise ErroDeBackup(f"Falta a tabela {nome} no arquivo.") from erro
            if hashlib.sha256(bruto).hexdigest() != info["sha256"]:
                raise ErroDeBackup(f"A tabela {nome} não bate com a impressão digital: arquivo alterado ou corrompido.")
            if len(bruto.splitlines()) != info["registros"]:
                raise ErroDeBackup(f"A tabela {nome} tem contagem diferente da declarada.")
    return ResumoDeBackup(
        manifesto["criado_em"],
        manifesto.get("revisao_do_esquema"),
        {k: v["registros"] for k, v in manifesto["tabelas"].items()},
    )


# ----------------------------------------------------------------- importar

def importar(engine: sa.Engine, origem: Path | BinaryIO, *, substituir: bool = False) -> ResumoDeBackup:
    """Carrega o backup. Tudo ou nada: qualquer erro desfaz a importação inteira.

    Por padrão **recusa** destino que já tenha dados. `substituir=True` esvazia o
    destino antes — irreversível, só com confirmação de quem chamou.
    """
    resumo = verificar(origem)
    if hasattr(origem, "seek"):
        origem.seek(0)
    zf, manifesto = _abrir(origem)
    tabelas = _tabelas()
    conhecidas = {t.name for t in tabelas}
    desconhecidas = set(manifesto["tabelas"]) - conhecidas
    if desconhecidas:
        raise ErroDeBackup(f"O backup tem tabelas que este CRM não conhece: {sorted(desconhecidas)}.")

    with zf, engine.connect() as conexao, conexao.begin():
        revisao_destino = _revisao(conexao)
        if resumo.revisao_do_esquema and revisao_destino and resumo.revisao_do_esquema != revisao_destino:
            raise ErroDeBackup(
                f"Esquemas diferentes: backup na revisão {resumo.revisao_do_esquema}, "
                f"destino na {revisao_destino}. Atualize o destino (alembic upgrade head) e tente de novo."
            )
        ocupadas = {
            t.name: n
            for t in tabelas
            if (n := conexao.execute(sa.select(sa.func.count()).select_from(t)).scalar())
        }
        if ocupadas and not substituir:
            raise ErroDeBackup(
                f"O destino já tem dados ({', '.join(f'{k}: {v}' for k, v in ocupadas.items())}). "
                "Importe num banco vazio ou confirme a substituição."
            )
        for t in reversed(tabelas):
            conexao.execute(sa.delete(t))

        for tabela in tabelas:
            nome = tabela.name
            if nome not in manifesto["tabelas"]:
                continue
            colunas = {c.name: c for c in tabela.columns}
            lote: list[dict] = []
            for bruto in zf.read(f"dados/{nome}.jsonl").splitlines():
                obj = json.loads(bruto)
                lote.append({k: _do_json(colunas[k], v) for k, v in obj.items() if k in colunas})
                if len(lote) >= _LOTE:
                    conexao.execute(sa.insert(tabela), lote)
                    lote = []
            if lote:
                conexao.execute(sa.insert(tabela), lote)

        if conexao.dialect.name == "postgresql":
            for t in tabelas:
                pk = list(t.primary_key.columns)
                if len(pk) == 1 and isinstance(pk[0].type, sa.Integer):
                    conexao.execute(
                        sa.text(
                            f"SELECT setval(pg_get_serial_sequence('{t.name}', '{pk[0].name}'), "
                            f"COALESCE((SELECT MAX({pk[0].name}) FROM {t.name}), 1), "
                            f"(SELECT COUNT(*) FROM {t.name}) > 0)"
                        )
                    )
    return resumo
