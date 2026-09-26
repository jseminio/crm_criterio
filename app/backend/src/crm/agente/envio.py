"""Envio do e-mail aprovado, pelo Microsoft Graph da conta corporativa.

Só roda depois da aprovação na tela. Usa o fluxo de credenciais do aplicativo
(client credentials) de um app registrado no Microsoft Entra com a permissão
de aplicativo `Mail.Send`, enviando em nome da caixa `CRM_M365_REMETENTE`.
"""

from __future__ import annotations

import httpx2 as httpx

from crm.agente.config import ConfiguracaoDoEmail

__all__ = ["EnvioFalhou", "enviar_email"]

_TOKEN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_ENVIO = "https://graph.microsoft.com/v1.0/users/{remetente}/sendMail"


class EnvioFalhou(RuntimeError):
    """O Microsoft 365 não aceitou o envio. Nada saiu."""


def enviar_email(
    config: ConfiguracaoDoEmail,
    *,
    para: str,
    assunto: str,
    corpo: str,
    http: httpx.Client | None = None,
) -> None:
    """Envia um e-mail de texto simples. Levanta `EnvioFalhou` se não saiu."""
    cliente = http or httpx.Client(timeout=30.0)
    try:
        token = cliente.post(
            _TOKEN.format(tenant=config.tenant),
            data={
                "grant_type": "client_credentials",
                "client_id": config.cliente,
                "client_secret": config.segredo,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        if token.status_code != 200:
            raise EnvioFalhou(
                f"O Microsoft 365 recusou as credenciais do app (HTTP {token.status_code}). "
                "Confira CRM_M365_* no .env."
            )
        resposta = cliente.post(
            _ENVIO.format(remetente=config.remetente),
            headers={"Authorization": f"Bearer {token.json()['access_token']}"},
            json={
                "message": {
                    "subject": assunto,
                    "body": {"contentType": "Text", "content": corpo},
                    "toRecipients": [{"emailAddress": {"address": para}}],
                },
                "saveToSentItems": True,
            },
        )
        if resposta.status_code != 202:
            raise EnvioFalhou(
                f"O Microsoft 365 não enviou o e-mail (HTTP {resposta.status_code}). "
                "Confira a permissão Mail.Send do app."
            )
    except httpx.HTTPError as falha:
        raise EnvioFalhou(f"Não consegui falar com o Microsoft 365: {type(falha).__name__}.") from falha
    finally:
        if http is None:
            cliente.close()
