"""Leads do formulário de anúncio do Meta (Lead Ads) — 14/10/2026.

Amostra aprovada por Eduardo em 14/10/2026. Só lê: os formulários da página e os leads novos de cada um, pela
Graph API, com o token da página (permissão `leads_retrieval`). A configuração vem da tela Configurações ›
Integrações (`meta_ads.leads`, `meta_ads.pagina`, `meta_ads.token_pagina`). Toda falha vira `LeituraFalhou`
(ou `AcessoNegado`) com uma frase, sem o token.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx2 as httpx

from crm import configuracao
from crm.anuncios import AcessoNegado, LeituraFalhou

__all__ = ["ConfiguracaoDosLeads", "LeadDoMeta", "buscar_leads", "conferir_pagina", "ler_configuracao"]

_PAGINA = re.compile(r"^\d{5,20}$")
_CAMPOS = "id,created_time,field_data,ad_id,ad_name,adset_name,campaign_id,campaign_name,form_id,is_organic,platform"


@dataclass(frozen=True)
class ConfiguracaoDosLeads:
    pagina: str
    token: str
    versao: str


@dataclass(frozen=True)
class LeadDoMeta:
    id: str
    criado_em: datetime
    respostas: dict[str, str]
    """Pergunta → resposta, como vieram do formulário (`field_data`)."""
    campanha: str | None
    anuncio: str | None
    formulario: str | None
    organico: bool


def ler_configuracao() -> ConfiguracaoDosLeads | None:
    """Com a busca ligada, a página e o token; `None` desligada ou faltando algum."""
    if configuracao.valor("meta_ads.leads") != "true":
        return None
    pagina = configuracao.valor("meta_ads.pagina").strip()
    token = configuracao.valor("meta_ads.token_pagina").strip()
    if not pagina or not token:
        return None
    return ConfiguracaoDosLeads(pagina, token, configuracao.valor("meta_ads.versao").strip() or "v24.0")


def _pedir(cliente: httpx.Client, url: str, params: dict | None, config: ConfiguracaoDosLeads) -> dict:
    try:
        resposta = cliente.get(url, params=params, headers={"Authorization": f"Bearer {config.token}"})
    except httpx.HTTPError as falha:
        raise LeituraFalhou(f"Não consegui falar com a Meta: {type(falha).__name__}.") from falha
    try:
        dados = resposta.json()
    except ValueError:
        dados = {}
    erro = dados.get("error") if isinstance(dados.get("error"), dict) else {}
    if resposta.status_code in (401, 403) or erro.get("code") in (190, 200, 10):
        raise AcessoNegado(f"A Meta recusou o token da página (HTTP {resposta.status_code}): "
                           f"{erro.get('message') or 'confira o token e a permissão leads_retrieval'}")
    if resposta.status_code != 200:
        raise LeituraFalhou(f"A Meta não respondeu à busca de leads (HTTP {resposta.status_code}): "
                            f"{erro.get('message') or 'confira o ID da página'}")
    return dados


def _paginas(cliente: httpx.Client, url: str, params: dict, config: ConfiguracaoDosLeads) -> list[dict]:
    itens: list[dict] = []
    proxima: str | None = url
    for _ in range(50):  # trava contra paginação sem fim
        if proxima is None:
            break
        dados = _pedir(cliente, proxima, params, config)
        itens.extend(dados.get("data") or [])
        proxima = (dados.get("paging") or {}).get("next")
        params = None  # o "next" já traz os parâmetros
    return itens


def _validar(config: ConfiguracaoDosLeads) -> None:
    if not _PAGINA.match(config.pagina):
        raise AcessoNegado("O ID da página do Facebook deve ter só números.")


def conferir_pagina(config: ConfiguracaoDosLeads, *, http: httpx.Client | None = None) -> str:
    """O teste da tela: o nome da página e quantos formulários de lead ela tem. Não grava nada."""
    _validar(config)
    base = f"https://graph.facebook.com/{config.versao}/{config.pagina}"
    cliente = http or httpx.Client(timeout=30.0)
    try:
        pagina = _pedir(cliente, base, {"fields": "name"}, config)
        formularios = _paginas(cliente, f"{base}/leadgen_forms", {"fields": "id,name,status", "limit": 100}, config)
    finally:
        if http is None:
            cliente.close()
    return f"Página {pagina.get('name') or config.pagina} · {len(formularios)} formulário(s) de lead."


def _quando(texto: str) -> datetime:
    """"2026-10-14T12:32:05+0000" → datetime em UTC."""
    return datetime.strptime(texto, "%Y-%m-%dT%H:%M:%S%z").astimezone(timezone.utc)


def buscar_leads(config: ConfiguracaoDosLeads, desde: datetime, *, http: httpx.Client | None = None) -> list[LeadDoMeta]:
    """Os leads criados depois de `desde`, de todos os formulários da página."""
    _validar(config)
    base = f"https://graph.facebook.com/{config.versao}"
    filtro = json.dumps([{"field": "time_created", "operator": "GREATER_THAN", "value": int(desde.timestamp())}])
    cliente = http or httpx.Client(timeout=60.0)
    leads: list[LeadDoMeta] = []
    try:
        formularios = _paginas(cliente, f"{base}/{config.pagina}/leadgen_forms", {"fields": "id,name", "limit": 100}, config)
        for formulario in formularios:
            for item in _paginas(cliente, f"{base}/{formulario['id']}/leads",
                                 {"fields": _CAMPOS, "filtering": filtro, "limit": 100}, config):
                respostas = {}
                for campo in item.get("field_data") or []:
                    valores = [str(v) for v in campo.get("values") or [] if str(v).strip()]
                    if campo.get("name") and valores:
                        respostas[str(campo["name"])] = ", ".join(valores)
                leads.append(LeadDoMeta(
                    id=str(item.get("id")), criado_em=_quando(item["created_time"]), respostas=respostas,
                    campanha=item.get("campaign_name"), anuncio=item.get("ad_name"),
                    formulario=formulario.get("name"), organico=bool(item.get("is_organic")),
                ))
    finally:
        if http is None:
            cliente.close()
    return leads
