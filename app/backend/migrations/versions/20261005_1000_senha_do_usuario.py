"""senha do usuário (entrada com e-mail e senha)

Issue #89, decisão de Eduardo em 05/10/2026: o CRM passa a ter login próprio, com e-mail e senha, no
lugar da conta Microsoft. Só acrescenta a coluna vazia `usuario.senha_hash` (o hash scrypt, nunca a
senha). Quem já está em `usuario` continua, sem senha, até quem administra definir uma; a conta de
`CRM_ADMIN_EMAIL` ganha a senha inicial ao subir a API.

Revisão: f4a7c2e9b1d3
Revisão anterior: c6e2a9d4f1b7
Criada em: 2026-10-05 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'f4a7c2e9b1d3'
down_revision: str | None = 'c6e2a9d4f1b7'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('usuario') as t:
        t.add_column(sa.Column('senha_hash', sa.String(length=200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('usuario') as t:
        t.drop_column('senha_hash')
