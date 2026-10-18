"""Assinatura eletrônica do contrato pela Clicksign (fase 1)

Amostra aprovada por Eduardo em 18/10/2026: o contrato vai para assinatura na Clicksign pelo CRM, e o aviso da
Clicksign ativa o contrato com a data da assinatura. Só cria a tabela `assinatura_de_contrato` (um envio por linha);
não mexe em dado existente.

Revisão: b4e7c1d9a2f3
Revisão anterior: a8d2c6e4f0b1
Criada em: 2026-10-18 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b4e7c1d9a2f3'
down_revision: str | None = 'a8d2c6e4f0b1'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'assinatura_de_contrato',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contrato_id', sa.Integer(), nullable=False),
        sa.Column('ambiente', sa.String(20), nullable=False),
        sa.Column('envelope_id', sa.String(64), nullable=False),
        sa.Column('documento_id', sa.String(64), nullable=False),
        sa.Column('nome_arquivo', sa.String(200), nullable=False),
        sa.Column('situacao', sa.String(20), nullable=False),
        sa.Column('prazo', sa.Date(), nullable=False),
        sa.Column('signatarios', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('enviado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('enviado_por', sa.String(200), nullable=False),
        sa.Column('concluido_em', sa.DateTime(timezone=True)),
        sa.Column('motivo', sa.String(400)),
        sa.Column('ultimo_evento', sa.String(60)),
        sa.Column('ultimo_evento_em', sa.DateTime(timezone=True)),
        sa.Column('assinado_base64', sa.Text()),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['contrato_id'], ['contrato.id'], name=op.f('fk_assinatura_de_contrato_contrato_id_contrato')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_assinatura_de_contrato')),
        sa.UniqueConstraint('envelope_id', name=op.f('uq_assinatura_de_contrato_envelope_id')),
    )
    op.create_index(op.f('ix_assinatura_de_contrato_contrato_id'), 'assinatura_de_contrato', ['contrato_id'])
    op.create_index(op.f('ix_assinatura_de_contrato_documento_id'), 'assinatura_de_contrato', ['documento_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_assinatura_de_contrato_documento_id'), 'assinatura_de_contrato')
    op.drop_index(op.f('ix_assinatura_de_contrato_contrato_id'), 'assinatura_de_contrato')
    op.drop_table('assinatura_de_contrato')
