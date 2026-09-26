"""O fluxo do agente, contra um cliente falso da API: sem chave, sem rede.

O que importa provar: ele retoma a pausa da busca no servidor, trata recusa,
lembra de registrar uma vez só, soma o custo mesmo quando falha, e não manda
e-mail nem telefone de contato para fora da máquina.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from crm.agente.sdr import (
    AgenteFalhou,
    AgenteRecusou,
    AgenteSDR,
    ContextoDaConta,
    Uso,
)
from crm.domain.listas import CanalDeAbordagem

REGISTRO = {
    "historico": "Staff loan em espera desde fev/25.",
    "pesquisa": [{"fato": "Abriu filial em 2025", "fonte": "https://exemplo.com/omega"}],
    "quem_decide": "Diretora financeira",
    "assunto": "Retomando a conversa",
    "mensagem": "Olá, [nome]. Proponho 30 minutos.",
}


def _uso(entrada=1000, saida=200, buscas=0):
    return NS(
        input_tokens=entrada,
        output_tokens=saida,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        server_tool_use=NS(web_search_requests=buscas),
    )


def _resposta(stop_reason, *blocos, uso=None):
    return NS(stop_reason=stop_reason, content=list(blocos), usage=uso or _uso())


def _registro(dados=REGISTRO):
    return NS(type="tool_use", name="registrar_preparo", id="tu_1", input=dados)


class ClienteFalso:
    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.chamadas: list[dict] = []
        self.beta = NS(messages=NS(create=self._criar))

    def _criar(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.respostas.pop(0)


@pytest.fixture
def contexto():
    return ContextoDaConta(
        nome="Omega",
        mes="2026-10",
        canal=CanalDeAbordagem.EMAIL,
        quem_apresenta="Parceiro A",
        historico_crm=["02/2025 · Staff loan · On hold"],
        contexto_informado="Já é cliente de consultoria.",
        contatos=["Ana Souza — Diretora financeira"],
    )


def test_retoma_a_pausa_da_busca_e_registra(contexto):
    pausa = NS(type="server_tool_use", name="web_search", id="srv_1", input={"query": "Omega"})
    cliente = ClienteFalso(
        _resposta("pause_turn", pausa, uso=_uso(buscas=2)),
        _resposta("tool_use", _registro(), uso=_uso(buscas=1)),
    )
    uso = Uso("claude-opus-5")
    preparo = AgenteSDR(cliente).preparar(contexto, uso=uso)

    assert preparo.mensagem == REGISTRO["mensagem"]
    assert preparo.pesquisa == REGISTRO["pesquisa"]
    # A retomada reenvia a vez do assistente como veio, sem "continue" inventado.
    segunda = cliente.chamadas[1]["messages"]
    assert [m["role"] for m in segunda] == ["user", "assistant"]
    assert segunda[1]["content"] == [pausa]
    assert uso.buscas_web == 3
    assert uso.tokens_entrada == 2000


def test_pede_com_fallback_e_as_duas_ferramentas(contexto):
    cliente = ClienteFalso(_resposta("tool_use", _registro()))
    AgenteSDR(cliente).preparar(contexto)
    chamada = cliente.chamadas[0]
    assert chamada["model"] == "claude-opus-5"
    assert chamada["fallbacks"] == "default"
    assert chamada["betas"] == ["server-side-fallback-2026-07-01"]
    assert [t["name"] for t in chamada["tools"]] == ["web_search", "registrar_preparo"]
    assert chamada["tools"][1]["strict"] is True


def test_nao_manda_email_nem_telefone_de_contato(contexto):
    cliente = ClienteFalso(_resposta("tool_use", _registro()))
    AgenteSDR(cliente).preparar(contexto)
    pedido = cliente.chamadas[0]["messages"][0]["content"]
    assert "Ana Souza — Diretora financeira" in pedido
    assert "@" not in pedido
    assert "<conta>" in pedido and "não instruções" in pedido


def test_recusa_vira_erro_explicado(contexto):
    cliente = ClienteFalso(_resposta("refusal"))
    with pytest.raises(AgenteRecusou, match="recusou"):
        AgenteSDR(cliente).preparar(contexto)


def test_lembra_de_registrar_uma_vez(contexto):
    texto = NS(type="text", text="Pronto.")
    cliente = ClienteFalso(_resposta("end_turn", texto), _resposta("tool_use", _registro()))
    preparo = AgenteSDR(cliente).preparar(contexto)
    assert preparo.assunto == "Retomando a conversa"
    lembrete = cliente.chamadas[1]["messages"][-1]
    assert lembrete["role"] == "user" and "registrar_preparo" in lembrete["content"]


def test_desiste_se_nunca_registra(contexto):
    texto = NS(type="text", text="Pronto.")
    cliente = ClienteFalso(_resposta("end_turn", texto), _resposta("end_turn", texto))
    uso = Uso("claude-opus-5")
    with pytest.raises(AgenteFalhou, match="sem registrar"):
        AgenteSDR(cliente).preparar(contexto, uso=uso)
    assert uso.tokens_entrada == 2000  # o custo da tentativa conta


def test_resposta_cortada(contexto):
    cliente = ClienteFalso(_resposta("max_tokens", NS(type="text", text="…")))
    with pytest.raises(AgenteFalhou, match="cortada"):
        AgenteSDR(cliente).preparar(contexto)


def test_registro_sem_mensagem_falha(contexto):
    cliente = ClienteFalso(_resposta("tool_use", _registro({**REGISTRO, "mensagem": " "})))
    with pytest.raises(AgenteFalhou, match="mensagem"):
        AgenteSDR(cliente).preparar(contexto)


def test_instrucao_e_rascunho_anterior_vao_no_pedido(contexto):
    cliente = ClienteFalso(_resposta("tool_use", _registro()))
    AgenteSDR(cliente).preparar(
        contexto, instrucao="Mais curta", rascunho_anterior="Texto antigo"
    )
    pedido = cliente.chamadas[0]["messages"][0]["content"]
    assert "Mais curta" in pedido and "Texto antigo" in pedido


def test_custo_estimado_do_opus_5():
    uso = Uso("claude-opus-5")
    uso.somar(_uso(entrada=100_000, saida=10_000, buscas=5))
    # 0,1 M × US$ 5 + 0,01 M × US$ 25 + 5 × US$ 0,01
    assert uso.custo_usd == Decimal("0.8000")


def test_modelo_sem_preco_nao_vira_zero():
    uso = Uso("modelo-desconhecido")
    uso.somar(_uso())
    assert uso.custo_usd is None
