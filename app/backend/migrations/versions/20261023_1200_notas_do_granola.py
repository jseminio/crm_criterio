"""Notas do Granola

Amostra aprovada por Eduardo em 23/10/2026: as notas das pastas do Granola chegam sozinhas ao CRM e esperam "A usar"
na oportunidade ou no grupo, ou "Precisa de você". Cria a tabela `nota_do_granola`. Não mexe em dado existente.

Revisão: 3c8e1a7b5d92
Revisão anterior: 9b4e2f6a1c37
Criada em: 2026-10-23 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = '3c8e1a7b5d92'
down_revision: str | None = '9b4e2f6a1c37'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'nota_do_granola',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('granola_id', sa.String(60), nullable=False),
        sa.Column('tipo', sa.String(40), nullable=False),
        sa.Column('situacao', sa.String(40), nullable=False),
        sa.Column('titulo', sa.String(300), nullable=False),
        sa.Column('data', sa.Date(), nullable=False),
        sa.Column('participantes', sa.String(300)),
        sa.Column('link', sa.String(400)),
        sa.Column('resumo', sa.Text()),
        sa.Column('transcricao', sa.Text()),
        sa.Column('motivo', sa.String(200)),
        sa.Column('oportunidade_id', sa.Integer()),
        sa.Column('grupo_id', sa.Integer()),
        sa.Column('resolvida_por', sa.String(200)),
        sa.Column('resolvida_em', sa.DateTime(timezone=True)),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['oportunidade_id'], ['oportunidade.id'],
                                name=op.f('fk_nota_do_granola_oportunidade_id_oportunidade'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['grupo_id'], ['grupo_economico.id'],
                                name=op.f('fk_nota_do_granola_grupo_id_grupo_economico')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_nota_do_granola')),
        sa.UniqueConstraint('granola_id', name=op.f('uq_nota_do_granola_granola_id')),
    )
    op.create_index(op.f('ix_nota_do_granola_situacao'), 'nota_do_granola', ['situacao'])
    op.create_index(op.f('ix_nota_do_granola_oportunidade_id'), 'nota_do_granola', ['oportunidade_id'])
    op.create_index(op.f('ix_nota_do_granola_grupo_id'), 'nota_do_granola', ['grupo_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_nota_do_granola_grupo_id'), table_name='nota_do_granola')
    op.drop_index(op.f('ix_nota_do_granola_oportunidade_id'), table_name='nota_do_granola')
    op.drop_index(op.f('ix_nota_do_granola_situacao'), table_name='nota_do_granola')
    op.drop_table('nota_do_granola')
