"""recebimentos importados por planilha

Pedido de Eduardo em 10/10/2026: o MRR da carteira mostra o contratado e o efetivamente recebido. O
recebido vem de planilha importada pela tela (só o Administrador). Cria as tabelas, vazias.

Revisão: a7c3e9f1b2d4
Revisão anterior: e5c1a9d3b7f2
Criada em: 2026-10-10 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a7c3e9f1b2d4'
down_revision: str | None = 'e5c1a9d3b7f2'
branch_labels: str | None = None
depends_on: str | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        'importacao_de_recebimentos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('arquivo', sa.String(length=200), nullable=False),
        sa.Column('importado_por', sa.String(length=200), nullable=True),
        sa.Column('importado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('competencias', _JSON, nullable=False),
        sa.Column('linhas', sa.Integer(), nullable=False),
        sa.Column('total', sa.Numeric(14, 2), nullable=False),
        sa.Column('fora', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_table(
        'recebimento',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('importacao_id', sa.Integer(), sa.ForeignKey('importacao_de_recebimentos.id'), nullable=False),
        sa.Column('grupo_id', sa.Integer(), sa.ForeignKey('grupo_economico.id'), nullable=False),
        sa.Column('empresa_id', sa.Integer(), sa.ForeignKey('empresa.id'), nullable=True),
        sa.Column('competencia', sa.Date(), nullable=False),
        sa.Column('valor', sa.Numeric(14, 2), nullable=False),
        sa.Column('data_do_recebimento', sa.Date(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index('ix_recebimento_importacao_id', 'recebimento', ['importacao_id'])
    op.create_index('ix_recebimento_grupo_id', 'recebimento', ['grupo_id'])
    op.create_index('ix_recebimento_empresa_id', 'recebimento', ['empresa_id'])
    op.create_index('ix_recebimento_competencia_ativo', 'recebimento', ['competencia', 'ativo'])


def downgrade() -> None:
    op.drop_table('recebimento')
    op.drop_table('importacao_de_recebimentos')
