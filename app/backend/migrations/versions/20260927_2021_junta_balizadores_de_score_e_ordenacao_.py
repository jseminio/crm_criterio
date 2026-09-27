"""junta balizadores de score e ordenacao nas tabelas

Revisão: a96818a796a7
Revisão anterior: 5935b1a6769e, bf638b8cce5f
Criada em: 2026-09-27 20:21:23.655430
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision: str = 'a96818a796a7'
down_revision: str | None = ('5935b1a6769e', 'bf638b8cce5f')
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
