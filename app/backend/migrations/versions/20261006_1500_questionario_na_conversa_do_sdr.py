"""questionário de volumetria na conversa do SDR de IA

Pedido de Eduardo em 06/10/2026: a IA agradece quem respondeu o questionário e lembra, uma vez, quem
não respondeu em 2 dias úteis. Só acrescenta três colunas vazias em `lead`: quando a IA enviou o link,
quando lembrou e quando agradeceu. Se o lead respondeu, o CRM já sabe por `questionario_recebido`.

Revisão: d2f8b4c6a1e3
Revisão anterior: b8d3f1a6c2e4
Criada em: 2026-10-06 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'd2f8b4c6a1e3'
down_revision: str | None = 'b8d3f1a6c2e4'
branch_labels: str | None = None
depends_on: str | None = None

_COLUNAS = ('questionario_enviado_em', 'questionario_lembrado_em', 'questionario_agradecido_em')


def upgrade() -> None:
    with op.batch_alter_table('lead') as t:
        for nome in _COLUNAS:
            t.add_column(sa.Column(nome, sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('lead') as t:
        for nome in reversed(_COLUNAS):
            t.drop_column(nome)
