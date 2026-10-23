"""Respostas do SDR de IA no WhatsApp (fase 1)

Amostra aprovada por Eduardo em 23/10/2026: a IA responde ao lead pelo roteador de custo (modelo leve nas
perguntas do roteiro, principal quando o leve não basta) e passa para a equipe tudo o que sai do roteiro. Só
acrescenta colunas vazias:
- em `conversa_do_sdr`, desde quando a conversa está com a equipe, por quê, e quem respondeu primeiro;
- em `mensagem_do_sdr`, o modelo que escreveu a resposta, o caminho (leve, principal, regra, trava) e a
  anotação do servidor (por que a trava barrou, por que o rascunho foi descartado).

Revisão: c3e9a1f7d5b2
Revisão anterior: 9b4e2f6a1c37
Criada em: 2026-10-23 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'c3e9a1f7d5b2'
down_revision: str | None = '9b4e2f6a1c37'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('conversa_do_sdr', sa.Column('equipe_desde', sa.DateTime(timezone=True)))
    op.add_column('conversa_do_sdr', sa.Column('equipe_motivo', sa.String(160)))
    op.add_column('conversa_do_sdr', sa.Column('atendida_por', sa.String(200)))
    op.add_column('mensagem_do_sdr', sa.Column('modelo', sa.String(60)))
    op.add_column('mensagem_do_sdr', sa.Column('rota', sa.String(20)))
    op.add_column('mensagem_do_sdr', sa.Column('observacao', sa.String(300)))


def downgrade() -> None:
    op.drop_column('mensagem_do_sdr', 'observacao')
    op.drop_column('mensagem_do_sdr', 'rota')
    op.drop_column('mensagem_do_sdr', 'modelo')
    op.drop_column('conversa_do_sdr', 'atendida_por')
    op.drop_column('conversa_do_sdr', 'equipe_motivo')
    op.drop_column('conversa_do_sdr', 'equipe_desde')
