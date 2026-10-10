"""data de envio da proposta na oportunidade

Pedido de Eduardo em 10/10/2026: o follow-up e o ciclo de vendas contavam da originação. A oportunidade ganha
`data_envio_proposta`. Só acrescenta a coluna; quem preenche as linhas que já existem (planilha de 2026: a
originação é o envio; propostas geradas e marcadas como enviadas) é a tarefa `2026_10_10_data_de_envio_da_proposta`.

Revisão: c3e7a1d5b9f2
Revisão anterior: b8d4f2a6c1e9
Criada em: 2026-10-10 17:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'c3e7a1d5b9f2'
down_revision: str | None = 'b8d4f2a6c1e9'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('oportunidade', sa.Column('data_envio_proposta', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('oportunidade', 'data_envio_proposta')
