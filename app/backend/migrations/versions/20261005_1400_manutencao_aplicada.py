"""manutenção aplicada (tarefas de dados rodadas uma vez pelo atualizador)

Issue #93, regra do dono em 05/10/2026: nenhuma mudança estrutural exige comando manual no servidor. A
tabela `manutencao_aplicada` guarda as tarefas de dados (`crm.manutencao`) que o `atualizador.sh` já
aplicou no Redeploy: id estável, quando e o resultado. **Só aditiva**: nenhuma tabela existente muda.

Revisão: b8d3f1a6c2e4
Revisão anterior: f4a7c2e9b1d3 (senha do usuário)
Criada em: 2026-10-05 14:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'b8d3f1a6c2e4'
down_revision: str | None = 'f4a7c2e9b1d3'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Tolerante a tabela já existente: restaurar um pg_dump feito na f4a7c2e9b1d3 (pg_restore --clean)
    # derruba só as tabelas do dump e volta alembic_version para f4a7, mas deixa esta tabela de pé.
    # Sem a checagem, o boot seguinte tentaria criá-la de novo e abortaria.
    if sa.inspect(op.get_bind()).has_table('manutencao_aplicada'):
        return
    op.create_table('manutencao_aplicada',
    sa.Column('id', sa.String(length=120), nullable=False),
    sa.Column('descricao', sa.String(length=300), nullable=False),
    sa.Column('aplicada_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('resultado', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_manutencao_aplicada'))
    )


def downgrade() -> None:
    op.drop_table('manutencao_aplicada')
