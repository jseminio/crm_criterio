"""ID do lead no formulário do Google Ads

Decisão de Eduardo em 14/10/2026: o lead do Google Ads entra pelo formulário de lead do próprio Google, como o do
Meta. O ID do envio impede a entrada em dobro. Só acrescenta.

Revisão: f5c1e7a3b9d6
Revisão anterior: e3b9d5f1a7c4
Criada em: 2026-10-14 21:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'f5c1e7a3b9d6'
down_revision: str | None = 'e3b9d5f1a7c4'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('lead', sa.Column('google_lead_id', sa.String(40)))
    op.create_index(op.f('ix_lead_google_lead_id'), 'lead', ['google_lead_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_lead_google_lead_id'), 'lead')
    op.drop_column('lead', 'google_lead_id')
