"""Troca o link do questionário que o SDR envia: do Netlify para o próprio CRM (decisão de Eduardo, 11/11/2026).

Só troca se a tela ainda tem o endereço antigo do Netlify (com ou sem `?v=…`); um endereço escolhido por alguém fica.
Sem nada na tela, vale o padrão do código, que já é o do CRM.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crm.agente.config import LINK_DO_QUESTIONARIO_NETLIFY, LINK_DO_QUESTIONARIO_PADRAO
from crm.db.base import agora
from crm.db.modelos import ConfiguracaoDoSistema

QUEM = "atualizador (questionário no CRM)"


def executar(sessao: Session) -> str:
    linha = sessao.get(ConfiguracaoDoSistema, "questionario.link")
    if linha is None or not linha.valor:
        return "nada a fazer: a tela não tem link próprio, vale o padrão do CRM"
    if not linha.valor.strip().startswith(LINK_DO_QUESTIONARIO_NETLIFY.split("/questionario")[0]):
        return f"nada a fazer: a tela tem um link escolhido ({linha.valor})"
    linha.valor, linha.alterado_por, linha.alterado_em = LINK_DO_QUESTIONARIO_PADRAO, QUEM, agora()
    sessao.flush()
    return f"link trocado para {LINK_DO_QUESTIONARIO_PADRAO}"
