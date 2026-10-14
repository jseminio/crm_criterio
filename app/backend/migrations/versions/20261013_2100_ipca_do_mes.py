"""ipca do mês

Pedido de Eduardo em 13/10/2026: o reajuste anual dos contratos é em julho, pelo IPCA, e a série do IPCA fica
guardada no CRM. A tabela `ipca_do_mes` guarda a variação mensal (série 433 do Banco Central). Não há dado a mover:
a tabela se preenche sozinha na primeira vez que o reajuste é aberto.

Revisão: a7c3e9b5d2f4
Revisão anterior: a7c3e9d1b5f2
Criada em: 2026-10-13 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'a7c3e9b5d2f4'
down_revision: str | None = 'a7c3e9d1b5f2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'ipca_do_mes',
        sa.Column('mes', sa.Date(), nullable=False),
        sa.Column('variacao', sa.Numeric(7, 4), nullable=False),
        sa.Column('buscado_em', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('mes'),
    )


def downgrade() -> None:
    op.drop_table('ipca_do_mes')
