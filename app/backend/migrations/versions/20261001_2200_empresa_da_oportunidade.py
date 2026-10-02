"""empresa da oportunidade

Pedido de Karine em 01/10/2026: a oportunidade é ligada a uma empresa já
cadastrada (escolhida na base de empresas), e o grupo vem dela.

As oportunidades que já existem e cujo grupo tem uma única empresa ganham
essa empresa (decisão de Karine: sem ambiguidade, preenche sozinho). As
demais ficam com a empresa em branco, para escolher no detalhe.

Revisão: b7d2e9f4a1c8
Revisão anterior: 9a1c7e4b2d63
Criada em: 2026-10-01 22:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'b7d2e9f4a1c8'
down_revision: str | None = '9a1c7e4b2d63'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('oportunidade', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_oportunidade_empresa_id'), ['empresa_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_oportunidade_empresa_id_empresa'), 'empresa', ['empresa_id'], ['id'])

    op.execute(
        "UPDATE oportunidade SET empresa_id = ("
        "  SELECT MIN(e.id) FROM empresa e WHERE e.grupo_id = oportunidade.grupo_id"
        ") WHERE empresa_id IS NULL AND ("
        "  SELECT COUNT(*) FROM empresa e WHERE e.grupo_id = oportunidade.grupo_id"
        ") = 1"
    )


def downgrade() -> None:
    with op.batch_alter_table('oportunidade', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_oportunidade_empresa_id_empresa'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_oportunidade_empresa_id'))
        batch_op.drop_column('empresa_id')
