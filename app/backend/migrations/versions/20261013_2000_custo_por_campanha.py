"""custo por campanha e origem do clique no lead

Amostra aprovada por Eduardo em 13/10/2026: o investimento passa a existir por campanha (lido do Meta Ads ou
digitado), e o lead guarda a origem do clique (utm, gclid, fbclid). Só acrescenta: nada é apagado.

Revisão: a7c3e9d1b5f2
Revisão anterior: f2b6d8a4c0e1
Criada em: 2026-10-13 20:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'a7c3e9d1b5f2'
down_revision: str | None = 'f2b6d8a4c0e1'
branch_labels: str | None = None
depends_on: str | None = None

_ORIGEM = [('utm_source', 120), ('utm_medium', 120), ('utm_campaign', 200), ('gclid', 255), ('fbclid', 255)]


def upgrade() -> None:
    op.create_table(
        'investimento_por_campanha',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mes', sa.String(7), nullable=False),
        sa.Column('canal', sa.String(120), nullable=False),
        sa.Column('campanha', sa.String(200), nullable=False),
        sa.Column('valor', sa.Numeric(14, 2), nullable=False),
        sa.Column('fonte', sa.String(10), nullable=False),
        sa.Column('id_externo', sa.String(60)),
        sa.Column('lido_em', sa.DateTime(timezone=True)),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('valor >= 0', name=op.f('ck_investimento_por_campanha_valor_nao_negativo')),
        sa.CheckConstraint("fonte IN ('lido', 'digitado')", name=op.f('ck_investimento_por_campanha_fonte_lido_ou_digitado')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_investimento_por_campanha')),
        sa.UniqueConstraint('mes', 'canal', 'campanha', name='uq_investimento_mes_canal_campanha'),
    )
    op.create_index(op.f('ix_investimento_por_campanha_mes'), 'investimento_por_campanha', ['mes'])
    for nome, tamanho in _ORIGEM:
        op.add_column('lead', sa.Column(nome, sa.String(tamanho)))


def downgrade() -> None:
    for nome, _ in reversed(_ORIGEM):
        op.drop_column('lead', nome)
    op.drop_index(op.f('ix_investimento_por_campanha_mes'), 'investimento_por_campanha')
    op.drop_table('investimento_por_campanha')
