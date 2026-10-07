"""configuração do sistema pela tela

Pedido de Eduardo em 07/10/2026: chaves e integrações se configuram na tela, não no painel do
servidor. Só cria a tabela `configuracao_do_sistema` (vazia). Quem a preenche com o que já está nas
variáveis de ambiente é a tarefa de manutenção `2026_10_07_configuracao_para_a_tela`.

Revisão: e5c1a9d3b7f2
Revisão anterior: d2f8b4c6a1e3
Criada em: 2026-10-07 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'e5c1a9d3b7f2'
down_revision: str | None = 'd2f8b4c6a1e3'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'configuracao_do_sistema',
        sa.Column('chave', sa.String(length=80), primary_key=True),
        sa.Column('valor', sa.Text(), nullable=True),
        sa.Column('cifrado', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('alterado_por', sa.String(length=200), nullable=True),
        sa.Column('alterado_em', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('configuracao_do_sistema')
