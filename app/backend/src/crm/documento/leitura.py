"""Leitura do PDF assinado pela IA (amostra aprovada por Eduardo em 18/10/2026).

A IA lê o contrato, a proposta aceita ou o aditivo e devolve, por campo, o valor com a página e o trecho de onde saiu.
É **sugestão**: nada aqui grava no banco, e a tela mostra lado a lado o que está no CRM e o que foi lido, para uma
pessoa marcar o que gravar (`crm.api.documentos`).

Uma chamada só, com o PDF em base64 num bloco `document` e saída estruturada (`output_config.format`). Só pela
Anthropic: o PDF é dado de cliente e não vai para um segundo fornecedor. Até 32 MB por pedido e 600 páginas (limites da
API da Anthropic); o CRM aceita PDF de até 20 MB, que em base64 fica abaixo de 27 MB. O PDF nunca vai para log.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from crm.agente.sdr import AgenteFalhou, AgenteRecusou, Uso

__all__ = ["CAMPOS", "TIPOS", "ler_pdf", "normalizar"]

_BETA_FALLBACK = "server-side-fallback-2026-07-01"
_MAX_TOKENS = 16000

TIPOS = ("contrato", "proposta", "aditivo")

CAMPOS: dict[str, str] = {
    "numero": "Número do documento como está escrito (ex.: CONT CCE RJ1 102.2026, PROP CCE RJ 041.2019)",
    "data_assinatura": "Data da assinatura (contrato, aditivo) ou do aceite (proposta), AAAA-MM-DD",
    "data_competencia": "Competência em que os serviços começam (ex.: \"a partir da competência de março/2025\"), "
                        "AAAA-MM-01; vazio se não diz",
    "data_inicio_pagamento": "Vencimento do primeiro pagamento, AAAA-MM-DD; vazio se não diz",
    "preco_mensal": "Honorário mensal total, em reais, só o número",
    "base_do_valor": "\"bruto\" se o valor inclui os impostos, \"liquido\" se os impostos são somados, vazio se não diz",
    "parcelas_no_ano": "12 ou 13 (13 quando há 13ª parcela/honorário no fim do ano)",
    "escopo": "Os serviços contratados ou propostos, em uma linha",
    "data_fim": "Fim da vigência, AAAA-MM-DD, só se o documento disser a data ou o prazo a partir da assinatura",
    "vigencia": "Prazo de vigência como está escrito (ex.: 12 meses)",
    "renovacao": "O que diz da renovação (ex.: automática por iguais períodos)",
    "multa_rescisoria": "A multa por rescisão, como está escrita (ex.: 2 parcelas mensais)",
    "aviso_previo_dias": "Dias de aviso prévio para rescindir, só o número",
    "signatario": "Quem assina pelo cliente (contratante), nome e cargo se houver",
    "plano": "Na proposta com vários planos, o plano escolhido; vazio se não há escolha marcada",
}

SISTEMA = """\
Você lê um documento comercial da Critério Consultores (BPO contábil, fiscal, DP e financeiro): um contrato assinado, \
uma proposta aceita ou um aditivo de contrato. Extraia os campos pedidos para uma pessoa conferir.

Regras:
- Use só o que está escrito no documento. Não invente, não estime e não complete. Campo que o documento não traz fica \
com valor vazio.
- A Critério é a contratada. O cliente é a contratante: CNPJ, razão social e signatário são os do cliente, nunca os \
da Critério.
- Para cada campo, "pagina" é o número da página do PDF de onde o valor saiu (0 se vazio) e "trecho" é a frase curta \
do documento que o sustenta, copiada como está (vazio se o valor é vazio).
- Datas em AAAA-MM-DD. Valores em reais só com o número, ponto como separador decimal (ex.: 7000.00).
- "tipo": "contrato", "proposta" ou "aditivo"; "outro" se não é nenhum deles.
- "cnpjs": todos os CNPJs do cliente que aparecem como contratante ou como empresas atendidas, só os 14 dígitos.
"""


def _esquema() -> dict[str, Any]:
    campo = {
        "type": "object",
        "properties": {"valor": {"type": "string"}, "pagina": {"type": "integer"}, "trecho": {"type": "string"}},
        "required": ["valor", "pagina", "trecho"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": [*TIPOS, "outro"]},
            "razao_social": {"type": "string"},
            "cnpjs": {"type": "array", "items": {"type": "string"}},
            "campos": {
                "type": "object",
                "properties": {nome: campo for nome in CAMPOS},
                "required": list(CAMPOS),
                "additionalProperties": False,
            },
        },
        "required": ["tipo", "razao_social", "cnpjs", "campos"],
        "additionalProperties": False,
    }


class ClienteDaApi(Protocol):
    @property
    def beta(self): ...  # noqa: ANN401,D102


def _data(v: str) -> str:
    v = v.strip()
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        return ""


def _dinheiro(v: str) -> str:
    v = v.replace("R$", "").strip()
    if "," in v:
        v = v.replace(".", "").replace(",", ".")
    try:
        n = Decimal(v)
    except InvalidOperation:
        return ""
    return f"{n:.2f}" if n > 0 else ""


def _inteiro(v: str, permitidos: tuple[int, ...] | None = None) -> str:
    m = re.search(r"\d+", v)
    if not m:
        return ""
    n = int(m.group())
    return str(n) if (permitidos is None or n in permitidos) and 0 < n < 1000 else ""


def normalizar(dados: dict[str, Any]) -> dict[str, Any]:
    """Põe cada valor no formato que o CRM grava; o que não se encaixa vira vazio (a pessoa preenche à mão)."""
    tratar = {
        "data_assinatura": _data, "data_fim": _data, "data_competencia": _data, "data_inicio_pagamento": _data, "preco_mensal": _dinheiro,
        "base_do_valor": lambda v: v.strip().lower().replace("í", "i") if v.strip().lower().replace("í", "i") in ("bruto", "liquido") else "",
        "parcelas_no_ano": lambda v: _inteiro(v, (12, 13)), "aviso_previo_dias": _inteiro,
    }
    campos = {}
    for nome in CAMPOS:
        bruto = (dados.get("campos") or {}).get(nome) or {}
        valor = str(bruto.get("valor") or "").strip()
        valor = tratar.get(nome, lambda v: v[:200])(valor) if valor else ""
        campos[nome] = {"valor": valor, "pagina": int(bruto.get("pagina") or 0) if valor else 0,
                        "trecho": str(bruto.get("trecho") or "").strip()[:300] if valor else ""}
    cnpjs = []
    for c in dados.get("cnpjs") or []:
        d = re.sub(r"\D", "", str(c))
        if len(d) == 14 and d not in cnpjs:
            cnpjs.append(d)
    tipo = dados.get("tipo") if dados.get("tipo") in (*TIPOS, "outro") else "outro"
    return {"tipo": tipo, "razao_social": str(dados.get("razao_social") or "").strip()[:200], "cnpjs": cnpjs,
            "campos": campos}


def ler_pdf(cliente_da_api: ClienteDaApi, modelo: str, *, pdf: bytes, nome: str, uso: Uso) -> dict[str, Any]:
    resposta = cliente_da_api.beta.messages.create(
        model=modelo, max_tokens=_MAX_TOKENS, system=SISTEMA,
        messages=[{"role": "user", "content": [
            {"type": "document", "title": nome[:200],
             "source": {"type": "base64", "media_type": "application/pdf", "data": base64.b64encode(pdf).decode()}},
            {"type": "text", "text": "Campos a extrair:\n" + "\n".join(f"- {n}: {d}" for n, d in CAMPOS.items())},
        ]}],
        output_config={"format": {"type": "json_schema", "schema": _esquema()}},
        betas=[_BETA_FALLBACK], fallbacks="default",
    )
    uso.somar(resposta.usage)
    if resposta.stop_reason == "refusal":
        raise AgenteRecusou("A IA recusou ler este documento. Preencha os campos à mão.")
    if resposta.stop_reason == "max_tokens":
        raise AgenteFalhou("A leitura ficou longa demais e foi cortada. Tente ler de novo.")
    texto = next((b.text for b in resposta.content if getattr(b, "type", None) == "text"), "")
    try:
        dados = json.loads(texto)
    except (TypeError, ValueError) as falha:
        raise AgenteFalhou("A IA não devolveu a leitura no formato esperado. Tente ler de novo.") from falha
    return normalizar(dados)
