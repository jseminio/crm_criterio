"""A Menino da Ilha tem o contrato de BPO Financeiro no formato antigo, sem 13ª (decisão de Eduardo em 11/10/2026):
12 parcelas no ano. Os demais seguem em 13. Em SQL direto e só nos contratos que ainda estão no padrão (13): se alguém
já mudou na tela, fica como está. Rodar de novo não muda nada."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session


def executar(sessao: Session) -> str:
    feitos = sessao.execute(sa.text(
        "UPDATE contrato SET parcelas_no_ano = 12 WHERE parcelas_no_ano = 13 "
        "AND lower(coalesce(escopo, '')) LIKE '%bpo financeiro%' "
        "AND grupo_id IN (SELECT id FROM grupo_economico WHERE lower(nome) LIKE '%menino da ilha%')"
    )).rowcount or 0
    if not feitos:
        return "nada a mudar: nenhum contrato de BPO Financeiro da Menino da Ilha em 13 parcelas"
    return f"{feitos} contrato(s) de BPO Financeiro da Menino da Ilha em 12 parcelas (formato antigo, sem 13ª)"
