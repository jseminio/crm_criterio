"""funil do sucesso do cliente: etapa do grupo, reuniões de resultado e cadência por classe

Aprovado por Eduardo em 02/10/2026. Só acrescenta três tabelas: `jornada_do_cliente` (em que etapa
o grupo está e o checklist feito), `reuniao_de_resultado` (as reuniões com o cliente, com as decisões
dele) e `cadencia_de_reuniao`, já com a cadência aceita: A tem mensal, bimestral, trimestral e anual;
B, trimestral e anual; C, só anual. As funcionalidades novas ("Funil do Sucesso do Cliente: ver" e
"marcar etapas e registrar reuniões") ficam só com o Administrador, que já tem tudo.

Revisão: a7d3e5f9c2b4
Revisão anterior: f6c2d8a4b1e9
Criada em: 2026-10-03 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a7d3e5f9c2b4'
down_revision: str | None = 'f6c2d8a4b1e9'
branch_labels: str | None = None
depends_on: str | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.create_table('jornada_do_cliente',
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('etapa', sa.String(length=20), nullable=False),
    sa.Column('itens_feitos', _JSON, nullable=False),
    sa.Column('etapa_desde', sa.Date(), nullable=False),
    sa.Column('em_curso_desde', sa.Date(), nullable=True),
    sa.Column('alterado_por', sa.String(length=200), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupo_economico.id'], name=op.f('fk_jornada_do_cliente_grupo_id_grupo_economico')),
    sa.PrimaryKeyConstraint('grupo_id', name=op.f('pk_jornada_do_cliente'))
    )
    op.create_table('reuniao_de_resultado',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('data', sa.Date(), nullable=False),
    sa.Column('participantes', sa.String(length=300), nullable=True),
    sa.Column('pauta', sa.Text(), nullable=True),
    sa.Column('dashboard', sa.String(length=400), nullable=True),
    sa.Column('decisoes', sa.Text(), nullable=True),
    sa.Column('proximos_passos', sa.Text(), nullable=True),
    sa.Column('registrada_por', sa.String(length=200), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupo_economico.id'], name=op.f('fk_reuniao_de_resultado_grupo_id_grupo_economico')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reuniao_de_resultado'))
    )
    op.create_index(op.f('ix_reuniao_de_resultado_grupo_id'), 'reuniao_de_resultado', ['grupo_id'], unique=False)
    cadencia = op.create_table('cadencia_de_reuniao',
    sa.Column('classe', sa.String(length=1), nullable=False),
    sa.Column('tipos', _JSON, nullable=False),
    sa.Column('alterado_por', sa.String(length=200), nullable=True),
    sa.Column('alterado_em', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('classe', name=op.f('pk_cadencia_de_reuniao'))
    )
    op.bulk_insert(cadencia, [
        {"classe": "A", "tipos": ["mensal", "bimestral", "trimestral", "anual"]},
        {"classe": "B", "tipos": ["trimestral", "anual"]},
        {"classe": "C", "tipos": ["anual"]},
    ])


def downgrade() -> None:
    op.drop_table('cadencia_de_reuniao')
    op.drop_index(op.f('ix_reuniao_de_resultado_grupo_id'), table_name='reuniao_de_resultado')
    op.drop_table('reuniao_de_resultado')
    op.drop_table('jornada_do_cliente')
