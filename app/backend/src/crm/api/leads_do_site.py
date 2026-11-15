"""A porta do formulário do site: `POST /api/publico/leads-do-site` (15/11/2026).

A landing page "Reforma Tributária para empresas de serviços" manda aqui o contato de quem fez a simulação
(nome, WhatsApp, perfil, consentimento). É uma das poucas rotas do CRM sem login, então a segurança está nas
travas, como no webhook do WhatsApp (`crm.api.whatsapp_recebido`):

- **desligada por padrão** (`site.ligado`, Configurações › Integrações › Site): desligada, responde 404;
- **só a origem da página** (`site.origens`): o navegador só deixa a página chamar se o `Origin` estiver na lista
  (CORS). Pedido sem `Origin` ou de outra origem é recusado com 403, sem cabeçalho de CORS;
- **limite por IP** (`site.limite_por_hora`, padrão 10): passou, 429;
- **campo isca** (`website`): a página o manda vazio; preenchido, o envio é tratado como robô — a resposta é a
  mesma de sucesso e nada é gravado;
- corpo acima de `LIMITE_DO_CORPO` é recusado antes de ser lido inteiro;
- a resposta nunca leva dado (nem o ID do lead, nem se o WhatsApp já existia), e o log só diz o motivo.

O WhatsApp que já está num lead não cria outro: o lead mais recente com esse número ganha a nova entrada na
observação (proposta à espera de Eduardo). A comparação é a do recebimento do WhatsApp (`chave_do_telefone`).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from crm import configuracao
from crm.agente.recebimento import chave_do_telefone
from crm.db.base import agora
from crm.db.modelos import Lead
from crm.domain.leads_do_site import CANAL, ISCA, Recusa, anotacao_da_nova_entrada, campos_do_lead, conferir

__all__ = ["CAMINHO", "LIMITE_DO_CORPO", "PREFIXO", "LimitePorIp", "origens_permitidas", "roteador_de_leads_do_site",
           "situacao_do_site"]

PREFIXO = "/api/publico/"
"""Tudo que começa aqui fica fora do CORS geral da API: cada rota pública cuida do seu."""
CAMINHO = PREFIXO + "leads-do-site"
LIMITE_DO_CORPO = 16_000
"""16 KB. O envio da página tem menos de 2 KB."""
LIMITE_PADRAO = 10
JANELA = 3600.0
"""O limite por IP vale por hora."""

_log = logging.getLogger(__name__)


class LimitePorIp:
    """Janela deslizante em memória (a API roda num processo só: `docker-compose.coolify.yml`). Guarda só o IP e
    os instantes; esquece o IP quando a janela passa."""

    def __init__(self, relogio: Callable[[], float] = time.monotonic, maximo_de_ips: int = 20_000) -> None:
        self._relogio = relogio
        self._trava = threading.Lock()
        self._pedidos: dict[str, deque[float]] = {}
        self._maximo_de_ips = maximo_de_ips

    def permite(self, ip: str, limite: int) -> bool:
        agora_ = self._relogio()
        with self._trava:
            if len(self._pedidos) > self._maximo_de_ips:
                self._pedidos = {k: v for k, v in self._pedidos.items() if v and agora_ - v[-1] < JANELA}
            fila = self._pedidos.setdefault(ip, deque())
            while fila and agora_ - fila[0] >= JANELA:
                fila.popleft()
            if len(fila) >= limite:
                return False
            fila.append(agora_)
            return True


@dataclass(frozen=True)
class Ocorrencia:
    em: datetime
    texto: str


_trava = threading.Lock()
_ultima_recusa: Ocorrencia | None = None


def _anotar_recusa(motivo: str) -> None:
    global _ultima_recusa
    with _trava:
        _ultima_recusa = Ocorrencia(agora(), motivo)
    _log.warning("Site: envio recusado (%s)", motivo)


def _ligado() -> bool:
    return configuracao.valor("site.ligado") == "true"


def origens_permitidas() -> frozenset[str]:
    """As origens da tela (vírgula, espaço ou linha), sem barra no fim, em minúsculas."""
    texto = configuracao.valor("site.origens") or ""
    return frozenset(o.strip().rstrip("/").lower() for o in texto.replace(",", " ").split() if o.strip())


def _limite() -> int:
    try:
        return max(1, int(configuracao.valor("site.limite_por_hora") or LIMITE_PADRAO))
    except ValueError:
        return LIMITE_PADRAO


def _brasilia(momento: datetime) -> str:
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y às %H:%M")


def situacao_do_site(sessao: Session) -> str:
    """A frase da tela de Integrações. Estado nunca só por cor: vai em texto."""
    if not _ligado():
        return "Formulário desligado: o CRM recusa o que o site enviar."
    if not origens_permitidas():
        return "⚠ Formulário ligado, mas sem origem permitida: o CRM recusa tudo até o endereço da página ser salvo."
    ultimo = sessao.scalar(sa.select(sa.func.max(Lead.criado_em)).where(Lead.canal == CANAL))
    partes = [f"✓ Último lead do site em {_brasilia(ultimo)}." if ultimo else "⚠ Nenhum lead do site ainda."]
    with _trava:
        recusa = _ultima_recusa
    if recusa is not None:
        partes.append(f"Último envio recusado em {_brasilia(recusa.em)}: {recusa.texto}.")
    return " ".join(partes)


def _cors(origem: str) -> dict[str, str]:
    return {"Access-Control-Allow-Origin": origem, "Vary": "Origin"}


def _lead_do_mesmo_whatsapp(sessao: Session, whatsapp: str) -> Lead | None:
    """O lead mais recente com o mesmo WhatsApp. O banco filtra pelos 8 últimos dígitos; a chave do recebimento
    do WhatsApp decide (com e sem o nono dígito, com e sem o 55, com máscara ou não)."""
    chave = chave_do_telefone(whatsapp)
    so_digitos = Lead.telefone
    for sinal in (" ", "-", "(", ")", "+", ".", "/"):
        so_digitos = sa.func.replace(so_digitos, sinal, "")
    candidatos = sessao.scalars(
        sa.select(Lead).where(so_digitos.like(f"%{whatsapp[-8:]}")).order_by(Lead.id.desc())
    )
    return next((l for l in candidatos if chave_do_telefone(l.telefone) == chave), None)


def gravar_envio(sessao: Session, corpo: dict, momento: datetime) -> str:
    """Cria o lead ou anota a nova entrada no que já existe. Devolve "novo" ou "repetido" (só para o log)."""
    envio = conferir(corpo)
    existente = _lead_do_mesmo_whatsapp(sessao, envio.whatsapp)
    if existente is None:
        sessao.add(Lead(**campos_do_lead(envio, momento)))
        sessao.flush()
        return "novo"
    nota = anotacao_da_nova_entrada(envio, momento)
    existente.observacao = f"{existente.observacao}\n\n{nota}" if existente.observacao else nota
    # Só preenche o que está vazio: o que a equipe já editou não muda.
    if not existente.email and envio.email:
        existente.email = envio.email
    if not existente.empresa_texto and envio.empresa:
        existente.empresa_texto = envio.empresa
    sessao.flush()
    return "repetido"


def roteador_de_leads_do_site(
    obter_sessao: Callable[[], Iterator[Session]], limite_por_ip: LimitePorIp | None = None
) -> APIRouter:
    r = APIRouter(tags=["site"])
    limite_ip = limite_por_ip or LimitePorIp()

    def _origem_aceita(request: Request) -> str | None:
        origem = (request.headers.get("origin") or "").strip().rstrip("/").lower()
        return origem if origem and origem in origens_permitidas() else None

    @r.options(CAMINHO, include_in_schema=False)
    def preparar(request: Request) -> Response:
        """O "pode?" do navegador antes do POST com JSON (preflight do CORS)."""
        if not _ligado():
            return Response(status_code=404)
        origem = _origem_aceita(request)
        if origem is None:
            _anotar_recusa("origem fora da lista")
            return Response(status_code=403)
        return Response(status_code=204, headers={
            **_cors(origem), "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "600",
        })

    @r.post(CAMINHO, status_code=201)
    async def receber(request: Request, sessao: Session = Depends(obter_sessao, scope="function")) -> Response:
        """Pública. 201 = recebido (sem dado na resposta); 400 campo que não vale (só o nome do campo);
        403 origem fora da lista; 404 desligado; 413 grande demais; 429 limite por IP."""
        if not _ligado():
            return Response(status_code=404)
        origem = _origem_aceita(request)
        if origem is None:
            _anotar_recusa("origem fora da lista")
            return JSONResponse({"detail": "Origem não permitida."}, status_code=403)
        cors = _cors(origem)
        ip = request.client.host if request.client else "?"
        if not limite_ip.permite(ip, _limite()):
            _anotar_recusa("limite de envios por IP")
            return JSONResponse({"detail": "Muitos envios em pouco tempo. Tente de novo mais tarde."},
                                status_code=429, headers=cors)
        tamanho = request.headers.get("content-length")
        if tamanho is not None and (not tamanho.isdigit() or int(tamanho) > LIMITE_DO_CORPO):
            _anotar_recusa("envio grande demais")
            return Response(status_code=413, headers=cors)
        bruto = b""
        async for parte in request.stream():
            bruto += parte
            if len(bruto) > LIMITE_DO_CORPO:
                _anotar_recusa("envio grande demais")
                return Response(status_code=413, headers=cors)
        try:
            corpo = json.loads(bruto)
        except ValueError:
            _anotar_recusa("corpo que não é JSON")
            return JSONResponse({"detail": "O envio precisa ser JSON."}, status_code=400, headers=cors)
        recebido = JSONResponse({"recebido": True}, status_code=201, headers=cors)
        if isinstance(corpo, dict) and corpo.get(ISCA) not in (None, ""):
            _anotar_recusa("campo isca preenchido")
            return recebido
        try:
            resultado = await run_in_threadpool(gravar_envio, sessao, corpo, agora())
        except Recusa as recusa:
            _anotar_recusa(f"campo {recusa.campo}")
            return JSONResponse({"detail": recusa.mensagem, "campo": recusa.campo}, status_code=400, headers=cors)
        except Exception as falha:  # noqa: BLE001 — o erro do banco traz os valores: no log, só o tipo
            sessao.rollback()
            _log.error("Site: falha ao gravar o envio (%s)", type(falha).__name__)
            return JSONResponse({"detail": "Não foi possível registrar agora."}, status_code=500, headers=cors)
        _log.info("Site: envio recebido (%s)", resultado)
        return recebido

    return r
