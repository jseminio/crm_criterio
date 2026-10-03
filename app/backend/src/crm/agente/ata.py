"""Ata da reunião de resultado a partir da transcrição do Granola (aprovado por Eduardo em 02/10/2026).

A ata existe para a **área técnica** fazer os ajustes identificados na reunião, com o responsável e o
prazo que a reunião combinou (03/10/2026), e para **vender**: das lacunas técnicas do cliente saem as
oportunidades de novos negócios (consultoria, plano maior, valuation…). O resto (resumo, decisões e
pendências do cliente, pontos sensíveis, estratégia e desafios) é contexto.

Uma chamada só, com saída estruturada (`output_config.format`): o JSON volta sempre no formato pedido.
Modelo: Claude Opus 5.5, com o fallback automático do servidor se recusar por política. O resultado é
**rascunho**: a tela mostra para o gestor revisar, escolher os responsáveis e só então gravar. Nada
aqui grava no banco. A transcrição é dado de cliente: vai só para a API, nunca para log.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
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
- Em cada ajuste, "responsavel" é o nome de quem ficou de fazer, como foi dito (só o nome, sem cargo); \
vazio se ninguém foi citado. "trecho" é a frase curta da transcrição de onde o ajuste saiu.
- "estrategia_e_desafios": o que o cliente contou da estratégia e dos desafios da empresa, em 1 a 3 \
frases; vazio se não falou.
- "oportunidades" são novos negócios para a Critério: uma lacuna técnica da equipe do cliente que um \
serviço da Critério cobre. Uma por serviço. "servico" é um nome da lista de serviços dada na mensagem, \
exatamente como está escrito; "tema" só para Consultoria, da lista dela; "valor" só se um valor foi \
dito, em reais, só o número (ex.: 4500); senão vazio. "trecho" é a frase curta de onde saiu. Não \
invente lacuna que não apareceu na conversa.
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
                "properties": {
                    "descricao": {"type": "string"}, "prazo": {"type": "string"},
                    "responsavel": {"type": "string"}, "trecho": {"type": "string"},
                },
                "required": ["descricao", "prazo", "responsavel", "trecho"],
                "additionalProperties": False,
            },
        },
        "estrategia_e_desafios": {"type": "string"},
        "oportunidades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lacuna": {"type": "string"}, "servico": {"type": "string"}, "tema": {"type": "string"},
                    "valor": {"type": "string"}, "trecho": {"type": "string"},
                },
                "required": ["lacuna", "servico", "tema", "valor", "trecho"],
                "additionalProperties": False,
            },
        },
        "pendencias_do_cliente": {"type": "array", "items": {"type": "string"}},
        "pontos_sensiveis": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumo", "decisoes_do_cliente", "ajustes", "pendencias_do_cliente", "pontos_sensiveis",
                 "estrategia_e_desafios", "oportunidades"],
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
    """`{"descricao", "prazo": "AAAA-MM-DD" | None, "responsavel": nome citado | None, "trecho": str | None}`"""
    pendencias_do_cliente: list[str] = field(default_factory=list)
    pontos_sensiveis: list[str] = field(default_factory=list)
    estrategia_e_desafios: str = ""
    oportunidades: list[dict[str, str | None]] = field(default_factory=list)
    """`{"lacuna", "servico", "tema": str | None, "valor": "4500.00" | None, "trecho": str | None}`"""


def _pedido(
    cliente: str, tipo: str, data: str, participantes: str | None, transcricao: str,
    responsaveis: list[str], servicos: list[str],
) -> str:
    return (
        f"Cliente: {cliente}\nReunião: {tipo}, em {data}\n"
        f"Participantes: {participantes or 'não informados'}\n"
        f"Área técnica da Critério (quem pode receber ajuste): {', '.join(responsaveis) or 'ninguém cadastrado'}\n"
        f"Serviços da Critério: {'; '.join(servicos)}\n\n"
        f"Transcrição:\n<transcricao>\n{transcricao}\n</transcricao>"
    )


def _prazo(valor: str | None) -> str | None:
    """Só data AAAA-MM-DD; qualquer outra coisa vira vazio (o gestor preenche)."""
    v = (valor or "").strip()
    if len(v) == 10 and v[4] == "-" and v[7] == "-" and v.replace("-", "").isdigit():
        return v
    return None


def _valor(texto: str | None) -> str | None:
    """Só número em reais ("4500", "4.500,00", "R$ 4500"); o resto vira vazio."""
    v = (texto or "").replace("R$", "").strip()
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        numero = Decimal(v)
    except InvalidOperation:
        return None
    return f"{numero:.2f}" if numero > 0 else None


def _ou_nada(texto: str | None) -> str | None:
    return (texto or "").strip() or None


def _limpos(itens: list[str]) -> list[str]:
    return [i.strip() for i in itens if i and i.strip()]


def escrever_ata(
    cliente_da_api: ClienteDaApi, modelo: str, *, cliente: str, tipo: str, data: str,
    participantes: str | None, transcricao: str, uso: Uso,
    responsaveis: list[str] | None = None, servicos: list[str] | None = None,
) -> RascunhoDaAta:
    resposta = cliente_da_api.beta.messages.create(
        model=modelo, max_tokens=_MAX_TOKENS, system=SISTEMA,
        messages=[{"role": "user", "content": _pedido(
            cliente, tipo, data, participantes, transcricao, responsaveis or [], servicos or [])}],
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
            {"descricao": a["descricao"].strip(), "prazo": _prazo(a.get("prazo")),
             "responsavel": _ou_nada(a.get("responsavel")), "trecho": _ou_nada(a.get("trecho"))}
            for a in dados.get("ajustes", []) if (a.get("descricao") or "").strip()
        ],
        pendencias_do_cliente=_limpos(dados.get("pendencias_do_cliente", [])),
        pontos_sensiveis=_limpos(dados.get("pontos_sensiveis", [])),
        estrategia_e_desafios=(dados.get("estrategia_e_desafios") or "").strip(),
        oportunidades=[
            {"lacuna": o["lacuna"].strip(), "servico": (o.get("servico") or "").strip(), "tema": _ou_nada(o.get("tema")),
             "valor": _valor(o.get("valor")), "trecho": _ou_nada(o.get("trecho"))}
            for o in dados.get("oportunidades", []) if (o.get("lacuna") or "").strip()
        ],
    )
