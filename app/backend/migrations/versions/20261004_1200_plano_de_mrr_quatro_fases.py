"""premissas das quatro fases no plano de MRR

Inteligência de Conversão, quatro fases (Atração, Engajamento, Conversão e Pós-venda), pedido de
Eduardo em 04/10/2026, sobre a amostra aprovada em 03/10/2026. Só acrescenta colunas vazias em
`plano_de_mrr`: as taxas do funil (lead no ICP → reunião, reunião → proposta, conversão) e os alvos
(% no ICP, indicações por mês, horas até o primeiro contato, ciclo de venda). Vazias, o previsto usa
a taxa histórica do CRM; sem histórico, a tela diz "sem dado".

Revisão: b3d9f2a6c8e1
Revisão anterior: e4a7c1b9d2f6
Criada em: 2026-10-04 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'b3d9f2a6c8e1'
down_revision: str | None = 'e4a7c1b9d2f6'
branch_labels: str | None = None
depends_on: str | None = None

COLUNAS = (
    "taxa_lead_reuniao_pct", "taxa_reuniao_proposta_pct", "taxa_conversao_pct", "icp_alvo_pct",
    "indicacoes_por_mes", "primeiro_contato_horas", "ciclo_alvo_dias",
)


def upgrade() -> None:
    with op.batch_alter_table('plano_de_mrr') as t:
        for nome in COLUNAS:
            t.add_column(sa.Column(nome, sa.Numeric(6, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('plano_de_mrr') as t:
        for nome in reversed(COLUNAS):
            t.drop_column(nome)
