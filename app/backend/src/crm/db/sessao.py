"""Conexão com o banco, lida do ambiente.

**Nenhuma credencial mora no código.** A regra do vortexOS é explícita: segredo
só em `.env` ou cofre, nunca em código, JSON, nota ou log. Este módulo lê a
variável e não guarda nem imprime o que leu.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

__all__ = ["url_do_banco", "criar_engine", "criar_fabrica_de_sessao", "sessao", "VARIAVEL"]

VARIAVEL = "CRM_DATABASE_URL"

#: Só para teste e exploração local. Não serve de produção: não persiste.
URL_DE_MEMORIA = "sqlite+pysqlite:///:memory:"


class BancoNaoConfigurado(RuntimeError):
    """Levantada quando ninguém disse onde está o banco.

    Falha visível, como manda a RN-16: cair aqui com uma mensagem clara é melhor
    do que escrever dados de cliente num SQLite improvisado que ninguém sabe que
    existe.
    """


def url_do_banco(padrao: str | None = None) -> str:
    """Devolve a URL de conexão do ambiente.

    `padrao` existe para o teste passar a URL em memória de propósito — nunca
    para produção adivinhar um destino.
    """
    url = os.environ.get(VARIAVEL) or padrao
    if not url:
        raise BancoNaoConfigurado(
            f"{VARIAVEL} não está definida. Aponte-a para o PostgreSQL, por "
            f"exemplo postgresql+psycopg://usuario@localhost/criterio_crm, "
            f"e mantenha o valor em .env — nunca no código."
        )
    return url


def criar_engine(url: str | None = None, *, echo: bool = False) -> sa.Engine:
    """Cria a engine. `echo=True` mostra o SQL — só para depurar, nunca em uso real."""
    destino = url or url_do_banco()
    parametros: dict = {"echo": echo, "future": True}
    if destino.startswith("postgresql"):
        # Devolve conexão morta ao pool antes que o servidor a derrube.
        parametros["pool_pre_ping"] = True
    return sa.create_engine(destino, **parametros)


def criar_fabrica_de_sessao(engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@contextmanager
def sessao(fabrica: sessionmaker[Session]) -> Iterator[Session]:
    """Abre uma sessão que confirma no fim ou desfaz por inteiro no erro."""
    sessao_aberta = fabrica()
    try:
        yield sessao_aberta
        sessao_aberta.commit()
    except Exception:
        sessao_aberta.rollback()
        raise
    finally:
        sessao_aberta.close()
