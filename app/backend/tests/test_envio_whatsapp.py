"""Envio de WhatsApp pela Cloud API da Meta, sem rede.

Mensagem é sempre template pré-aprovado (regra da Meta fora da janela de
24h), nunca texto livre. Mesmas duas garantias do e-mail: formato certo e
nenhum segredo em mensagem de erro ou em `repr`.
"""

from __future__ import annotations

import json

import httpx2 as httpx
import pytest

from crm.agente.config import ConfiguracaoDoWhatsApp, ler_configuracao
from crm.agente.envio import EnvioFalhou, enviar_whatsapp

CONFIG = ConfiguracaoDoWhatsApp(token="tok-super-secreto", telefone_id="1234567890")


def _cliente(status=200, pedidos=None):
    def tratar(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        return httpx.Response(status, json={"error": {"message": "recusado"}} if status != 200 else {})

    return httpx.Client(transport=httpx.MockTransport(tratar))


def test_envia_no_formato_da_cloud_api():
    pedidos: list[httpx.Request] = []
    enviar_whatsapp(
        CONFIG,
        para="5511999998888",
        template="lembrete_diagnostico",
        parametros=["Ana", "quinta-feira"],
        http=_cliente(pedidos=pedidos),
    )

    (pedido,) = pedidos
    assert str(pedido.url) == "https://graph.facebook.com/v21.0/1234567890/messages"
    assert pedido.headers["Authorization"] == "Bearer tok-super-secreto"
    corpo = json.loads(pedido.content)
    assert corpo["messaging_product"] == "whatsapp"
    assert corpo["to"] == "5511999998888"
    assert corpo["type"] == "template"
    assert corpo["template"]["name"] == "lembrete_diagnostico"
    assert corpo["template"]["language"] == {"code": "pt_BR"}
    assert corpo["template"]["components"] == [
        {"type": "body", "parameters": [{"type": "text", "text": "Ana"}, {"type": "text", "text": "quinta-feira"}]}
    ]


def test_sem_parametros_nao_manda_components():
    pedidos: list[httpx.Request] = []
    enviar_whatsapp(CONFIG, para="5511999998888", template="saudacao", http=_cliente(pedidos=pedidos))
    corpo = json.loads(pedidos[0].content)
    assert "components" not in corpo["template"]


def test_falha_explica_sem_mostrar_o_token():
    with pytest.raises(EnvioFalhou) as falha:
        enviar_whatsapp(CONFIG, para="5511999998888", template="x", http=_cliente(401))
    assert "HTTP 401" in str(falha.value)
    assert "tok-super-secreto" not in str(falha.value)


def test_repr_nao_mostra_o_token():
    assert "tok-super-secreto" not in repr(CONFIG)


def test_configuracao_vem_do_env(tmp_path, monkeypatch):
    from crm.db import sessao as modulo

    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "CRM_WHATSAPP_TOKEN=tok-teste\nCRM_WHATSAPP_PHONE_ID=999\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)
    config = ler_configuracao()
    assert config.whatsapp is not None
    assert config.whatsapp.telefone_id == "999"
    assert config.whatsapp.versao_api == "v21.0"
    assert "tok-teste" not in repr(config.whatsapp)


def test_whatsapp_incompleto_fica_desligado(tmp_path, monkeypatch):
    from crm.db import sessao as modulo

    arquivo = tmp_path / ".env"
    arquivo.write_text("CRM_WHATSAPP_TOKEN=tok-teste\n", encoding="utf-8")
    monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)
    config = ler_configuracao()
    assert config.whatsapp is None
