"""Ambiente das migrações.

Lê o destino de `CRM_DATABASE_URL` — nunca do `alembic.ini`, que é versionado.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context

from crm.db.modelos import Base  # importa todas as entidades
from crm.db.sessao import criar_engine, url_do_banco

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A URL **não** é gravada em `config`. O `alembic.ini` é lido por configparser,
# que trata `%` como marcador de interpolação — e a senha chega até aqui
# codificada para endereço, cheia de `%23` e `%40`. Gravá-la ali derrubava a
# migração com "invalid interpolation syntax", sem relação aparente com a causa.
#
# Aqui a URL vai direto para quem precisa dela, e o `.ini` segue sem credencial
# nenhuma — que é como tem de ser num arquivo versionado.

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
        url=url_do_banco(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_opcoes_comuns(),
    )
    with context.begin_transaction():
        context.run_migrations()


def migrar_com_conexao() -> None:

    engine = criar_engine(url_do_banco())
    with engine.connect() as conexao:
        context.configure(connection=conexao, **_opcoes_comuns())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    migrar_sem_conexao()
else:
    migrar_com_conexao()
