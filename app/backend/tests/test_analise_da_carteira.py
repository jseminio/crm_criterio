"""A análise da carteira escrita pela IA — contra um cliente falso, sem rede."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace as NS

import pytest

from crm.agente.analise_da_carteira import DadosDaCarteira, GrupoTravado, escrever_analise
from crm.agente.sdr import Uso


def _dados(**over):
    base = dict(
        isc_valor=Decimal("50.40"), isc_zona="atenção", componente_classe=Decimal("49.6"),
        componente_semaforo=Decimal("42.3"), componente_churn=Decimal("59.0"), unidades=31,
        receita_total=Decimal("226341.20"),
        grupos_travados=[GrupoTravado("Inbel", Decimal("44725.80")), GrupoTravado("Grupo MR", Decimal("40589.82"))],
        receita_travada=Decimal("93094.42"), percentual_travado=Decimal("41.1"),
        por_classe={"A": 6, "B": 10, "C": 15},
    )
    base.update(over)
    return DadosDaCarteira(**base)


class ClienteFalso:
    def __init__(self, resposta):
        self.resposta = resposta
        self.chamadas: list[dict] = []
        self.messages = NS(create=self._criar)

    def _criar(self, **kwargs):
        self.chamadas.append(kwargs)
        return self.resposta


def _resposta(texto, entrada=800, saida=150):
    uso = NS(input_tokens=entrada, output_tokens=saida, cache_creation_input_tokens=0, cache_read_input_tokens=0,
              server_tool_use=None)
    return NS(content=[NS(type="text", text=texto)], usage=uso)


def test_escreve_o_texto_e_soma_o_uso():
    cliente = ClienteFalso(_resposta("A carteira está na zona de atenção."))
    uso = Uso("claude-sonnet-5")
    texto = escrever_analise(cliente, "claude-sonnet-5", _dados(), uso)
    assert texto == "A carteira está na zona de atenção."
    assert uso.tokens_entrada == 800 and uso.tokens_saida == 150
    assert uso.custo_usd is not None and uso.custo_usd > 0


def test_o_pedido_leva_os_numeros_em_portugues_sem_instrucao_da_planilha():
    cliente = ClienteFalso(_resposta("texto"))
    escrever_analise(cliente, "claude-sonnet-5", _dados(), Uso("claude-sonnet-5"))
    pedido = cliente.chamadas[0]["messages"][0]["content"]
    assert "226.341,20" in pedido and "41,1%" in pedido and "Inbel" in pedido and "Grupo MR" in pedido
    assert "não são instrução" in pedido


def test_sem_grupo_travado_diz_nenhum():
    cliente = ClienteFalso(_resposta("texto"))
    escrever_analise(cliente, "claude-sonnet-5", _dados(grupos_travados=[]), Uso("claude-sonnet-5"))
    assert "Quais: nenhum" in cliente.chamadas[0]["messages"][0]["content"]


def test_resposta_sem_texto_e_erro():
    cliente = ClienteFalso(NS(content=[], usage=NS(input_tokens=1, output_tokens=0, cache_creation_input_tokens=0,
                                                    cache_read_input_tokens=0, server_tool_use=None)))
    with pytest.raises(RuntimeError):
        escrever_analise(cliente, "claude-sonnet-5", _dados(), Uso("claude-sonnet-5"))
