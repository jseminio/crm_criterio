"""Funil de parceiros

Amostra aprovada por Eduardo em 19/10/2026: menu próprio Parceiros, com o cadastro do parceiro (PF ou PJ, nível, acordo,
sócio responsável), a indicação ligada à oportunidade e o finder fee que o sócio da conta aprova e marca pago. Cria as
tabelas `parceiro` e `fee_de_parceiro` e acrescenta à `oportunidade` quatro colunas em branco. Não mexe em dado
existente: a conferência da tela liga os textos de canal antigos ao parceiro.

Revisão: 7d3a9c2e5f14
Revisão anterior: b4e7c1d9a2f3
Criada em: 2026-10-19 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '7d3a9c2e5f14'
down_revision: str | None = 'b4e7c1d9a2f3'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        'parceiro',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(120), nullable=False),
        sa.Column('tipo_pessoa', sa.String(40), nullable=False),
        sa.Column('documento', sa.String(20)),
        sa.Column('tipo', sa.String(60)),
        sa.Column('nivel', sa.String(40), nullable=False),
        sa.Column('etapa_manual', sa.String(40), nullable=False),
        sa.Column('acordo', sa.String(40), nullable=False),
        sa.Column('contrato_assinado_em', sa.Date()),
        sa.Column('regra_combinada', sa.String(400)),
        sa.Column('combinado_por', sa.String(60)),
        sa.Column('combinado_em', sa.Date()),
        sa.Column('socio_responsavel', sa.String(60)),
        sa.Column('perfil_pedido', sa.String(400)),
        sa.Column('contato', sa.String(200)),
        sa.Column('textos_do_canal', sa.JSON().with_variant(postgresql.JSONB(), 'postgresql'), nullable=False),
        sa.Column('observacao', sa.Text()),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_parceiro')),
        sa.UniqueConstraint('nome', name=op.f('uq_parceiro_nome')),
    )
    op.create_table(
        'fee_de_parceiro',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parceiro_id', sa.Integer(), nullable=False),
        sa.Column('oportunidade_id', sa.Integer(), nullable=False),
        sa.Column('regra', sa.String(40), nullable=False),
        sa.Column('competencia', sa.Date(), nullable=False),
        sa.Column('base', sa.Numeric(14, 2), nullable=False),
        sa.Column('calculado', sa.Numeric(14, 2), nullable=False),
        sa.Column('valor_aprovado', sa.Numeric(14, 2)),
        sa.Column('situacao', sa.String(40), nullable=False),
        sa.Column('decidido_por', sa.String(200)),
        sa.Column('decidido_em', sa.DateTime(timezone=True)),
        sa.Column('pago_em', sa.Date()),
        sa.Column('motivo', sa.String(300)),
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['parceiro_id'], ['parceiro.id'], name=op.f('fk_fee_de_parceiro_parceiro_id_parceiro')),
        sa.ForeignKeyConstraint(['oportunidade_id'], ['oportunidade.id'],
                                name=op.f('fk_fee_de_parceiro_oportunidade_id_oportunidade')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_fee_de_parceiro')),
        sa.UniqueConstraint('oportunidade_id', 'competencia', name='uq_fee_oportunidade_competencia'),
    )
    op.create_index(op.f('ix_fee_de_parceiro_parceiro_id'), 'fee_de_parceiro', ['parceiro_id'])
    op.create_index(op.f('ix_fee_de_parceiro_oportunidade_id'), 'fee_de_parceiro', ['oportunidade_id'])
    op.add_column('oportunidade', sa.Column('parceiro_id', sa.Integer(), nullable=True))
    op.add_column('oportunidade', sa.Column('indicacao_recebida_em', sa.Date(), nullable=True))
    op.add_column('oportunidade', sa.Column('indicacao_validada_em', sa.Date(), nullable=True))
    op.add_column('oportunidade', sa.Column('indicacao_recusada', sa.String(40), nullable=True))
    op.create_foreign_key(op.f('fk_oportunidade_parceiro_id_parceiro'), 'oportunidade', 'parceiro', ['parceiro_id'], ['id'])
    op.create_index(op.f('ix_oportunidade_parceiro_id'), 'oportunidade', ['parceiro_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_oportunidade_parceiro_id'), table_name='oportunidade')
    op.drop_constraint(op.f('fk_oportunidade_parceiro_id_parceiro'), 'oportunidade', type_='foreignkey')
    for coluna in ('indicacao_recusada', 'indicacao_validada_em', 'indicacao_recebida_em', 'parceiro_id'):
        op.drop_column('oportunidade', coluna)
    op.drop_index(op.f('ix_fee_de_parceiro_oportunidade_id'), table_name='fee_de_parceiro')
    op.drop_index(op.f('ix_fee_de_parceiro_parceiro_id'), table_name='fee_de_parceiro')
    op.drop_table('fee_de_parceiro')
    op.drop_table('parceiro')
