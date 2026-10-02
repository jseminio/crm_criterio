"""ficha da oportunidade e pendências da proposta (E4)

Pedido de Eduardo em 02/10/2026, amostra aprovada: a ficha guarda o que se corrigiu na entrevista
(a resposta do questionário continua no questionário recebido) e a lista do que falta para a
proposta ganha responsável e prazo. Só acrescenta: nada existente muda.

Revisão: c4e1a7d2f9b3
Revisão anterior: b7d2e9f4a1c8
Criada em: 2026-10-02 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c4e1a7d2f9b3'
down_revision: str | None = 'b7d2e9f4a1c8'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('oportunidade', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ficha', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
                                      server_default=sa.text("'{}'"), nullable=False))

    op.create_table('pendencia_da_proposta',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('oportunidade_id', sa.Integer(), nullable=False),
    sa.Column('chave', sa.String(length=40), nullable=True),
    sa.Column('descricao', sa.String(length=300), nullable=True),
    sa.Column('responsavel', sa.String(length=60), nullable=True),
    sa.Column('prazo', sa.Date(), nullable=True),
    sa.Column('criada_por', sa.String(length=60), nullable=False),
    sa.Column('feita_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('feita_por', sa.String(length=60), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['oportunidade_id'], ['oportunidade.id'], name=op.f('fk_pendencia_da_proposta_oportunidade_id_oportunidade'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pendencia_da_proposta')),
    sa.UniqueConstraint('oportunidade_id', 'chave', name='uq_pendencia_oportunidade_chave')
    )
    with op.batch_alter_table('pendencia_da_proposta', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pendencia_da_proposta_oportunidade_id'), ['oportunidade_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('pendencia_da_proposta', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pendencia_da_proposta_oportunidade_id'))
    op.drop_table('pendencia_da_proposta')
    with op.batch_alter_table('oportunidade', schema=None) as batch_op:
        batch_op.drop_column('ficha')
