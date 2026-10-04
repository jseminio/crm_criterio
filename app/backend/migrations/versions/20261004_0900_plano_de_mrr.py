"""plano de MRR da aba Inteligência de Conversão

Aprovado por Eduardo em 03/10/2026. Só acrescenta:
- a tabela `plano_de_mrr`, as premissas do plano (uma linha só). Fica vazia: sem a linha valem as
  premissas de `crm.domain.plano_de_mrr.PADRAO`, e a linha nasce na primeira edição do Administrador;
- a tabela `contrato_previsto_do_plano`, o pipeline contábil que o plano já conta, carregada com os
  três contratos de 03/10/2026 (sem nome de cliente): dois atípicos, em nov e dez/2026, e um normal
  em nov/2026.

Revisão: a7c3e9f1b5d2
Revisão anterior: d1e5b8c3f7a2
Criada em: 2026-10-04 09:00:00
"""

from __future__ import annotations

from datetime import date

from alembic import op
import sqlalchemy as sa

revision: str = 'a7c3e9f1b5d2'
down_revision: str | None = 'd1e5b8c3f7a2'
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    dinheiro = lambda nome: sa.Column(nome, sa.Numeric(14, 2), nullable=False)
    quantidade = lambda nome: sa.Column(nome, sa.Numeric(6, 2), nullable=False)
    op.create_table('plano_de_mrr',
    sa.Column('id', sa.Integer(), nullable=False),
    dinheiro('meta_liquida'),
    sa.Column('inicio', sa.Date(), nullable=False),
    sa.Column('fim', sa.Date(), nullable=False),
    sa.Column('inicio_da_projecao', sa.Date(), nullable=False),
    dinheiro('ponto_de_partida'),
    dinheiro('mrr_de_partida'),
    quantidade('churn_anual_pct'),
    dinheiro('bpo_ticket'),
    quantidade('bpo_teto'),
    quantidade('contabil_vagas'),
    quantidade('atipico_vagas'),
    sa.Column('escada_prazo_meses', sa.Integer(), nullable=False),
    dinheiro('plus_acrescimo'),
    quantidade('plus_pct'),
    dinheiro('cfo_acrescimo'),
    quantidade('cfo_pct'),
    quantidade('alerta_bpo_por_mes'),
    quantidade('previsto_bpo_por_mes'),
    quantidade('otimista_bpo_por_mes'),
    dinheiro('alerta_ticket_contabil'),
    dinheiro('previsto_ticket_contabil'),
    dinheiro('otimista_ticket_contabil'),
    sa.Column('alerta_com_previstos', sa.Boolean(), nullable=False),
    sa.Column('previsto_com_previstos', sa.Boolean(), nullable=False),
    sa.Column('otimista_com_previstos', sa.Boolean(), nullable=False),
    sa.Column('alterado_por', sa.String(length=200), nullable=True),
    sa.Column('alterado_em', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_plano_de_mrr'))
    )
    previstos = op.create_table('contrato_previsto_do_plano',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('descricao', sa.String(length=120), nullable=False),
    sa.Column('mes', sa.Date(), nullable=False),
    sa.Column('valor', sa.Numeric(14, 2), nullable=False),
    sa.Column('atipico', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_contrato_previsto_do_plano'))
    )
    op.bulk_insert(previstos, [
        {"descricao": "Atípico do pipeline (nov)", "mes": date(2026, 11, 1), "valor": 18000, "atipico": True},
        {"descricao": "Normal do pipeline (nov)", "mes": date(2026, 11, 1), "valor": 5500, "atipico": False},
        {"descricao": "Atípico do pipeline (dez)", "mes": date(2026, 12, 1), "valor": 16000, "atipico": True},
    ])


def downgrade() -> None:
    op.drop_table('contrato_previsto_do_plano')
    op.drop_table('plano_de_mrr')
