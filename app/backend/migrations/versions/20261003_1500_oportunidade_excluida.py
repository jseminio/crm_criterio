"""oportunidades excluídas no CRM (a recarga da planilha não as traz de volta)

Pedido de Karine em 02/10/2026: o Funil ganhou "Excluir oportunidade". A da planilha de 2026
fica lembrada aqui pela chave de origem, para a recarga não a recriar. Só acrescenta a tabela.

Revisão: d4a8c2e6f1b9
Revisão anterior: c9f2a7d4e1b8
Criada em: 2026-10-03 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'd4a8c2e6f1b9'
down_revision: str | None = 'c9f2a7d4e1b8'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table('oportunidade_excluida',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chave_origem', sa.String(length=400), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('excluida_em', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_oportunidade_excluida')),
    sa.UniqueConstraint('chave_origem', name=op.f('uq_oportunidade_excluida_chave_origem'))
    )


def downgrade() -> None:
    op.drop_table('oportunidade_excluida')
