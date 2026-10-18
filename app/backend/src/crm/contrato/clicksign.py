"""A API v3 da Clicksign: envelope, documento, signatários, requisitos e ativação (amostra aprovada em 18/10/2026).

Conferido na documentação oficial (developers.clicksign.com) em 18/10/2026:

- produção `https://app.clicksign.com`, sandbox `https://sandbox.clicksign.com` (sem validade jurídica); caminho
  `/api/v3/`; cabeçalho `Authorization` com o token puro, sem `Bearer`; JSON:API (`application/vnd.api+json`);
- o envelope nasce em `draft` e vira `running` pelo `PATCH` (sem volta); cada signatário precisa de um requisito de
  qualificação (`agree`, papel `sign`) e um de autenticação (`provide_evidence`, `email`/`sms`/`whatsapp`);
- o documento se cancela pelo `PATCH` do documento com `status: canceled`;
- o webhook vem assinado com HMAC SHA256 do corpo bruto no cabeçalho `Content-Hmac` (`sha256=<hex>`).

**O PDF assinado:** a referência da API v3 só documenta o original em `links.files`; o aviso traz
`downloads.signed_file_url`. O CRM usa o que vier, mas só de endereço HTTPS da Clicksign ou do S3 dela
(`endereco_confiavel`). Sem ele, o contrato assina do mesmo jeito e o PDF se anexa pela tela.

**Sem polling:** a Clicksign proíbe consulta em laço sem autorização do suporte. O CRM só consulta quando a pessoa
clica em "Conferir"; o resto vem pelo aviso.

Nenhum token passa por log ou mensagem de erro.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import httpx2 as httpx

from crm import configuracao

__all__ = [
    "AUTENTICACOES", "ConfiguracaoDaClicksign", "Documento", "Envelope", "FalhaNaClicksign", "Signatario",
    "assinatura_valida", "baixar_assinado", "cancelar", "conferir_conta", "consultar", "criar_envelope",
    "endereco_confiavel",
    "ler_configuracao", "lembrar",
]

HOSTS = {"sandbox": "https://sandbox.clicksign.com", "producao": "https://app.clicksign.com"}
AUTENTICACOES = ("email", "whatsapp", "sms")
TIPO = "application/vnd.api+json"
BRASILIA = ZoneInfo("America/Sao_Paulo")


class FalhaNaClicksign(RuntimeError):
    """A Clicksign recusou ou não respondeu. A mensagem é para a pessoa ler; nunca leva o token."""


@dataclass(frozen=True)
class ConfiguracaoDaClicksign:
    ambiente: str
    """"sandbox" ou "producao"."""
    token: str
    autenticacao: str

    @property
    def host(self) -> str:
        return HOSTS[self.ambiente]

    @property
    def painel(self) -> str:
        """Onde a pessoa abre o envelope na Clicksign."""
        return self.host


@dataclass(frozen=True)
class Signatario:
    nome: str
    email: str
    telefone: str | None = None


@dataclass(frozen=True)
class Envelope:
    envelope_id: str
    documento_id: str
    signatarios: dict[str, str]
    """{e-mail: id do signatário na Clicksign}."""


@dataclass(frozen=True)
class Documento:
    situacao: str
    """O `status` do documento na Clicksign: running, closed, canceled…"""
    modificado_em: datetime | None
    assinado_url: str | None


def ler_configuracao() -> ConfiguracaoDaClicksign | None:
    """A configuração da tela, ou `None` com a assinatura desligada ou sem token."""
    if configuracao.valor("clicksign.ligado") != "true":
        return None
    token = configuracao.valor("clicksign.token").strip()
    if not token:
        return None
    ambiente = configuracao.valor("clicksign.ambiente").strip()
    autenticacao = configuracao.valor("clicksign.autenticacao").strip()
    return ConfiguracaoDaClicksign(
        ambiente=ambiente if ambiente in HOSTS else "sandbox", token=token,
        autenticacao=autenticacao if autenticacao in AUTENTICACOES else "email",
    )


def assinatura_valida(corpo: bytes, cabecalho: str | None, segredo: str) -> bool:
    """`Content-Hmac: sha256=<hex>` sobre o corpo bruto, comparado em tempo constante."""
    if not cabecalho or not segredo:
        return False
    esperado = "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(cabecalho.strip().lower(), esperado)


# ── Pedidos ──────────────────────────────────────────────────────────────────────────────────────────

def _cliente(http: httpx.Client | None) -> httpx.Client:
    return http or httpx.Client(timeout=60.0)


def _erros(dados: dict) -> str:
    erros = dados.get("errors") if isinstance(dados, dict) else None
    if not isinstance(erros, list):
        return ""
    textos = []
    for e in erros[:3]:
        if isinstance(e, dict):
            ponteiro = (e.get("source") or {}).get("pointer") if isinstance(e.get("source"), dict) else None
            texto = str(e.get("detail") or e.get("title") or "").strip()
            if texto:
                textos.append(f"{texto} ({ponteiro.rsplit('/', 1)[-1]})" if ponteiro else texto)
    return "; ".join(textos)


def _pedir(config: ConfiguracaoDaClicksign, http: httpx.Client, metodo: str, caminho: str,
           corpo: dict | None = None) -> dict:
    try:
        resposta = http.request(metodo, f"{config.host}/api/v3{caminho}", json=corpo,
                                headers={"Authorization": config.token, "Content-Type": TIPO, "Accept": TIPO})
    except httpx.HTTPError as falha:
        raise FalhaNaClicksign(f"Não consegui falar com a Clicksign: {type(falha).__name__}.") from falha
    try:
        dados = resposta.json() if resposta.content else {}
    except ValueError:
        dados = {}
    if resposta.status_code in (401, 403):
        raise FalhaNaClicksign(f"A Clicksign recusou o token (HTTP {resposta.status_code}). Confira o access token "
                               "e o ambiente em Configurações › Integrações › Clicksign.")
    if resposta.status_code == 503:
        raise FalhaNaClicksign("A Clicksign diz que o envelope não está ativado nesta conta (HTTP 503). "
                               "Peça a ativação da API de envelopes ao suporte da Clicksign.")
    if resposta.status_code >= 300:
        detalhe = _erros(dados)
        raise FalhaNaClicksign(f"A Clicksign recusou o pedido (HTTP {resposta.status_code})"
                               + (f": {detalhe}" if detalhe else "."))
    return dados if isinstance(dados, dict) else {}


def _id(dados: dict) -> str:
    valor = (dados.get("data") or {}).get("id") if isinstance(dados.get("data"), dict) else None
    if not valor:
        raise FalhaNaClicksign("A Clicksign respondeu sem o identificador do que foi criado.")
    return str(valor)


def _requisito(documento_id: str, signatario_id: str, atributos: dict) -> dict:
    return {"data": {"type": "requirements", "attributes": atributos, "relationships": {
        "document": {"data": {"type": "documents", "id": documento_id}},
        "signer": {"data": {"type": "signers", "id": signatario_id}},
    }}}


def _prazo(prazo: date) -> str:
    """Fim do dia do prazo, em Brasília, no formato RFC 3339."""
    return datetime.combine(prazo, time(23, 59), BRASILIA).isoformat(timespec="seconds")


def conferir_conta(config: ConfiguracaoDaClicksign, *, http: httpx.Client | None = None) -> str:
    """Só lê: lista um envelope para saber se o token e o ambiente servem."""
    _pedir(config, _cliente(http), "GET", "/envelopes?page%5Bsize%5D=1")
    nome = "sandbox (teste, sem validade jurídica)" if config.ambiente == "sandbox" else "produção"
    return f"A Clicksign aceitou o token no ambiente {nome}."


def criar_envelope(config: ConfiguracaoDaClicksign, *, nome: str, nome_arquivo: str, pdf: bytes,
                   signatarios: list[Signatario], prazo: date, http: httpx.Client | None = None) -> Envelope:
    """Cria o envelope com o PDF e os signatários, define os requisitos e ativa. A ativação manda o pedido de
    assinatura a cada um. Se algo falhar antes da ativação, o envelope fica em rascunho na Clicksign e nada é enviado."""
    cliente = _cliente(http)
    envelope_id = _id(_pedir(config, cliente, "POST", "/envelopes", {"data": {"type": "envelopes", "attributes": {
        "name": nome[:200], "locale": "pt-BR", "auto_close": True, "remind_interval": "3",
        "block_after_refusal": True, "deadline_at": _prazo(prazo),
    }}}))
    documento_id = _id(_pedir(config, cliente, "POST", f"/envelopes/{envelope_id}/documents", {"data": {
        "type": "documents",
        "attributes": {"filename": nome_arquivo, "content_base64": "data:application/pdf;base64,"
                       + base64.b64encode(pdf).decode()},
    }}))
    ids: dict[str, str] = {}
    for s in signatarios:
        atributos: dict = {"name": s.nome, "email": s.email, "has_documentation": False, "refusable": True,
                           "communicate_events": {"signature_request": "email", "signature_reminder": "email",
                                                  "document_signed": "email"}}
        if s.telefone:
            atributos["phone_number"] = s.telefone
        signatario_id = _id(_pedir(config, cliente, "POST", f"/envelopes/{envelope_id}/signers",
                                   {"data": {"type": "signers", "attributes": atributos}}))
        ids[s.email] = signatario_id
        _pedir(config, cliente, "POST", f"/envelopes/{envelope_id}/requirements",
               _requisito(documento_id, signatario_id, {"action": "agree", "role": "sign"}))
        _pedir(config, cliente, "POST", f"/envelopes/{envelope_id}/requirements",
               _requisito(documento_id, signatario_id, {"action": "provide_evidence", "auth": config.autenticacao}))
    _pedir(config, cliente, "PATCH", f"/envelopes/{envelope_id}",
           {"data": {"id": envelope_id, "type": "envelopes", "attributes": {"status": "running"}}})
    return Envelope(envelope_id, documento_id, ids)


def quando(texto: object) -> datetime | None:
    if not isinstance(texto, str) or not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def consultar(config: ConfiguracaoDaClicksign, envelope_id: str, documento_id: str, *,
              http: httpx.Client | None = None) -> Documento:
    """A situação do documento e, se assinado, o endereço (temporário) do PDF assinado."""
    dados = _pedir(config, _cliente(http), "GET", f"/envelopes/{envelope_id}/documents/{documento_id}")
    d = dados.get("data") if isinstance(dados.get("data"), dict) else {}
    atributos = d.get("attributes") if isinstance(d.get("attributes"), dict) else {}
    arquivos = (d.get("links") or {}).get("files") if isinstance(d.get("links"), dict) else None
    arquivos = arquivos if isinstance(arquivos, dict) else {}
    assinado = arquivos.get("signed") or next(
        (v for k, v in arquivos.items() if "signed" in str(k) and "zip" not in str(k)), None)
    return Documento(situacao=str(atributos.get("status") or ""), modificado_em=quando(atributos.get("modified")),
                     assinado_url=endereco_confiavel(assinado))


def endereco_confiavel(url: object) -> str | None:
    """O endereço do PDF assinado só vale se for HTTPS na Clicksign ou no armazenamento dela (S3). O aviso chega
    assinado (HMAC), mas mesmo assim o CRM não segue endereço de outro lugar."""
    if not isinstance(url, str) or not url.startswith("https://"):
        return None
    host = url[len("https://"):].split("/", 1)[0].split("?", 1)[0].lower()
    if host.endswith(".clicksign.com") or (host.endswith(".amazonaws.com") and "clicksign" in host):
        return url
    return None


def baixar_assinado(url: str, *, http: httpx.Client | None = None) -> bytes:
    """O endereço vem da API (assinado e válido por poucos minutos): sem o token, que é só da API."""
    try:
        resposta = _cliente(http).get(url)
    except httpx.HTTPError as falha:
        raise FalhaNaClicksign(f"Não consegui baixar o PDF assinado: {type(falha).__name__}.") from falha
    if resposta.status_code != 200 or not resposta.content.startswith(b"%PDF"):
        raise FalhaNaClicksign(f"A Clicksign não entregou o PDF assinado (HTTP {resposta.status_code}).")
    return resposta.content


def lembrar(config: ConfiguracaoDaClicksign, envelope_id: str, signatario_id: str, *,
            http: httpx.Client | None = None) -> None:
    _pedir(config, _cliente(http), "POST", f"/envelopes/{envelope_id}/signers/{signatario_id}/notifications",
           {"data": {"type": "notifications", "attributes": {}}})


def cancelar(config: ConfiguracaoDaClicksign, envelope_id: str, documento_id: str, *,
             http: httpx.Client | None = None) -> None:
    _pedir(config, _cliente(http), "PATCH", f"/envelopes/{envelope_id}/documents/{documento_id}",
           {"data": {"id": documento_id, "type": "documents", "attributes": {"status": "canceled"}}})
