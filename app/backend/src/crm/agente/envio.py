"""Envio do e-mail e do WhatsApp aprovados.

Só roda depois da aprovação na tela.

O e-mail usa o fluxo de credenciais do aplicativo (client credentials) de um
app registrado no Microsoft Entra com a permissão de aplicativo `Mail.Send`,
enviando em nome da caixa `CRM_M365_REMETENTE`.

O WhatsApp usa a Cloud API oficial da Meta. Fora da janela de 24h aberta por
uma mensagem do próprio contato, a Meta só aceita mandar uma mensagem de
**template pré-aprovado** — por isso `enviar_whatsapp` recebe o nome do
template e os parâmetros da variação, nunca texto livre.
"""

from __future__ import annotations

import httpx2 as httpx

from crm.agente.config import ConfiguracaoDoEmail, ConfiguracaoDoWhatsApp

__all__ = ["EnvioFalhou", "enviar_email", "enviar_whatsapp"]

_TOKEN = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
_ENVIO = "https://graph.microsoft.com/v1.0/users/{remetente}/sendMail"
_WHATSAPP = "https://graph.facebook.com/{versao}/{telefone_id}/messages"


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


def enviar_whatsapp(
    config: ConfiguracaoDoWhatsApp,
    *,
    para: str,
    template: str,
    parametros: list[str] = (),
    idioma: str = "pt_BR",
    http: httpx.Client | None = None,
) -> None:
    """Envia uma mensagem de template pela Cloud API. Levanta `EnvioFalhou` se não saiu.

    `parametros` preenche, em ordem, as variáveis `{{1}}`, `{{2}}`... do corpo
    do template — não é texto livre. O template precisa já estar aprovado
    pela Meta, criado fora deste código, no Business Manager.
    """
    cliente = http or httpx.Client(timeout=30.0)
    corpo = {
        "messaging_product": "whatsapp",
        "to": para,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": idioma},
        },
    }
    if parametros:
        corpo["template"]["components"] = [
            {"type": "body", "parameters": [{"type": "text", "text": p} for p in parametros]}
        ]
    try:
        resposta = cliente.post(
            _WHATSAPP.format(versao=config.versao_api, telefone_id=config.telefone_id),
            headers={"Authorization": f"Bearer {config.token}"},
            json=corpo,
        )
        if resposta.status_code != 200:
            raise EnvioFalhou(
                f"A Meta não aceitou o envio do WhatsApp (HTTP {resposta.status_code}). "
                "Confira CRM_WHATSAPP_* no .env e se o template está aprovado."
            )
    except httpx.HTTPError as falha:
        raise EnvioFalhou(f"Não consegui falar com a Meta: {type(falha).__name__}.") from falha
    finally:
        if http is None:
            cliente.close()
