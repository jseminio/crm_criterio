"""Configuração do agente SDR e do envio, lida do `.env` do backend.

Segredo só no `.env` (regra do projeto). Este módulo lê as variáveis e não
guarda, não imprime e não devolve em mensagem de erro nenhum valor.
"""

from __future__ import annotations

from dataclasses import dataclass

from crm.agente.sdr import MODELO_PADRAO
from crm.db.sessao import ler_ambiente

__all__ = [
    "ConfiguracaoDoAgente",
    "ConfiguracaoDoEmail",
    "ConfiguracaoDoWhatsApp",
    "VARIAVEIS",
    "ler_configuracao",
]

VERSAO_API_WHATSAPP_PADRAO = "v21.0"

VARIAVEIS = {
    "chave": "ANTHROPIC_API_KEY",
    "modelo": "CRM_AGENTE_MODELO",
    "tenant": "CRM_M365_TENANT_ID",
    "cliente": "CRM_M365_CLIENT_ID",
    "segredo": "CRM_M365_CLIENT_SECRET",
    "remetente": "CRM_M365_REMETENTE",
    "whatsapp_token": "CRM_WHATSAPP_TOKEN",
    "whatsapp_telefone_id": "CRM_WHATSAPP_PHONE_ID",
    "whatsapp_versao_api": "CRM_WHATSAPP_API_VERSION",
}


@dataclass(frozen=True)
class ConfiguracaoDoEmail:
    tenant: str
    cliente: str
    segredo: str
    remetente: str

    def __repr__(self) -> str:  # nunca mostrar o segredo, nem em log de erro
        return f"ConfiguracaoDoEmail(remetente={self.remetente!r})"


@dataclass(frozen=True)
class ConfiguracaoDoWhatsApp:
    token: str
    telefone_id: str
    versao_api: str = VERSAO_API_WHATSAPP_PADRAO

    def __repr__(self) -> str:  # nunca mostrar o token, nem em log de erro
        return f"ConfiguracaoDoWhatsApp(telefone_id={self.telefone_id!r})"


@dataclass(frozen=True)
class ConfiguracaoDoAgente:
    chave: str | None
    modelo: str
    email: ConfiguracaoDoEmail | None
    whatsapp: ConfiguracaoDoWhatsApp | None

    def __repr__(self) -> str:
        return f"ConfiguracaoDoAgente(modelo={self.modelo!r}, chave={'sim' if self.chave else 'não'})"


def ler_configuracao() -> ConfiguracaoDoAgente:
    valores = ler_ambiente()
    partes_do_email = [valores.get(VARIAVEIS[k]) for k in ("tenant", "cliente", "segredo", "remetente")]
    email = ConfiguracaoDoEmail(*partes_do_email) if all(partes_do_email) else None
    token = valores.get(VARIAVEIS["whatsapp_token"])
    telefone_id = valores.get(VARIAVEIS["whatsapp_telefone_id"])
    whatsapp = (
        ConfiguracaoDoWhatsApp(
            token=token,
            telefone_id=telefone_id,
            versao_api=valores.get(VARIAVEIS["whatsapp_versao_api"]) or VERSAO_API_WHATSAPP_PADRAO,
        )
        if token and telefone_id
        else None
    )
    return ConfiguracaoDoAgente(
        chave=valores.get(VARIAVEIS["chave"]),
        modelo=valores.get(VARIAVEIS["modelo"]) or MODELO_PADRAO,
        email=email,
        whatsapp=whatsapp,
    )
