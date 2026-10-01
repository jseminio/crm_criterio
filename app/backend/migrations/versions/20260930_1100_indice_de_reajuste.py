"""índice de reajuste da oportunidade

Revisão: 7c4e2a91d6b0
Revisão anterior: 3b1d5c0a9e27
Criada em: 2026-09-30 11:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = '7c4e2a91d6b0'
down_revision: str | None = '3b1d5c0a9e27'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('oportunidade', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reajuste', sa.Enum('IPCA (IBGE)', 'IGP-M (FGV)', 'Sem reajuste', name='indicedereajuste', native_enum=False, length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('oportunidade', schema=None) as batch_op:
        batch_op.drop_column('reajuste')
