"""Google Ads: o gasto de cada campanha num mês, pela API do Google Ads — 14/10/2026.

Amostra aprovada por Eduardo em 14/10/2026. Só lê (`googleAds:search` com GAQL). Tudo vem da tela
Configurações › Integrações (`google_ads.*`): o token de desenvolvedor, o cliente OAuth, o refresh token,
a conta e, se houver, a conta de administrador. A cada leitura o refresh token vira um token de acesso
(`oauth2.googleapis.com/token`). Toda falha vira `LeituraFalhou` com uma frase, sem segredo.

A versão padrão é a v25, a mais nova em 14/10/2026 (lançada em julho de 2026). O Google aposenta uma
versão por volta de um ano depois: quando o Testar acusar versão vencida, troque na tela.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from zoneinfo import ZoneInfo

import httpx2 as httpx

from crm import configuracao
from crm.anuncios import GastoDaCampanha, LeituraFalhou, intervalo

__all__ = ["CANAL", "ConfiguracaoDoGoogleAds", "conferir_conta", "gasto_por_campanha", "ler_configuracao"]

CANAL = "Google Ads"
"""O mesmo texto de `Lead.canal` nos leads que vieram do Google."""

VERSAO_PADRAO = "v25"
_CONTA = re.compile(r"^\d{10}$")
_MILHAO = Decimal(1_000_000)
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_FUSO = ZoneInfo("America/Sao_Paulo")


@dataclass(frozen=True)
class ConfiguracaoDoGoogleAds:
    token_de_desenvolvedor: str
    cliente_id: str
    cliente_segredo: str
    refresh_token: str
    conta: str
    """Só os dígitos: 123-456-7890 vira 1234567890."""
    conta_admin: str | None
    versao: str


def so_digitos(valor: str) -> str:
    return re.sub(r"[\s-]", "", valor or "")


def ler_configuracao() -> ConfiguracaoDoGoogleAds | None:
    """A configuração da tela, ou `None` com a leitura desligada ou faltando algum campo obrigatório."""
    if configuracao.valor("google_ads.ligado") != "true":
        return None
    return _credenciais()


def _validar(config: ConfiguracaoDoGoogleAds) -> None:
    if not _CONTA.match(config.conta):
        raise LeituraFalhou("O ID da conta do Google Ads tem 10 dígitos, como 123-456-7890.")
    if config.conta_admin and not _CONTA.match(config.conta_admin):
        raise LeituraFalhou("O ID da conta de administrador tem 10 dígitos, como 123-456-7890.")


def _mensagem(resposta: httpx.Response) -> str:
    try:
        dados = resposta.json()
    except ValueError:
        return ""
    if isinstance(dados, list) and dados:
        dados = dados[0]
    erro = dados.get("error") if isinstance(dados, dict) else None
    if isinstance(erro, dict):
        return str(erro.get("message") or "")
    return str(dados.get("error_description") or "") if isinstance(dados, dict) else ""


def _acesso(cliente: httpx.Client, config: ConfiguracaoDoGoogleAds) -> str:
    """Troca o refresh token por um token de acesso, que dura cerca de uma hora."""
    try:
        resposta = cliente.post(_TOKEN_URL, data={
            "grant_type": "refresh_token", "refresh_token": config.refresh_token,
            "client_id": config.cliente_id, "client_secret": config.cliente_segredo,
        })
    except httpx.HTTPError as falha:
        raise LeituraFalhou(f"Não consegui falar com o Google: {type(falha).__name__}.") from falha
    if resposta.status_code != 200:
        raise LeituraFalhou("O Google recusou o cliente OAuth ou o refresh token "
                            f"(HTTP {resposta.status_code}). Confira os três em Configurações › Integrações.")
    token = (resposta.json() or {}).get("access_token")
    if not token:
        raise LeituraFalhou("O Google não devolveu o token de acesso. Gere o refresh token de novo.")
    return token


def _buscar(cliente: httpx.Client, config: ConfiguracaoDoGoogleAds, acesso: str, consulta: str) -> list[dict]:
    """Uma consulta GAQL, página por página."""
    cabecalho = {"Authorization": f"Bearer {acesso}", "developer-token": config.token_de_desenvolvedor}
    if config.conta_admin:
        cabecalho["login-customer-id"] = config.conta_admin
    url = f"https://googleads.googleapis.com/{config.versao}/customers/{config.conta}/googleAds:search"
    linhas: list[dict] = []
    pagina: str | None = None
    for _ in range(50):  # trava contra paginação sem fim
        corpo = {"query": consulta} | ({"pageToken": pagina} if pagina else {})
        try:
            resposta = cliente.post(url, json=corpo, headers=cabecalho)
        except httpx.HTTPError as falha:
            raise LeituraFalhou(f"Não consegui falar com o Google Ads: {type(falha).__name__}.") from falha
        if resposta.status_code == 404:
            raise LeituraFalhou(f"O Google Ads não reconheceu a versão {config.versao} da API ou a conta. "
                                "Confira a versão em Configurações › Integrações.")
        if resposta.status_code in (401, 403):
            raise LeituraFalhou(f"O Google Ads recusou o acesso (HTTP {resposta.status_code}): "
                                f"{_mensagem(resposta) or 'confira o token de desenvolvedor e a conta'}")
        if resposta.status_code != 200:
            raise LeituraFalhou(f"O Google Ads não respondeu à leitura (HTTP {resposta.status_code}): "
                                f"{_mensagem(resposta) or 'tente de novo'}")
        dados = resposta.json() or {}
        linhas.extend(dados.get("results") or [])
        pagina = dados.get("nextPageToken")
        if not pagina:
            break
    return linhas


def conferir_conta(config: ConfiguracaoDoGoogleAds, *, http: httpx.Client | None = None) -> str:
    """O teste da tela: o nome e a moeda da conta. Não grava nada."""
    _validar(config)
    cliente = http or httpx.Client(timeout=30.0)
    try:
        linhas = _buscar(cliente, config, _acesso(cliente, config),
                         "SELECT customer.descriptive_name, customer.currency_code FROM customer LIMIT 1")
    finally:
        if http is None:
            cliente.close()
    conta = (linhas[0].get("customer") if linhas else None) or {}
    return (f"O Google Ads reconheceu a conta {conta.get('descriptiveName') or config.conta}, "
            f"moeda {conta.get('currencyCode') or '?'}.")


def gasto_por_campanha(config: ConfiguracaoDoGoogleAds, mes: str, hoje: date, *,
                       http: httpx.Client | None = None) -> list[GastoDaCampanha]:
    """O gasto de cada campanha no mês, na moeda da conta. O Google informa em micros (÷ 1.000.000)."""
    _validar(config)
    periodo = intervalo(mes, hoje)
    if periodo is None:
        return []
    consulta = ("SELECT campaign.id, campaign.name, metrics.cost_micros FROM campaign "
                f"WHERE segments.date BETWEEN '{periodo[0].isoformat()}' AND '{periodo[1].isoformat()}' "
                "AND metrics.cost_micros > 0")
    cliente = http or httpx.Client(timeout=60.0)
    try:
        linhas = _buscar(cliente, config, _acesso(cliente, config), consulta)
    finally:
        if http is None:
            cliente.close()
    gastos = []
    for linha in linhas:
        campanha = linha.get("campaign") or {}
        nome = (campanha.get("name") or "").strip()
        micros = (linha.get("metrics") or {}).get("costMicros") or "0"
        if nome:
            gastos.append(GastoDaCampanha(str(campanha.get("id") or ""), nome[:200], Decimal(str(micros)) / _MILHAO))
    return gastos


# ------------------------------------------------- devolução de conversões (14/10/2026)
ACOES = {
    "lead_qualificado": "google_ads.acao_qualificado",
    "reuniao_marcada": "google_ads.acao_reuniao",
    "contrato_fechado": "google_ads.acao_contrato",
}
"""Cada evento do CRM vai para uma ação de conversão do tipo importação, criada no Google Ads."""


@dataclass(frozen=True)
class EnvioDoGoogle:
    credenciais: ConfiguracaoDoGoogleAds
    acoes: dict[str, str]
    """Evento do CRM → ID da ação de conversão. Evento sem ação fica sem enviar."""


def _credenciais() -> ConfiguracaoDoGoogleAds | None:
    campos = {c: configuracao.valor(f"google_ads.{c}").strip()
              for c in ("token_dev", "cliente_id", "cliente_segredo", "refresh_token", "conta")}
    if not all(campos.values()):
        return None
    return ConfiguracaoDoGoogleAds(
        token_de_desenvolvedor=campos["token_dev"], cliente_id=campos["cliente_id"],
        cliente_segredo=campos["cliente_segredo"], refresh_token=campos["refresh_token"],
        conta=so_digitos(campos["conta"]), conta_admin=so_digitos(configuracao.valor("google_ads.conta_admin")) or None,
        versao=configuracao.valor("google_ads.versao").strip() or VERSAO_PADRAO,
    )


def ler_envio() -> EnvioDoGoogle | None:
    """Com a devolução ligada e as credenciais completas; `None` desligada ou faltando credencial."""
    if configuracao.valor("google_ads.conversoes") != "true":
        return None
    credenciais = _credenciais()
    if credenciais is None:
        return None
    acoes = {evento: re.sub(r"\D", "", configuracao.valor(chave)) for evento, chave in ACOES.items()}
    return EnvioDoGoogle(credenciais, {e: a for e, a in acoes.items() if a})


def conversao_da_api(config: EnvioDoGoogle, envio) -> dict:
    """A conversão de clique no formato do `uploadClickConversions`. E-mail e telefone vão só em SHA-256."""
    conta = config.credenciais.conta
    momento = envio.momento.astimezone(_FUSO)
    conversao = {
        "gclid": envio.gclid,
        "conversionAction": f"customers/{conta}/conversionActions/{config.acoes[envio.evento]}",
        "conversionDateTime": momento.strftime("%Y-%m-%d %H:%M:%S") + momento.strftime("%z")[:3] + ":"
                              + momento.strftime("%z")[3:],
        "orderId": f"crm-{envio.lead_id}-{envio.evento}",
    }
    if envio.valor is not None:
        conversao |= {"conversionValue": float(envio.valor), "currencyCode": "BRL"}
    identificadores = ([{"hashedEmail": envio.hash_email}] if envio.hash_email else []) + (
        [{"hashedPhoneNumber": envio.hash_telefone_google}] if envio.hash_telefone_google else [])
    if identificadores:
        conversao["userIdentifiers"] = identificadores
    return conversao


def enviar_conversao(config: EnvioDoGoogle, envio, *, http: httpx.Client | None = None,
                     acesso: str | None = None) -> str:
    """Manda uma conversão de clique. Devolve a frase do aceite; levanta `Recusado`, `AcessoNegado`
    ou `LeituraFalhou` (tenta de novo depois). `acesso` reaproveita o token da rodada."""
    from crm.anuncios import AcessoNegado, Recusado

    cred = config.credenciais
    if envio.evento not in config.acoes:
        raise AcessoNegado(f"Falta o ID da ação de conversão de “{envio.evento}” em Configurações › Integrações.")
    try:
        _validar(cred)
    except LeituraFalhou as falha:
        raise AcessoNegado(str(falha)) from falha
    cliente = http or httpx.Client(timeout=30.0)
    try:
        try:
            token = acesso or _acesso(cliente, cred)
        except LeituraFalhou as falha:
            raise AcessoNegado(str(falha)) from falha
        cabecalho = {"Authorization": f"Bearer {token}", "developer-token": cred.token_de_desenvolvedor}
        if cred.conta_admin:
            cabecalho["login-customer-id"] = cred.conta_admin
        try:
            resposta = cliente.post(
                f"https://googleads.googleapis.com/{cred.versao}/customers/{cred.conta}:uploadClickConversions",
                json={"conversions": [conversao_da_api(config, envio)], "partialFailure": True}, headers=cabecalho)
        except httpx.HTTPError as falha:
            raise LeituraFalhou(f"Não consegui falar com o Google Ads: {type(falha).__name__}.") from falha
    finally:
        if http is None:
            cliente.close()
    if resposta.status_code in (401, 403, 404):
        raise AcessoNegado(f"O Google Ads recusou o envio (HTTP {resposta.status_code}): "
                           f"{_mensagem(resposta) or 'confira as credenciais e a versão'}")
    if resposta.status_code >= 500:
        raise LeituraFalhou(f"O Google Ads está instável (HTTP {resposta.status_code}). Tento de novo.")
    if resposta.status_code != 200:
        raise Recusado(f"O Google Ads recusou a conversão: {_mensagem(resposta) or f'HTTP {resposta.status_code}'}")
    falha_parcial = (resposta.json() or {}).get("partialFailureError")
    if falha_parcial:
        raise Recusado(f"O Google Ads recusou a conversão: {str(falha_parcial.get('message') or '')[:300]}")
    return "O Google Ads recebeu a conversão."
