"""Meta Ads: o gasto de cada campanha num mês, pela API de Marketing — 13/10/2026.

Só lê (permissão `ads_read`). O token, a conta e a versão vêm da tela Configurações › Integrações
(`meta_ads.*`). Toda falha vira `LeituraFalhou` com uma frase para a pessoa ler, sem o token.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx2 as httpx

from crm import configuracao
from crm.anuncios import GastoDaCampanha, LeituraFalhou, intervalo

__all__ = ["ConfiguracaoDoMetaAds", "GastoDaCampanha", "LeituraFalhou", "conferir_conta", "gasto_por_campanha",
           "ler_configuracao"]

CANAL = "Meta Ads"
"""O mesmo texto de `Lead.canal` nos leads que vieram do Meta."""

_CONTA = re.compile(r"^\d{5,20}$")


@dataclass(frozen=True)
class ConfiguracaoDoMetaAds:
    token: str
    conta: str
    versao: str


def ler_configuracao() -> ConfiguracaoDoMetaAds | None:
    """A configuração da tela, ou `None` com a leitura desligada ou faltando token ou conta."""
    if configuracao.valor("meta_ads.ligado") != "true":
        return None
    token = configuracao.valor("meta_ads.token").strip()
    conta = configuracao.valor("meta_ads.conta").strip().removeprefix("act_")
    if not token or not conta:
        return None
    return ConfiguracaoDoMetaAds(token, conta, configuracao.valor("meta_ads.versao").strip() or "v24.0")


def _validar(config: ConfiguracaoDoMetaAds) -> None:
    if not _CONTA.match(config.conta):
        raise LeituraFalhou("O ID da conta de anúncios deve ter só números, como 1708029123631617.")


def _pedir(cliente: httpx.Client, url: str, params: dict | None, config: ConfiguracaoDoMetaAds) -> dict:
    try:
        resposta = cliente.get(url, params=params, headers={"Authorization": f"Bearer {config.token}"})
    except httpx.HTTPError as falha:
        raise LeituraFalhou(f"Não consegui falar com a Meta: {type(falha).__name__}.") from falha
    try:
        dados = resposta.json()
    except ValueError:
        dados = {}
    if resposta.status_code in (401, 403):
        raise LeituraFalhou(f"A Meta recusou o token do Meta Ads (HTTP {resposta.status_code}). Confira o token "
                            "e a permissão ads_read em Configurações › Integrações.")
    if resposta.status_code != 200:
        erro = dados.get("error") if isinstance(dados.get("error"), dict) else {}
        raise LeituraFalhou(f"A Meta não respondeu à leitura (HTTP {resposta.status_code}): "
                            f"{erro.get('message') or 'confira o ID da conta'}")
    return dados


def _base(config: ConfiguracaoDoMetaAds) -> str:
    return f"https://graph.facebook.com/{config.versao}/act_{config.conta}"


def conferir_conta(config: ConfiguracaoDoMetaAds, *, http: httpx.Client | None = None) -> str:
    """O teste da tela: o nome, a situação e a moeda da conta. Não grava nada."""
    _validar(config)
    cliente = http or httpx.Client(timeout=30.0)
    try:
        dados = _pedir(cliente, _base(config), {"fields": "name,account_status,currency"}, config)
    finally:
        if http is None:
            cliente.close()
    situacao = "ativa" if dados.get("account_status") == 1 else f"situação {dados.get('account_status')}"
    return f"A Meta reconheceu a conta {dados.get('name') or config.conta}: {situacao}, moeda {dados.get('currency') or '?'}."


def gasto_por_campanha(config: ConfiguracaoDoMetaAds, mes: str, hoje: date, *,
                       http: httpx.Client | None = None) -> list[GastoDaCampanha]:
    """O gasto de cada campanha no mês (em reais, a moeda da conta), página por página."""
    _validar(config)
    periodo = intervalo(mes, hoje)
    if periodo is None:
        return []
    params: dict | None = {
        "level": "campaign",
        "fields": "campaign_id,campaign_name,spend",
        "time_range": json.dumps({"since": periodo[0].isoformat(), "until": periodo[1].isoformat()}),
        "limit": 500,
    }
    url: str | None = f"{_base(config)}/insights"
    cliente = http or httpx.Client(timeout=60.0)
    gastos: list[GastoDaCampanha] = []
    try:
        for _ in range(50):  # trava contra paginação sem fim
            if url is None:
                break
            dados = _pedir(cliente, url, params, config)
            for linha in dados.get("data") or []:
                try:
                    valor = Decimal(str(linha.get("spend") or "0"))
                except InvalidOperation:
                    continue
                nome = (linha.get("campaign_name") or "").strip()
                if nome:
                    gastos.append(GastoDaCampanha(str(linha.get("campaign_id") or ""), nome[:200], valor))
            url = (dados.get("paging") or {}).get("next")
            params = None  # o "next" já traz os parâmetros
    finally:
        if http is None:
            cliente.close()
    return gastos
