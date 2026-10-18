"""PDF assinado no CRM, com a conferência do que a IA leu (amostra aprovada por Eduardo em 18/10/2026).

- `POST /api/documentos?tipo=&contrato_id=|oportunidade_id=&nome_arquivo=`: o corpo é o PDF. Sem contrato nem
  oportunidade, é o lote de documentos antigos (Contratos › Incluir documentos antigos). A leitura pela IA começa logo
  depois da resposta, fora do pedido; a tela acompanha pela situação da leitura.
- `GET /api/documentos?contrato_id=|oportunidade_id=|origem=lote`: os documentos, sem o arquivo.
- `GET /api/documentos/{id}`: o documento com a conferência: por campo, o que está no CRM, o que foi lido, a página,
  o trecho, se é igual, diferente ou novo, e se pode ser gravado (pelas mesmas regras da edição do contrato).
- `PATCH /api/documentos/{id}`: o tipo e o vínculo (grupo, contrato, oportunidade), ou criar o contrato anterior ao
  CRM a partir do documento.
- `POST /api/documentos/{id}/ler`: ler de novo. `POST /api/documentos/{id}/conferir`: grava os campos marcados.
- `GET /api/documentos/{id}/pdf`: o arquivo (permissão própria: contrato assinado tem dado sensível).

Nada é gravado no contrato sem alguém marcar. Número de proposta antiga fica no documento e não entra na numeração do
CRM. Aditivo não vira evento sozinho: os dados lidos aparecem para registrar o evento, que segue a alçada.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import unicodedata
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, defer, sessionmaker

from crm.api.acesso import quem_fez
from crm.db.base import agora
from crm.db.modelos import (
    Contrato, DocumentoAnexado, DocumentoDeContrato, Empresa, GrupoEconomico, Oportunidade, Proposta,
)
from crm.documento import leitura as regra
from crm.domain.edicao_de_contrato import problema_na_edicao
from crm.domain.listas import SituacaoContrato

__all__ = ["NUMERO_DO_CRM", "Leitor", "leitor_real", "roteador_de_documentos", "ler_documento"]

_log = logging.getLogger(__name__)

LIMITE = 20 * 1024 * 1024
NUMERO_DO_CRM = re.compile(r"(CONT|PROP)\D{0,12}?(?:RJ1\s*)?(\d{1,5})[.\-/](\d{4})")
"""CONT CCE RJ1 102.2026 ou PROP CCE RJ 154.2026. O "RJ1" do contrato tem dígito: sem o grupo opcional, não casava."""
LEITURA_PARADA = timedelta(minutes=10)
"""Lendo há mais que isto: a leitura se perdeu (o CRM reiniciou no meio) e a tela oferece ler de novo."""

Leitor = Callable[[bytes, str], dict]
"""PDF e nome → a leitura normalizada (`crm.documento.leitura.normalizar`), com `uso` opcional. O teste troca por um
falso, sem rede."""


def leitor_real(pdf: bytes, nome: str) -> dict:
    """Só pela Anthropic, com a chave e o modelo de Configurações › Integrações."""
    from crm.agente.config import ler_configuracao
    from crm.agente.ia import ANTHROPIC, cliente_de
    from crm.agente.sdr import Uso

    config = ler_configuracao()
    cliente = cliente_de(ANTHROPIC, config)
    uso = Uso(modelo=config.modelo)
    lido = regra.ler_pdf(cliente, config.modelo, pdf=pdf, nome=nome, uso=uso)
    custo = uso.custo_usd()
    lido["uso"] = {"modelo": uso.modelo, "tokens_entrada": uso.tokens_entrada, "tokens_saida": uso.tokens_saida,
                   "custo_usd": str(custo) if custo is not None else None}
    return lido


# ── Os campos e para onde vão ─────────────────────────────────────────────────────────────────────

TipoDoValor = Literal["data", "dinheiro", "inteiro", "texto"]

ROTULOS: dict[str, tuple[str, TipoDoValor]] = {
    "numero": ("Número no documento", "texto"),
    "data_assinatura": ("Data da assinatura", "data"),
    "cnpj": ("CNPJ do contrato", "texto"),
    "preco_mensal": ("Preço mensal", "dinheiro"),
    "base_do_valor": ("Base do valor", "texto"),
    "parcelas_no_ano": ("Parcelas no ano", "inteiro"),
    "escopo": ("Escopo", "texto"),
    "data_fim": ("Fim da vigência", "data"),
    "vigencia": ("Vigência", "texto"),
    "renovacao": ("Renovação", "texto"),
    "multa_rescisoria": ("Multa rescisória", "texto"),
    "aviso_previo_dias": ("Aviso prévio (dias)", "inteiro"),
    "signatario": ("Signatário", "texto"),
    "plano": ("Plano escolhido", "texto"),
}

DO_CONTRATO: dict[str, str] = {
    "data_assinatura": "data_inicio", "preco_mensal": "preco_mensal", "base_do_valor": "base_do_valor",
    "parcelas_no_ano": "parcelas_no_ano", "escopo": "escopo", "data_fim": "data_fim", "renovacao": "renovacao",
    "multa_rescisoria": "multa_rescisoria", "aviso_previo_dias": "aviso_previo_dias", "signatario": "signatario",
}
"""Campo lido → coluna do contrato, para o PDF do tipo contrato."""

DO_DOCUMENTO = ("numero", "data_assinatura")
"""Ficam sempre no próprio documento (número como escrito e data), em qualquer tipo."""

ORDEM = ("numero", "data_assinatura", "cnpj", "preco_mensal", "base_do_valor", "parcelas_no_ano", "escopo", "data_fim",
         "vigencia", "renovacao", "multa_rescisoria", "aviso_previo_dias", "signatario", "plano")

_TAMANHOS = {"escopo": 200, "renovacao": 200, "multa_rescisoria": 200, "signatario": 200}


def _converter(campo: str, texto: str) -> Any:
    """O texto (lido ou corrigido na tela) no tipo da coluna. `ValueError` com a frase, se não serve."""
    texto = (texto or "").strip()
    if not texto:
        return None
    tipo = ROTULOS[campo][1]
    if tipo == "data":
        try:
            return date.fromisoformat(texto)
        except ValueError:
            raise ValueError(f"{ROTULOS[campo][0]}: data no formato AAAA-MM-DD") from None
    if tipo == "dinheiro":
        try:
            valor = Decimal(texto)
        except InvalidOperation:
            raise ValueError(f"{ROTULOS[campo][0]}: só o número, como 7000.00") from None
        if valor <= 0:
            raise ValueError(f"{ROTULOS[campo][0]}: o valor precisa ser maior que zero")
        return valor.quantize(Decimal("0.01"))
    if tipo == "inteiro":
        if not texto.isdigit():
            raise ValueError(f"{ROTULOS[campo][0]}: só o número")
        n = int(texto)
        if campo == "parcelas_no_ano" and n not in (12, 13):
            raise ValueError("Parcelas no ano: 12 ou 13")
        return n
    if campo == "base_do_valor":
        if texto not in ("bruto", "liquido"):
            raise ValueError("Base do valor: bruto ou liquido")
        return texto
    if campo == "cnpj":
        d = re.sub(r"\D", "", texto)
        if len(d) != 14:
            raise ValueError("CNPJ: os 14 dígitos")
        return d
    return texto[:_TAMANHOS.get(campo, 200)]


def _texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return f"{valor:.2f}"
    return str(valor)


def _iguais(a: Any, b: Any) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return unicodedata.normalize("NFKC", a).casefold().split() == unicodedata.normalize("NFKC", b).casefold().split()
    return a == b


# ── Esquemas ──────────────────────────────────────────────────────────────────────────────────────

class Sugestao(BaseModel):
    grupo_id: int | None = None
    grupo_nome: str | None = None
    empresa_id: int | None = None
    contrato_id: int | None = None
    oportunidade_id: int | None = None
    motivo: str | None = None
    """De onde veio: "pelo número", "pelo CNPJ" ou por que não achou."""


class DocumentoResumo(BaseModel):
    id: int
    tipo: str
    nome_arquivo: str
    tamanho: int
    origem: str
    enviado_em: datetime
    enviado_por: str
    substituido_em: datetime | None
    leitura_situacao: str
    """"pendente", "lendo", "lida", "falhou", "conferida"; "parada" quando a leitura se perdeu."""
    leitura_erro: str | None
    tipo_lido: str | None
    grupo_id: int | None
    grupo_nome: str | None
    contrato_id: int | None
    oportunidade_id: int | None
    numero_no_documento: str | None
    data_do_documento: date | None
    conferido_em: datetime | None
    conferido_por: str | None
    sugestao: Sugestao | None
    cnpjs_lidos: list[str]
    razao_social_lida: str | None
    custo_usd: str | None


class LinhaDaConferencia(BaseModel):
    campo: str
    rotulo: str
    tipo_do_valor: TipoDoValor
    no_crm: str
    """Vazio quando o campo não vai para o CRM (só fica no documento)."""
    lido: str
    pagina: int
    trecho: str
    situacao: Literal["igual", "diferente", "novo", "nao_achou", "informativo"]
    destino: Literal["contrato", "oportunidade", "documento", "nenhum"]
    gravavel: bool
    motivo: str | None
    """Por que não grava (contrato assinado, encerrado, só fica no documento…)."""
    marcar: bool
    """A sugestão de marcação: novo e gravável. Diferente nunca vem marcado."""


class DocumentoDetalhe(DocumentoResumo):
    conferencia: list[LinhaDaConferencia]
    aviso: str | None
    """O que falta para conferir (vincular, ler de novo)."""


class Vinculo(BaseModel):
    tipo: Literal["contrato", "proposta", "aditivo"] | None = None
    grupo_id: int | None = None
    contrato_id: int | None = None
    oportunidade_id: int | None = None
    criar_contrato: bool = False
    """Cria o contrato anterior ao CRM no grupo, a partir deste PDF (CNPJ fora de contrato existente)."""
    desvincular: bool = False


class Conferencia(BaseModel):
    campos: list[str] = Field(default_factory=list)
    valores: dict[str, str] = Field(default_factory=dict)
    """O valor corrigido na tela; sem ele, vale o lido."""
    conferido_por: str | None = Field(default=None, max_length=200)
    """Só sem login."""


# ── Regras ────────────────────────────────────────────────────────────────────────────────────────

def _situacao_da_leitura(d: DocumentoAnexado, agora_: datetime) -> str:
    if d.leitura_situacao == "lendo" and d.leitura_iniciada_em is not None:
        iniciada = d.leitura_iniciada_em if d.leitura_iniciada_em.tzinfo else d.leitura_iniciada_em.replace(tzinfo=agora_.tzinfo)
        if agora_ - iniciada > LEITURA_PARADA:
            return "parada"
    return d.leitura_situacao


def _sugerir(sessao: Session, lido: dict) -> dict:
    """Pelo número do CRM no documento (CONT CCE RJ1 102.2026, PROP CCE RJ 154.2026) e, sem ele, pelo CNPJ."""
    numero = ((lido.get("campos") or {}).get("numero") or {}).get("valor") or ""
    achado = NUMERO_DO_CRM.search(numero.upper())
    if achado:
        n, ano = int(achado.group(2)), int(achado.group(3))
        if achado.group(1) == "CONT":
            gerado = sessao.scalar(sa.select(DocumentoDeContrato).where(
                DocumentoDeContrato.numero == n, DocumentoDeContrato.ano == ano))
            if gerado is not None:
                c = sessao.get(Contrato, gerado.contrato_id)
                return {"grupo_id": c.grupo_id, "contrato_id": c.id, "empresa_id": c.empresa_id, "motivo": "pelo número"}
        else:
            p = sessao.scalar(sa.select(Proposta).where(Proposta.numero == n, Proposta.ano == ano))
            if p is not None:
                o = sessao.get(Oportunidade, p.oportunidade_id)
                c = sessao.scalar(sa.select(Contrato).where(Contrato.oportunidade_id == o.id))
                return {"grupo_id": o.grupo_id, "oportunidade_id": o.id, "contrato_id": c.id if c else None,
                        "motivo": "pelo número"}
    cnpjs = lido.get("cnpjs") or []
    if not cnpjs:
        return {"motivo": "o documento não traz CNPJ do cliente"}
    empresas = sessao.scalars(sa.select(Empresa).where(Empresa.cnpj.in_(cnpjs))).all()
    grupos = {e.grupo_id for e in empresas}
    if not grupos:
        return {"motivo": "CNPJ fora do cadastro"}
    if len(grupos) > 1:
        return {"motivo": "CNPJs de grupos diferentes"}
    grupo_id = grupos.pop()
    empresa = empresas[0] if len(empresas) == 1 else None
    contratos = sessao.scalars(sa.select(Contrato).where(
        Contrato.grupo_id == grupo_id, Contrato.situacao != SituacaoContrato.ENCERRADO)).all()
    if empresa is not None and len(contratos) > 1:
        do_cnpj = [c for c in contratos if c.empresa_id == empresa.id]
        contratos = do_cnpj or contratos
    return {"grupo_id": grupo_id, "empresa_id": empresa.id if empresa else None,
            "contrato_id": contratos[0].id if len(contratos) == 1 else None, "motivo": "pelo CNPJ"}


def ler_documento(fabrica: sessionmaker[Session], leitor: Leitor, documento_id: int) -> None:
    """Lê o PDF fora do pedido. Nunca derruba o CRM: a falha fica no documento, com a frase."""
    from crm.agente.sdr import AgenteFalhou

    with fabrica() as sessao:
        d = sessao.get(DocumentoAnexado, documento_id)
        if d is None:
            return
        d.leitura_situacao, d.leitura_iniciada_em, d.leitura_erro = "lendo", agora(), None
        pdf, nome = base64.b64decode(d.conteudo_base64), d.nome_arquivo
        sessao.commit()
    erro, lido = None, None
    try:
        lido = leitor(pdf, nome)
    except AgenteFalhou as falha:
        erro = str(falha)
    except Exception as falha:  # noqa: BLE001 — o motivo vai para a tela e o log, nunca o PDF
        _log.exception("leitura do documento %s falhou", documento_id)
        erro = f"Falha inesperada na leitura ({type(falha).__name__}). Tente ler de novo."
    with fabrica() as sessao:
        d = sessao.get(DocumentoAnexado, documento_id)
        if d is None:
            return
        if erro is not None:
            d.leitura_situacao, d.leitura_erro = "falhou", erro[:400]
        else:
            lido["sugestao"] = _sugerir(sessao, lido)
            d.leitura, d.leitura_situacao = lido, "lida"
            if d.origem == "lote" and d.contrato_id is None and d.oportunidade_id is None and lido.get("tipo") in regra.TIPOS:
                d.tipo = lido["tipo"]
        sessao.commit()


def _destino(d: DocumentoAnexado, campo: str) -> str:
    if campo == "numero":
        return "documento"
    if d.tipo == "contrato" and d.contrato_id is not None and (campo in DO_CONTRATO or campo == "cnpj"):
        return "contrato"
    if d.tipo == "proposta" and d.oportunidade_id is not None and campo == "data_assinatura":
        return "oportunidade"
    if campo == "data_assinatura":
        return "documento"
    return "nenhum"


def _no_crm(sessao: Session, d: DocumentoAnexado, campo: str, destino: str) -> Any:
    if destino == "contrato":
        c = sessao.get(Contrato, d.contrato_id)
        if campo == "cnpj":
            return c.empresa.cnpj if c.empresa is not None else None
        return getattr(c, DO_CONTRATO[campo])
    if destino == "oportunidade":
        return sessao.get(Oportunidade, d.oportunidade_id).data_aceite
    if destino == "documento":
        return d.numero_no_documento if campo == "numero" else d.data_do_documento
    return None


def _empresa_do_grupo(sessao: Session, grupo_id: int, cnpj: str) -> Empresa | None:
    return sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == cnpj, Empresa.grupo_id == grupo_id))


def _problema(sessao: Session, d: DocumentoAnexado, campo: str, destino: str, valor: Any) -> str | None:
    if destino == "nenhum":
        if d.tipo == "aditivo":
            return "fica no documento; registre o aditivo na aba Eventos do contrato"
        if d.contrato_id is None and d.oportunidade_id is None:
            return "vincule o documento primeiro"
        return "fica só no documento"
    if destino == "contrato":
        c = sessao.get(Contrato, d.contrato_id)
        if campo == "cnpj":
            if valor is not None and _empresa_do_grupo(sessao, c.grupo_id, valor) is None:
                return "este CNPJ não está no grupo do contrato: cadastre a empresa no grupo"
            return "contrato encerrado não se mexe mais" if c.situacao is SituacaoContrato.ENCERRADO else None
        return problema_na_edicao(c, {DO_CONTRATO[campo]: valor})
    return None


def _linhas(sessao: Session, d: DocumentoAnexado) -> list[LinhaDaConferencia]:
    campos = ((d.leitura or {}).get("campos") or {})
    cnpjs = (d.leitura or {}).get("cnpjs") or []
    linhas = []
    for campo in ORDEM:
        lido_bruto = campos.get(campo) or {}
        lido_texto = cnpjs[0] if campo == "cnpj" and cnpjs else (lido_bruto.get("valor") or "")
        destino = _destino(d, campo)
        try:
            lido = _converter(campo, lido_texto)
        except ValueError:
            lido = None
        atual = _no_crm(sessao, d, campo, destino)
        problema = _problema(sessao, d, campo, destino, lido) if lido is not None else None
        if destino == "nenhum":
            situacao = "informativo" if lido is not None else "nao_achou"
        elif lido is None:
            situacao = "nao_achou"
        elif atual is None or atual == "":
            situacao = "novo"
        elif _iguais(atual, lido):
            situacao = "igual"
        else:
            situacao = "diferente"
        gravavel = destino != "nenhum" and lido is not None and problema is None and situacao != "igual"
        linhas.append(LinhaDaConferencia(
            campo=campo, rotulo=ROTULOS[campo][0], tipo_do_valor=ROTULOS[campo][1], no_crm=_texto(atual),
            lido=_texto(lido), pagina=int(lido_bruto.get("pagina") or 0) if campo != "cnpj" else 0,
            trecho=str(lido_bruto.get("trecho") or ""), situacao=situacao, destino=destino,
            gravavel=gravavel, motivo=problema, marcar=gravavel and situacao == "novo",
        ))
    return linhas


def _resumo(sessao: Session, d: DocumentoAnexado, agora_: datetime) -> DocumentoResumo:
    lido = d.leitura or {}
    sugestao = lido.get("sugestao")
    if sugestao and sugestao.get("grupo_id"):
        g = sessao.get(GrupoEconomico, sugestao["grupo_id"])
        sugestao = {**sugestao, "grupo_nome": g.nome if g else None}
    grupo = sessao.get(GrupoEconomico, d.grupo_id) if d.grupo_id else None
    return DocumentoResumo(
        id=d.id, tipo=d.tipo, nome_arquivo=d.nome_arquivo, tamanho=d.tamanho, origem=d.origem, enviado_em=d.enviado_em,
        enviado_por=d.enviado_por, substituido_em=d.substituido_em, leitura_situacao=_situacao_da_leitura(d, agora_),
        leitura_erro=d.leitura_erro, tipo_lido=lido.get("tipo"), grupo_id=d.grupo_id,
        grupo_nome=grupo.nome if grupo else None, contrato_id=d.contrato_id, oportunidade_id=d.oportunidade_id,
        numero_no_documento=d.numero_no_documento, data_do_documento=d.data_do_documento, conferido_em=d.conferido_em,
        conferido_por=d.conferido_por, sugestao=Sugestao(**sugestao) if sugestao else None,
        cnpjs_lidos=list(lido.get("cnpjs") or []), razao_social_lida=lido.get("razao_social") or None,
        custo_usd=(lido.get("uso") or {}).get("custo_usd"),
    )


def _aviso(d: DocumentoAnexado, situacao: str) -> str | None:
    if situacao in ("pendente", "lendo"):
        return "A IA está lendo o PDF. Pode fechar a tela: a leitura continua."
    if situacao == "parada":
        return "A leitura se perdeu no meio (o CRM reiniciou). Leia de novo."
    if situacao == "falhou":
        return f"A leitura falhou: {d.leitura_erro}. Leia de novo ou preencha os campos à mão."
    if d.contrato_id is None and d.oportunidade_id is None:
        return "Vincule o documento a um contrato ou oportunidade para gravar os campos."
    return None


def _disposicao(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return f'attachment; filename="{sem_acento.replace(chr(34), "")}"'


# ── Rotas ─────────────────────────────────────────────────────────────────────────────────────────

def roteador_de_documentos(
    obter_sessao: Callable[[], Iterator[Session]],
    fabrica: Callable[[], sessionmaker[Session]],
    leitor: Leitor | None = None,
) -> APIRouter:
    r = APIRouter(prefix="/api/documentos", tags=["documentos"])
    ler: Leitor = leitor or leitor_real

    def _doc(sessao: Session, documento_id: int) -> DocumentoAnexado:
        d = sessao.get(DocumentoAnexado, documento_id)
        if d is None:
            raise HTTPException(404, "documento não encontrado")
        return d

    def _detalhe(sessao: Session, d: DocumentoAnexado) -> DocumentoDetalhe:
        momento = agora()
        resumo = _resumo(sessao, d, momento)
        pronto = resumo.leitura_situacao in ("lida", "conferida") or (resumo.leitura_situacao == "falhou")
        return DocumentoDetalhe(**resumo.model_dump(), conferencia=_linhas(sessao, d) if pronto else [],
                                aviso=_aviso(d, resumo.leitura_situacao))

    @r.post("", response_model=DocumentoDetalhe, status_code=201)
    async def anexar(
        request: Request, tarefas: BackgroundTasks,
        nome_arquivo: str = Query(min_length=1, max_length=200),
        tipo: Literal["contrato", "proposta", "aditivo"] | None = None,
        contrato_id: int | None = None, oportunidade_id: int | None = None,
        enviado_por: str | None = Query(default=None, max_length=200),
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> DocumentoDetalhe:
        if not nome_arquivo.lower().endswith(".pdf"):
            raise HTTPException(422, "só PDF")
        dados = await request.body()
        if not dados:
            raise HTTPException(400, "nenhum arquivo enviado")
        if len(dados) > LIMITE:
            raise HTTPException(413, f"arquivo grande demais (o limite é {LIMITE // (1024 * 1024)} MB)")
        if not dados.startswith(b"%PDF"):
            raise HTTPException(422, "o arquivo não é um PDF")
        if contrato_id is not None and oportunidade_id is not None:
            raise HTTPException(422, "anexe no contrato ou na oportunidade, não nos dois")
        grupo_id = None
        if contrato_id is not None:
            c = sessao.get(Contrato, contrato_id)
            if c is None:
                raise HTTPException(404, "contrato não encontrado")
            grupo_id, tipo = c.grupo_id, tipo or "contrato"
        if oportunidade_id is not None:
            o = sessao.get(Oportunidade, oportunidade_id)
            if o is None:
                raise HTTPException(404, "oportunidade não encontrada")
            grupo_id, tipo = o.grupo_id, tipo or "proposta"
        resumo = hashlib.sha256(dados).hexdigest()
        repetido = sessao.scalar(sa.select(DocumentoAnexado).options(defer(DocumentoAnexado.conteudo_base64)).where(
            DocumentoAnexado.sha256 == resumo, DocumentoAnexado.substituido_em.is_(None)))
        if repetido is not None:
            raise HTTPException(409, f"este PDF já está no CRM ({repetido.nome_arquivo}, anexado por {repetido.enviado_por})")
        if tipo in ("contrato", "proposta") and (contrato_id or oportunidade_id):
            alvo = DocumentoAnexado.contrato_id == contrato_id if contrato_id else DocumentoAnexado.oportunidade_id == oportunidade_id
            for anterior in sessao.scalars(sa.select(DocumentoAnexado).options(defer(DocumentoAnexado.conteudo_base64))
                                           .where(alvo, DocumentoAnexado.tipo == tipo, DocumentoAnexado.substituido_em.is_(None))):
                anterior.substituido_em = agora()  # o anterior fica no histórico
        quem = (quem_fez((enviado_por or "").strip()) or "").strip() or "sem login"
        d = DocumentoAnexado(
            tipo=tipo or "contrato", grupo_id=grupo_id, contrato_id=contrato_id, oportunidade_id=oportunidade_id,
            nome_arquivo=nome_arquivo, tamanho=len(dados), sha256=resumo, conteudo_base64=base64.b64encode(dados).decode(),
            origem="tela" if (contrato_id or oportunidade_id) else "lote", enviado_em=agora(), enviado_por=quem[:200],
            leitura_situacao="pendente",
        )
        sessao.add(d)
        sessao.flush()
        tarefas.add_task(ler_documento, fabrica(), ler, d.id)
        return _detalhe(sessao, d)

    @r.get("", response_model=list[DocumentoResumo])
    def listar(
        contrato_id: int | None = None, oportunidade_id: int | None = None, grupo_id: int | None = None,
        origem: Literal["tela", "lote"] | None = None, historico: bool = False,
        limite: int = Query(default=200, le=1000),
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> list[DocumentoResumo]:
        consulta = sa.select(DocumentoAnexado).options(defer(DocumentoAnexado.conteudo_base64))
        if contrato_id is not None:
            consulta = consulta.where(DocumentoAnexado.contrato_id == contrato_id)
        if oportunidade_id is not None:
            consulta = consulta.where(DocumentoAnexado.oportunidade_id == oportunidade_id)
        if grupo_id is not None:
            consulta = consulta.where(DocumentoAnexado.grupo_id == grupo_id)
        if origem is not None:
            consulta = consulta.where(DocumentoAnexado.origem == origem)
        if not historico:
            consulta = consulta.where(DocumentoAnexado.substituido_em.is_(None))
        momento = agora()
        return [_resumo(sessao, d, momento) for d in sessao.scalars(
            consulta.order_by(DocumentoAnexado.enviado_em.desc(), DocumentoAnexado.id.desc()).limit(limite))]

    @r.get("/{documento_id}", response_model=DocumentoDetalhe)
    def ver(documento_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> DocumentoDetalhe:
        return _detalhe(sessao, _doc(sessao, documento_id))

    @r.post("/{documento_id}/ler", response_model=DocumentoDetalhe)
    def ler_de_novo(documento_id: int, tarefas: BackgroundTasks,
                    sessao: Session = Depends(obter_sessao, scope="function")) -> DocumentoDetalhe:
        d = _doc(sessao, documento_id)
        if _situacao_da_leitura(d, agora()) == "lendo":
            raise HTTPException(409, "a IA ainda está lendo este PDF")
        d.leitura_situacao, d.leitura_erro = "pendente", None
        sessao.flush()
        tarefas.add_task(ler_documento, fabrica(), ler, d.id)
        return _detalhe(sessao, d)

    @r.patch("/{documento_id}", response_model=DocumentoDetalhe)
    def vincular(documento_id: int, corpo: Vinculo,
                 sessao: Session = Depends(obter_sessao, scope="function")) -> DocumentoDetalhe:
        d = _doc(sessao, documento_id)
        if d.conferido_em is not None and (corpo.desvincular or corpo.contrato_id or corpo.oportunidade_id or corpo.criar_contrato):
            raise HTTPException(409, "documento já conferido: o vínculo não muda mais")
        if corpo.tipo is not None:
            d.tipo = corpo.tipo
        if corpo.desvincular:
            d.grupo_id = d.contrato_id = d.oportunidade_id = None
            sessao.flush()
            return _detalhe(sessao, d)
        if corpo.contrato_id is not None:
            c = sessao.get(Contrato, corpo.contrato_id)
            if c is None:
                raise HTTPException(404, "contrato não encontrado")
            d.contrato_id, d.grupo_id = c.id, c.grupo_id
            if d.tipo == "proposta" and c.oportunidade_id and corpo.oportunidade_id is None:
                d.oportunidade_id = c.oportunidade_id
        if corpo.oportunidade_id is not None:
            o = sessao.get(Oportunidade, corpo.oportunidade_id)
            if o is None:
                raise HTTPException(404, "oportunidade não encontrada")
            if d.grupo_id is not None and d.contrato_id is not None and o.grupo_id != d.grupo_id:
                raise HTTPException(422, "a oportunidade é de outro grupo")
            d.oportunidade_id, d.grupo_id = o.id, o.grupo_id
        if corpo.criar_contrato:
            grupo_id = corpo.grupo_id or d.grupo_id
            if grupo_id is None or sessao.get(GrupoEconomico, grupo_id) is None:
                raise HTTPException(422, "escolha o grupo do contrato")
            if d.tipo != "contrato":
                raise HTTPException(422, "só o PDF de contrato cria contrato")
            escopo = (((d.leitura or {}).get("campos") or {}).get("escopo") or {}).get("valor") or None
            c = Contrato(grupo_id=grupo_id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO,
                         escopo=escopo[:200] if escopo else None,
                         observacao="Criado a partir do PDF assinado incluído em Documentos antigos.")
            sessao.add(c)
            sessao.flush()
            d.contrato_id, d.grupo_id = c.id, grupo_id
        elif corpo.grupo_id is not None and corpo.contrato_id is None and corpo.oportunidade_id is None:
            if sessao.get(GrupoEconomico, corpo.grupo_id) is None:
                raise HTTPException(404, "grupo não encontrado")
            d.grupo_id = corpo.grupo_id
        sessao.flush()
        return _detalhe(sessao, d)

    @r.post("/{documento_id}/conferir", response_model=DocumentoDetalhe)
    def conferir(documento_id: int, corpo: Conferencia,
                 sessao: Session = Depends(obter_sessao, scope="function")) -> DocumentoDetalhe:
        d = _doc(sessao, documento_id)
        if d.contrato_id is None and d.oportunidade_id is None:
            raise HTTPException(422, "vincule o documento a um contrato ou oportunidade antes de conferir")
        desconhecidos = [c for c in corpo.campos if c not in ROTULOS]
        if desconhecidos:
            raise HTTPException(422, f"campo desconhecido: {', '.join(desconhecidos)}")
        lidos = (d.leitura or {}).get("campos") or {}
        cnpjs = (d.leitura or {}).get("cnpjs") or []

        def valor_de(campo: str) -> Any:
            texto = corpo.valores.get(campo)
            if texto is None:
                texto = cnpjs[0] if campo == "cnpj" and cnpjs else (lidos.get(campo) or {}).get("valor") or ""
            try:
                return _converter(campo, texto)
            except ValueError as falha:
                raise HTTPException(422, str(falha)) from falha

        mudancas_contrato: dict[str, Any] = {}
        empresa: Empresa | None = None
        gravados = []
        for campo in corpo.campos:
            destino = _destino(d, campo)
            valor = valor_de(campo)
            if valor is None:
                raise HTTPException(422, f"{ROTULOS[campo][0]}: sem valor para gravar")
            problema = _problema(sessao, d, campo, destino, valor)
            if problema:
                raise HTTPException(422, f"{ROTULOS[campo][0]}: {problema}")
            if destino == "contrato" and campo == "cnpj":
                empresa = _empresa_do_grupo(sessao, sessao.get(Contrato, d.contrato_id).grupo_id, valor)
            elif destino == "contrato":
                mudancas_contrato[DO_CONTRATO[campo]] = valor
            elif destino == "oportunidade":
                sessao.get(Oportunidade, d.oportunidade_id).data_aceite = valor
            gravados.append(campo)
        if mudancas_contrato or empresa is not None:
            c = sessao.get(Contrato, d.contrato_id)
            problema = problema_na_edicao(c, mudancas_contrato)
            if problema:
                raise HTTPException(422, problema)
            for coluna, valor in mudancas_contrato.items():
                setattr(c, coluna, valor)
            if empresa is not None:
                c.empresa_id = empresa.id
        # O número como escrito e a data ficam sempre no documento, conferidos ou não pela marcação.
        for campo in DO_DOCUMENTO:
            if campo in corpo.campos or campo in corpo.valores:
                valor = valor_de(campo)
                if campo == "numero":
                    d.numero_no_documento = valor[:60] if valor else None
                else:
                    d.data_do_documento = valor
        quem = (quem_fez((corpo.conferido_por or "").strip()) or "").strip() or "sem login"
        d.conferido_em, d.conferido_por, d.campos_gravados = agora(), quem[:200], gravados
        d.leitura_situacao = "conferida"
        sessao.flush()
        return _detalhe(sessao, d)

    @r.get("/{documento_id}/pdf")
    def baixar(documento_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> Response:
        d = _doc(sessao, documento_id)
        return Response(base64.b64decode(d.conteudo_base64), media_type="application/pdf",
                        headers={"Content-Disposition": _disposicao(d.nome_arquivo), "Cache-Control": "no-store"})

    return r
