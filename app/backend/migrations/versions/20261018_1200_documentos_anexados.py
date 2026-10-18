"""Documentos anexados: PDF assinado, proposta aceita e aditivo, inclusive os antigos

Amostra aprovada por Eduardo em 18/10/2026: o CRM guarda o PDF assinado do contrato e o da proposta aceita, inclusive
os antigos, feitos fora do CRM; a IA sugere os campos e uma pessoa confere. Só cria a tabela e acrescenta colunas
vazias no contrato (multa rescisória, aviso prévio e renovação): nenhum dado existente muda.

Revisão: c3e9b1d7a5f2
Revisão anterior: a8d2c6e4f0b1
Criada em: 2026-10-18 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'c3e9b1d7a5f2'
down_revision: str | None = 'a8d2c6e4f0b1'
branch_labels: str | None = None
depends_on: str | None = None

_JSON = sa.JSON().with_variant(JSONB(), "postgresql")


def _carimbo() -> list[sa.Column]:
    return [
        sa.Column('criado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.add_column('contrato', sa.Column('multa_rescisoria', sa.String(200)))
    op.add_column('contrato', sa.Column('aviso_previo_dias', sa.SmallInteger()))
    op.add_column('contrato', sa.Column('renovacao', sa.String(200)))

    op.create_table(
        'documento_anexado',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tipo', sa.String(20), nullable=False),
        sa.Column('grupo_id', sa.Integer(), sa.ForeignKey('grupo_economico.id')),
        sa.Column('contrato_id', sa.Integer(), sa.ForeignKey('contrato.id')),
        sa.Column('oportunidade_id', sa.Integer(), sa.ForeignKey('oportunidade.id')),
        sa.Column('nome_arquivo', sa.String(200), nullable=False),
        sa.Column('tamanho', sa.Integer(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('conteudo_base64', sa.Text(), nullable=False),
        sa.Column('origem', sa.String(20), nullable=False),
        sa.Column('enviado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('enviado_por', sa.String(200), nullable=False),
        sa.Column('substituido_em', sa.DateTime(timezone=True)),
        sa.Column('leitura_situacao', sa.String(20), nullable=False),
        sa.Column('leitura_iniciada_em', sa.DateTime(timezone=True)),
        sa.Column('leitura', _JSON),
        sa.Column('leitura_erro', sa.String(400)),
        sa.Column('conferido_em', sa.DateTime(timezone=True)),
        sa.Column('conferido_por', sa.String(200)),
        sa.Column('campos_gravados', _JSON),
        sa.Column('numero_no_documento', sa.String(60)),
        sa.Column('data_do_documento', sa.Date()),
        *_carimbo(),
    )
    for coluna in ('grupo_id', 'contrato_id', 'oportunidade_id', 'sha256'):
        op.create_index(op.f(f'ix_documento_anexado_{coluna}'), 'documento_anexado', [coluna])


def downgrade() -> None:
    op.drop_table('documento_anexado')
    op.drop_column('contrato', 'renovacao')
    op.drop_column('contrato', 'aviso_previo_dias')
    op.drop_column('contrato', 'multa_rescisoria')
