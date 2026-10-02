"""contrato: o valor é bruto ou líquido

Aprovado por Eduardo em 02/10/2026: cada contrato diz se o preço já inclui o imposto, e o MRR soma
em bruto (o líquido entra com o imposto dos Parâmetros). Só acrescenta a coluna `base_do_valor`.
Preenche "liquido" só onde não há dúvida: o contrato que nasceu de uma oportunidade com proposta
gerada no CRM, que grava o líquido no preço (01/10/2026). Os outros ficam vazios, para a pessoa
dizer em cada contrato.

Revisão: c9f2a7d4e1b8
Revisão anterior: b8e4f1a6d3c7
Criada em: 2026-10-03 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'c9f2a7d4e1b8'
down_revision: str | None = 'b8e4f1a6d3c7'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('contrato') as t:
        t.add_column(sa.Column('base_do_valor', sa.String(length=10), nullable=True))
    op.execute(
        "UPDATE contrato SET base_do_valor = 'liquido' WHERE oportunidade_id IS NOT NULL AND EXISTS "
        "(SELECT 1 FROM proposta p WHERE p.oportunidade_id = contrato.oportunidade_id AND p.valor_liquido IS NOT NULL)"
    )


def downgrade() -> None:
    with op.batch_alter_table('contrato') as t:
        t.drop_column('base_do_valor')
