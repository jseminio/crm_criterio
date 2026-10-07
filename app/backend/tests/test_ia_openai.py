"""Anthropic e OpenAI, uma ou outra ou as duas (07/10/2026): o adaptador da OpenAI, a reserva e o custo, sem rede."""

from __future__ import annotations

import json
from decimal import Decimal
from types import SimpleNamespace as NS

import httpx2 as httpx
import pytest

from crm.agente.ata import escrever_ata
from crm.agente.ia import ClienteComReserva, ClienteOpenAI, cliente_de, em_uso, montar_cliente
from crm.agente.sdr import AgenteFalhou, AgenteSDR, ContextoDaConta, Uso
from crm.domain.listas import CanalDeAbordagem


def _openai(respostas: list[dict], status: int = 200, pedidos: list | None = None) -> ClienteOpenAI:
    fila = list(respostas)

    def tratar(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(json.loads(pedido.content))
        return httpx.Response(status, json=fila.pop(0) if fila else {})

    return ClienteOpenAI("sk-openai-secreta", "gpt-6.1-sol", http=httpx.Client(transport=httpx.MockTransport(tratar)))


def _texto(t: str, **uso) -> dict:
    return {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": t}]}],
            "usage": {"input_tokens": 1000, "output_tokens": 100, **uso}}


REGISTRO = {"historico": "Sem histórico.", "pesquisa": [{"fato": "Hospital em BH", "fonte": "https://exemplo.com"}],
            "quem_decide": "a confirmar", "assunto": "", "mensagem": "Olá, [nome]."}

CONTEXTO = ContextoDaConta(nome="Hospital Exemplo", mes="2026-10", canal=CanalDeAbordagem.WHATSAPP,
                           quem_apresenta="Eduardo", historico_crm=[])


class TestTraducao:
    def test_o_pedido_vai_no_formato_da_responses_api(self):
        pedidos: list[dict] = []
        cliente = _openai([_texto("ok")], pedidos=pedidos)
        cliente.beta.messages.create(
            model="claude-opus-5", max_tokens=500, system="Você é o SDR.",
            messages=[{"role": "user", "content": "Prepare."}],
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 8},
                   {"name": "registrar", "description": "Registra.", "strict": True,
                    "input_schema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}}],
            betas=["x"], fallbacks="default",
        )
        (corpo,) = pedidos
        assert corpo["model"] == "gpt-6.1-sol"  # sempre o modelo da OpenAI configurado
        assert corpo["instructions"] == "Você é o SDR." and corpo["max_output_tokens"] == 500
        assert corpo["input"] == [{"role": "user", "content": "Prepare."}]
        assert corpo["tools"] == [
            {"type": "web_search"},
            {"type": "function", "name": "registrar", "description": "Registra.", "strict": True,
             "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}},
        ]
        assert "betas" not in corpo and "fallbacks" not in corpo

    def test_a_resposta_volta_no_formato_da_anthropic(self):
        resposta = _openai([{
            "status": "completed",
            "output": [{"type": "web_search_call"}, {"type": "web_search_call"},
                       {"type": "function_call", "name": "registrar", "arguments": json.dumps({"a": 1}), "call_id": "c1"}],
            "usage": {"input_tokens": 1000, "output_tokens": 50, "input_tokens_details": {"cached_tokens": 400}},
        }]).messages.create(messages=[{"role": "user", "content": "x"}])
        assert resposta.stop_reason == "tool_use"
        (bloco,) = resposta.content
        assert (bloco.type, bloco.name, bloco.input) == ("tool_use", "registrar", {"a": 1})
        u = resposta.usage
        assert (u.modelo, u.input_tokens, u.cache_read_input_tokens, u.output_tokens) == ("gpt-6.1-sol", 600, 400, 50)
        assert u.server_tool_use.web_search_requests == 2

    @pytest.mark.parametrize("dados, parada", [
        ({"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "não"}]}]}, "refusal"),
        ({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}, "output": []}, "max_tokens"),
    ])
    def test_recusa_e_corte(self, dados, parada):
        assert _openai([dados]).messages.create(messages=[{"role": "user", "content": "x"}]).stop_reason == parada

    @pytest.mark.parametrize("status, trecho", [(401, "recusou a chave"), (429, "limite"), (500, "erro 500")])
    def test_erro_explica_sem_mostrar_a_chave(self, status, trecho):
        with pytest.raises(AgenteFalhou) as falha:
            _openai([{"error": {"message": "falhou"}}], status=status).messages.create(messages=[])
        assert trecho in str(falha.value) and "sk-openai-secreta" not in str(falha.value)
        assert "sk-openai-secreta" not in repr(_openai([]))


class TestUsosReais:
    def test_o_agente_sdr_pesquisa_e_registra_pela_openai(self):
        pedidos: list[dict] = []
        cliente = _openai([{
            "status": "completed",
            "output": [{"type": "web_search_call"},
                       {"type": "function_call", "name": "registrar_preparo", "arguments": json.dumps(REGISTRO)}],
            "usage": {"input_tokens": 10_000, "output_tokens": 1_000},
        }], pedidos=pedidos)
        uso = Uso("gpt-6.1-sol")
        preparo = AgenteSDR(cliente, "gpt-6.1-sol").preparar(CONTEXTO, uso=uso)
        assert preparo.mensagem == "Olá, [nome]." and preparo.pesquisa[0]["fonte"] == "https://exemplo.com"
        assert {"type": "web_search"} in pedidos[0]["tools"]
        # 10 mil de entrada a US$ 2 + mil de saída a US$ 10 (por milhão) + uma busca a US$ 0,01
        assert uso.custo_usd == Decimal("0.0400")

    def test_a_ata_sai_em_json_pela_openai(self):
        ata = {"resumo": "Reunião boa.", "decisoes_do_cliente": [], "ajustes": [], "pendencias_do_cliente": [],
               "pontos_sensiveis": [], "estrategia_e_desafios": "", "oportunidades": []}
        pedidos: list[dict] = []
        rascunho = escrever_ata(_openai([_texto(json.dumps(ata))], pedidos=pedidos), "claude-sonnet-5",
                                cliente="Exemplo", tipo="Mensal", data="2026-10-07", participantes=None,
                                transcricao="…", uso=Uso("claude-sonnet-5"))
        assert rascunho.resumo == "Reunião boa."
        assert pedidos[0]["text"]["format"]["type"] == "json_schema" and pedidos[0]["text"]["format"]["strict"]


class Falso:
    def __init__(self, resposta=None, falha=None, modelo="m"):
        self.modelo, self.chamadas = modelo, 0

        def criar(**_):
            self.chamadas += 1
            if falha:
                raise falha
            return resposta
        self.messages = NS(create=criar)
        self.beta = NS(messages=NS(create=criar))


class TestReserva:
    def test_falha_da_principal_passa_para_a_reserva(self):
        reserva = Falso(NS(stop_reason="end_turn"))
        cliente = ClienteComReserva(Falso(falha=AgenteFalhou("caiu")), reserva)
        assert cliente.messages.create(messages=[]).stop_reason == "end_turn" and reserva.chamadas == 1

    def test_recusa_da_principal_passa_para_a_reserva(self):
        reserva = Falso(NS(stop_reason="end_turn"))
        ClienteComReserva(Falso(NS(stop_reason="refusal")), reserva).beta.messages.create(messages=[])
        assert reserva.chamadas == 1

    def test_principal_bem_sucedida_nao_chama_a_reserva(self):
        reserva = Falso(NS(stop_reason="end_turn"))
        ClienteComReserva(Falso(NS(stop_reason="end_turn")), reserva).messages.create(messages=[])
        assert reserva.chamadas == 0


def _config(**k):
    base = dict(chave="sk-ant", modelo="claude-opus-5", openai_chave="sk-oa", openai_modelo="gpt-6-astra",
                ia_principal="Anthropic", ia_reserva="Nenhuma")
    return NS(**(base | k))


class TestMontagem:
    def test_openai_principal_e_anthropic_reserva(self):
        cliente, modelo = montar_cliente(_config(ia_principal="OpenAI", ia_reserva="Anthropic"))
        assert isinstance(cliente, ClienteComReserva) and modelo == "gpt-6-astra"
        assert em_uso(_config(ia_principal="OpenAI", ia_reserva="Anthropic")) == ["OpenAI", "Anthropic"]

    def test_sem_a_chave_da_principal_diz_o_que_falta(self):
        with pytest.raises(AgenteFalhou, match="falta a chave dela"):
            montar_cliente(_config(ia_principal="OpenAI", openai_chave=None))

    def test_reserva_sem_chave_nao_atrapalha(self):
        cliente, _ = montar_cliente(_config(ia_principal="OpenAI", ia_reserva="Anthropic", chave=None))
        assert isinstance(cliente, ClienteOpenAI)

    def test_reserva_igual_a_principal_e_ignorada(self):
        assert em_uso(_config(ia_reserva="Anthropic")) == ["Anthropic"]
        assert cliente_de("OpenAI", _config()).modelo == "gpt-6-astra"


class TestCusto:
    def test_cada_parte_pelo_preco_do_modelo_que_respondeu(self):
        uso = Uso("claude-opus-5")
        uso.somar(NS(input_tokens=1_000_000, output_tokens=0))                      # Opus: US$ 5
        uso.somar(NS(modelo="gpt-6-luna", input_tokens=1_000_000, output_tokens=0))  # Luna: US$ 0,10
        assert uso.custo_usd == Decimal("5.1000") and uso.modelo == "gpt-6-luna"

    def test_modelo_sem_preco_nao_inventa_custo(self):
        uso = Uso("claude-opus-5")
        uso.somar(NS(modelo="modelo-novo", input_tokens=10, output_tokens=10))
        assert uso.custo_usd is None
