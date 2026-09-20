"""Conexão com o banco, lida do ambiente.

**Nenhuma credencial mora no código.** A regra do vortexOS é explícita: segredo
só em `.env` ou cofre, nunca em código, JSON, nota ou log. Este módulo lê a
variável e não guarda nem imprime o que leu.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

__all__ = [
    "url_do_banco",
    "criar_engine",
    "criar_fabrica_de_sessao",
    "sessao",
    "VARIAVEL",
    "ARQUIVO_ENV",
    "BancoNaoConfigurado",
]

VARIAVEL = "CRM_DATABASE_URL"

#: Só para teste e exploração local. Não serve de produção: não persiste.
URL_DE_MEMORIA = "sqlite+pysqlite:///:memory:"


class BancoNaoConfigurado(RuntimeError):
    """Levantada quando ninguém disse onde está o banco.

    Falha visível, como manda a RN-16: cair aqui com uma mensagem clara é melhor
    do que escrever dados de cliente num SQLite improvisado que ninguém sabe que
    existe.
    """


#: Onde procurar o arquivo de ambiente: a raiz do backend.
ARQUIVO_ENV = Path(__file__).resolve().parents[3] / ".env"


def _ler_do_arquivo(arquivo: Path | None = None) -> str | None:
    """Lê `CRM_DATABASE_URL` do `.env`, quando ele existir.

    Evita que cada comando precise exportar a variável à mão — e, principalmente,
    evita que alguém a cole numa linha de comando, onde ela ficaria no histórico
    do shell. O `.env` é ignorado pelo git.

    **O valor lido nunca é registrado em log nem devolvido em mensagem de erro.**
    Formato aceito: uma atribuição por linha, `#` comenta, aspas são opcionais.
    """
    arquivo = arquivo or ARQUIVO_ENV
    if not arquivo.is_file():
        return None
    try:
        conteudo = arquivo.read_text(encoding="utf-8")
    except OSError:
        return None
    for linha in conteudo.splitlines():
        limpa = linha.strip()
        if not limpa or limpa.startswith("#") or "=" not in limpa:
            continue
        chave, _, valor = limpa.partition("=")
        if chave.strip() != VARIAVEL:
            continue
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        return valor or None
    return None


def url_do_banco(padrao: str | None = None) -> str:
    """Devolve a URL de conexão: variável de ambiente, depois `.env`, depois `padrao`.

    `padrao` existe para o teste passar a URL em memória de propósito — nunca
    para produção adivinhar um destino.
    """
    url = os.environ.get(VARIAVEL) or _ler_do_arquivo() or padrao
    if not url:
        raise BancoNaoConfigurado(
            f"{VARIAVEL} não está definida, e {ARQUIVO_ENV.name} não a traz. "
            f"Aponte-a para o PostgreSQL, por exemplo "
            f"postgresql+psycopg://usuario@localhost:5432/criterio_crm, e "
            f"mantenha o valor em .env — nunca no código."
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
