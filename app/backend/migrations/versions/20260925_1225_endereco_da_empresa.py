"""endereco da empresa: logradouro, numero, complemento, bairro e cep

Revisão: b3f1c9a7d2e4
Revisão anterior: a701e6cc6b34
Criada em: 2026-09-25 12:25:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'b3f1c9a7d2e4'
down_revision: str | None = 'a701e6cc6b34'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('empresa', schema=None) as batch_op:
        batch_op.add_column(sa.Column('logradouro', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('numero', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('complemento', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('bairro', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('cep', sa.String(length=8), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('empresa', schema=None) as batch_op:
        batch_op.drop_column('cep')
        batch_op.drop_column('bairro')
        batch_op.drop_column('complemento')
        batch_op.drop_column('numero')
        batch_op.drop_column('logradouro')
