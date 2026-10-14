"""ID do lead no formulário do Meta

Amostra aprovada por Eduardo em 14/10/2026: os leads do formulário de anúncio do Meta entram sozinhos no CRM. O ID
do lead no Meta impede a entrada em dobro e ajuda a devolução de conversões. Só acrescenta.

Revisão: e3b9d5f1a7c4
Revisão anterior: d1f7b3a9c5e2
Criada em: 2026-10-14 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'e3b9d5f1a7c4'
down_revision: str | None = 'd1f7b3a9c5e2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('lead', sa.Column('meta_lead_id', sa.String(40)))
    op.create_index(op.f('ix_lead_meta_lead_id'), 'lead', ['meta_lead_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_lead_meta_lead_id'), 'lead')
    op.drop_column('lead', 'meta_lead_id')
