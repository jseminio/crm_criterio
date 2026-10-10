"""Leva a meta e o alerta do MRR para a base de 13 parcelas (aprovado por Eduardo em 10/10/2026).

O MRR do CRM é a parcela × 13 ÷ 12 desde 09/10/2026; a régua de Configurações › Metas ainda estava pela
parcela (R$ 400 mil e R$ 200 mil). Converte só a linha que ainda está nesses valores de origem: se
alguém já mudou a meta na tela, a escolha dessa pessoa vale e nada muda. Sem linha gravada, vale o
padrão do código, que já está em 13 parcelas.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from crm.db.base import agora
from crm.db.modelos import MetaDeIndicador
from crm.domain.mrr import ALERTA_DE_MRR, META_DE_MRR

QUEM = "atualizador (meta de MRR em 13 parcelas)"
DE = (Decimal("400000"), Decimal("200000"))


def executar(sessao: Session) -> str:
    linha = sessao.get(MetaDeIndicador, "mrr")
    if linha is None:
        return "nada a converter: a meta de MRR usa o padrão do código, já em 13 parcelas"
    if (linha.meta, linha.alerta) != DE:
        return "nada a converter: a meta de MRR foi definida na tela e fica como está"
    linha.meta, linha.alerta = META_DE_MRR, ALERTA_DE_MRR
    linha.alterado_por, linha.alterado_em = QUEM, agora()
    return "meta de MRR convertida para 13 parcelas: R$ 433.333,33, alerta R$ 216.666,67"
