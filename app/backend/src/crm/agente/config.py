"""Configuração do agente SDR e do envio, lida do `.env` do backend.

Segredo só no `.env` (regra do projeto). Este módulo lê as variáveis e não
guarda, não imprime e não devolve em mensagem de erro nenhum valor.
"""

from __future__ import annotations

from dataclasses import dataclass

from crm.agente.sdr import MODELO_PADRAO
from crm.db.sessao import ler_ambiente

__all__ = ["ConfiguracaoDoAgente", "ConfiguracaoDoEmail", "VARIAVEIS", "ler_configuracao"]

VARIAVEIS = {
    "chave": "ANTHROPIC_API_KEY",
    "modelo": "CRM_AGENTE_MODELO",
    "tenant": "CRM_M365_TENANT_ID",
    "cliente": "CRM_M365_CLIENT_ID",
    "segredo": "CRM_M365_CLIENT_SECRET",
    "remetente": "CRM_M365_REMETENTE",
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
class ConfiguracaoDoAgente:
    chave: str | None
    modelo: str
    email: ConfiguracaoDoEmail | None

    def __repr__(self) -> str:
        return f"ConfiguracaoDoAgente(modelo={self.modelo!r}, chave={'sim' if self.chave else 'não'})"


def ler_configuracao() -> ConfiguracaoDoAgente:
    valores = ler_ambiente()
    partes_do_email = [valores.get(VARIAVEIS[k]) for k in ("tenant", "cliente", "segredo", "remetente")]
    email = ConfiguracaoDoEmail(*partes_do_email) if all(partes_do_email) else None
    return ConfiguracaoDoAgente(
        chave=valores.get(VARIAVEIS["chave"]),
        modelo=valores.get(VARIAVEIS["modelo"]) or MODELO_PADRAO,
        email=email,
    )
