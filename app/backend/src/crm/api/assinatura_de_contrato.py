"""Assinatura eletrônica pela Clicksign (amostras aprovadas por Eduardo em 18/10/2026, unificadas no mesmo dia).

Pelo CRM (origem "crm"):

- `GET /api/contratos/{id}/assinatura`: se dá para enviar, os signatários sugeridos (quem assina pela Critério, da
  configuração do contrato e da tela de Integrações; o decisor do cliente, dos contatos do grupo) e os envelopes.
- `POST /api/contratos/{id}/assinatura`: sobe o PDF final, cria o envelope na Clicksign e o ativa (a Clicksign manda
  o pedido de assinatura). Só com o contrato "Aguardando assinatura" e sem outro envelope em assinatura.
- `POST …/assinatura/conferir`: uma consulta à Clicksign, quando a pessoa clica. **Nunca em laço:** a Clicksign
  proíbe polling sem autorização do suporte.
- `POST …/assinatura/lembrete` e `POST …/assinatura/cancelar`.

Pelo aviso (`POST /api/clicksign/webhook`), o segundo endereço do CRM aberto sem login. Como no WhatsApp, a trava é a
assinatura: desligado responde 404; sem a chave do webhook salva, recusa tudo; com ela, exige `Content-Hmac`.

- envelope do CRM assinado por todos: **ativa o contrato sozinho**, com a data em que fechou (Brasília);
- envelope feito direto na Clicksign: entra (origem "fora") só se o nome traz um número do CRM (CONT CCE RJ1 ou
  PROP CCE RJ), porque o aviso é da conta inteira. Não mexe no contrato;
- nos dois, o PDF assinado vira um documento anexado (origem "clicksign") e a IA o lê: a conferência
  (`crm.api.documentos`) mostra o que gravar. No de fora, é ela que decide o que vai para o contrato;
- aviso de documento que não interessa é aceito (200) e ignorado, para a Clicksign não repetir.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import re
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, defer, sessionmaker

import httpx2 as httpx

from crm import configuracao
from crm.api.acesso import quem_fez
from crm.api.documentos import NUMERO_DO_CRM, Leitor, _sugerir, ler_documento, leitor_real
from crm.contrato import clicksign as cs
from crm.db.base import agora
from crm.db.modelos import (
    ConfiguracaoDeContrato, Contrato, DocumentoAnexado, Empresa, EnvelopeDoClicksign, Oportunidade, PessoaContato,
    VinculoDeContato,
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
Agendar = Callable[[int], None]
"""Agenda a leitura do documento anexado, fora do pedido."""


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
    origem: str
    """"crm" (enviado pelo CRM) ou "fora" (feito direto na Clicksign)."""
    situacao: str
    situacao_texto: str
    ambiente: str
    nome_arquivo: str
    prazo: date | None
    enviado_em: datetime
    enviado_por: str
    concluido_em: datetime | None
    motivo: str | None
    ultimo_evento: str | None
    ultimo_evento_em: datetime | None
    signatarios: list[SignatarioDoEnvio]
    documento_anexado_id: int | None
    """O PDF assinado, na seção Documento assinado."""


class AbaDaAssinatura(BaseModel):
    ligada: bool
    ambiente: str
    autenticacao: str
    pede_telefone: bool
    problema: str | None
    """Por que não dá para enviar agora (desligada, contrato já assinado, envelope em assinatura)."""
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


def _envio(e: EnvelopeDoClicksign) -> Envio:
    return Envio(
        id=e.id, origem=e.origem, situacao=e.situacao, situacao_texto=SITUACOES.get(e.situacao, e.situacao),
        ambiente=e.ambiente, nome_arquivo=e.nome_arquivo, prazo=e.prazo, enviado_em=e.enviado_em,
        enviado_por=e.enviado_por, concluido_em=e.concluido_em, motivo=e.motivo, ultimo_evento=e.ultimo_evento,
        ultimo_evento_em=e.ultimo_evento_em, documento_anexado_id=e.documento_anexado_id,
        signatarios=[SignatarioDoEnvio(nome=s.get("nome", ""), email=s.get("email", ""), telefone=s.get("telefone"),
                                       papel=s.get("papel", ""), assinou_em=s.get("assinou_em"))
                     for s in e.signatarios],
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


def _encerrar(e: EnvelopeDoClicksign, situacao: str, quando: datetime, motivo: str) -> None:
    if e.situacao == "em_assinatura":
        e.situacao, e.concluido_em, e.motivo = situacao, quando, motivo[:400]


def _anexar(sessao: Session, e: EnvelopeDoClicksign, pdf: bytes) -> DocumentoAnexado:
    """O PDF assinado vira um documento anexado (origem "clicksign"), como se alguém o tivesse subido na seção
    Documento assinado: substitui o anterior do mesmo tipo, que fica no histórico. PDF repetido não entra de novo."""
    resumo = hashlib.sha256(pdf).hexdigest()
    repetido = sessao.scalar(sa.select(DocumentoAnexado).options(defer(DocumentoAnexado.conteudo_base64)).where(
        DocumentoAnexado.sha256 == resumo, DocumentoAnexado.substituido_em.is_(None)))
    if repetido is not None:
        return repetido
    tipo = "proposta" if e.contrato_id is None and e.oportunidade_id is not None else "contrato"
    grupo_id = None
    if e.contrato_id is not None:
        grupo_id = sessao.get(Contrato, e.contrato_id).grupo_id
    elif e.oportunidade_id is not None:
        grupo_id = sessao.get(Oportunidade, e.oportunidade_id).grupo_id
    if e.contrato_id or e.oportunidade_id:
        alvo = (DocumentoAnexado.contrato_id == e.contrato_id if tipo == "contrato"
                else DocumentoAnexado.oportunidade_id == e.oportunidade_id)
        for anterior in sessao.scalars(sa.select(DocumentoAnexado).options(defer(DocumentoAnexado.conteudo_base64))
                                       .where(alvo, DocumentoAnexado.tipo == tipo, DocumentoAnexado.substituido_em.is_(None))):
            anterior.substituido_em = agora()
    nome = e.nome_arquivo if e.nome_arquivo.lower().endswith(".pdf") else f"{e.nome_arquivo}.pdf"
    d = DocumentoAnexado(
        tipo=tipo, grupo_id=grupo_id, contrato_id=e.contrato_id if tipo == "contrato" else None,
        oportunidade_id=e.oportunidade_id if tipo == "proposta" else None, nome_arquivo=nome[:200], tamanho=len(pdf),
        sha256=resumo, conteudo_base64=base64.b64encode(pdf).decode(), origem="clicksign", enviado_em=agora(),
        enviado_por="Clicksign" + (" (enviado pelo CRM)" if e.origem == "crm" else " (feito fora do CRM)"),
        leitura_situacao="pendente",
    )
    sessao.add(d)
    sessao.flush()
    return d


def _pdf_assinado(e: EnvelopeDoClicksign, config: cs.ConfiguracaoDaClicksign | None, url_do_aviso: str | None,
                  http: httpx.Client | None) -> bytes | None:
    """O endereço do aviso, se confiável; senão, o que a API informar. Falhou, fica para a tela."""
    url = cs.endereco_confiavel(url_do_aviso)
    if url is None and config is not None and e.envelope_id:
        try:
            url = cs.consultar(config, e.envelope_id, e.documento_id, http=http).assinado_url
        except cs.FalhaNaClicksign as falha:
            _log.warning("Clicksign: consulta do PDF assinado falhou (%s)", falha)
    if url is None:
        return None
    try:
        return cs.baixar_assinado(url, http=http)
    except cs.FalhaNaClicksign as falha:
        _log.warning("Clicksign: PDF assinado não baixado (%s)", falha)
        return None


def _fechar(sessao: Session, e: EnvelopeDoClicksign, quando: datetime, pdf: bytes | None, agendar: Agendar) -> None:
    """Assinado por todos. Do CRM, ativa o contrato; de fora, só leva o PDF à conferência."""
    if e.situacao != "assinado":
        e.situacao, e.concluido_em = "assinado", quando
        e.signatarios = [{**s, "assinou_em": s.get("assinou_em") or quando.isoformat()} for s in e.signatarios]
        if e.origem == "crm" and e.contrato_id is not None:
            c = sessao.get(Contrato, e.contrato_id)
            if c.situacao is SituacaoContrato.AGUARDANDO_ASSINATURA:
                c.data_inicio, c.situacao = _brasilia(quando), SituacaoContrato.ATIVO
                clientes = [s["nome"] for s in e.signatarios if s.get("papel") == "Contratante"]
                if not c.signatario and clientes:
                    c.signatario = ", ".join(clientes)[:200]
                if not c.documento_assinado:
                    c.documento_assinado = "Clicksign (PDF na seção Documento assinado)"
    if pdf is not None and e.documento_anexado_id is None:
        d = _anexar(sessao, e, pdf)
        e.documento_anexado_id = d.id
        if d.leitura_situacao == "pendente":
            agendar(d.id)


def _conferir(sessao: Session, e: EnvelopeDoClicksign, config: cs.ConfiguracaoDaClicksign,
              http: httpx.Client | None, agendar: Agendar) -> None:
    """Uma consulta, a pedido da pessoa: fechado vira assinado (e traz o PDF); cancelado, cancelado."""
    if not e.envelope_id:
        raise HTTPException(409, "Este envelope foi feito fora do CRM e chegou sem o identificador da API: "
                                 "o CRM depende do aviso da Clicksign.")
    doc = cs.consultar(config, e.envelope_id, e.documento_id, http=http)
    if doc.situacao == "closed":
        pdf = None
        if e.documento_anexado_id is None and doc.assinado_url:
            try:
                pdf = cs.baixar_assinado(doc.assinado_url, http=http)
            except cs.FalhaNaClicksign as falha:
                _log.warning("Clicksign: PDF assinado não baixado (%s)", falha)
        _fechar(sessao, e, e.concluido_em or doc.modificado_em or agora(), pdf, agendar)
    elif doc.situacao == "canceled":
        _encerrar(e, "cancelado", doc.modificado_em or agora(), "cancelado na Clicksign")


# ── Rotas ────────────────────────────────────────────────────────────────────────────────────────────

def roteador_da_assinatura(obter_sessao: Callable[[], Iterator[Session]],
                           fabrica: Callable[[], sessionmaker[Session]] | None = None,
                           leitor: Leitor | None = None,
                           http_da_clicksign: FabricaDeHttp | None = None) -> APIRouter:
    r = APIRouter(tags=["contratos"])
    novo_http: FabricaDeHttp = http_da_clicksign or (lambda: None)
    ler: Leitor = leitor or leitor_real

    def _agendador(tarefas: BackgroundTasks) -> Agendar:
        def agendar(documento_id: int) -> None:
            if fabrica is not None:
                tarefas.add_task(ler_documento, fabrica(), ler, documento_id)
        return agendar

    def _contrato(sessao: Session, contrato_id: int) -> Contrato:
        c = sessao.get(Contrato, contrato_id)
        if c is None:
            raise HTTPException(404, "contrato não encontrado")
        return c

    def _envelopes(sessao: Session, contrato_id: int) -> list[EnvelopeDoClicksign]:
        return list(sessao.scalars(sa.select(EnvelopeDoClicksign).where(EnvelopeDoClicksign.contrato_id == contrato_id)
                                   .order_by(EnvelopeDoClicksign.id.desc())))

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
        envelopes = _envelopes(sessao, c.id)
        atual = envelopes[0] if envelopes else None
        problema = None
        if config is None:
            problema = "Assinatura eletrônica desligada: ligue e salve o access token em Configurações › Integrações › Clicksign."
        elif atual is not None and atual.situacao == "em_assinatura":
            problema = "Já há um envelope em assinatura. Para mandar outro documento, cancele este antes."
        elif c.situacao is not SituacaoContrato.AGUARDANDO_ASSINATURA:
            problema = f"O contrato está {c.situacao.value}: só se envia para assinatura o que aguarda assinatura."
        autenticacao = config.autenticacao if config else configuracao.valor("clicksign.autenticacao")
        return AbaDaAssinatura(
            ligada=config is not None, ambiente=config.ambiente if config else configuracao.valor("clicksign.ambiente"),
            autenticacao=autenticacao, pede_telefone=autenticacao != "email", problema=problema,
            sugeridos=_sugeridos(sessao, c), prazo_sugerido=hoje + timedelta(days=30),
            atual=_envio(atual) if atual else None, anteriores=[_envio(e) for e in envelopes[1:]],
        )

    def _em_andamento(sessao: Session, contrato_id: int) -> EnvelopeDoClicksign:
        envelopes = _envelopes(sessao, contrato_id)
        if not envelopes or envelopes[0].situacao != "em_assinatura":
            raise HTTPException(409, "não há envelope em assinatura neste contrato")
        if envelopes[0].origem != "crm":
            raise HTTPException(409, "este envelope foi feito fora do CRM: lembre ou cancele pela Clicksign")
        return envelopes[0]

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
        envelopes = _envelopes(sessao, c.id)
        if envelopes and envelopes[0].situacao == "em_assinatura":
            raise HTTPException(409, "Já há um envelope em assinatura. Cancele antes de mandar outro.")
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
        sessao.add(EnvelopeDoClicksign(
            origem="crm", contrato_id=c.id, ambiente=config.ambiente, envelope_id=envelope.envelope_id,
            documento_id=envelope.documento_id, nome_arquivo=corpo.nome_arquivo, situacao="em_assinatura",
            prazo=corpo.prazo, signatarios=signatarios, enviado_em=agora(), enviado_por=quem[:200],
        ))
        sessao.flush()
        return _aba(sessao, c, hoje)

    @r.post("/api/contratos/{contrato_id}/assinatura/conferir", response_model=AbaDaAssinatura)
    def conferir(contrato_id: int, tarefas: BackgroundTasks, hoje: date | None = None,
                 sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDaAssinatura:
        config = _config()
        c = _contrato(sessao, contrato_id)
        envelopes = _envelopes(sessao, c.id)
        if not envelopes:
            raise HTTPException(409, "este contrato ainda não foi enviado para assinatura")
        try:
            _conferir(sessao, envelopes[0], config, novo_http(), _agendador(tarefas))
        except cs.FalhaNaClicksign as falha:
            raise HTTPException(502, str(falha)) from falha
        sessao.flush()
        return _aba(sessao, c, hoje or date.today())

    @r.post("/api/contratos/{contrato_id}/assinatura/lembrete", response_model=AbaDaAssinatura)
    def lembrete(contrato_id: int, corpo: PedidoDeLembrete, hoje: date | None = None,
                 sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDaAssinatura:
        config = _config()
        c = _contrato(sessao, contrato_id)
        e = _em_andamento(sessao, c.id)
        s = next((s for s in e.signatarios if s.get("email") == corpo.email.strip().lower()), None)
        if s is None or not s.get("clicksign_id"):
            raise HTTPException(404, "signatário não encontrado neste envelope")
        if s.get("assinou_em"):
            raise HTTPException(409, "este signatário já assinou")
        try:
            cs.lembrar(config, e.envelope_id, s["clicksign_id"], http=novo_http())
        except cs.FalhaNaClicksign as falha:
            raise HTTPException(502, str(falha)) from falha
        e.ultimo_evento, e.ultimo_evento_em = f"lembrete para {s['nome']}"[:60], agora()
        sessao.flush()
        return _aba(sessao, c, hoje or date.today())

    @r.post("/api/contratos/{contrato_id}/assinatura/cancelar", response_model=AbaDaAssinatura)
    def cancelar(contrato_id: int, hoje: date | None = None,
                 sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDaAssinatura:
        config = _config()
        c = _contrato(sessao, contrato_id)
        e = _em_andamento(sessao, c.id)
        try:
            cs.cancelar(config, e.envelope_id, e.documento_id, http=novo_http())
        except cs.FalhaNaClicksign as falha:
            raise HTTPException(502, str(falha)) from falha
        _encerrar(e, "cancelado", agora(), f"cancelado no CRM por {quem_fez(None) or 'sem login'}")
        sessao.flush()
        return _aba(sessao, c, hoje or date.today())

    # ── Webhook ───────────────────────────────────────────────────────────────────────────────────────

    @r.post(CAMINHO_DO_WEBHOOK, tags=["clicksign"])
    async def aviso(request: Request, tarefas: BackgroundTasks,
                    sessao: Session = Depends(obter_sessao, scope="function")) -> Response:
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
            _aplicar_aviso(sessao, payload, request.headers.get("event"), novo_http, _agendador(tarefas))
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


def _de_fora(sessao: Session, payload: dict, chave: str, quando: datetime) -> EnvelopeDoClicksign | None:
    """Envelope feito direto na Clicksign: só com número do CRM no nome. Liga ao contrato ou à oportunidade pelo
    número, como a conferência faz; sem achar, fica para alguém vincular na conferência."""
    documento = payload.get("document") if isinstance(payload.get("document"), dict) else {}
    nome = _texto(documento, "filename") or (_texto(documento, "path") or "").rsplit("/", 1)[-1]
    achado = NUMERO_DO_CRM.search(nome.upper()) if nome else None
    if achado is None:
        return None
    vinculo = _sugerir(sessao, {"campos": {"numero": {"valor": nome}}})
    if vinculo.get("motivo") != "pelo número":
        vinculo = {}
    proposta = achado.group(1) == "PROP"  # proposta aceita fica na oportunidade, não no contrato
    signatarios = [{"nome": _texto(s, "name") or "", "email": (_texto(s, "email") or "").lower(), "telefone": None,
                    "papel": "", "clicksign_id": _texto(s, "key"), "assinou_em": None}
                   for s in (documento.get("signers") or []) if isinstance(s, dict)]
    e = EnvelopeDoClicksign(
        origem="fora", contrato_id=None if proposta else vinculo.get("contrato_id"),
        oportunidade_id=vinculo.get("oportunidade_id") if proposta else None,
        ambiente=configuracao.valor("clicksign.ambiente"), envelope_id=None, documento_id=chave,
        nome_arquivo=nome[:200], situacao="em_assinatura", signatarios=signatarios,
        enviado_em=cs.quando(_texto(documento, "uploaded_at")) or quando, enviado_por="direto na Clicksign",
    )
    sessao.add(e)
    sessao.flush()
    return e


def _aplicar_aviso(sessao: Session, payload: dict, cabecalho: str | None, novo_http: FabricaDeHttp,
                   agendar: Agendar) -> None:
    evento = _texto(payload, "event", "name") or (cabecalho or "").strip()
    chave = _texto(payload, "document", "key") or _texto(payload, "document", "id")
    if not evento or not chave:
        return
    quando = cs.quando(_texto(payload, "event", "occurred_at")) or agora()
    e = sessao.scalar(sa.select(EnvelopeDoClicksign).where(EnvelopeDoClicksign.documento_id == chave))
    if e is None:
        e = _de_fora(sessao, payload, chave, quando)
        if e is None:
            _log.info("Clicksign: aviso %s de documento sem número do CRM; ignorado", evento)
            return
    e.ultimo_evento, e.ultimo_evento_em = evento[:60], quando
    dados = (payload.get("event") or {}).get("data") if isinstance(payload.get("event"), dict) else None
    email = (_texto(dados, "signer", "email") or "").lower()
    nome = _texto(dados, "signer", "name") or _texto(dados, "user", "name") or ""
    if evento == "sign" and email:
        e.signatarios = [{**s, "assinou_em": s.get("assinou_em") or quando.isoformat()} if s.get("email") == email else s
                         for s in e.signatarios]
    elif evento == "refusal":
        _encerrar(e, "recusado", quando, f"recusado por {nome or email or 'um signatário'} na Clicksign")
    elif evento == "deadline":
        _encerrar(e, "expirado", quando, "o prazo para assinar venceu")
    elif evento == "cancel":
        _encerrar(e, "cancelado", quando, "cancelado na Clicksign")
    elif evento in FECHAMENTO and (e.situacao != "assinado" or e.documento_anexado_id is None):
        config = cs.ler_configuracao()
        pdf = None if e.documento_anexado_id else _pdf_assinado(
            e, config, _texto(payload, "document", "downloads", "signed_file_url"), novo_http())
        _fechar(sessao, e, e.concluido_em or quando, pdf, agendar)
    sessao.flush()
