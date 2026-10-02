"""perfis de acesso, pessoas e histórico de alterações (E1)

Pedido e amostra aprovados por Eduardo em 02/10/2026: entrada pela conta Microsoft, perfis que
liberam funcionalidades dentro de cada menu (ou o menu inteiro) e histórico de alterações por
usuário. Só acrescenta. Nasce com dois perfis: **Administrador** (tudo) e **Comercial** (o comercial
inteiro, sem converter em contrato, sem Carteira e sem Configurações; contratos e grupos para ver).
As pessoas entram pela tela (Configurações › Perfis e acesso) ou, o primeiro Administrador, por
`CRM_ADMINISTRADORES` no `.env`.

Revisão: d8b2f5a1c3e7
Revisão anterior: c4e1a7d2f9b3
Criada em: 2026-10-02 14:00:00
"""

from __future__ import annotations


from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd8b2f5a1c3e7'
down_revision: str | None = 'c4e1a7d2f9b3'
branch_labels: str | None = None
depends_on: str | None = None

_JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')
COMERCIAL = ["abordagens.editar", "abordagens.ver", "agenda.ver", "conferencia.ver", "contatos.editar", "contatos.excluir", "contatos.ver", "contratos.ver", "funil.editar", "funil.enviar_proposta", "funil.exportar", "funil.proposta", "funil.questionarios", "funil.ver", "grupos.ver", "sdr.editar", "sdr.ver"]


def upgrade() -> None:
    perfil = op.create_table('perfil',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=60), nullable=False),
    sa.Column('administrador', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('permissoes', _JSON, server_default=sa.text("'[]'"), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_perfil')),
    sa.UniqueConstraint('nome', name=op.f('uq_perfil_nome'))
    )
    op.create_table('usuario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=True),
    sa.Column('perfil_id', sa.Integer(), nullable=False),
    sa.Column('ativo', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('liberado_por', sa.String(length=200), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['perfil_id'], ['perfil.id'], name=op.f('fk_usuario_perfil_id_perfil')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_usuario')),
    sa.UniqueConstraint('email', name=op.f('uq_usuario_email'))
    )
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_usuario_perfil_id'), ['perfil_id'], unique=False)

    op.create_table('registro_de_alteracao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('quando', sa.DateTime(timezone=True), nullable=False),
    sa.Column('usuario_email', sa.String(length=200), nullable=False),
    sa.Column('usuario_nome', sa.String(length=200), nullable=True),
    sa.Column('acao', sa.String(length=10), nullable=False),
    sa.Column('tabela', sa.String(length=60), nullable=False),
    sa.Column('registro_id', sa.Integer(), nullable=True),
    sa.Column('descricao', sa.String(length=200), nullable=True),
    sa.Column('campo', sa.String(length=60), nullable=True),
    sa.Column('antes', sa.Text(), nullable=True),
    sa.Column('depois', sa.Text(), nullable=True),
    sa.Column('rota', sa.String(length=200), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_registro_de_alteracao'))
    )
    with op.batch_alter_table('registro_de_alteracao', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_registro_de_alteracao_quando'), ['quando'], unique=False)
        batch_op.create_index(batch_op.f('ix_registro_de_alteracao_usuario_email'), ['usuario_email'], unique=False)
        batch_op.create_index('ix_registro_de_alteracao_tabela_registro', ['tabela', 'registro_id'], unique=False)

    agora = sa.func.now()
    op.execute(perfil.insert().values(nome='Administrador', administrador=True, permissoes=[], criado_em=agora, atualizado_em=agora))
    op.execute(perfil.insert().values(nome='Comercial', administrador=False, permissoes=COMERCIAL, criado_em=agora, atualizado_em=agora))


def downgrade() -> None:
    with op.batch_alter_table('registro_de_alteracao', schema=None) as batch_op:
        batch_op.drop_index('ix_registro_de_alteracao_tabela_registro')
        batch_op.drop_index(batch_op.f('ix_registro_de_alteracao_usuario_email'))
        batch_op.drop_index(batch_op.f('ix_registro_de_alteracao_quando'))
    op.drop_table('registro_de_alteracao')
    with op.batch_alter_table('usuario', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_usuario_perfil_id'))
    op.drop_table('usuario')
    op.drop_table('perfil')
