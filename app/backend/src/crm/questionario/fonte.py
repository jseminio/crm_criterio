"""Onde os questionários enviados ficam: a tabela `questionarios_proposta` no Supabase do site.

O CRM **busca**; o site nunca chama o CRM, que continua só em 127.0.0.1. Dois caminhos, escolhidos
pelo endereço em `CRM_QUESTIONARIO_URL`:

- **Função do site** (`…/functions/v1/questionarios-crm`, 01/10/2026): o banco do site é administrado
  pelo Lovable e a chave secreta do Supabase não fica à vista. A função só entrega os pendentes e
  marca os importados, e só responde a quem manda a senha combinada (`CRM_QUESTIONARIO_CHAVE`).
- **Supabase direto** (`https://<projeto>.supabase.co`): com a chave secreta do projeto.

A senha ou chave fica só no `.env` (regra do projeto): este módulo não guarda, não imprime e não
devolve em mensagem de erro nenhum valor dela.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

import httpx2 as httpx

from crm.db.sessao import ler_ambiente

__all__ = [
    "VARIAVEIS", "BuscaFalhou", "ConfiguracaoDoQuestionario", "FonteDeQuestionarios", "FonteSupabase",
    "FonteDaFuncao", "e_funcao", "ler_configuracao",
]

VARIAVEIS = {"url": "CRM_QUESTIONARIO_URL", "chave": "CRM_QUESTIONARIO_CHAVE"}
TABELA = "questionarios_proposta"
CABECALHO_DA_SENHA = "x-crm-senha"
LOTE = 50


class BuscaFalhou(RuntimeError):
    """O Supabase não respondeu ou recusou. Nada foi importado nem marcado."""


@dataclass(frozen=True)
class ConfiguracaoDoQuestionario:
    url: str
    chave: str

    def __repr__(self) -> str:  # nunca mostrar a chave, nem em log de erro
        return f"ConfiguracaoDoQuestionario(url={self.url!r})"


def ler_configuracao() -> ConfiguracaoDoQuestionario | None:
    valores = ler_ambiente()
    url, chave = valores.get(VARIAVEIS["url"]), valores.get(VARIAVEIS["chave"])
    return ConfiguracaoDoQuestionario(url.rstrip("/"), chave) if url and chave else None


def e_funcao(config: ConfiguracaoDoQuestionario) -> bool:
    return "/functions/v1/" in config.url


class FonteDeQuestionarios(Protocol):
    def novos(self) -> list[dict[str, Any]]:
        """Os ainda não importados (`importado_crm_em` vazio), do mais antigo ao mais novo."""

    def marcar_importado(self, externo_id: str, quando: datetime) -> None:
        """Grava `importado_crm_em` na origem, para não voltar na próxima busca."""


class FonteSupabase:
    def __init__(self, config: ConfiguracaoDoQuestionario, http: httpx.Client | None = None) -> None:
        self._config = config
        self._http = http or httpx.Client(timeout=30.0)

    def _cabecalhos(self) -> dict[str, str]:
        cab = {"apikey": self._config.chave}
        # Chave antiga (service_role) é um JWT e vai também no Authorization; a nova (sb_secret_…), só no apikey.
        if self._config.chave.startswith("eyJ"):
            cab["Authorization"] = f"Bearer {self._config.chave}"
        return cab

    def novos(self) -> list[dict[str, Any]]:
        try:
            r = self._http.get(
                f"{self._config.url}/rest/v1/{TABELA}",
                params={"select": "*", "importado_crm_em": "is.null", "order": "criado_em.asc", "limit": str(LOTE)},
                headers=self._cabecalhos(),
            )
        except httpx.HTTPError as falha:
            raise BuscaFalhou(f"Não consegui falar com o Supabase: {type(falha).__name__}.") from falha
        if r.status_code in (401, 403):
            raise BuscaFalhou(
                f"O Supabase recusou a chave (HTTP {r.status_code}). Confira {VARIAVEIS['chave']} no backend/.env: "
                "precisa ser a chave secreta (secret / service_role), não a publicável."
            )
        if r.status_code != 200:
            raise BuscaFalhou(f"O Supabase não devolveu os questionários (HTTP {r.status_code}).")
        return r.json()

    def marcar_importado(self, externo_id: str, quando: datetime) -> None:
        try:
            r = self._http.patch(
                f"{self._config.url}/rest/v1/{TABELA}",
                params={"id": f"eq.{externo_id}"},
                headers={**self._cabecalhos(), "Prefer": "return=minimal"},
                json={"importado_crm_em": quando.isoformat()},
            )
        except httpx.HTTPError as falha:
            raise BuscaFalhou(f"Não consegui marcar no Supabase: {type(falha).__name__}.") from falha
        if r.status_code not in (200, 204):
            raise BuscaFalhou(f"O Supabase não marcou o questionário como importado (HTTP {r.status_code}).")


class FonteDaFuncao:
    """A função `questionarios-crm` do site: GET devolve os pendentes (do mais antigo ao mais novo,
    até 50); POST `{id, importado_crm_em}` marca um como importado. Senha no cabeçalho `x-crm-senha`."""

    def __init__(self, config: ConfiguracaoDoQuestionario, http: httpx.Client | None = None) -> None:
        self._config = config
        self._http = http or httpx.Client(timeout=30.0)

    def _cabecalhos(self) -> dict[str, str]:
        return {CABECALHO_DA_SENHA: self._config.chave}

    def _recusa(self, r: httpx.Response) -> None:
        if r.status_code in (401, 403):
            raise BuscaFalhou(
                f"A função do site recusou a senha (HTTP {r.status_code}). Confira se {VARIAVEIS['chave']} no "
                "backend/.env é a mesma senha guardada no Lovable (segredo CRM_QUESTIONARIO_SENHA)."
            )

    def novos(self) -> list[dict[str, Any]]:
        try:
            r = self._http.get(self._config.url, headers=self._cabecalhos())
        except httpx.HTTPError as falha:
            raise BuscaFalhou(f"Não consegui falar com a função do site: {type(falha).__name__}.") from falha
        self._recusa(r)
        if r.status_code != 200:
            raise BuscaFalhou(f"A função do site não devolveu os questionários (HTTP {r.status_code}).")
        dados = r.json()
        if not isinstance(dados, list):
            raise BuscaFalhou("A função do site devolveu algo que não é a lista de questionários.")
        return dados

    def marcar_importado(self, externo_id: str, quando: datetime) -> None:
        try:
            r = self._http.post(
                self._config.url, headers=self._cabecalhos(),
                json={"id": externo_id, "importado_crm_em": quando.isoformat()},
            )
        except httpx.HTTPError as falha:
            raise BuscaFalhou(f"Não consegui marcar na função do site: {type(falha).__name__}.") from falha
        self._recusa(r)
        if r.status_code not in (200, 204):
            raise BuscaFalhou(f"A função do site não marcou o questionário como importado (HTTP {r.status_code}).")
