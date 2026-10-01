"""junta as duas linhas de migração: proposta em PowerPoint e contatos/parcelas/reajuste da Karine

As migrações da Karine (parcelas, reajuste, vínculo de contato) partiram do
questionário do site, em paralelo com a da proposta em PowerPoint. Esta não
muda nada no banco: só reúne as duas pontas, para o `alembic upgrade head`
servir tanto ao banco que já tem a proposta quanto ao que já tem os contatos.

Revisão: a1f0c2d93b5e
Revisões anteriores: 3e2336222a59, 5e8b3f1a2c47
Criada em: 2026-10-01 21:00:00
"""

from __future__ import annotations

revision: str = 'a1f0c2d93b5e'
down_revision: tuple[str, str] = ('3e2336222a59', '5e8b3f1a2c47')
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
