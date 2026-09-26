"""Envio pelo Microsoft Graph e leitura da configuração, sem rede.

Duas garantias: o e-mail vai no formato que o Graph pede, e nenhum segredo
aparece em mensagem de erro ou em `repr`.
"""

from __future__ import annotations

import json

import httpx2 as httpx
import pytest

from crm.agente.config import ConfiguracaoDoEmail, ler_configuracao
from crm.agente.envio import EnvioFalhou, enviar_email

CONFIG = ConfiguracaoDoEmail(
    tenant="tenant-1", cliente="app-1", segredo="segredo-super", remetente="eduardo@criterio.com"
)


def _cliente(token_status=200, envio_status=202, pedidos=None):
    def tratar(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        if "oauth2" in str(pedido.url):
            return httpx.Response(token_status, json={"access_token": "tok-123"})
        return httpx.Response(envio_status)

    return httpx.Client(transport=httpx.MockTransport(tratar))


def test_envia_no_formato_do_graph():
    pedidos: list[httpx.Request] = []
    enviar_email(CONFIG, para="ana@omega.com.br", assunto="Oi", corpo="Texto", http=_cliente(pedidos=pedidos))

    token, envio = pedidos
    assert str(token.url) == "https://login.microsoftonline.com/tenant-1/oauth2/v2.0/token"
    assert str(envio.url) == "https://graph.microsoft.com/v1.0/users/eduardo@criterio.com/sendMail"
    assert envio.headers["Authorization"] == "Bearer tok-123"
    corpo = json.loads(envio.content)
    assert corpo["message"]["toRecipients"] == [{"emailAddress": {"address": "ana@omega.com.br"}}]
    assert corpo["message"]["body"] == {"contentType": "Text", "content": "Texto"}
    assert corpo["saveToSentItems"] is True


@pytest.mark.parametrize("token, envio, trecho", [(401, 202, "credenciais"), (200, 403, "Mail.Send")])
def test_falha_explica_sem_mostrar_o_segredo(token, envio, trecho):
    with pytest.raises(EnvioFalhou) as falha:
        enviar_email(CONFIG, para="a@b.com", assunto="x", corpo="y", http=_cliente(token, envio))
    assert trecho in str(falha.value)
    assert "segredo-super" not in str(falha.value)


def test_repr_nao_mostra_segredo():
    assert "segredo-super" not in repr(CONFIG)


def test_configuracao_vem_do_env(tmp_path, monkeypatch):
    from crm.db import sessao as modulo

    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "ANTHROPIC_API_KEY=sk-teste\nCRM_M365_TENANT_ID=t\nCRM_M365_CLIENT_ID=c\n"
        "CRM_M365_CLIENT_SECRET=s\nCRM_M365_REMETENTE=r@x.com\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)
    config = ler_configuracao()
    assert config.chave == "sk-teste"
    assert config.modelo == "claude-opus-5"
    assert config.email is not None and config.email.remetente == "r@x.com"
    assert "sk-teste" not in repr(config)


def test_email_incompleto_fica_desligado(tmp_path, monkeypatch):
    from crm.db import sessao as modulo

    arquivo = tmp_path / ".env"
    arquivo.write_text("CRM_M365_TENANT_ID=t\nCRM_AGENTE_MODELO=claude-sonnet-5\n", encoding="utf-8")
    monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)
    config = ler_configuracao()
    assert config.email is None and config.chave is None
    assert config.modelo == "claude-sonnet-5"
