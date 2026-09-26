"""Banco de teste: SQLite em memória, criado e destruído a cada teste.

**Por que não PostgreSQL aqui.** Não há PostgreSQL instalado nesta máquina —
é a pendência de segunda-feira. Os modelos usam só tipos genéricos, sem `JSONB`,
sem array e sem tipo nativo de lista, justamente para que o comportamento seja o
mesmo nos dois bancos.

⚠️ **Isso não substitui rodar contra o PostgreSQL.** Vale como verificação de
lógica, não de dialeto. O esquema precisa subir uma vez no Postgres real antes
de qualquer dado entrar.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Base


@pytest.fixture(autouse=True)
def ambiente_isolado(tmp_path, monkeypatch):
    """Nenhum teste enxerga o `.env` nem as variáveis da máquina de quem roda.

    Sem isto a suíte passa ou falha conforme o computador esteja configurado —
    e foi exatamente o que aconteceu: três testes de configuração passaram
    enquanto não havia `.env` e quebraram no instante em que ele foi criado.
    Teste que depende do ambiente local não prova nada.
    """
    from crm.agente.config import VARIAVEIS as DO_AGENTE
    from crm.db import sessao as modulo

    monkeypatch.setattr(modulo, "ARQUIVO_ENV", tmp_path / "sem-env")
    for nome in (modulo.VARIAVEL, *modulo.PARTES.values(), *DO_AGENTE.values()):
        monkeypatch.delenv(nome, raising=False)


@pytest.fixture
def engine() -> sa.Engine:
    # StaticPool com uma conexão só, compartilhada entre threads.
    #
    # SQLite em memória cria um banco **por conexão**: sem isto, o teste grava
    # num banco e a API, que roda noutra thread, lê de outro vazio. O padrão
    # `check_same_thread` do driver também proibiria o uso cruzado.
    motor = sa.create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        poolclass=sa.pool.StaticPool,
        connect_args={"check_same_thread": False},
    )

    # O SQLite ignora chave estrangeira por padrão. Sem isto, um teste passaria
    # com um vínculo que o PostgreSQL recusaria.
    @sa.event.listens_for(motor, "connect")
    def _ligar_chaves(conexao, _):
        conexao.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(motor)
    return motor


@pytest.fixture
def sessao(engine: sa.Engine) -> Session:
    with Session(engine, future=True) as aberta:
        yield aberta
