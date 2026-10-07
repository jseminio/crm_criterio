"""Envio de modelo aprovado pelo WhatsApp, pela Cloud API da Meta (06/10/2026).

Só modelo: fora da janela de 24 horas desde a última mensagem do lead, o WhatsApp não aceita texto
livre, e o CRM ainda não recebe as respostas do lead (sem webhook), então não sabe se a janela está
aberta. O modelo vale dentro e fora dela.

Usa o token permanente de um usuário do sistema do Business Manager, com a permissão
`whatsapp_business_messaging`, e o ID do número de telefone da conta (`CRM_WHATSAPP_*`).
"""

from __future__ import annotations

import httpx2 as httpx

from crm.agente.config import ConfiguracaoDoWhatsapp
from crm.agente.envio import EnvioFalhou

__all__ = ["enviar_modelo", "conferir_numero"]

_ENVIO = "https://graph.facebook.com/{versao}/{numero}/messages"


def enviar_modelo(
    config: ConfiguracaoDoWhatsapp,
    *,
    para: str,
    modelo: str,
    parametros: dict[str, str],
    idioma: str = "pt_BR",
    http: httpx.Client | None = None,
) -> str:
    """Envia um modelo com parâmetros nomeados no corpo. Devolve o id da mensagem na Meta.
    Levanta `EnvioFalhou` se não saiu, com o motivo da Meta e sem o token."""
    cliente = http or httpx.Client(timeout=30.0)
    try:
        resposta = cliente.post(
            _ENVIO.format(versao=config.versao, numero=config.numero_id),
            headers={"Authorization": f"Bearer {config.token}"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": para,
                "type": "template",
                "template": {
                    "name": modelo,
                    "language": {"code": idioma},
                    "components": [{
                        "type": "body",
                        "parameters": [
                            {"type": "text", "parameter_name": nome, "text": valor}
                            for nome, valor in parametros.items()
                        ],
                    }],
                },
            },
        )
        if resposta.status_code in (401, 403):
            raise EnvioFalhou(
                f"A Meta recusou o token do WhatsApp (HTTP {resposta.status_code}). Confira o token em Configurações › Integrações."
            )
        dados = _json(resposta)
        if resposta.status_code != 200:
            erro = dados.get("error") if isinstance(dados.get("error"), dict) else {}
            motivo = erro.get("message") or "sem detalhe"
            raise EnvioFalhou(f"A Meta não enviou o WhatsApp (HTTP {resposta.status_code}): {motivo}")
        mensagens = dados.get("messages") or [{}]
        return str(mensagens[0].get("id") or "")
    except httpx.HTTPError as falha:
        raise EnvioFalhou(f"Não consegui falar com a Meta: {type(falha).__name__}.") from falha
    finally:
        if http is None:
            cliente.close()


def _json(resposta: httpx.Response) -> dict:
    try:
        dados = resposta.json()
    except ValueError:
        return {}
    return dados if isinstance(dados, dict) else {}


def conferir_numero(config: ConfiguracaoDoWhatsapp, *, http: httpx.Client | None = None) -> str:
    """O teste da tela: pergunta à Meta qual é o número. Não envia nada. Devolve "número · nome"."""
    cliente = http or httpx.Client(timeout=30.0)
    try:
        resposta = cliente.get(
            f"https://graph.facebook.com/{config.versao}/{config.numero_id}",
            params={"fields": "display_phone_number,verified_name"},
            headers={"Authorization": f"Bearer {config.token}"},
        )
        if resposta.status_code in (401, 403):
            raise EnvioFalhou(
                f"A Meta recusou o token do WhatsApp (HTTP {resposta.status_code}). Confira o token em "
                "Configurações › Integrações."
            )
        dados = _json(resposta)
        if resposta.status_code != 200:
            erro = dados.get("error") if isinstance(dados.get("error"), dict) else {}
            raise EnvioFalhou(f"A Meta não reconheceu o número (HTTP {resposta.status_code}): "
                              f"{erro.get('message') or 'confira o ID do número'}")
        return " · ".join(str(v) for v in (dados.get("display_phone_number"), dados.get("verified_name")) if v)
    except httpx.HTTPError as falha:
        raise EnvioFalhou(f"Não consegui falar com a Meta: {type(falha).__name__}.") from falha
    finally:
        if http is None:
            cliente.close()
