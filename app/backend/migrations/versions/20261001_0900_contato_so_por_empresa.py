"""contato ligado só a empresas, nunca ao grupo

Pedido de Karine em 01/10/2026: as empresas de um contato nem sempre são do
mesmo grupo, então o contato passa a ser vinculado só a empresas. O grupo
continua existindo, mas é informado na empresa, não no contato.

Cada contato que hoje aponta para um grupo (`pessoa_contato.grupo_id`) vira
vínculo com empresa:

- grupo com uma empresa: vínculo com ela;
- grupo sem empresa: nasce a empresa com o nome do grupo (como o botão
  "Cadastrar empresa") e o vínculo com ela;
- grupo com duas ou mais: se a pessoa já está numa empresa do grupo, fica só
  nela; senão, vai para todas as empresas do grupo.

Depois, a coluna `grupo_id` sai do contato.

Revisão: 9a1c7e4b2d63
Revisão anterior: 5e8b3f1a2c47
Criada em: 2026-10-01 09:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = '9a1c7e4b2d63'
down_revision: str | None = '5e8b3f1a2c47'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    conexao = op.get_bind()
    ligados = conexao.execute(sa.text(
        "SELECT p.id, p.grupo_id, g.nome FROM pessoa_contato p "
        "JOIN grupo_economico g ON g.id = p.grupo_id ORDER BY p.id"
    )).all()
    empresa_criada: dict[int, int] = {}
    for pessoa_id, grupo_id, grupo_nome in ligados:
        empresas = list(conexao.execute(
            sa.text("SELECT id FROM empresa WHERE grupo_id = :g ORDER BY id"), {"g": grupo_id}
        ).scalars())
        if not empresas:
            if grupo_id not in empresa_criada:
                empresa_criada[grupo_id] = conexao.execute(sa.text(
                    "INSERT INTO empresa (grupo_id, razao_social, situacao, criado_em, atualizado_em) "
                    "VALUES (:g, :n, 'Ativa', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) RETURNING id"
                ), {"g": grupo_id, "n": grupo_nome[:200]}).scalar_one()
            empresas = [empresa_criada[grupo_id]]
        ja = set(conexao.execute(
            sa.text("SELECT empresa_id FROM vinculo_de_contato WHERE pessoa_id = :p"), {"p": pessoa_id}
        ).scalars())
        if len(empresas) > 1 and ja & set(empresas):
            continue
        for empresa_id in empresas:
            if empresa_id not in ja:
                conexao.execute(sa.text(
                    "INSERT INTO vinculo_de_contato (pessoa_id, empresa_id, principal, criado_em, atualizado_em) "
                    "VALUES (:p, :e, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                ), {"p": pessoa_id, "e": empresa_id})

    with op.batch_alter_table('pessoa_contato', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pessoa_contato_grupo_id'))
        batch_op.drop_constraint(op.f('fk_pessoa_contato_grupo_id_grupo_economico'), type_='foreignkey')
        batch_op.drop_column('grupo_id')


def downgrade() -> None:
    # A coluna volta vazia: os contatos continuam ligados pelas empresas (vínculos), e as
    # empresas criadas pelo upgrade ficam. Nada se perde, só não se refaz a ligação ao grupo.
    with op.batch_alter_table('pessoa_contato', schema=None) as batch_op:
        batch_op.add_column(sa.Column('grupo_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(op.f('fk_pessoa_contato_grupo_id_grupo_economico'), 'grupo_economico', ['grupo_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_pessoa_contato_grupo_id'), ['grupo_id'], unique=False)
