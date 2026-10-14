"""Mensagens do WhatsApp recebidas pelo CRM (fase 0 do SDR de IA)

Amostra aprovada por Eduardo em 14/10/2026: o CRM passa a receber as mensagens dos leads pelo webhook
da Meta. Só acrescenta colunas vazias:
- em `mensagem_do_sdr`, o ID da mensagem na Meta (impede gravar duas vezes a mesma entrega) e a
  situação de entrega das mensagens que a Critério envia (enviada, entregue, lida, falhou);
- em `conversa_do_sdr`, a hora da última mensagem do lead, que abre a janela de 24 horas do WhatsApp.

Revisão: a8d2c6e4f0b1
Revisão anterior: f5c1e7a3b9d6
Criada em: 2026-10-14 23:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision: str = 'a8d2c6e4f0b1'
down_revision: str | None = 'f5c1e7a3b9d6'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column('mensagem_do_sdr', sa.Column('externo_id', sa.String(128)))
    op.create_index(op.f('ix_mensagem_do_sdr_externo_id'), 'mensagem_do_sdr', ['externo_id'], unique=True)
    op.add_column('mensagem_do_sdr', sa.Column('entrega', sa.String(20)))
    op.add_column('conversa_do_sdr', sa.Column('ultima_do_lead_em', sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column('conversa_do_sdr', 'ultima_do_lead_em')
    op.drop_column('mensagem_do_sdr', 'entrega')
    op.drop_index(op.f('ix_mensagem_do_sdr_externo_id'), 'mensagem_do_sdr')
    op.drop_column('mensagem_do_sdr', 'externo_id')
