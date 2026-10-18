"""Assinatura eletrônica do contrato pela Clicksign — fase 1 (amostra aprovada por Eduardo em 18/10/2026).

- `GET /api/contratos/{id}/assinatura`: se dá para enviar, os signatários sugeridos (quem assina pela Critério, da
  configuração do contrato e da tela de Integrações; o decisor do cliente, dos contatos do grupo) e os envios feitos.
- `POST /api/contratos/{id}/assinatura`: sobe o PDF final, cria o envelope na Clicksign e o ativa (a Clicksign manda
  o pedido de assinatura). Só com o contrato "Aguardando assinatura" e sem outro envio em andamento.
- `POST …/assinatura/conferir`: pergunta à Clicksign como está o documento — o caminho de reserva se um aviso não
  chegar — e baixa o PDF assinado se ainda faltar.
- `POST …/assinatura/lembrete` e `POST …/assinatura/cancelar`.
- `GET /api/assinaturas-de-contrato/{id}/pdf`: o PDF assinado.
- `POST /api/clicksign/webhook`: o segundo endereço do CRM aberto sem login. Como no WhatsApp, a trava é a
  assinatura: desligado responde 404; sem a chave do webhook salva, recusa tudo; com ela, exige `Content-Hmac`.
  Aviso de documento que o CRM não enviou é aceito (200) e ignorado, para a Clicksign não repetir.

**Assinado ativa o contrato sozinho**, com a data em que o envelope fechou (Brasília): a vigência começa na
assinatura (25/09/2026). O PDF assinado vem sempre da API, nunca de um endereço que o aviso traga.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, undefer

import httpx2 as httpx

from crm import configuracao
from crm.api.acesso import quem_fez
from crm.contrato import clicksign as cs
from crm.db.base import agora
from crm.db.modelos import (
    AssinaturaDeContrato, ConfiguracaoDeContrato, Contrato, Empresa, PessoaContato, VinculoDeContato,
)
from crm.domain.listas import PapelContato, SituacaoContrato

__all__ = ["CAMINHO_DO_WEBHOOK", "roteador_da_assinatura"]

CAMINHO_DO_WEBHOOK = "/api/clicksign/webhook"
LIMITE_DO_PDF = 20 * 1024 * 1024
LIMITE_DO_AVISO = 1_000_000
PAPEIS = ("Contratada", "Contratante", "Testemunha")
SITUACOES = {"em_assinatura": "Em assinatura", "assinado": "Assinado", "recusado": "Recusado",
             "expirado": "Prazo vencido", "cancelado": "Cancelado"}
FECHAMENTO = {"auto_close", "close", "document_closed"}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_log = logging.getLogger(__name__)

FabricaDeHttp = Callable[[], httpx.Client | None]


# ── Esquemas ─────────────────────────────────────────────────────────────────────────────────────────

class SignatarioSugerido(BaseModel):
    nome: str
    email: str
    telefone: str | None
    papel: str
    origem: str
    """De onde veio: "configurações", "contato decisor", "contato principal" ou "digitar"."""


class SignatarioDoEnvio(BaseModel):
    nome: str
    email: str
    telefone: str | None
    papel: str
    assinou_em: datetime | None


class Envio(BaseModel):
    id: int
    situacao: str
    situacao_texto: str
    ambiente: str
    nome_arquivo: str
    prazo: date
    enviado_em: datetime
    enviado_por: str
    concluido_em: datetime | None
    motivo: str | None
    ultimo_evento: str | None
    ultimo_evento_em: datetime | None
    signatarios: list[SignatarioDoEnvio]
    tem_pdf: bool


class AbaDaAssinatura(BaseModel):
    ligada: bool
    ambiente: str
    autenticacao: str
    pede_telefone: bool
    problema: str | None
    """Por que não dá para enviar agora (desligada, contrato já assinado, envio em andamento)."""
    sugeridos: list[SignatarioSugerido]
    prazo_sugerido: date
    atual: Envio | None
    anteriores: list[Envio]


class SignatarioNovo(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=200)
    telefone: str | None = Field(default=None, max_length=30)
    papel: str


class PedidoDeEnvio(BaseModel):
    nome_arquivo: str = Field(min_length=1, max_length=200)
    conteudo_base64: str = Field(min_length=1)
    signatarios: list[SignatarioNovo] = Field(min_length=2, max_length=10)
    prazo: date
    enviado_por: str | None = Field(default=None, max_length=200)
    """Só sem login."""


class PedidoDeLembrete(BaseModel):
    email: str = Field(min_length=3, max_length=200)


# ── Regras ───────────────────────────────────────────────────────────────────────────────────────────

def _brasilia(momento: datetime) -> date:
    return (momento if momento.tzinfo else momento.replace(tzinfo=cs.BRASILIA)).astimezone(cs.BRASILIA).date()


def _envio(a: AssinaturaDeContrato, tem_pdf: bool) -> Envio:
    return Envio(
        id=a.id, situacao=a.situacao, situacao_texto=SITUACOES.get(a.situacao, a.situacao), ambiente=a.ambiente,
        nome_arquivo=a.nome_arquivo, prazo=a.prazo, enviado_em=a.enviado_em, enviado_por=a.enviado_por,
        concluido_em=a.concluido_em, motivo=a.motivo, ultimo_evento=a.ultimo_evento,
        ultimo_evento_em=a.ultimo_evento_em, tem_pdf=tem_pdf,
        signatarios=[SignatarioDoEnvio(nome=s.get("nome", ""), email=s.get("email", ""), telefone=s.get("telefone"),
                                       papel=s.get("papel", ""), assinou_em=s.get("assinou_em"))
                     for s in a.signatarios],
    )


def _decisor(sessao: Session, c: Contrato) -> tuple[PessoaContato, str] | None:
    """O contato decisor do grupo, preferindo a empresa do contrato; sem decisor, o contato principal."""
    empresas = list(sessao.scalars(sa.select(Empresa.id).where(Empresa.grupo_id == c.grupo_id)))
    if not empresas:
        return None
    linhas = sessao.execute(
        sa.select(PessoaContato, VinculoDeContato.empresa_id, VinculoDeContato.principal)
        .join(VinculoDeContato, VinculoDeContato.pessoa_id == PessoaContato.id)
        .where(VinculoDeContato.empresa_id.in_(empresas))
    ).all()

    def ordem(linha) -> tuple:
        pessoa, empresa_id, principal = linha
        return (pessoa.papel is not PapelContato.DECISOR, empresa_id != c.empresa_id, not principal,
                not pessoa.email, pessoa.id)

    for pessoa, _, principal in sorted(linhas, key=ordem):
        if pessoa.papel is PapelContato.DECISOR:
            return pessoa, "contato decisor"
        if principal:
            return pessoa, "contato principal"
    return None


def _sugeridos(sessao: Session, c: Contrato) -> list[SignatarioSugerido]:
    cfg = sessao.get(ConfiguracaoDeContrato, 1)
    criterio_nome = (cfg.signatario if cfg else None) or ""
    criterio_email = configuracao.valor("clicksign.email_criterio").strip()
    sugeridos = [SignatarioSugerido(
        nome=criterio_nome, email=criterio_email, telefone=None, papel="Contratada",
        origem="configurações" if criterio_nome or criterio_email else "digitar")]
    decisor = _decisor(sessao, c)
    if decisor is not None:
        pessoa, origem = decisor
        sugeridos.append(SignatarioSugerido(nome=pessoa.nome, email=pessoa.email or "", telefone=pessoa.telefone,
                                            papel="Contratante", origem=origem))
    else:
        sugeridos.append(SignatarioSugerido(nome="", email="", telefone=None, papel="Contratante", origem="digitar"))
    return sugeridos


def _telefone(texto: str | None) -> str:
    digitos = re.sub(r"\D", "", texto or "")
    return digitos[2:] if digitos.startswith("55") and len(digitos) in (12, 13) else digitos


def _validar(corpo: PedidoDeEnvio, autenticacao: str, hoje: date) -> tuple[bytes, list[dict]]:
    problemas: list[str] = []
    if not corpo.nome_arquivo.lower().endswith(".pdf"):
        problemas.append("o documento precisa ser o PDF final (salve o Word como PDF)")
    try:
        conteudo = corpo.conteudo_base64.split(",", 1)[-1] if corpo.conteudo_base64.startswith("data:") else corpo.conteudo_base64
        pdf = base64.b64decode(conteudo, validate=True)
    except (binascii.Error, ValueError):
        pdf = b""
    if not pdf.startswith(b"%PDF"):
        problemas.append("o arquivo não é um PDF")
    elif len(pdf) > LIMITE_DO_PDF:
        problemas.append(f"o PDF passa de {LIMITE_DO_PDF // (1024 * 1024)} MB")
    if corpo.prazo <= hoje:
        problemas.append("o prazo para assinar precisa ser depois de hoje")
    elif corpo.prazo > hoje + timedelta(days=90):
        problemas.append("o prazo para assinar vai até 90 dias")
    signatarios, emails = [], set()
    for i, s in enumerate(corpo.signatarios, start=1):
        nome, email = " ".join(s.nome.split()), s.email.strip().lower()
        if len(nome.split()) < 2:
            problemas.append(f"signatário {i}: nome e sobrenome (a Clicksign pede ao menos duas palavras)")
        if not _EMAIL.match(email):
            problemas.append(f"signatário {i}: e-mail inválido")
        elif email in emails:
            problemas.append(f"signatário {i}: e-mail repetido")
        emails.add(email)
        if s.papel not in PAPEIS:
            problemas.append(f"signatário {i}: papel deve ser {', '.join(PAPEIS)}")
        telefone = _telefone(s.telefone)
        if autenticacao != "email" and len(telefone) not in (10, 11):
            problemas.append(f"signatário {i}: celular com DDD (a autenticação é por {autenticacao})")
        signatarios.append({"nome": nome, "email": email, "telefone": telefone or None, "papel": s.papel,
                            "clicksign_id": None, "assinou_em": None})
    papeis = {s["papel"] for s in signatarios}
    if "Contratada" not in papeis or "Contratante" not in papeis:
        problemas.append("é preciso ao menos um signatário Contratada (Critério) e um Contratante (cliente)")
    if problemas:
        raise HTTPException(422, "; ".join(problemas))
    return pdf, signatarios


def _concluir_assinado(c: Contrato, a: AssinaturaDeContrato, quando: datetime, pdf: bytes | None) -> None:
    a.situacao, a.concluido_em = "assinado", quando
    a.signatarios = [{**s, "assinou_em": s.get("assinou_em") or quando.isoformat()} for s in a.signatarios]
    if pdf is not None:
        a.assinado_base64 = base64.b64encode(pdf).decode()
    if c.situacao is SituacaoContrato.AGUARDANDO_ASSINATURA:
        c.data_inicio = _brasilia(quando)
        c.situacao = SituacaoContrato.ATIVO
        clientes = [s["nome"] for s in a.signatarios if s.get("papel") == "Contratante"]
        if not c.signatario and clientes:
            c.signatario = ", ".join(clientes)[:200]
        if not c.documento_assinado:
            c.documento_assinado = f"Clicksign · envelope {a.envelope_id} (PDF na seção Assinatura eletrônica)"[:400]


def _encerrar(a: AssinaturaDeContrato, situacao: str, quando: datetime, motivo: str) -> None:
    if a.situacao == "em_assinatura":
        a.situacao, a.concluido_em, a.motivo = situacao, quando, motivo[:400]


def _conferir(sessao: Session, a: AssinaturaDeContrato, config: cs.ConfiguracaoDaClicksign,
              http: httpx.Client | None) -> None:
    """Pergunta à Clicksign e aplica: fechado vira assinado (e baixa o PDF); cancelado, cancelado."""
    doc = cs.consultar(config, a.envelope_id, a.documento_id, http=http)
    c = sessao.get(Contrato, a.contrato_id)
    if doc.situacao == "closed":
        pdf = None
        if doc.assinado_url:
            try:
                pdf = cs.baixar_assinado(doc.assinado_url, http=http)
            except cs.FalhaNaClicksign as falha:
                _log.warning("Clicksign: envelope fechado, PDF não baixado (%s)", falha)
        if a.situacao == "assinado":
            if pdf is not None:
                a.assinado_base64 = base64.b64encode(pdf).decode()
        else:
            _concluir_assinado(c, a, a.concluido_em or doc.modificado_em or agora(), pdf)
    elif doc.situacao == "canceled":
        _encerrar(a, "cancelado", doc.modificado_em or agora(), "cancelado na Clicksign")


def _tem_pdf(sessao: Session, a: AssinaturaDeContrato) -> bool:
    return bool(sessao.scalar(sa.select(AssinaturaDeContrato.assinado_base64.is_not(None))
                              .where(AssinaturaDeContrato.id == a.id)))


# ── Rotas ────────────────────────────────────────────────────────────────────────────────────────────

def roteador_da_assinatura(obter_sessao: Callable[[], Iterator[Session]],
                           http_da_clicksign: FabricaDeHttp | None = None) -> APIRouter:
    r = APIRouter(tags=["contratos"])
    novo_http: FabricaDeHttp = http_da_clicksign or (lambda: None)

    def _contrato(sessao: Session, contrato_id: int) -> Contrato:
        c = sessao.get(Contrato, contrato_id)
        if c is None:
            raise HTTPException(404, "contrato não encontrado")
        return c

    def _envios(sessao: Session, contrato_id: int) -> list[AssinaturaDeContrato]:
        return list(sessao.scalars(sa.select(AssinaturaDeContrato).where(AssinaturaDeContrato.contrato_id == contrato_id)
                                   .order_by(AssinaturaDeContrato.id.desc())))

    def _config() -> cs.ConfiguracaoDaClicksign:
        configuracao.invalidar()
        config = cs.ler_configuracao()
        if config is None:
            raise HTTPException(409, "Ligue a assinatura e salve o access token em Configurações › Integrações › Clicksign.")
        return config

    def _aba(sessao: Session, c: Contrato, hoje: date) -> AbaDaAssinatura:
        # A configuração já foi lida no começo da rota (`_config` ou `ver`): ler de novo aqui, depois de gravar,
        # abriria outra sessão no meio desta.
        config = cs.ler_configuracao()
        envios = _envios(sessao, c.id)
        atual = envios[0] if envios else None
        problema = None
        if config is None:
            problema = "Assinatura eletrônica desligada: ligue e salve o access token em Configurações › Integrações › Clicksign."
        elif atual is not None and atual.situacao == "em_assinatura":
            problema = "Já há um envio em assinatura. Para mandar outro documento, cancele este antes."
        elif c.situacao is not SituacaoContrato.AGUARDANDO_ASSINATURA:
            problema = f"O contrato está {c.situacao.value}: só se envia para assinatura o que aguarda assinatura."
        autenticacao = config.autenticacao if config else configuracao.valor("clicksign.autenticacao")
        return AbaDaAssinatura(
            ligada=config is not None, ambiente=config.ambiente if config else configuracao.valor("clicksign.ambiente"),
            autenticacao=autenticacao, pede_telefone=autenticacao != "email", problema=problema,
            sugeridos=_sugeridos(sessao, c), prazo_sugerido=hoje + timedelta(days=30),
            atual=_envio(atual, _tem_pdf(sessao, atual)) if atual else None,
            anteriores=[_envio(a, _tem_pdf(sessao, a)) for a in envios[1:]],
        )

    def _em_andamento(sessao: Session, contrato_id: int) -> AssinaturaDeContrato:
        envios = _envios(sessao, contrato_id)
        if not envios or envios[0].situacao != "em_assinatura":
            raise HTTPException(409, "não há envio em assinatura neste contrato")
        return envios[0]

    @r.get("/api/contratos/{contrato_id}/assinatura", response_model=AbaDaAssinatura)
    def ver(contrato_id: int, hoje: date | None = None,
            sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDaAssinatura:
        configuracao.invalidar()
        return _aba(sessao, _contrato(sessao, contrato_id), hoje or date.today())

    @r.post("/api/contratos/{contrato_id}/assinatura", response_model=AbaDaAssinatura)
    def enviar(contrato_id: int, corpo: PedidoDeEnvio, hoje: date | None = None,
               sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDaAssinatura:
        hoje = hoje or date.today()
        config = _config()
        c = sessao.get(Contrato, contrato_id, with_for_update=True) or _contrato(sessao, contrato_id)
        if c.situacao is not SituacaoContrato.AGUARDANDO_ASSINATURA:
            raise HTTPException(409, f"O contrato está {c.situacao.value}: só se envia o que aguarda assinatura.")
        envios = _envios(sessao, c.id)
        if envios and envios[0].situacao == "em_assinatura":
            raise HTTPException(409, "Já há um envio em assinatura. Cancele antes de mandar outro.")
        pdf, signatarios = _validar(corpo, config.autenticacao, hoje)
        nome = f"{c.grupo.nome} · {corpo.nome_arquivo.rsplit('.', 1)[0]}"
        try:
            envelope = cs.criar_envelope(
                config, nome=nome, nome_arquivo=corpo.nome_arquivo, pdf=pdf, prazo=corpo.prazo, http=novo_http(),
                signatarios=[cs.Signatario(s["nome"], s["email"], s["telefone"]) for s in signatarios],
            )
        except cs.FalhaNaClicksign as falha:
            raise HTTPException(502, str(falha)) from falha
        for s in signatarios:
            s["clicksign_id"] = envelope.signatarios.get(s["email"])
        quem = (quem_fez((corpo.enviado_por or "").strip()) or "").strip() or "sem login"
        sessao.add(AssinaturaDeContrato(
            contrato_id=c.id, ambiente=config.ambiente, envelope_id=envelope.envelope_id,
            documento_id=envelope.documento_id, nome_arquivo=corpo.nome_arquivo, situacao="em_assinatura",
            prazo=corpo.prazo, signatarios=signatarios, enviado_em=agora(), enviado_por=quem[:200],
        ))
        sessao.flush()
        return _aba(sessao, c, hoje)

    @r.post("/api/contratos/{contrato_id}/assinatura/conferir", response_model=AbaDaAssinatura)
    def conferir(contrato_id: int, hoje: date | None = None,
                 sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDaAssinatura:
        config = _config()
        c = _contrato(sessao, contrato_id)
        envios = _envios(sessao, c.id)
        if not envios:
            raise HTTPException(409, "este contrato ainda não foi enviado para assinatura")
        try:
            _conferir(sessao, envios[0], config, novo_http())
        except cs.FalhaNaClicksign as falha:
            raise HTTPException(502, str(falha)) from falha
        sessao.flush()
        return _aba(sessao, c, hoje or date.today())

    @r.post("/api/contratos/{contrato_id}/assinatura/lembrete", response_model=AbaDaAssinatura)
    def lembrete(contrato_id: int, corpo: PedidoDeLembrete, hoje: date | None = None,
                 sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDaAssinatura:
        config = _config()
        c = _contrato(sessao, contrato_id)
        a = _em_andamento(sessao, c.id)
        s = next((s for s in a.signatarios if s.get("email") == corpo.email.strip().lower()), None)
        if s is None or not s.get("clicksign_id"):
            raise HTTPException(404, "signatário não encontrado neste envio")
        if s.get("assinou_em"):
            raise HTTPException(409, "este signatário já assinou")
        try:
            cs.lembrar(config, a.envelope_id, s["clicksign_id"], http=novo_http())
        except cs.FalhaNaClicksign as falha:
            raise HTTPException(502, str(falha)) from falha
        a.ultimo_evento, a.ultimo_evento_em = f"lembrete para {s['nome']}"[:60], agora()
        sessao.flush()
        return _aba(sessao, c, hoje or date.today())

    @r.post("/api/contratos/{contrato_id}/assinatura/cancelar", response_model=AbaDaAssinatura)
    def cancelar(contrato_id: int, hoje: date | None = None,
                 sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDaAssinatura:
        config = _config()
        c = _contrato(sessao, contrato_id)
        a = _em_andamento(sessao, c.id)
        try:
            cs.cancelar(config, a.envelope_id, a.documento_id, http=novo_http())
        except cs.FalhaNaClicksign as falha:
            raise HTTPException(502, str(falha)) from falha
        _encerrar(a, "cancelado", agora(), f"cancelado no CRM por {quem_fez(None) or 'sem login'}")
        sessao.flush()
        return _aba(sessao, c, hoje or date.today())

    @r.get("/api/assinaturas-de-contrato/{assinatura_id}/pdf")
    def baixar(assinatura_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> Response:
        a = sessao.scalar(sa.select(AssinaturaDeContrato).options(undefer(AssinaturaDeContrato.assinado_base64))
                          .where(AssinaturaDeContrato.id == assinatura_id))
        if a is None or not a.assinado_base64:
            raise HTTPException(404, "PDF assinado não encontrado: use Conferir na Clicksign para baixá-lo")
        nome = re.sub(r'[^\w .-]+', " ", a.nome_arquivo.rsplit(".", 1)[0]).strip()[:80] or "contrato"
        return Response(base64.b64decode(a.assinado_base64), media_type="application/pdf", headers={
            "Content-Disposition": f'attachment; filename="{nome} - assinado.pdf"', "Cache-Control": "no-store"})

    # ── Webhook ───────────────────────────────────────────────────────────────────────────────────────

    @r.post(CAMINHO_DO_WEBHOOK, tags=["clicksign"])
    async def aviso(request: Request, sessao: Session = Depends(obter_sessao, scope="function")) -> Response:
        configuracao.invalidar()
        if configuracao.valor("clicksign.ligado") != "true":
            return _recusar("assinatura desligada", 404)
        segredo = configuracao.valor("clicksign.segredo_webhook")
        if not segredo:
            return _recusar("falta a chave do webhook", 403)
        tamanho = request.headers.get("content-length")
        if tamanho is not None and (not tamanho.isdigit() or int(tamanho) > LIMITE_DO_AVISO):
            return _recusar("aviso grande demais", 413)
        corpo = b""
        async for parte in request.stream():
            corpo += parte
            if len(corpo) > LIMITE_DO_AVISO:
                return _recusar("aviso grande demais", 413)
        if not cs.assinatura_valida(corpo, request.headers.get("content-hmac"), segredo):
            return _recusar("assinatura ausente ou inválida", 401)
        try:
            payload = json.loads(corpo)
        except ValueError:
            return _recusar("corpo que não é JSON", 400)
        if not isinstance(payload, dict):
            return _recusar("aviso fora do formato", 400)
        try:
            _aplicar_aviso(sessao, payload, request.headers.get("event"), novo_http)
        except Exception as falha:  # noqa: BLE001 — o erro do banco traz valores: no log, só o tipo
            sessao.rollback()
            _log.error("Clicksign: falha ao aplicar o aviso (%s); a Clicksign vai reenviar", type(falha).__name__)
            return Response(status_code=500)
        return Response(status_code=200)

    return r


def _recusar(motivo: str, status: int) -> Response:
    _log.warning("Clicksign: aviso recusado (%s)", motivo)
    return Response(status_code=status)


def _texto(d: object, *caminho: str) -> str | None:
    for chave in caminho:
        d = d.get(chave) if isinstance(d, dict) else None
    return d if isinstance(d, str) and d else None


def _aplicar_aviso(sessao: Session, payload: dict, cabecalho: str | None, novo_http: FabricaDeHttp) -> None:
    evento = _texto(payload, "event", "name") or (cabecalho or "").strip()
    chaves = {k for k in (_texto(payload, "document", "key"), _texto(payload, "document", "id"),
                          _texto(payload, "envelope", "key"), _texto(payload, "envelope", "id")) if k}
    if not evento or not chaves:
        return
    a = sessao.scalar(sa.select(AssinaturaDeContrato).where(sa.or_(
        AssinaturaDeContrato.documento_id.in_(chaves), AssinaturaDeContrato.envelope_id.in_(chaves))))
    if a is None:
        _log.info("Clicksign: aviso %s de documento que o CRM não enviou; ignorado", evento)
        return
    quando = cs._quando(_texto(payload, "event", "occurred_at")) or agora()
    a.ultimo_evento, a.ultimo_evento_em = evento[:60], quando
    dados = (payload.get("event") or {}).get("data") if isinstance(payload.get("event"), dict) else None
    email = (_texto(dados, "signer", "email") or "").lower()
    nome = _texto(dados, "signer", "name") or _texto(dados, "user", "name") or ""
    if evento == "sign" and email:
        a.signatarios = [{**s, "assinou_em": s.get("assinou_em") or quando.isoformat()} if s.get("email") == email else s
                         for s in a.signatarios]
    elif evento == "refusal":
        _encerrar(a, "recusado", quando, f"recusado por {nome or email or 'um signatário'} na Clicksign")
    elif evento == "deadline":
        _encerrar(a, "expirado", quando, "o prazo para assinar venceu")
    elif evento == "cancel":
        _encerrar(a, "cancelado", quando, "cancelado na Clicksign")
    elif evento in FECHAMENTO and a.situacao != "assinado":
        config = cs.ler_configuracao()
        if config is None:
            return
        try:
            _conferir(sessao, a, config, novo_http())
        except cs.FalhaNaClicksign as falha:
            # O aviso fica registrado; o botão Conferir termina o trabalho.
            _log.warning("Clicksign: envelope fechado, mas a consulta falhou (%s)", falha)
    sessao.flush()
