"""ata da reunião de resultado e ajustes da área técnica

Aprovado por Eduardo em 02/10/2026. Só acrescenta:
- em `reuniao_de_resultado`, o resumo, as pendências do cliente, os pontos sensíveis e a transcrição
  colada do Granola (colunas vazias para as reuniões que já existem);
- a tabela `ajuste_tecnico`: cada ajuste que a reunião identificou, com responsável, prazo e quando
  foi feito;
- o perfil **Área técnica**, que vê os próprios ajustes na Agenda e marca feito, e nada mais. Se já
  existir um perfil com esse nome, fica como está.

Revisão: b8e4f1a6d3c7
Revisão anterior: a7d3e5f9c2b4
Criada em: 2026-10-03 11:00:00
"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'b8e4f1a6d3c7'
down_revision: str | None = 'a7d3e5f9c2b4'
branch_labels: str | None = None
depends_on: str | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    with op.batch_alter_table('reuniao_de_resultado') as t:
        t.add_column(sa.Column('resumo', sa.Text(), nullable=True))
        t.add_column(sa.Column('pendencias_do_cliente', sa.Text(), nullable=True))
        t.add_column(sa.Column('pontos_sensiveis', sa.Text(), nullable=True))
        t.add_column(sa.Column('transcricao', sa.Text(), nullable=True))
    op.create_table('ajuste_tecnico',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reuniao_id', sa.Integer(), nullable=False),
    sa.Column('grupo_id', sa.Integer(), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=False),
    sa.Column('responsavel_email', sa.String(length=200), nullable=False),
    sa.Column('responsavel_nome', sa.String(length=200), nullable=True),
    sa.Column('prazo', sa.Date(), nullable=True),
    sa.Column('feito_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('feito_por', sa.String(length=200), nullable=True),
    sa.Column('observacao', sa.String(length=500), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['grupo_id'], ['grupo_economico.id'], name=op.f('fk_ajuste_tecnico_grupo_id_grupo_economico')),
    sa.ForeignKeyConstraint(['reuniao_id'], ['reuniao_de_resultado.id'], name=op.f('fk_ajuste_tecnico_reuniao_id_reuniao_de_resultado')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ajuste_tecnico'))
    )
    op.create_index(op.f('ix_ajuste_tecnico_grupo_id'), 'ajuste_tecnico', ['grupo_id'], unique=False)
    op.create_index(op.f('ix_ajuste_tecnico_reuniao_id'), 'ajuste_tecnico', ['reuniao_id'], unique=False)
    op.create_index(op.f('ix_ajuste_tecnico_responsavel_email'), 'ajuste_tecnico', ['responsavel_email'], unique=False)

    perfil = sa.table('perfil', sa.column('nome', sa.String), sa.column('administrador', sa.Boolean),
                      sa.column('permissoes', _JSON), sa.column('criado_em', sa.DateTime(timezone=True)),
                      sa.column('atualizado_em', sa.DateTime(timezone=True)))
    existe = op.get_bind().execute(sa.text("SELECT 1 FROM perfil WHERE nome = 'Área técnica'")).first()
    if existe is None:
        agora = datetime.now(timezone.utc)
        op.execute(perfil.insert().values(nome='Área técnica', administrador=False, permissoes=['ajustes.concluir'],
                                          criado_em=agora, atualizado_em=agora))


def downgrade() -> None:
    op.execute("DELETE FROM perfil WHERE nome = 'Área técnica' AND NOT EXISTS "
               "(SELECT 1 FROM usuario u WHERE u.perfil_id = perfil.id)")
    op.drop_index(op.f('ix_ajuste_tecnico_responsavel_email'), table_name='ajuste_tecnico')
    op.drop_index(op.f('ix_ajuste_tecnico_reuniao_id'), table_name='ajuste_tecnico')
    op.drop_index(op.f('ix_ajuste_tecnico_grupo_id'), table_name='ajuste_tecnico')
    op.drop_table('ajuste_tecnico')
    with op.batch_alter_table('reuniao_de_resultado') as t:
        t.drop_column('transcricao')
        t.drop_column('pontos_sensiveis')
        t.drop_column('pendencias_do_cliente')
        t.drop_column('resumo')
