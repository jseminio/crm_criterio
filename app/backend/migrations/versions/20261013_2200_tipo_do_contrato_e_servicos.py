"""tipo do contrato e contrato do serviço

Aprovado por Eduardo em 13/10/2026: a tabela de serviços orienta o contrato. O contrato ganha `recorrente`
(perguntado na conversão, com o tipo do serviço como sugestão) e a tabela `contrato_do_servico` guarda o modelo de
contrato e o reajuste escolhidos por serviço. Os contratos de antes são preenchidos pela tarefa
`2026_10_13_tipo_dos_contratos`.

Revisão: b8d4f0c6e3a5
Revisão anterior: a7c3e9b5d2f4
Criada em: 2026-10-13 22:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'b8d4f0c6e3a5'
down_revision: str | None = 'a7c3e9b5d2f4'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('contrato', sa.Column('recorrente', sa.Boolean(), nullable=True))
    op.create_table(
        'contrato_do_servico',
        sa.Column('servico', sa.String(length=120), nullable=False),
        sa.Column('modelo', sa.String(length=40), nullable=False),
        sa.Column('reajuste', sa.String(length=40), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('servico'),
    )


def downgrade() -> None:
    op.drop_table('contrato_do_servico')
    op.drop_column('contrato', 'recorrente')
