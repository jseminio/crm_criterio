"""funil do sucesso por classe: semestral, bimestral da carteira, intenção e oportunidades da reunião

Aprovado por Eduardo em 03/10/2026:
- a cadência passa a ser uma reunião por classe (A mensal, B trimestral, C semestral). **Sobrescreve** a
  cadência gravada em Configurações (Eduardo autorizou): as linhas de `cadencia_de_reuniao` são apagadas
  e vale o padrão novo. As reuniões já registradas (inclusive bimestral e anual) ficam no histórico;
- `cadencia_de_reuniao.intencao`: o que a Critério quer com cada classe;
- `reuniao_de_resultado.estrategia_e_desafios`;
- a tabela `oportunidade_da_reuniao`: os novos negócios que a reunião achou, ligados à oportunidade do
  Funil comercial quando abertos lá;
- a tabela `reuniao_da_carteira`: a bimestral interna (Head do BPO e CEO).

Revisão: d1e5b8c3f7a2
Revisão anterior: c9f2a7d4e1b8
Criada em: 2026-10-03 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'd1e5b8c3f7a2'
down_revision: str | None = 'c9f2a7d4e1b8'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table('cadencia_de_reuniao') as t:
        t.add_column(sa.Column('intencao', sa.Text(), nullable=True))
    op.execute("DELETE FROM cadencia_de_reuniao")
    with op.batch_alter_table('reuniao_de_resultado') as t:
        t.add_column(sa.Column('estrategia_e_desafios', sa.Text(), nullable=True))
    op.create_table('oportunidade_da_reuniao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reuniao_id', sa.Integer(), nullable=False),
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('lacuna', sa.Text(), nullable=False),
    sa.Column('servico', sa.String(length=120), nullable=False),
    sa.Column('servico_tema', sa.String(length=80), nullable=True),
    sa.Column('valor', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('recorrente', sa.Boolean(), nullable=False),
    sa.Column('oportunidade_id', sa.Integer(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupo_economico.id'], name=op.f('fk_oportunidade_da_reuniao_grupo_id_grupo_economico')),
    sa.ForeignKeyConstraint(['oportunidade_id'], ['oportunidade.id'], name=op.f('fk_oportunidade_da_reuniao_oportunidade_id_oportunidade')),
    sa.ForeignKeyConstraint(['reuniao_id'], ['reuniao_de_resultado.id'], name=op.f('fk_oportunidade_da_reuniao_reuniao_id_reuniao_de_resultado')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_oportunidade_da_reuniao'))
    )
    op.create_index(op.f('ix_oportunidade_da_reuniao_grupo_id'), 'oportunidade_da_reuniao', ['grupo_id'], unique=False)
    op.create_index(op.f('ix_oportunidade_da_reuniao_oportunidade_id'), 'oportunidade_da_reuniao', ['oportunidade_id'], unique=False)
    op.create_index(op.f('ix_oportunidade_da_reuniao_reuniao_id'), 'oportunidade_da_reuniao', ['reuniao_id'], unique=False)
    op.create_table('reuniao_da_carteira',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('data', sa.Date(), nullable=False),
    sa.Column('participantes', sa.String(length=300), nullable=True),
    sa.Column('resumo', sa.Text(), nullable=True),
    sa.Column('correcoes_de_rota', sa.Text(), nullable=True),
    sa.Column('registrada_por', sa.String(length=200), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reuniao_da_carteira'))
    )
    op.create_index(op.f('ix_reuniao_da_carteira_data'), 'reuniao_da_carteira', ['data'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reuniao_da_carteira_data'), table_name='reuniao_da_carteira')
    op.drop_table('reuniao_da_carteira')
    op.drop_index(op.f('ix_oportunidade_da_reuniao_reuniao_id'), table_name='oportunidade_da_reuniao')
    op.drop_index(op.f('ix_oportunidade_da_reuniao_oportunidade_id'), table_name='oportunidade_da_reuniao')
    op.drop_index(op.f('ix_oportunidade_da_reuniao_grupo_id'), table_name='oportunidade_da_reuniao')
    op.drop_table('oportunidade_da_reuniao')
    with op.batch_alter_table('reuniao_de_resultado') as t:
        t.drop_column('estrategia_e_desafios')
    with op.batch_alter_table('cadencia_de_reuniao') as t:
        t.drop_column('intencao')
