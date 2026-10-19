"""Follow-up de parceiros

Amostra aprovada por Eduardo em 19/10/2026: o parceiro ganha o próximo follow-up (o que fazer e quando), que entra na
Agenda de follow-up, e o histórico dos follow-ups feitos. Acrescenta duas colunas em branco a `parceiro` e cria a tabela
`follow_up_de_parceiro`. Não mexe em dado existente.

Revisão: 9b4e2f6a1c37
Revisão anterior: 7d3a9c2e5f14
Criada em: 2026-10-19 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = '9b4e2f6a1c37'
down_revision: str | None = '7d3a9c2e5f14'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('parceiro', sa.Column('proximo_follow_up', sa.String(200), nullable=True))
    op.add_column('parceiro', sa.Column('proximo_follow_up_em', sa.Date(), nullable=True))
    op.create_index(op.f('ix_parceiro_proximo_follow_up_em'), 'parceiro', ['proximo_follow_up_em'])
    op.create_table(
        'follow_up_de_parceiro',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parceiro_id', sa.Integer(), nullable=False),
        sa.Column('feito_em', sa.Date(), nullable=False),
        sa.Column('resultado', sa.String(40), nullable=False),
        sa.Column('nota', sa.Text()),
        sa.Column('registrado_por', sa.String(200)),
        sa.Column('registrado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['parceiro_id'], ['parceiro.id'], name=op.f('fk_follow_up_de_parceiro_parceiro_id_parceiro')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_follow_up_de_parceiro')),
    )
    op.create_index(op.f('ix_follow_up_de_parceiro_parceiro_id'), 'follow_up_de_parceiro', ['parceiro_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_follow_up_de_parceiro_parceiro_id'), table_name='follow_up_de_parceiro')
    op.drop_table('follow_up_de_parceiro')
    op.drop_index(op.f('ix_parceiro_proximo_follow_up_em'), table_name='parceiro')
    op.drop_column('parceiro', 'proximo_follow_up_em')
    op.drop_column('parceiro', 'proximo_follow_up')
