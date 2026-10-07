"""Configuração do agente SDR e do envio.

Desde 07/10/2026 vale primeiro o que está na tela Configurações › Integrações (cifrado no banco,
`crm.configuracao`); sem valor na tela, a variável de ambiente antiga (`.env` ou painel do servidor).
Este módulo não guarda, não imprime e não devolve em mensagem de erro nenhum valor.
"""

from __future__ import annotations

from dataclasses import dataclass

from crm.agente.sdr import MODELO_PADRAO
from crm.configuracao import ambiente_efetivo

__all__ = ["ConfiguracaoDoAgente", "ConfiguracaoDoEmail", "ConfiguracaoDoWhatsapp", "VERSAO_DO_WHATSAPP", "LINK_DO_QUESTIONARIO_PADRAO", "VARIAVEIS", "ler_configuracao"]

VARIAVEIS = {
    "chave": "ANTHROPIC_API_KEY",
    "modelo": "CRM_AGENTE_MODELO",
    "tenant": "CRM_M365_TENANT_ID",
    "cliente": "CRM_M365_CLIENT_ID",
    "segredo": "CRM_M365_CLIENT_SECRET",
    "remetente": "CRM_M365_REMETENTE",
    "questionario": "CRM_LINK_DO_QUESTIONARIO",
    "whatsapp_token": "CRM_WHATSAPP_TOKEN",
    "whatsapp_numero": "CRM_WHATSAPP_NUMERO_ID",
    "whatsapp_versao": "CRM_WHATSAPP_VERSAO",
    "disparo": "CRM_DISPARO_DO_QUESTIONARIO",
}

#: O questionário de volumetria que o SDR de IA envia ao lead (decisão de Eduardo, 06/10/2026). Vai
#: mudar para o domínio da Critério: aí basta pôr `CRM_LINK_DO_QUESTIONARIO` no `.env`.
LINK_DO_QUESTIONARIO_PADRAO = "https://criterio-questionario-proposta.netlify.app/questionario"


@dataclass(frozen=True)
class ConfiguracaoDoEmail:
    tenant: str
    cliente: str
    segredo: str
    remetente: str

    def __repr__(self) -> str:  # nunca mostrar o segredo, nem em log de erro
        return f"ConfiguracaoDoEmail(remetente={self.remetente!r})"


#: Versão da Graph API da Meta. Cada versão vale cerca de dois anos; trocar é mudar `CRM_WHATSAPP_VERSAO`.
VERSAO_DO_WHATSAPP = "v24.0"


@dataclass(frozen=True)
class ConfiguracaoDoWhatsapp:
    token: str
    numero_id: str
    versao: str = VERSAO_DO_WHATSAPP

    def __repr__(self) -> str:  # nunca mostrar o token, nem em log de erro
        return f"ConfiguracaoDoWhatsapp(numero_id={self.numero_id!r}, versao={self.versao!r})"


@dataclass(frozen=True)
class ConfiguracaoDoAgente:
    chave: str | None
    modelo: str
    email: ConfiguracaoDoEmail | None
    link_do_questionario: str = LINK_DO_QUESTIONARIO_PADRAO
    whatsapp: ConfiguracaoDoWhatsapp | None = None
    disparo_ligado: bool = False
    """O disparo automático do lembrete e do agradecimento do questionário. Desligado por padrão:
    liga com `CRM_DISPARO_DO_QUESTIONARIO=true`, depois de os modelos da Meta estarem aprovados."""

    def __repr__(self) -> str:
        return f"ConfiguracaoDoAgente(modelo={self.modelo!r}, chave={'sim' if self.chave else 'não'})"


def ler_configuracao() -> ConfiguracaoDoAgente:
    valores = ambiente_efetivo()  # a tela vale mais que a variável de ambiente (07/10/2026)
    partes_do_email = [valores.get(VARIAVEIS[k]) for k in ("tenant", "cliente", "segredo", "remetente")]
    email = ConfiguracaoDoEmail(*partes_do_email) if all(partes_do_email) else None
    token, numero = (valores.get(VARIAVEIS[k]) for k in ("whatsapp_token", "whatsapp_numero"))
    whatsapp = ConfiguracaoDoWhatsapp(
        token, numero, (valores.get(VARIAVEIS["whatsapp_versao"]) or "").strip() or VERSAO_DO_WHATSAPP
    ) if token and numero else None
    return ConfiguracaoDoAgente(
        chave=valores.get(VARIAVEIS["chave"]),
        modelo=valores.get(VARIAVEIS["modelo"]) or MODELO_PADRAO,
        email=email,
        link_do_questionario=(valores.get(VARIAVEIS["questionario"]) or "").strip() or LINK_DO_QUESTIONARIO_PADRAO,
        whatsapp=whatsapp,
        disparo_ligado=(valores.get(VARIAVEIS["disparo"]) or "").strip().casefold() in ("true", "1", "sim"),
    )
