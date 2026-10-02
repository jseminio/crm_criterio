"""metas dos indicadores editáveis (MRR e taxa de conversão)

Aprovado por Eduardo em 02/10/2026: a meta e o alerta deixam de ser fixos no código e passam a ser
alterados em Configurações › Metas. Só acrescenta: a tabela `meta_de_indicador`, já com os valores do
KPI oficial de hoje (MRR: meta R$ 400 mil, alerta R$ 200 mil; conversão: meta 50%, alerta 30%). A
funcionalidade "Configurações: metas" fica só com o Administrador, que já tem tudo.

Revisão: f6c2d8a4b1e9
Revisão anterior: e3a9c6b4d2f1
Criada em: 2026-10-02 20:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'f6c2d8a4b1e9'
down_revision: str | None = 'e3a9c6b4d2f1'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    tabela = op.create_table('meta_de_indicador',
    sa.Column('chave', sa.String(length=30), nullable=False),
    sa.Column('meta', sa.Numeric(14, 2), nullable=False),
    sa.Column('alerta', sa.Numeric(14, 2), nullable=False),
    sa.Column('alterado_por', sa.String(length=200), nullable=True),
    sa.Column('alterado_em', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('chave', name=op.f('pk_meta_de_indicador'))
    )
    op.bulk_insert(tabela, [
        {"chave": "mrr", "meta": 400000, "alerta": 200000},
        {"chave": "conversao", "meta": 50, "alerta": 30},
    ])


def downgrade() -> None:
    op.drop_table('meta_de_indicador')
