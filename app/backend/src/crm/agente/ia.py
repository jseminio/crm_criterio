"""Anthropic e OpenAI, uma ou outra ou as duas (pedido de Eduardo, 07/10/2026).

O CRM não fica preso a um fornecedor: na tela Configurações › Integrações escolhe-se a IA principal
e, se quiser, uma de reserva, que entra quando a principal falha ou recusa.

Para não reescrever o agente SDR, a ata e a análise da carteira, a OpenAI entra por um **adaptador**
que fala a mesma língua do cliente da Anthropic que eles já usam (`messages.create` e
`beta.messages.create`) e traduz para a Responses API da OpenAI (`POST /v1/responses`, conferida na
documentação oficial em 07/10/2026): instrução de sistema, pesquisa na web, ferramenta com esquema
estrito e resposta em JSON com esquema.

Cada resposta leva em `usage.modelo` o modelo que de fato respondeu, para o custo sair pelo preço
certo (`crm.agente.sdr.Uso`). **É OpenAI pela API, não o ChatGPT.**
"""

from __future__ import annotations

import json
from types import SimpleNamespace as NS
from typing import Any

import httpx2 as httpx

from crm.agente.sdr import AgenteFalhou

__all__ = [
    "ANTHROPIC", "OPENAI", "NENHUMA", "MODELO_OPENAI_PADRAO", "ClienteOpenAI", "ClienteAnthropic",
    "ClienteComReserva", "cliente_de", "montar_cliente", "em_uso",
]

ANTHROPIC = "Anthropic"
OPENAI = "OpenAI"
NENHUMA = "Nenhuma"
MODELO_OPENAI_PADRAO = "gpt-6.1-sol"
"""Perto do topo de linha da OpenAI a um custo menor (página de modelos da OpenAI, 07/10/2026)."""

_RESPOSTAS = "https://api.openai.com/v1/responses"


def _texto_do_conteudo(conteudo: Any) -> str:
    if isinstance(conteudo, str):
        return conteudo
    partes = []
    for bloco in conteudo or []:
        tipo = bloco.get("type") if isinstance(bloco, dict) else getattr(bloco, "type", None)
        texto = bloco.get("text") if isinstance(bloco, dict) else getattr(bloco, "text", None)
        if tipo == "text" and texto:
            partes.append(texto)
    return "\n".join(partes)


def _ferramentas(tools: list[dict] | None) -> list[dict]:
    traduzidas = []
    for t in tools or []:
        if str(t.get("type", "")).startswith("web_search"):
            traduzidas.append({"type": "web_search"})
        elif "input_schema" in t:
            traduzidas.append({
                "type": "function", "name": t["name"], "description": t.get("description", ""),
                "parameters": t["input_schema"], "strict": bool(t.get("strict", True)),
            })
    return traduzidas


class _Mensagens:
    def __init__(self, dono: "ClienteOpenAI") -> None:
        self._dono = dono

    def create(self, **pedido: Any) -> Any:
        return self._dono.criar(**pedido)


class ClienteOpenAI:
    """Fala como o cliente da Anthropic, responde pela OpenAI. Usa sempre o próprio modelo."""

    def __init__(self, chave: str, modelo: str = MODELO_OPENAI_PADRAO, http: httpx.Client | None = None) -> None:
        self.chave = chave
        self.modelo = modelo or MODELO_OPENAI_PADRAO
        self._http = http
        self.messages = _Mensagens(self)
        self.beta = NS(messages=_Mensagens(self))

    def __repr__(self) -> str:  # nunca a chave
        return f"ClienteOpenAI(modelo={self.modelo!r})"

    def criar(self, *, system: Any = None, messages: list[dict], max_tokens: int = 4096,
              tools: list[dict] | None = None, output_config: dict | None = None, **_ignorado: Any) -> Any:
        corpo: dict[str, Any] = {
            "model": self.modelo,
            "input": [{"role": m["role"], "content": _texto_do_conteudo(m["content"])} for m in messages],
            "max_output_tokens": max_tokens,
        }
        instrucoes = _texto_do_conteudo(system) if system else ""
        if instrucoes:
            corpo["instructions"] = instrucoes
        ferramentas = _ferramentas(tools)
        if ferramentas:
            corpo["tools"] = ferramentas
        formato = (output_config or {}).get("format")
        if formato and formato.get("type") == "json_schema":
            corpo["text"] = {"format": {"type": "json_schema", "name": "resposta",
                                        "schema": formato["schema"], "strict": True}}
        return self._traduzir(self._postar(corpo))

    def _postar(self, corpo: dict) -> dict:
        cliente = self._http or httpx.Client(timeout=300.0)
        try:
            r = cliente.post(_RESPOSTAS, headers={"Authorization": f"Bearer {self.chave}"}, json=corpo)
        except httpx.HTTPError as falha:
            raise AgenteFalhou(f"Não consegui falar com a OpenAI: {type(falha).__name__}.") from falha
        finally:
            if self._http is None:
                cliente.close()
        if r.status_code == 401:
            raise AgenteFalhou("A OpenAI recusou a chave da API. Confira a chave em Configurações › Integrações.")
        if r.status_code == 429:
            raise AgenteFalhou("O limite de uso da OpenAI foi atingido (ou acabou o crédito). Tente de novo mais tarde.")
        try:
            dados = r.json()
        except ValueError:
            dados = {}
        if r.status_code != 200:
            erro = dados.get("error") if isinstance(dados.get("error"), dict) else {}
            raise AgenteFalhou(f"A API da OpenAI respondeu com erro {r.status_code}: {erro.get('message') or 'sem detalhe'}")
        return dados

    def _traduzir(self, dados: dict) -> Any:
        conteudo, recusou, buscas = [], False, 0
        for item in dados.get("output") or []:
            tipo = item.get("type")
            if tipo == "web_search_call":
                buscas += 1
            elif tipo == "function_call":
                try:
                    entrada = json.loads(item.get("arguments") or "{}")
                except ValueError:
                    entrada = None
                conteudo.append(NS(type="tool_use", name=item.get("name"), input=entrada, id=item.get("call_id")))
            elif tipo == "message":
                for parte in item.get("content") or []:
                    if parte.get("type") == "output_text":
                        conteudo.append(NS(type="text", text=parte.get("text", "")))
                    elif parte.get("type") == "refusal":
                        recusou = True
        incompleto = dados.get("status") == "incomplete" and \
            (dados.get("incomplete_details") or {}).get("reason") == "max_output_tokens"
        parada = ("refusal" if recusou else "max_tokens" if incompleto
                  else "tool_use" if any(b.type == "tool_use" for b in conteudo) else "end_turn")
        uso = dados.get("usage") or {}
        cache = (uso.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0
        return NS(content=conteudo, stop_reason=parada, usage=NS(
            modelo=self.modelo,
            input_tokens=max((uso.get("input_tokens") or 0) - cache, 0),
            cache_read_input_tokens=cache,
            cache_creation_input_tokens=0,
            output_tokens=uso.get("output_tokens") or 0,
            server_tool_use=NS(web_search_requests=buscas),
        ))


class ClienteAnthropic:
    """O cliente da Anthropic, como sempre, marcando no `usage` o modelo que respondeu. Pedido com
    modelo de outro fornecedor (a reserva entrando) vai com o modelo configurado da Anthropic."""

    def __init__(self, cliente: Any, modelo: str) -> None:
        self._cliente = cliente
        self.modelo = modelo
        self.beta = NS(messages=NS(create=lambda **p: self._criar(self._cliente.beta.messages.create, p)))
        self.messages = NS(create=lambda **p: self._criar(self._cliente.messages.create, p))

    def _criar(self, metodo: Any, pedido: dict) -> Any:
        modelo = pedido.get("model") or self.modelo
        if not str(modelo).startswith("claude"):
            modelo = self.modelo
        resposta = metodo(**{**pedido, "model": modelo})
        u = resposta.usage
        return NS(content=resposta.content, stop_reason=resposta.stop_reason, usage=NS(
            modelo=modelo,
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            cache_read_input_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            cache_creation_input_tokens=getattr(u, "cache_creation_input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
            server_tool_use=getattr(u, "server_tool_use", None),
        ))


class ClienteComReserva:
    """A principal responde; se ela falhar ou recusar, a reserva tenta o mesmo pedido."""

    def __init__(self, principal: Any, reserva: Any) -> None:
        self.principal, self.reserva = principal, reserva
        self.messages = NS(create=lambda **p: self._criar(lambda c: c.messages.create(**p)))
        self.beta = NS(messages=NS(create=lambda **p: self._criar(lambda c: c.beta.messages.create(**p))))

    def _criar(self, chamar: Any) -> Any:
        try:
            resposta = chamar(self.principal)
        except Exception:  # noqa: BLE001 — qualquer falha da principal passa para a reserva
            return chamar(self.reserva)
        if getattr(resposta, "stop_reason", None) == "refusal":
            return chamar(self.reserva)
        return resposta


def cliente_de(nome: str, config: Any) -> Any:
    """O cliente de um fornecedor só ("Anthropic" ou "OpenAI"). Sem a chave dele, `AgenteFalhou`."""
    if nome == OPENAI:
        if not config.openai_chave:
            raise AgenteFalhou("A IA escolhida é a OpenAI, mas falta a chave dela em Configurações › Integrações.")
        return ClienteOpenAI(config.openai_chave, config.openai_modelo)
    if not config.chave:
        raise AgenteFalhou("A IA escolhida é a Anthropic, mas falta a chave dela em Configurações › Integrações.")
    import anthropic

    return ClienteAnthropic(anthropic.Anthropic(api_key=config.chave), config.modelo)


def em_uso(config: Any) -> list[str]:
    """Os fornecedores que a configuração usa: a principal e, se houver, a reserva."""
    nomes = [config.ia_principal]
    if config.ia_reserva not in (NENHUMA, "", None, config.ia_principal):
        nomes.append(config.ia_reserva)
    return nomes


def montar_cliente(config: Any) -> tuple[Any, str]:
    """O cliente de IA da configuração (principal, com a reserva atrás) e o modelo da principal."""
    principal = cliente_de(config.ia_principal, config)
    modelo = principal.modelo
    if config.ia_reserva not in (NENHUMA, "", None, config.ia_principal):
        try:
            reserva = cliente_de(config.ia_reserva, config)
        except AgenteFalhou:
            reserva = None  # reserva sem chave não impede a principal
        if reserva is not None:
            return ClienteComReserva(principal, reserva), modelo
    return principal, modelo
