"""A API pública do Granola (https://docs.granola.ai, conferida em 23/10/2026). Só lê.

- Endereço `https://public-api.granola.ai/v1`, com `Authorization: Bearer grn_…`. A chave é pessoal (plano Business ou
  Enterprise) e, com o escopo "Personal notes", enxerga só as notas do dono e as compartilhadas com ele.
- `GET /v1/folders` lista as pastas; `GET /v1/notes?folder_id=…&created_after=…` lista as notas da pasta (e das
  subpastas), 30 por página no máximo, com `cursor`; `GET /v1/notes/{id}?include=transcript` traz a nota inteira.
  Transcrição grande demais volta 413 (`TRANSCRIPT_TOO_LARGE`) e vem por `GET /v1/notes/{id}/transcript`, em páginas.
- Só aparecem notas que já têm o resumo da IA pronto. Limite: 25 pedidos em 5 segundos, 5 por segundo
  sustentado; acima disso, 429.

A configuração vem da tela Configurações › Integrações › Granola. Toda falha vira `FalhaNoGranola`, com uma frase
para a tela e sem a chave.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx2 as httpx

from crm import configuracao
from crm.domain.granola import falante

__all__ = ["BASE", "ConfiguracaoDoGranola", "FalhaNoGranola", "Nota", "NotaResumida", "Pasta", "achar_pasta",
           "conferir", "ler_configuracao", "ler_nota", "listar_notas", "listar_pastas", "novo_http"]

BASE = "https://public-api.granola.ai"
_RIO = ZoneInfo("America/Sao_Paulo")
_MAX_PAGINAS = 100
"""Trava contra paginação sem fim: 100 páginas de 30 notas."""


class FalhaNoGranola(RuntimeError):
    """A frase é para a pessoa ler; nunca leva a chave."""


@dataclass(frozen=True)
class ConfiguracaoDoGranola:
    chave: str
    pasta_lead: str
    pasta_resultado: str
    desde: date | None
    """Notas criadas antes ficam no Granola; `None` = as dos últimos 30 dias."""


@dataclass(frozen=True)
class Pasta:
    id: str
    nome: str


@dataclass(frozen=True)
class NotaResumida:
    id: str
    titulo: str
    criada_em: datetime


@dataclass(frozen=True)
class Nota:
    id: str
    titulo: str
    data: date
    """O dia da reunião no horário de Brasília: o início do evento da agenda, senão quando a nota nasceu."""
    link: str | None
    dono_nome: str | None
    dono_email: str | None
    pessoas: list[tuple[str | None, str | None]] = field(default_factory=list)
    """(nome, e-mail) de quem participou e de quem foi convidado no evento, sem repetir e-mail."""
    resumo: str = ""
    transcricao: str | None = None


def data_de_texto(texto: str) -> date | None:
    """"01/10/2026" → date. Vazio → None. Fora do formato → ValueError."""
    texto = (texto or "").strip()
    if not texto:
        return None
    return datetime.strptime(texto, "%d/%m/%Y").date()


def ler_configuracao(*, exigir_ligada: bool = True) -> ConfiguracaoDoGranola | None:
    """A chave e as pastas; `None` com a busca desligada (quando `exigir_ligada`) ou sem chave."""
    if exigir_ligada and configuracao.valor("granola.ligado") != "true":
        return None
    chave = configuracao.valor("granola.chave").strip()
    if not chave:
        return None
    try:
        desde = data_de_texto(configuracao.valor("granola.desde"))
    except ValueError:
        desde = None
    return ConfiguracaoDoGranola(
        chave=chave,
        pasta_lead=configuracao.valor("granola.pasta_lead").strip() or "Potencial Cliente",
        pasta_resultado=configuracao.valor("granola.pasta_resultado").strip() or "Reunião de Resultado",
        desde=desde,
    )


def novo_http() -> httpx.Client:
    return httpx.Client(timeout=30)


def _pedir(http: httpx.Client, caminho: str, params: dict | None, config: ConfiguracaoDoGranola,
           esperar: Callable[[float], None] = time.sleep) -> dict:
    for tentativa in range(4):
        try:
            resposta = http.get(f"{BASE}{caminho}", params=params,
                                headers={"Authorization": f"Bearer {config.chave}", "Accept": "application/json"})
        except httpx.HTTPError as falha:
            raise FalhaNoGranola(f"Não consegui falar com o Granola: {type(falha).__name__}.") from falha
        if resposta.status_code == 429 and tentativa < 3:
            try:
                segundos = float(resposta.headers.get("retry-after", "2"))
            except ValueError:
                segundos = 2.0
            esperar(min(max(segundos, 1.0), 10.0))
            continue
        break
    try:
        dados = resposta.json()
    except ValueError:
        dados = {}
    if not isinstance(dados, dict):
        dados = {}
    if resposta.status_code in (401, 403):
        raise FalhaNoGranola(f"O Granola recusou a chave (HTTP {resposta.status_code}). Confira se ela foi copiada "
                             "inteira, se não foi revogada e se a conta está no plano Business.")
    if resposta.status_code == 429:
        raise FalhaNoGranola("O Granola pediu para esperar (limite de pedidos). A próxima busca tenta de novo.")
    if resposta.status_code == 413:
        raise _GrandeDemais()
    if resposta.status_code == 404:
        raise FalhaNoGranola("O Granola não achou o que o CRM pediu (HTTP 404).")
    if resposta.status_code != 200:
        raise FalhaNoGranola(f"O Granola não respondeu como esperado (HTTP {resposta.status_code}).")
    return dados


class _GrandeDemais(FalhaNoGranola):
    def __init__(self) -> None:
        super().__init__("A transcrição é grande demais para vir junto com a nota.")


def _paginas(http: httpx.Client, caminho: str, params: dict, chave_da_lista: str,
             config: ConfiguracaoDoGranola, esperar: Callable[[float], None]) -> list[dict]:
    itens: list[dict] = []
    cursor: str | None = None
    for _ in range(_MAX_PAGINAS):
        dados = _pedir(http, caminho, {**params, **({"cursor": cursor} if cursor else {})}, config, esperar)
        itens.extend(i for i in (dados.get(chave_da_lista) or []) if isinstance(i, dict))
        cursor = dados.get("cursor")
        if not dados.get("hasMore") or not cursor:
            break
    return itens


def _momento(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


def listar_pastas(http: httpx.Client, config: ConfiguracaoDoGranola,
                  esperar: Callable[[float], None] = time.sleep) -> list[Pasta]:
    itens = _paginas(http, "/v1/folders", {"page_size": 30}, "folders", config, esperar)
    return [Pasta(i["id"], (i.get("name") or "").strip()) for i in itens if i.get("id")]


def achar_pasta(pastas: list[Pasta], nome: str) -> Pasta | None:
    alvo = " ".join(nome.split()).casefold()
    return next((p for p in pastas if " ".join(p.nome.split()).casefold() == alvo), None)


def listar_notas(http: httpx.Client, config: ConfiguracaoDoGranola, pasta: Pasta, desde: date,
                 esperar: Callable[[float], None] = time.sleep) -> list[NotaResumida]:
    itens = _paginas(http, "/v1/notes", {"folder_id": pasta.id, "created_after": desde.isoformat(), "page_size": 30},
                     "notes", config, esperar)
    notas = []
    for i in itens:
        if not i.get("id") or i.get("deleted_at"):
            continue
        notas.append(NotaResumida(i["id"], (i.get("title") or "").strip(), _momento(i.get("created_at")) or datetime.min))
    return notas


def _transcricao(itens: list, dono: str | None) -> str | None:
    linhas = []
    for t in itens or []:
        if not isinstance(t, dict) or not (t.get("text") or "").strip():
            continue
        linhas.append(f"{falante(t, dono)}: {t['text'].strip()}")
    return "\n".join(linhas) or None


def ler_nota(http: httpx.Client, config: ConfiguracaoDoGranola, nota_id: str, *, com_transcricao: bool,
             esperar: Callable[[float], None] = time.sleep) -> Nota:
    """A nota inteira. Sem `com_transcricao` (nota de lead), a transcrição nem é pedida."""
    params = {"include": "transcript"} if com_transcricao else None
    transcricao_em_paginas = False
    try:
        dados = _pedir(http, f"/v1/notes/{nota_id}", params, config, esperar)
    except _GrandeDemais:
        dados = _pedir(http, f"/v1/notes/{nota_id}", None, config, esperar)
        transcricao_em_paginas = True
    dono = dados.get("owner") or {}
    evento = dados.get("calendar_event") or {}
    inicio = _momento(evento.get("scheduled_start_time")) or _momento(dados.get("created_at"))
    dia = inicio.astimezone(_RIO).date() if inicio and inicio.tzinfo else (inicio.date() if inicio else date.today())
    pessoas: list[tuple[str | None, str | None]] = []
    vistos: set[str] = set()
    for p in [*(dados.get("attendees") or []), *(evento.get("invitees") or [])]:
        if not isinstance(p, dict):
            continue
        email = (p.get("email") or "").strip()
        if email.lower() in vistos:
            continue
        vistos.add(email.lower())
        pessoas.append((p.get("name"), email or None))
    transcricao = None
    if com_transcricao:
        if transcricao_em_paginas:
            itens = _paginas(http, f"/v1/notes/{nota_id}/transcript", {"page_size": 100}, "transcript", config, esperar)
        else:
            itens = dados.get("transcript") or []
        transcricao = _transcricao(itens, dono.get("name"))
    return Nota(
        id=dados.get("id") or nota_id, titulo=(dados.get("title") or "").strip() or "Reunião sem título",
        data=dia, link=dados.get("web_url"), dono_nome=dono.get("name"), dono_email=dono.get("email"),
        pessoas=pessoas, resumo=(dados.get("summary_markdown") or dados.get("summary_text") or "").strip(),
        transcricao=transcricao,
    )


def desde_efetivo(config: ConfiguracaoDoGranola, hoje: date) -> date:
    return config.desde or hoje - timedelta(days=30)


def conferir(http: httpx.Client, config: ConfiguracaoDoGranola,
             esperar: Callable[[float], None] = time.sleep) -> str:
    """O teste da tela: a chave abre as pastas, e as duas pastas configuradas existem. Não grava nada."""
    pastas = listar_pastas(http, config, esperar)
    faltam = [n for n in (config.pasta_lead, config.pasta_resultado) if achar_pasta(pastas, n) is None]
    if faltam:
        raise FalhaNoGranola(f"Conectado, mas a chave não enxerga a pasta {' nem a pasta '.join(repr(n) for n in faltam)}. "
                             "Crie a pasta no Granola ou escolha outra.")
    return f"Conectado ao Granola. A chave enxerga {len(pastas)} pasta{'s' if len(pastas) != 1 else ''}."
