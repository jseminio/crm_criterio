"""Quem está mexendo, e o histórico de alterações gravado sozinho (E1, 02/10/2026).

A entrada (`crm.acesso.entrada`) põe a pessoa em `usuario_atual` a cada pedido. Depois de cada
gravação no banco, o ouvinte `registrar` escreve uma linha de `registro_de_alteracao` por campo que
mudou: quem, quando, antes e depois. Sem ninguém identificado (o CRM sem login, ou um script), não
grava nada: o histórico começa no dia em que o login entrar no ar (decisão de Eduardo, 02/10/2026).
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from crm.db.base import agora

__all__ = ["UsuarioAtual", "usuario_atual", "ligar"]

# Campos que não dizem nada a quem lê o histórico, ou que são grandes demais para ele.
_IGNORADOS = {"criado_em", "atualizado_em", "conteudo_base64", "pdf_base64", "respostas", "avaliacao_do_site", "campos_do_crm", "transcricao"}
_TABELAS_IGNORADAS = {"registro_de_alteracao", "execucao_de_carga", "ocorrencia_de_carga"}
_LIMITE = 1000


@dataclass(frozen=True)
class UsuarioAtual:
    email: str
    nome: str | None
    perfil: str
    administrador: bool
    permissoes: frozenset[str] = field(default_factory=frozenset)
    rota: str | None = None

    def pode(self, *permissoes: str) -> bool:
        """Basta uma; sem nenhuma pedida, qualquer um que entrou pode."""
        return self.administrador or not permissoes or any(p in self.permissoes for p in permissoes)


usuario_atual: ContextVar[UsuarioAtual | None] = ContextVar("usuario_atual", default=None)


def _texto(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, Enum):
        v = v.value
    elif isinstance(v, (datetime, date)):
        v = v.isoformat()
    elif isinstance(v, Decimal):
        v = str(v)
    elif isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
    texto = str(v)
    return texto if len(texto) <= _LIMITE else texto[: _LIMITE - 1] + "…"


def _descricao(obj: Any) -> str | None:
    for nome in ("nome", "razao_social", "titulo", "descricao", "email", "escopo", "nome_arquivo"):
        v = getattr(obj, nome, None)
        if isinstance(v, str) and v.strip():
            return v.strip()[:200]
    return None


def _id(obj: Any) -> int | None:
    v = getattr(obj, "id", None)
    return v if isinstance(v, int) else None


def _linhas(sessao: Session, quem: UsuarioAtual) -> list[dict[str, Any]]:
    quando = agora()
    base = {"quando": quando, "usuario_email": quem.email, "usuario_nome": quem.nome, "rota": quem.rota}
    linhas: list[dict[str, Any]] = []
    for obj in sessao.new:
        tabela = getattr(obj, "__tablename__", None)
        if tabela and tabela not in _TABELAS_IGNORADAS:
            linhas.append({**base, "acao": "criou", "tabela": tabela, "registro_id": _id(obj),
                           "descricao": _descricao(obj), "campo": None, "antes": None, "depois": None})
    for obj in sessao.dirty:
        tabela = getattr(obj, "__tablename__", None)
        if not tabela or tabela in _TABELAS_IGNORADAS or not sessao.is_modified(obj, include_collections=False):
            continue
        estado = inspect(obj)
        for atributo in estado.mapper.column_attrs:
            nome = atributo.key
            if nome in _IGNORADOS:
                continue
            historia = estado.attrs[nome].history
            if not historia.has_changes():
                continue
            antes = historia.deleted[0] if historia.deleted else None
            depois = historia.added[0] if historia.added else None
            if _texto(antes) == _texto(depois):
                continue
            linhas.append({**base, "acao": "alterou", "tabela": tabela, "registro_id": _id(obj),
                           "descricao": _descricao(obj), "campo": nome, "antes": _texto(antes), "depois": _texto(depois)})
    for obj in sessao.deleted:
        tabela = getattr(obj, "__tablename__", None)
        if tabela and tabela not in _TABELAS_IGNORADAS:
            linhas.append({**base, "acao": "excluiu", "tabela": tabela, "registro_id": _id(obj),
                           "descricao": _descricao(obj), "campo": None, "antes": None, "depois": None})
    return linhas


def ligar() -> None:
    """Liga o ouvinte uma vez, para todas as sessões. Depois do flush os registros novos já têm id, e
    o que mudou ainda está à vista; a gravação vai direto na conexão, na mesma transação."""
    from crm.db.modelos import RegistroDeAlteracao

    if event.contains(Session, "after_flush", _depois_da_gravacao):
        return
    _tabela[:] = [RegistroDeAlteracao.__table__]
    event.listen(Session, "after_flush", _depois_da_gravacao)


_tabela: list[sa.Table] = []


def _depois_da_gravacao(sessao: Session, _contexto) -> None:
    quem = usuario_atual.get()
    if quem is None:
        return
    linhas = _linhas(sessao, quem)
    if linhas:
        sessao.connection().execute(_tabela[0].insert(), linhas)
