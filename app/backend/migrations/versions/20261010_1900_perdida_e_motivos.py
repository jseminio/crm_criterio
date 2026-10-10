"""descrição do motivo de perda

Decisão de Eduardo em 10/10/2026: "Recusada" e "Perdido" viram uma etapa só, "Perdida", com o motivo obrigatório
("Outro" pede a descrição). Só acrescenta a coluna da descrição. Quem leva as linhas antigas para "Perdida" e os
motivos para os nomes aprovados é a tarefa `2026_10_10_perdida_e_motivos`.

Revisão: d9f1b3c7e5a2
Revisão anterior: c3e7a1d5b9f2
Criada em: 2026-10-10 19:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'd9f1b3c7e5a2'
down_revision: str | None = 'c3e7a1d5b9f2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('oportunidade', sa.Column('motivo_recusa_detalhe', sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column('oportunidade', 'motivo_recusa_detalhe')
