"""O leitor real do PDF, com a Anthropic trocada por uma falsa (29/10/2026).

Os testes da tela usam um leitor falso inteiro; este passa pelo `leitor_real`, onde `uso.custo_usd()` (chamado
como método, sendo propriedade) derrubava toda leitura com TypeError depois da resposta da IA."""

from __future__ import annotations

import json
from types import SimpleNamespace

import crm.agente.config as config_do_agente
import crm.agente.ia as ia
from crm.api.documentos import leitor_real


class _Mensagens:
    def create(self, **_):
        dados = {"tipo": "contrato", "campos": {"numero": {"valor": "CONT CCE RJ1 45.2026", "pagina": 1, "trecho": "x"}},
                 "cnpjs": []}
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(dados))],
            usage=SimpleNamespace(input_tokens=1000, output_tokens=200, cache_creation_input_tokens=None,
                                  cache_read_input_tokens=None, server_tool_use=None),
        )


def test_leitor_real_le_e_devolve_o_uso(monkeypatch):
    monkeypatch.setattr(config_do_agente, "ler_configuracao", lambda: SimpleNamespace(modelo="claude-opus-5"))
    monkeypatch.setattr(ia, "cliente_de", lambda *_: SimpleNamespace(beta=SimpleNamespace(messages=_Mensagens())))
    lido = leitor_real(b"%PDF-1.4 falso", "contrato.pdf")
    assert lido["campos"]["numero"]["valor"] == "CONT CCE RJ1 45.2026"
    assert lido["uso"]["modelo"] == "claude-opus-5"
    assert lido["uso"]["tokens_entrada"] == 1000 and lido["uso"]["tokens_saida"] == 200
