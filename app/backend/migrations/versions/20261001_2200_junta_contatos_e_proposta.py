"""junta as migrações de contatos (Karine) e da proposta em PowerPoint

Revisão: 9a4c6e1b7d20
Revisões anteriores: 5e8b3f1a2c47 (vínculo de contato), 3e2336222a59 (proposta em PowerPoint)
Criada em: 2026-10-01 22:00

As duas linhas partiram da mesma revisão (3b26e19f7eeb) e não mexem nas mesmas
tabelas. Esta revisão só junta as pontas para o `alembic upgrade head` ter um
destino único; não altera esquema nem dado.
"""

from __future__ import annotations

revision: str = '9a4c6e1b7d20'
down_revision: tuple[str, ...] = ('5e8b3f1a2c47', '3e2336222a59')
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
