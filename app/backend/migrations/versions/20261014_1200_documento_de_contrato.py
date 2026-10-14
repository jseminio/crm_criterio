"""documento de contrato

Aprovado por Eduardo em 14/10/2026: o contrato recorrente é gerado em Word pelo CRM, a partir de uma matriz com
marcadores, como a proposta. Três tabelas novas: `matriz_de_contrato`, `configuracao_de_contrato` (próximo número,
quem assina, vencimento e excedente do DP) e `documento_de_contrato`. Nada existente muda.

Revisão: c9e5a1d7f4b6
Revisão anterior: b8d4f0c6e3a5
Criada em: 2026-10-14 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c9e5a1d7f4b6'
down_revision: str | None = 'b8d4f0c6e3a5'
branch_labels: str | None = None
depends_on: str | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        'matriz_de_contrato',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('modelo', sa.String(length=40), nullable=False),
        sa.Column('nome_arquivo', sa.String(length=200), nullable=False),
        sa.Column('conteudo_base64', sa.Text(), nullable=False),
        sa.Column('enviada_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('enviada_por', sa.String(length=200), nullable=False),
        sa.Column('encontrados', _JSON, nullable=False),
        sa.Column('faltando', _JSON, nullable=False),
        sa.Column('desconhecidos', _JSON, nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_matriz_de_contrato_modelo', 'matriz_de_contrato', ['modelo'])
    op.create_table(
        'configuracao_de_contrato',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proximo_numero', sa.Integer(), nullable=False),
        sa.Column('signatario', sa.String(length=200), nullable=True),
        sa.Column('cargo_signatario', sa.String(length=100), nullable=True),
        sa.Column('cpf_signatario', sa.String(length=14), nullable=True),
        sa.Column('vencimento', sa.SmallInteger(), nullable=False),
        sa.Column('excedente_dp', sa.Numeric(14, 2), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'documento_de_contrato',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contrato_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('ano', sa.SmallInteger(), nullable=False),
        sa.Column('matriz_id', sa.Integer(), nullable=False),
        sa.Column('valores', _JSON, nullable=False),
        sa.Column('gerado_por', sa.String(length=200), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['contrato_id'], ['contrato.id']),
        sa.ForeignKeyConstraint(['matriz_id'], ['matriz_de_contrato.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ano', 'numero', name='uq_documento_de_contrato_ano_numero'),
    )
    op.create_index('ix_documento_de_contrato_contrato_id', 'documento_de_contrato', ['contrato_id'])


def downgrade() -> None:
    op.drop_index('ix_documento_de_contrato_contrato_id', 'documento_de_contrato')
    op.drop_table('documento_de_contrato')
    op.drop_table('configuracao_de_contrato')
    op.drop_index('ix_matriz_de_contrato_modelo', 'matriz_de_contrato')
    op.drop_table('matriz_de_contrato')
