"""parcelas no ano do contrato

Decisão de Eduardo em 11/10/2026: todo contrato recorrente tem 13 parcelas (contábil, fiscal, DP e BPO Financeiro),
menos a Menino da Ilha, no formato antigo, sem 13ª. O contrato ganha `parcelas_no_ano` (13 por padrão); o MRR passa a
ser a parcela × parcelas ÷ 12. Quem põe 12 na Menino da Ilha é a tarefa `2026_10_11_menino_da_ilha_em_12_parcelas`.

Revisão: f2b6d8a4c0e1
Revisão anterior: e4a8c2f6b1d3
Criada em: 2026-10-11 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'f2b6d8a4c0e1'
down_revision: str | None = 'e4a8c2f6b1d3'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('contrato', sa.Column('parcelas_no_ano', sa.SmallInteger(), nullable=False, server_default='13'))


def downgrade() -> None:
    op.drop_column('contrato', 'parcelas_no_ano')
