"""Envelopes da Clicksign: o enviado pelo CRM e o feito fora

Amostras aprovadas por Eduardo em 18/10/2026 e unificadas no mesmo dia: o contrato vai para assinatura na Clicksign
pelo CRM, e o aviso da Clicksign ativa o contrato com a data da assinatura; o envelope feito direto na Clicksign, com
número do CRM no nome, tem o PDF assinado levado à conferência. Só cria a tabela `envelope_do_clicksign`; não mexe em
dado existente.

Revisão: b4e7c1d9a2f3
Revisão anterior: c3e9b1d7a5f2
Criada em: 2026-10-18 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b4e7c1d9a2f3'
down_revision: str | None = 'c3e9b1d7a5f2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'envelope_do_clicksign',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('origem', sa.String(10), nullable=False),
        sa.Column('contrato_id', sa.Integer()),
        sa.Column('oportunidade_id', sa.Integer()),
        sa.Column('ambiente', sa.String(20), nullable=False),
        sa.Column('envelope_id', sa.String(64)),
        sa.Column('documento_id', sa.String(64), nullable=False),
        sa.Column('nome_arquivo', sa.String(200), nullable=False),
        sa.Column('situacao', sa.String(20), nullable=False),
        sa.Column('prazo', sa.Date()),
        sa.Column('signatarios', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('enviado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('enviado_por', sa.String(200), nullable=False),
        sa.Column('concluido_em', sa.DateTime(timezone=True)),
        sa.Column('motivo', sa.String(400)),
        sa.Column('ultimo_evento', sa.String(60)),
        sa.Column('ultimo_evento_em', sa.DateTime(timezone=True)),
        sa.Column('documento_anexado_id', sa.Integer()),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['contrato_id'], ['contrato.id'], name=op.f('fk_envelope_do_clicksign_contrato_id_contrato')),
        sa.ForeignKeyConstraint(['oportunidade_id'], ['oportunidade.id'],
                                name=op.f('fk_envelope_do_clicksign_oportunidade_id_oportunidade')),
        sa.ForeignKeyConstraint(['documento_anexado_id'], ['documento_anexado.id'],
                                name=op.f('fk_envelope_do_clicksign_documento_anexado_id_documento_anexado')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_envelope_do_clicksign')),
        sa.UniqueConstraint('envelope_id', name=op.f('uq_envelope_do_clicksign_envelope_id')),
        sa.UniqueConstraint('documento_id', name=op.f('uq_envelope_do_clicksign_documento_id')),
    )
    op.create_index(op.f('ix_envelope_do_clicksign_contrato_id'), 'envelope_do_clicksign', ['contrato_id'])
    op.create_index(op.f('ix_envelope_do_clicksign_oportunidade_id'), 'envelope_do_clicksign', ['oportunidade_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_envelope_do_clicksign_oportunidade_id'), 'envelope_do_clicksign')
    op.drop_index(op.f('ix_envelope_do_clicksign_contrato_id'), 'envelope_do_clicksign')
    op.drop_table('envelope_do_clicksign')
