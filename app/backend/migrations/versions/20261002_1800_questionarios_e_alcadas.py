"""pedidos de aprovação de eventos de contrato e o menu Questionários

Amostra aprovada por Eduardo em 02/10/2026. Só acrescenta: a tabela `pedido_de_aprovacao` (evento de
contrato acima da alçada esperando quem aprova) e a funcionalidade "Questionários: ver" no perfil
Comercial. A funcionalidade nova "aprovar eventos acima da alçada" fica só com o Administrador, que
já tem tudo; outro perfil a recebe pela tela.

Revisão: e3a9c6b4d2f1
Revisão anterior: d8b2f5a1c3e7
Criada em: 2026-10-02 18:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'e3a9c6b4d2f1'
down_revision: str | None = 'd8b2f5a1c3e7'
branch_labels: str | None = None
depends_on: str | None = None

_DINHEIRO = sa.Numeric(14, 2)
_NOVA = "questionarios.ver"


def _permissoes_do_comercial(mudar) -> None:
    conexao = op.get_bind()
    perfil = sa.table("perfil", sa.column("id", sa.Integer), sa.column("nome", sa.String),
                      sa.column("permissoes", sa.JSON))
    linha = conexao.execute(sa.select(perfil.c.id, perfil.c.permissoes).where(perfil.c.nome == "Comercial")).first()
    if linha is None:
        return
    novas = mudar(list(linha.permissoes or []))
    conexao.execute(perfil.update().where(perfil.c.id == linha.id).values(permissoes=novas))


def upgrade() -> None:
    op.create_table('pedido_de_aprovacao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('contrato_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(length=40), nullable=False),
    sa.Column('data_do_evento', sa.Date(), nullable=False),
    sa.Column('descricao', sa.String(length=500), nullable=True),
    sa.Column('preco_mensal_anterior', _DINHEIRO, nullable=True),
    sa.Column('preco_mensal_novo', _DINHEIRO, nullable=True),
    sa.Column('preco_anual_anterior', _DINHEIRO, nullable=True),
    sa.Column('preco_anual_novo', _DINHEIRO, nullable=True),
    sa.Column('escopo_anterior', sa.String(length=200), nullable=True),
    sa.Column('escopo_novo', sa.String(length=200), nullable=True),
    sa.Column('motivo', sa.String(length=300), nullable=False),
    sa.Column('pedido_por', sa.String(length=200), nullable=False),
    sa.Column('pedido_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('situacao', sa.String(length=20), nullable=False),
    sa.Column('decidido_por', sa.String(length=200), nullable=True),
    sa.Column('decidido_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motivo_da_recusa', sa.String(length=500), nullable=True),
    sa.Column('evento_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['contrato_id'], ['contrato.id'], name=op.f('fk_pedido_de_aprovacao_contrato_id_contrato')),
    sa.ForeignKeyConstraint(['evento_id'], ['evento_de_contrato.id'], name=op.f('fk_pedido_de_aprovacao_evento_id_evento_de_contrato')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pedido_de_aprovacao'))
    )
    op.create_index(op.f('ix_pedido_de_aprovacao_contrato_id'), 'pedido_de_aprovacao', ['contrato_id'], unique=False)
    op.create_index(op.f('ix_pedido_de_aprovacao_situacao'), 'pedido_de_aprovacao', ['situacao'], unique=False)
    _permissoes_do_comercial(lambda ps: sorted(set(ps) | {_NOVA}))


def downgrade() -> None:
    _permissoes_do_comercial(lambda ps: [p for p in ps if p != _NOVA])
    op.drop_index(op.f('ix_pedido_de_aprovacao_situacao'), table_name='pedido_de_aprovacao')
    op.drop_index(op.f('ix_pedido_de_aprovacao_contrato_id'), table_name='pedido_de_aprovacao')
    op.drop_table('pedido_de_aprovacao')
