"""permissão de excluir contrato no perfil Comercial

Amostra aprovada por Karine em 30/10/2026: excluir contrato vale para Administrador e Comercial. Só
acrescenta "contratos.excluir" ao perfil Comercial já gravado; o Administrador já tem tudo.

Revisão: f1c7a3e9b5d2
Revisão anterior: d8b2f4a6c1e3
Criada em: 2026-10-30 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'f1c7a3e9b5d2'
down_revision: str | None = 'd8b2f4a6c1e3'
branch_labels: str | None = None
depends_on: str | None = None

_NOVA = "contratos.excluir"


def _permissoes_do_comercial(mudar) -> None:
    conexao = op.get_bind()
    perfil = sa.table("perfil", sa.column("id", sa.Integer), sa.column("nome", sa.String),
                      sa.column("permissoes", sa.JSON))
    linha = conexao.execute(sa.select(perfil.c.id, perfil.c.permissoes).where(perfil.c.nome == "Comercial")).first()
    if linha is None:
        return
    novas = mudar(list(linha.permissoes or []))
    conexao.execute(perfil.update().where(perfil.c.id == linha.id).values(permissoes=novas))


def upgrade() -> None:
    _permissoes_do_comercial(lambda ps: sorted(set(ps) | {_NOVA}))


def downgrade() -> None:
    _permissoes_do_comercial(lambda ps: [p for p in ps if p != _NOVA])
