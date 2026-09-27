"""Mensagem de erro comum a qualquer chamada à API da Anthropic — SDR e análise da carteira.

Nunca expõe chave, corpo da requisição ou dado do cliente: só o que ajuda a pessoa a agir.
"""

from __future__ import annotations

from crm.agente.sdr import AgenteFalhou

__all__ = ["mensagem_de_falha"]


def mensagem_de_falha(falha: Exception) -> str:
    if isinstance(falha, AgenteFalhou):
        return str(falha)
    try:
        import anthropic
    except ImportError:  # pragma: no cover — o pacote é dependência
        return f"Falha inesperada no agente ({type(falha).__name__})."
    if isinstance(falha, anthropic.AuthenticationError):
        return "A Anthropic recusou a chave da API. Confira ANTHROPIC_API_KEY no .env."
    if isinstance(falha, anthropic.RateLimitError):
        return "O limite de uso da API foi atingido. Tente de novo em alguns minutos."
    if isinstance(falha, anthropic.APIConnectionError):
        return "Não consegui falar com a Anthropic. A máquina está na internet?"
    if isinstance(falha, anthropic.APIStatusError):
        return f"A API da Anthropic respondeu com erro {falha.status_code}. Tente de novo."
    return f"Falha inesperada no agente ({type(falha).__name__})."
