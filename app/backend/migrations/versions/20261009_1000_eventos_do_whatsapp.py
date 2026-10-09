"""eventos do webhook do WhatsApp

Demanda de 09/10/2026: o CRM passa a receber as respostas do lead pelo webhook da Meta. Só cria a
tabela `evento_do_whatsapp` (vazia); nenhum dado existente muda.

Revisão: f7a3c2e9d1b4
Revisão anterior: e5c1a9d3b7f2
Criada em: 2026-10-09 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f7a3c2e9d1b4'
down_revision: str | None = 'e5c1a9d3b7f2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'evento_do_whatsapp',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('externo_id', sa.String(length=200), nullable=False),
        sa.Column('recebido_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('telefone', sa.String(length=20), nullable=False),
        sa.Column('situacao', sa.String(length=40), nullable=False),
        sa.Column('lead_id', sa.Integer(), sa.ForeignKey('lead.id', name='fk_evento_do_whatsapp_lead_id_lead'), nullable=True),
        sa.Column('mensagem_id', sa.Integer(),
                  sa.ForeignKey('mensagem_do_sdr.id', name='fk_evento_do_whatsapp_mensagem_id_mensagem_do_sdr'), nullable=True),
        sa.Column('conteudo', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.UniqueConstraint('externo_id', name='uq_evento_do_whatsapp_externo_id'),
    )
    op.create_index('ix_evento_do_whatsapp_recebido_em', 'evento_do_whatsapp', ['recebido_em'])
    op.create_index('ix_evento_do_whatsapp_telefone', 'evento_do_whatsapp', ['telefone'])
    op.create_index('ix_evento_do_whatsapp_lead_id', 'evento_do_whatsapp', ['lead_id'])


def downgrade() -> None:
    op.drop_table('evento_do_whatsapp')
