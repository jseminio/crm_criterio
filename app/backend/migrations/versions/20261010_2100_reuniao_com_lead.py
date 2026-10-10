"""reunião com o lead (Granola, template Potencial Cliente)

Amostra aprovada por Eduardo em 10/10/2026: o resumo da nota do Granola alimenta a contextualização e o
perfil do cliente na aba Proposta. Tabela nova; nada se perde.

Revisão: e4a8c2f6b1d3
Revisão anterior: d9f1b3c7e5a2
Criada em: 2026-10-10 21:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e4a8c2f6b1d3'
down_revision: str | None = 'd9f1b3c7e5a2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'reuniao_com_lead',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('oportunidade_id', sa.Integer(), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('participantes', sa.String(length=300), nullable=True),
        sa.Column('link_do_granola', sa.String(length=400), nullable=True),
        sa.Column('resumo_do_granola', sa.Text(), nullable=False),
        sa.Column('ciencia_da_gravacao', sa.Boolean(), nullable=False),
        sa.Column('contextualizacao', sa.Text(), nullable=True),
        sa.Column('perfil', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('registrada_por', sa.String(length=200), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['oportunidade_id'], ['oportunidade.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reuniao_com_lead_oportunidade_id'), 'reuniao_com_lead', ['oportunidade_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reuniao_com_lead_oportunidade_id'), table_name='reuniao_com_lead')
    op.drop_table('reuniao_com_lead')
