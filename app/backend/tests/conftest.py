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


@pytest.fixture
def engine() -> sa.Engine:
    motor = sa.create_engine("sqlite+pysqlite:///:memory:", future=True)

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
