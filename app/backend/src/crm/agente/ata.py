"""Ata da reunião de resultado a partir da transcrição do Granola (aprovado por Eduardo em 02/10/2026).

A ata existe para a **área técnica** fazer os ajustes identificados na reunião. Por isso o centro dela é
a lista de ajustes; o resto (resumo, decisões e pendências do cliente, pontos sensíveis) é contexto.

Uma chamada só, com saída estruturada (`output_config.format`): o JSON volta sempre no formato pedido.
Modelo: Claude Opus 5.5, com o fallback automático do servidor se recusar por política. O resultado é
**rascunho**: a tela mostra para o gestor revisar, escolher os responsáveis e só então gravar. Nada
aqui grava no banco. A transcrição é dado de cliente: vai só para a API, nunca para log.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from crm.agente.sdr import AgenteFalhou, AgenteRecusou, Uso

__all__ = ["MODELO_PADRAO", "RascunhoDaAta", "escrever_ata"]

MODELO_PADRAO = "claude-opus-5-5"
_BETA_FALLBACK = "server-side-fallback-2026-07-01"
_MAX_TOKENS = 16000

SISTEMA = """\
Você escreve a ata de uma reunião de resultado entre a Critério (BPO contábil, fiscal, DP e \
financeiro) e um cliente, a partir da transcrição da reunião. A ata serve, antes de tudo, para a \
área técnica da Critério fazer os ajustes que a reunião identificou.

Regras:
- Use só o que está na transcrição. Não invente número, nome, prazo nem decisão. Se algo não foi \
dito, deixe de fora.
- "ajustes" são os trabalhos que a área técnica da Critério precisa fazer: correção de lançamento, \
reclassificação, conciliação, ajuste de relatório, mudança de procedimento. Cada um precisa ser \
acionável sozinho: diga o quê, onde (empresa, conta, mês, relatório) e o porquê, se foi dito. Um \
ajuste por item. Prazo só se foi combinado na reunião, no formato AAAA-MM-DD; senão, vazio.
- "decisoes_do_cliente" são decisões de negócio do cliente tomadas a partir dos números.
- "pendencias_do_cliente" são coisas que o cliente ficou de mandar ou fazer.
- "pontos_sensiveis" são riscos ou atritos no relacionamento ou na operação.
- "resumo": 3 a 5 frases, português do Brasil, tom direto, sem saudação.
- Listas sem item ficam vazias.
"""

_ESQUEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resumo": {"type": "string"},
        "decisoes_do_cliente": {"type": "array", "items": {"type": "string"}},
        "ajustes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"descricao": {"type": "string"}, "prazo": {"type": "string"}},
                "required": ["descricao", "prazo"],
                "additionalProperties": False,
            },
        },
        "pendencias_do_cliente": {"type": "array", "items": {"type": "string"}},
        "pontos_sensiveis": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumo", "decisoes_do_cliente", "ajustes", "pendencias_do_cliente", "pontos_sensiveis"],
    "additionalProperties": False,
}


class ClienteDaApi(Protocol):
    @property
    def beta(self): ...  # noqa: ANN401,D102


@dataclass
class RascunhoDaAta:
    resumo: str
    decisoes_do_cliente: list[str] = field(default_factory=list)
    ajustes: list[dict[str, str | None]] = field(default_factory=list)
    """`{"descricao": ..., "prazo": "AAAA-MM-DD" | None}`"""
    pendencias_do_cliente: list[str] = field(default_factory=list)
    pontos_sensiveis: list[str] = field(default_factory=list)


def _pedido(cliente: str, tipo: str, data: str, participantes: str | None, transcricao: str) -> str:
    return (
        f"Cliente: {cliente}\nReunião: {tipo}, em {data}\n"
        f"Participantes: {participantes or 'não informados'}\n\n"
        f"Transcrição:\n<transcricao>\n{transcricao}\n</transcricao>"
    )


def _prazo(valor: str | None) -> str | None:
    """Só data AAAA-MM-DD; qualquer outra coisa vira vazio (o gestor preenche)."""
    v = (valor or "").strip()
    if len(v) == 10 and v[4] == "-" and v[7] == "-" and v.replace("-", "").isdigit():
        return v
    return None


def _limpos(itens: list[str]) -> list[str]:
    return [i.strip() for i in itens if i and i.strip()]


def escrever_ata(
    cliente_da_api: ClienteDaApi, modelo: str, *, cliente: str, tipo: str, data: str,
    participantes: str | None, transcricao: str, uso: Uso,
) -> RascunhoDaAta:
    resposta = cliente_da_api.beta.messages.create(
        model=modelo, max_tokens=_MAX_TOKENS, system=SISTEMA,
        messages=[{"role": "user", "content": _pedido(cliente, tipo, data, participantes, transcricao)}],
        output_config={"format": {"type": "json_schema", "schema": _ESQUEMA}},
        betas=[_BETA_FALLBACK], fallbacks="default",
    )
    uso.somar(resposta.usage)
    if resposta.stop_reason == "refusal":
        raise AgenteRecusou("O modelo recusou escrever esta ata. Confira a transcrição colada e tente de novo.")
    if resposta.stop_reason == "max_tokens":
        raise AgenteFalhou("A ata ficou longa demais e foi cortada. Cole só o trecho da reunião e tente de novo.")
    texto = next((b.text for b in resposta.content if getattr(b, "type", None) == "text"), "")
    try:
        dados = json.loads(texto)
    except (TypeError, ValueError) as falha:
        raise AgenteFalhou("O modelo não devolveu a ata no formato esperado. Tente de novo.") from falha
    return RascunhoDaAta(
        resumo=(dados.get("resumo") or "").strip(),
        decisoes_do_cliente=_limpos(dados.get("decisoes_do_cliente", [])),
        ajustes=[
            {"descricao": a["descricao"].strip(), "prazo": _prazo(a.get("prazo"))}
            for a in dados.get("ajustes", []) if (a.get("descricao") or "").strip()
        ],
        pendencias_do_cliente=_limpos(dados.get("pendencias_do_cliente", [])),
        pontos_sensiveis=_limpos(dados.get("pontos_sensiveis", [])),
    )
