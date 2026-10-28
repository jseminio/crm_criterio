"""Data de competência, início do pagamento e parcelas do não recorrente

Pedido de Eduardo em 28/10/2026, na oportunidade e no contrato. Só acrescenta colunas vazias: nenhum dado existente
muda. Sem as datas, o CRM segue usando a assinatura.

Revisão: d8b2f4a6c1e3
Revisão anterior: c3e9a1f7d5b2
Criada em: 2026-10-28 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'd8b2f4a6c1e3'
down_revision: str | None = 'c3e9a1f7d5b2'
branch_labels: str | None = None
depends_on: str | None = None

TABELAS = ('oportunidade', 'contrato')


def upgrade() -> None:
    for tabela in TABELAS:
        op.add_column(tabela, sa.Column('data_competencia', sa.Date()))
        op.add_column(tabela, sa.Column('data_inicio_pagamento', sa.Date()))
        op.add_column(tabela, sa.Column('parcelas', sa.JSON().with_variant(JSONB(), 'postgresql')))


def downgrade() -> None:
    for tabela in TABELAS:
        op.drop_column(tabela, 'parcelas')
        op.drop_column(tabela, 'data_inicio_pagamento')
        op.drop_column(tabela, 'data_competencia')
