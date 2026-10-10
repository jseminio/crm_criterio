"""data da saída efetiva no encerramento do contrato

Pedido de Eduardo em 10/10/2026: o cliente anuncia a saída e sai de fato 30 ou 60 dias depois. O evento de
encerramento ganha `data_da_saida`; o MRR cai e o churn conta nela. Só acrescenta a coluna. Quem preenche os
encerramentos antigos (saída = data do evento) é a tarefa `2026_10_10_saida_dos_encerramentos_antigos`.

Revisão: b8d4f2a6c1e9
Revisão anterior: a7c3e9f1b2d4
Criada em: 2026-10-10 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'b8d4f2a6c1e9'
down_revision: str | None = 'a7c3e9f1b2d4'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('evento_de_contrato', sa.Column('data_da_saida', sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column('evento_de_contrato', 'data_da_saida')
