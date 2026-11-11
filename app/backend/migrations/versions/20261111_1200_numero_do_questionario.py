"""número do envio, chave de quem preencheu e combinação no questionário recebido

Decisão de Eduardo em 11/11/2026: o questionário passa a ter um link único, servido pelo próprio CRM, e cada envio
ganha um número (Q-1001…) e a chave de quem preencheu (CNPJ + primeiro nome). Quando a mesma empresa envia mais de
uma vez, os envios ficam todos guardados e quem resolve compara e combina (`combinacao`). Os questionários que já
existem recebem número e chave pela tarefa `2026_11_11_numero_dos_questionarios`.

Revisão: a3d5f7b9c1e2
Revisão anterior: f1c7a3e9b5d2
Criada em: 2026-11-11 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a3d5f7b9c1e2'
down_revision: str | None = 'f1c7a3e9b5d2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("questionario_recebido") as t:
        t.add_column(sa.Column("numero", sa.Integer(), nullable=True))
        t.add_column(sa.Column("chave_do_preenchedor", sa.String(length=80), nullable=True))
        t.add_column(sa.Column("combinacao", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True))
        t.create_unique_constraint("uq_questionario_recebido_numero", ["numero"])
        t.create_index("ix_questionario_recebido_chave_do_preenchedor", ["chave_do_preenchedor"])


def downgrade() -> None:
    with op.batch_alter_table("questionario_recebido") as t:
        t.drop_index("ix_questionario_recebido_chave_do_preenchedor")
        t.drop_constraint("uq_questionario_recebido_numero", type_="unique")
        t.drop_column("combinacao")
        t.drop_column("chave_do_preenchedor")
        t.drop_column("numero")
