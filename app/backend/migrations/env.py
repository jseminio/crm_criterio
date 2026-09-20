"""Ambiente das migrações.

Lê o destino de `CRM_DATABASE_URL` — nunca do `alembic.ini`, que é versionado.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from crm.db.modelos import Base  # importa todas as entidades
from crm.db.sessao import url_do_banco

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", url_do_banco())

#: O alvo da comparação automática. Tudo que estiver em `Base` é candidato.
target_metadata = Base.metadata


def _opcoes_comuns() -> dict:
    return {
        "target_metadata": target_metadata,
        # Sem isso, mudar o tamanho de um VARCHAR não gera migração e o esquema
        # do banco se afasta do código em silêncio.
        "compare_type": True,
        "compare_server_default": True,
        # Necessário no SQLite, que não sabe alterar coluna: o Alembic recria a
        # tabela. Inofensivo no PostgreSQL.
        "render_as_batch": True,
    }


def migrar_sem_conexao() -> None:
    """Gera o SQL sem tocar no banco — para revisar antes de aplicar."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_opcoes_comuns(),
    )
    with context.begin_transaction():
        context.run_migrations()


def migrar_com_conexao() -> None:
    engine = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with engine.connect() as conexao:
        context.configure(connection=conexao, **_opcoes_comuns())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    migrar_sem_conexao()
else:
    migrar_com_conexao()
