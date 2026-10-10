"""Leva o funil para a etapa única "Perdida" e os motivos de perda para os nomes aprovados (Eduardo, 10/10/2026).

"Recusada" e "Perdido" viram "Perdida". Os motivos mudam só de nome ("Sem retorno" → "Sem retorno do cliente",
"Momento" → "Momento / adiou a decisão", "Escopo" → "Escopo não atende", "Expectativa diferente" → "Expectativa
diferente da promessa"). Em SQL direto: com os valores antigos, o ORM nem leria as linhas. Rodar de novo não muda nada.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

SITUACOES = {"Recusada": "Perdida", "Perdido": "Perdida"}
MOTIVOS = {
    "Sem retorno": "Sem retorno do cliente",
    "Momento": "Momento / adiou a decisão",
    "Escopo": "Escopo não atende",
    "Expectativa diferente": "Expectativa diferente da promessa",
}


def executar(sessao: Session) -> str:
    situacoes = motivos = 0
    for antes, depois in SITUACOES.items():
        situacoes += sessao.execute(sa.text("UPDATE oportunidade SET situacao = :d WHERE situacao = :a"),
                                    {"a": antes, "d": depois}).rowcount or 0
    for antes, depois in MOTIVOS.items():
        motivos += sessao.execute(sa.text("UPDATE oportunidade SET motivo_recusa = :d WHERE motivo_recusa = :a"),
                                  {"a": antes, "d": depois}).rowcount or 0
    if not (situacoes or motivos):
        return "nada a mudar"
    return f"{situacoes} oportunidade(s) para Perdida e {motivos} motivo(s) com o nome aprovado"
