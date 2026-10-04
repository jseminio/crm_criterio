"""base de conhecimento do SDR de IA

Amostra aprovada por Eduardo em 03/10/2026: a tabela `ficha_da_base`, uma ficha por assunto, com
o que a IA pode dizer, o que nunca diz, fonte, dono, situação e validade. **Só aditiva**: nenhuma
tabela existente muda. As fichas iniciais entram pela tela ("Trazer a carga inicial"), não aqui.

Revisão: e4a7c1b9d2f6
Revisão anterior: d1e5b8c3f7a2
Criada em: 2026-10-03 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'e4a7c1b9d2f6'
down_revision: str | None = 'd1e5b8c3f7a2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table('ficha_da_base',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(length=20), nullable=True),
    sa.Column('titulo', sa.String(length=200), nullable=False),
    sa.Column('bloco', sa.String(length=40), nullable=False),
    sa.Column('servico', sa.String(length=120), nullable=True),
    sa.Column('texto', sa.Text(), nullable=True),
    sa.Column('nunca_dizer', sa.Text(), nullable=True),
    sa.Column('como_o_lead_pergunta', sa.Text(), nullable=True),
    sa.Column('fonte', sa.String(length=300), nullable=True),
    sa.Column('dono', sa.String(length=120), nullable=True),
    sa.Column('depende_de_hipotese', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('situacao', sa.String(length=40), nullable=False),
    sa.Column('validade', sa.Date(), nullable=True),
    sa.Column('aprovada_por', sa.String(length=200), nullable=True),
    sa.Column('aprovada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ficha_da_base')),
    sa.UniqueConstraint('codigo', name=op.f('uq_ficha_da_base_codigo'))
    )
    op.create_index(op.f('ix_ficha_da_base_bloco'), 'ficha_da_base', ['bloco'], unique=False)
    op.create_index(op.f('ix_ficha_da_base_situacao'), 'ficha_da_base', ['situacao'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ficha_da_base_situacao'), table_name='ficha_da_base')
    op.drop_index(op.f('ix_ficha_da_base_bloco'), table_name='ficha_da_base')
    op.drop_table('ficha_da_base')
