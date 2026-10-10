"""Contexto da proposta a partir da reunião com o lead (amostra aprovada por Eduardo em 10/10/2026).

A pessoa cola o **resumo** da nota do Granola feita com o template [Potencial Cliente]; a IA sugere a
contextualização da proposta e os campos do perfil do cliente que a reunião trouxe, cada um com a frase
de onde saiu. É **sugestão**: a tela mostra ao lado do que já está, a pessoa escolhe e só então aplica.
Nada aqui grava no banco. O resumo é dado de cliente: vai só para a API, nunca para log.

Mesma mecânica da ata (`crm.agente.ata`): uma chamada, saída estruturada, fallback do servidor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from crm.agente.ata import ClienteDaApi
from crm.agente.sdr import AgenteFalhou, AgenteRecusou, Uso
from crm.proposta.rascunho import FRASE_PADRAO

__all__ = ["MODELO_PADRAO", "SugestaoDoContexto", "sugerir_contexto"]

MODELO_PADRAO = "claude-opus-5-5"
_BETA_FALLBACK = "server-side-fallback-2026-07-01"
_MAX_TOKENS = 8000

SISTEMA = """\
Você prepara a contextualização de uma proposta comercial da Critério (BPO contábil, fiscal, DP e \
financeiro) a partir do resumo da reunião com o potencial cliente, feito no Granola.

Regras:
- Use só o que está no resumo. Não invente número, nome, sistema, cidade nem dor. Se algo não foi \
dito, deixe de fora.
- "contextualizacao": 2 a 4 frases, português do Brasil, terceira pessoa, tom executivo e sóbrio, sem \
adjetivo de venda e sem citar preço. Diga o que a empresa faz e onde opera, a dor que levou à conversa \
e o que ela espera de um parceiro. Comece pelo nome do cliente dado na mensagem. Não escreva a frase \
de fechamento: ela é acrescentada depois.
- "perfil": só os campos da lista dada na mensagem que o resumo informa, com a chave exatamente como \
está na lista. "valor" é curto, como vai na proposta (ex.: "Omie", "R$ 18 milhões", "3 empresas", \
"Rio de Janeiro/RJ e Campinas/SP"). "trecho" é a frase curta do resumo de onde saiu. Campo que o \
resumo não informa fica fora.
- "para_a_carta": até 4 itens curtos que ajudam a escrever a carta: a dor principal, o que espera do \
parceiro, quem decide. Vazio se o resumo não diz.
"""

_ESQUEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "contextualizacao": {"type": "string"},
        "perfil": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"campo": {"type": "string"}, "valor": {"type": "string"}, "trecho": {"type": "string"}},
                "required": ["campo", "valor", "trecho"],
                "additionalProperties": False,
            },
        },
        "para_a_carta": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["contextualizacao", "perfil", "para_a_carta"],
    "additionalProperties": False,
}

_LIMITE_DO_VALOR = 120


@dataclass
class SugestaoDoContexto:
    contextualizacao: str
    """Já com a frase padrão no fim."""
    perfil: list[dict[str, str | None]] = field(default_factory=list)
    """`{"campo": chave da lista, "valor": str, "trecho": str | None}`, só campos da lista, sem repetir."""
    para_a_carta: list[str] = field(default_factory=list)


def _pedido(cliente: str, servicos: list[str], campos: dict[str, str], data: str,
            participantes: str | None, resumo: str) -> str:
    lista = "\n".join(f"- {chave}: {rotulo}" for chave, rotulo in campos.items())
    return (
        f"Cliente: {cliente}\nServiços da proposta: {', '.join(servicos) or 'não definidos'}\n"
        f"Reunião em {data}, com {participantes or 'participantes não informados'}\n\n"
        f"Campos do perfil (chave: o que é):\n{lista}\n\n"
        f"Resumo da reunião:\n<resumo>\n{resumo}\n</resumo>"
    )


def _com_a_frase_padrao(texto: str) -> str:
    texto = texto.strip()
    if not texto:
        return ""
    if FRASE_PADRAO in texto:
        return texto
    return f"{texto}\n{FRASE_PADRAO}"


def sugerir_contexto(
    cliente_da_api: ClienteDaApi, modelo: str, *, cliente: str, servicos: list[str], campos: dict[str, str],
    data: str, participantes: str | None, resumo: str, uso: Uso,
) -> SugestaoDoContexto:
    resposta = cliente_da_api.beta.messages.create(
        model=modelo, max_tokens=_MAX_TOKENS, system=SISTEMA,
        messages=[{"role": "user", "content": _pedido(cliente, servicos, campos, data, participantes, resumo)}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA}},
        betas=[_BETA_FALLBACK], fallbacks="default",
    )
    uso.somar(resposta.usage)
    if resposta.stop_reason == "refusal":
        raise AgenteRecusou("O modelo recusou ler este resumo. Confira o que foi colado e tente de novo.")
    if resposta.stop_reason == "max_tokens":
        raise AgenteFalhou("A sugestão ficou longa demais e foi cortada. Cole só o resumo da reunião e tente de novo.")
    texto = next((b.text for b in resposta.content if getattr(b, "type", None) == "text"), "")
    try:
        dados = json.loads(texto)
    except (TypeError, ValueError) as falha:
        raise AgenteFalhou("O modelo não devolveu a sugestão no formato esperado. Tente de novo.") from falha
    perfil: list[dict[str, str | None]] = []
    vistos: set[str] = set()
    for p in dados.get("perfil", []):
        campo, valor = (p.get("campo") or "").strip(), " ".join((p.get("valor") or "").split())
        if campo not in campos or campo in vistos or not valor:
            continue  # campo fora da lista, repetido ou vazio: a IA não cria campo novo
        vistos.add(campo)
        perfil.append({"campo": campo, "valor": valor[:_LIMITE_DO_VALOR], "trecho": (p.get("trecho") or "").strip() or None})
    return SugestaoDoContexto(
        contextualizacao=_com_a_frase_padrao(dados.get("contextualizacao") or ""),
        perfil=perfil,
        para_a_carta=[i.strip() for i in dados.get("para_a_carta", []) if i and i.strip()][:4],
    )
