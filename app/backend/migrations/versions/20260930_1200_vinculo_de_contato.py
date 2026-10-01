"""vínculo entre pessoa de contato e empresa (muitos para muitos)

Pedido de Karine em 30/09/2026: a pessoa nasce antes da empresa, pode estar
em várias empresas, e cada empresa pode ter vários contatos principais.

Os contatos que hoje apontam para uma empresa (`pessoa_contato.empresa_id`)
viram um vínculo cada, sem perder nenhum. Os ligados só ao grupo continuam
como estão. A regra "todo contato pertence a alguém" sai: agora a pessoa pode
existir sem empresa.

Revisão: 5e8b3f1a2c47
Revisão anterior: 7c4e2a91d6b0
Criada em: 2026-09-30 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = '5e8b3f1a2c47'
down_revision: str | None = '7c4e2a91d6b0'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table('vinculo_de_contato',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('pessoa_id', sa.Integer(), nullable=False),
    sa.Column('empresa_id', sa.Integer(), nullable=False),
    sa.Column('principal', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['empresa_id'], ['empresa.id'], name=op.f('fk_vinculo_de_contato_empresa_id_empresa'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['pessoa_id'], ['pessoa_contato.id'], name=op.f('fk_vinculo_de_contato_pessoa_id_pessoa_contato'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_vinculo_de_contato')),
    sa.UniqueConstraint('pessoa_id', 'empresa_id', name='uq_vinculo_pessoa_empresa')
    )
    with op.batch_alter_table('vinculo_de_contato', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vinculo_de_contato_empresa_id'), ['empresa_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_vinculo_de_contato_pessoa_id'), ['pessoa_id'], unique=False)

    op.execute(
        "INSERT INTO vinculo_de_contato (pessoa_id, empresa_id, principal, criado_em, atualizado_em) "
        "SELECT id, empresa_id, false, criado_em, atualizado_em FROM pessoa_contato WHERE empresa_id IS NOT NULL"
    )

    # IF EXISTS: uma cópia feita com pg_dump/pg_restore chegou sem esta regra
    # (ensaio de 30/09/2026); o banco original a tem. Os dois têm de migrar.
    op.execute("ALTER TABLE pessoa_contato DROP CONSTRAINT IF EXISTS ck_pessoa_contato_contato_pertence_a_alguem")
    with op.batch_alter_table('pessoa_contato', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pessoa_contato_empresa_id'))
        batch_op.drop_constraint(op.f('fk_pessoa_contato_empresa_id_empresa'), type_='foreignkey')
        batch_op.drop_column('empresa_id')


def downgrade() -> None:
    # Volta ao formato de uma empresa por pessoa: fica o vínculo de menor id.
    # Os demais vínculos e a marca de principal se perdem. A regra "todo
    # contato pertence a alguém" não é recriada, porque pessoas sem empresa
    # cadastradas depois do upgrade a violariam.
    with op.batch_alter_table('pessoa_contato', schema=None) as batch_op:
        batch_op.add_column(sa.Column('empresa_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(op.f('fk_pessoa_contato_empresa_id_empresa'), 'empresa', ['empresa_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_pessoa_contato_empresa_id'), ['empresa_id'], unique=False)

    op.execute(
        "UPDATE pessoa_contato SET empresa_id = ("
        "SELECT v.empresa_id FROM vinculo_de_contato v WHERE v.pessoa_id = pessoa_contato.id "
        "ORDER BY v.id LIMIT 1)"
    )

    with op.batch_alter_table('vinculo_de_contato', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vinculo_de_contato_pessoa_id'))
        batch_op.drop_index(batch_op.f('ix_vinculo_de_contato_empresa_id'))

    op.drop_table('vinculo_de_contato')
