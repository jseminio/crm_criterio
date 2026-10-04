"""primeiro contato e aderência da promessa no lead

Amostra aprovada por Eduardo em 04/10/2026. Só acrescenta colunas vazias em `lead`: a data e hora do
primeiro contato, a aderência da promessa ("Bate", "Em parte", "Não bate"), sobre o quê a expectativa
não bateu e o que o lead esperava, em uma frase; e, em `plano_de_mrr`, o alvo de aderência. Os motivos novos ("Esperava outra coisa" no descarte,
"Expectativa diferente" na recusa) são texto: não pedem mudança no banco.

Revisão: c6e2a9d4f1b7
Revisão anterior: b3d9f2a6c8e1
Criada em: 2026-10-04 13:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'c6e2a9d4f1b7'
down_revision: str | None = 'b3d9f2a6c8e1'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('lead') as t:
        t.add_column(sa.Column('primeiro_contato_em', sa.DateTime(timezone=True), nullable=True))
        t.add_column(sa.Column('aderencia', sa.String(length=20), nullable=True))
        t.add_column(sa.Column('aderencia_sobre', sa.JSON().with_variant(JSONB(), 'postgresql'), nullable=True))
        t.add_column(sa.Column('aderencia_esperava', sa.String(length=300), nullable=True))
    with op.batch_alter_table('plano_de_mrr') as t:
        t.add_column(sa.Column('aderencia_alvo_pct', sa.Numeric(6, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('plano_de_mrr') as t:
        t.drop_column('aderencia_alvo_pct')
    with op.batch_alter_table('lead') as t:
        for nome in ('aderencia_esperava', 'aderencia_sobre', 'aderencia', 'primeiro_contato_em'):
            t.drop_column(nome)
