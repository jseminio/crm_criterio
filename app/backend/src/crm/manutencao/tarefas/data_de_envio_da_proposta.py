"""Preenche a data de envio da proposta nas oportunidades que já existem (decisão de Eduardo, 10/10/2026).

- **Planilha de 2026:** a originação já era o envio. Recebe a data de originação quem já passou de "Enviar
  proposta" (quem ainda está em "Enviar proposta" não enviou).
- **Proposta gerada no CRM e marcada como enviada:** a primeira data de envio dela.

Em SQL direto, sem ler as oportunidades pelo ORM: esta tarefa roda antes de `2026_10_10_perdida_e_motivos`, e com
"Recusada" ainda no banco o ORM nem leria as linhas. Não toca em quem já tem a data. Rodar de novo não muda nada.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.domain.listas import Origem, Situacao


def executar(sessao: Session) -> str:
    da_proposta = sessao.execute(sa.text(
        "UPDATE oportunidade SET data_envio_proposta = ("
        "  SELECT MIN(p.enviada_em) FROM proposta p WHERE p.oportunidade_id = oportunidade.id AND p.enviada_em IS NOT NULL"
        ") WHERE data_envio_proposta IS NULL AND EXISTS ("
        "  SELECT 1 FROM proposta p WHERE p.oportunidade_id = oportunidade.id AND p.enviada_em IS NOT NULL)"
    )).rowcount or 0
    da_planilha = sessao.execute(sa.text(
        "UPDATE oportunidade SET data_envio_proposta = data_colocacao "
        "WHERE data_envio_proposta IS NULL AND data_colocacao IS NOT NULL AND origem = :carga AND situacao <> :enviar"
    ), {"carga": Origem.CARGA_2026.value, "enviar": Situacao.ENVIAR_PROPOSTA.value}).rowcount or 0
    if not (da_proposta or da_planilha):
        return "nada a preencher"
    return f"{da_planilha} da planilha de 2026 (envio = originação) e {da_proposta} pela proposta marcada como enviada"
