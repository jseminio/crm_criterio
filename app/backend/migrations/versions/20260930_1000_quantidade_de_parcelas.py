"""quantidade de parcelas da oportunidade

Revisão: 3b1d5c0a9e27
Revisão anterior: 3b26e19f7eeb
Criada em: 2026-09-30 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = '3b1d5c0a9e27'
down_revision: str | None = '3b26e19f7eeb'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('oportunidade', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantidade_parcelas', sa.SmallInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('oportunidade', schema=None) as batch_op:
        batch_op.drop_column('quantidade_parcelas')
