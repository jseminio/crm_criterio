"""conversões devolvidas às plataformas de anúncio

Amostra aprovada por Eduardo em 14/10/2026: o CRM devolve ao Meta Ads e ao Google Ads quando um lead de tráfego
pago é qualificado, marca reunião ou fecha contrato. Uma linha por lead, evento e plataforma, para nada sair duas
vezes. Só acrescenta.

Revisão: d1f7b3a9c5e2
Revisão anterior: c9e5a1d7f4b6
Criada em: 2026-10-14 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'd1f7b3a9c5e2'
down_revision: str | None = 'c9e5a1d7f4b6'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'conversao_enviada',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('evento', sa.String(30), nullable=False),
        sa.Column('plataforma', sa.String(30), nullable=False),
        sa.Column('situacao', sa.String(10), nullable=False),
        sa.Column('momento_do_evento', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valor', sa.Numeric(14, 2)),
        sa.Column('tentativas', sa.SmallInteger(), nullable=False),
        sa.Column('enviado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resposta', sa.String(500)),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("situacao IN ('enviado', 'recusado', 'falhou')",
                           name=op.f('ck_conversao_enviada_situacao_da_conversao')),
        sa.ForeignKeyConstraint(['lead_id'], ['lead.id'], name=op.f('fk_conversao_enviada_lead_id_lead'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_conversao_enviada')),
        sa.UniqueConstraint('lead_id', 'evento', 'plataforma', name='uq_conversao_lead_evento_plataforma'),
    )
    op.create_index(op.f('ix_conversao_enviada_lead_id'), 'conversao_enviada', ['lead_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_conversao_enviada_lead_id'), 'conversao_enviada')
    op.drop_table('conversao_enviada')
