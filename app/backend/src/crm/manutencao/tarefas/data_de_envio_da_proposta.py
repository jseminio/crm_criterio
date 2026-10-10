"""Preenche a data de envio da proposta nas oportunidades que já existem (decisão de Eduardo, 10/10/2026).

- **Planilha de 2026:** a originação já era o envio. Recebe a data de originação quem já passou de "Enviar
  proposta" (quem ainda está em "Enviar proposta" não enviou).
- **Proposta gerada no CRM e marcada como enviada:** a primeira data de envio dela.

Não toca em quem já tem a data. Rodar de novo não muda nada.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Oportunidade, Proposta
from crm.domain.listas import Origem, Situacao


def executar(sessao: Session) -> str:
    enviadas: dict[int, object] = {}
    for p in sessao.scalars(sa.select(Proposta).where(Proposta.enviada_em.is_not(None))):
        if p.oportunidade_id not in enviadas or p.enviada_em < enviadas[p.oportunidade_id]:
            enviadas[p.oportunidade_id] = p.enviada_em
    da_proposta = da_planilha = 0
    for o in sessao.scalars(sa.select(Oportunidade).where(Oportunidade.data_envio_proposta.is_(None))):
        if o.id in enviadas:
            o.data_envio_proposta = enviadas[o.id]
            da_proposta += 1
        elif o.origem is Origem.CARGA_2026 and o.data_colocacao and o.situacao is not Situacao.ENVIAR_PROPOSTA:
            o.data_envio_proposta = o.data_colocacao
            da_planilha += 1
    if not (da_proposta or da_planilha):
        return "nada a preencher"
    return f"{da_planilha} da planilha de 2026 (envio = originação) e {da_proposta} pela proposta marcada como enviada"
