"""Gerar o contrato recorrente em Word (amostra aprovada por Eduardo em 14/10/2026). Matriz em `crm.contrato.matriz`.

- `GET /api/contratos/{id}/documento`: os campos da matriz com o valor sugerido e de onde veio (empresa, proposta,
  contrato, parâmetros, configurações) e o documento já gerado, se houver.
- `POST /api/contratos/{id}/documento`: grava os valores confirmados e reserva o número CONT CCE RJ1. Enquanto o
  contrato aguarda assinatura, gerar de novo regrava o mesmo documento, com o mesmo número. Número usado não volta.
- `GET /api/documentos-de-contrato/{id}/docx`: o Word, sempre com a matriz e os valores gravados.
- Configurações › Serviços e contratos: `GET`/`POST /api/documentos-de-contrato/matriz`,
  `GET /api/documentos-de-contrato/matriz/{id}/docx` e `GET`/`PUT /api/documentos-de-contrato/configuracao`.

Só o modelo "Recorrente padrão", por enquanto; o não recorrente (minuta v1.1) entra depois da revisão do advogado.
"""

from __future__ import annotations

import base64
import re
import unicodedata
from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, defer

from crm.api.acesso import quem_fez
from crm.api.classificacao import parametros_vigentes
from crm.contrato import matriz as regra
from crm.db.base import agora
from crm.db.modelos import (
    ConfiguracaoDeContrato, Contrato, DocumentoDeContrato, Empresa, MatrizDeContrato, Proposta,
)
from crm.domain.contrato_do_servico import ModeloDeContrato
from crm.domain.listas import SituacaoContrato
from crm.proposta import conta

__all__ = ["roteador_do_documento_de_contrato", "valores_sugeridos", "data_por_extenso"]

MODELO = ModeloDeContrato.RECORRENTE_PADRAO
LIMITE_DA_MATRIZ = 50 * 1024 * 1024
MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro")
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def data_por_extenso(d: date) -> str:
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _cnpj(cnpj: str | None) -> str:
    d = re.sub(r"\D", "", cnpj or "")
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else (cnpj or "")


def _endereco(e: Empresa) -> str:
    if not e.logradouro:
        return ""
    partes = [e.logradouro + (f", nº {e.numero}" if e.numero else "")]
    partes += [p for p in (e.complemento, e.bairro) if p]
    cidade = " – ".join(filter(None, [e.municipio, e.uf])) if e.municipio else ""
    texto = " – ".join(partes + ([cidade.replace(" – ", "/")] if cidade else []))
    cep = re.sub(r"\D", "", e.cep or "")
    return texto + (f", CEP {cep[:2]}.{cep[2:5]}-{cep[5:]}" if len(cep) == 8 else "")


def _reais(v: Decimal | None) -> str:
    return f"R$ {conta.reais(v)}" if v is not None else ""


def _empresa(sessao: Session, c: Contrato) -> Empresa | None:
    if c.empresa is not None:
        return c.empresa
    if c.oportunidade is not None and c.oportunidade.empresa_id:
        return sessao.get(Empresa, c.oportunidade.empresa_id)
    empresas = sessao.scalars(sa.select(Empresa).where(Empresa.grupo_id == c.grupo_id).limit(2)).all()
    return empresas[0] if len(empresas) == 1 else None


def _proposta(sessao: Session, c: Contrato) -> Proposta | None:
    """A proposta da oportunidade que virou o contrato: a enviada mais recente ou, sem envio, a última gerada."""
    if c.oportunidade_id is None:
        return None
    return sessao.scalars(
        sa.select(Proposta).where(Proposta.oportunidade_id == c.oportunidade_id)
        .order_by(Proposta.enviada_em.is_(None), Proposta.gerada_em.desc(), Proposta.id.desc()).limit(1)
    ).first()


def _configuracao(sessao: Session) -> ConfiguracaoDeContrato:
    c = sessao.get(ConfiguracaoDeContrato, 1)
    if c is None:
        c = ConfiguracaoDeContrato(id=1, proximo_numero=102, vencimento=25, excedente_dp=Decimal("50.00"))
        sessao.add(c)
        sessao.flush()
    return c


def valores_sugeridos(sessao: Session, c: Contrato, hoje: date) -> dict[str, tuple[str, str]]:
    """{marcador: (valor, origem)}. Vazio = a pessoa preenche."""
    v: dict[str, tuple[str, str]] = {m: ("", "digitar") for m in regra.MARCADORES}
    e = _empresa(sessao, c)
    if e is not None:
        v["razao_social"] = (e.razao_social, "empresa")
        if e.cnpj:
            v["cnpj"] = (_cnpj(e.cnpj), "empresa")
        if _endereco(e):
            v["endereco"] = (_endereco(e), "empresa")
        if e.regime_tributario:
            v["regime"] = (e.regime_tributario, "empresa")
    imposto = parametros_vigentes(sessao)[1].imposto
    p = _proposta(sessao, c)
    if p is not None:
        entrada, marcas = p.valores.get("entrada", {}), p.valores.get("marcadores", {})
        for nome, campo in (("valor_contabil", "bruto_contabil"), ("valor_dp", "bruto_dp")):
            bruto = entrada.get(nome)
            if bruto not in (None, ""):
                valor = Decimal(str(bruto))
                v[nome] = (_reais(valor), "proposta")
                v[campo] = (_reais(conta.bruto_de(valor, imposto)), "parâmetros")
        for nome in ("horas_contabil", "horas_dp"):
            if marcas.get(nome) not in (None, "", "—"):
                v[nome] = (str(marcas[nome]), "proposta")
        for de, para in (("regime", "regime"), ("faturamento", "faturamento"), ("funcionarios", "funcionarios"),
                         ("movimentacao", "lancamentos"), ("segmento", "atividade")):
            if v[para][1] == "digitar" and marcas.get(de) not in (None, "", "—", "N/D"):
                v[para] = (str(marcas[de]), "proposta")
    elif c.preco_mensal is not None:
        v["valor_contabil"] = (_reais(c.preco_mensal), "contrato")
        v["bruto_contabil"] = (_reais(conta.bruto_de(c.preco_mensal, imposto)), "parâmetros")
    inicio = c.data_inicio or hoje
    v["competencia_inicial"] = (f"{MESES[inicio.month - 1]} de {inicio.year}", "contrato" if c.data_inicio else "hoje")
    v["data_extenso"] = (data_por_extenso(hoje), "hoje")
    cfg = _configuracao(sessao)
    v["vencimento"] = (str(cfg.vencimento), "configurações")
    v["excedente_dp"] = (_reais(cfg.excedente_dp), "configurações")
    for nome in ("signatario", "cargo_signatario", "cpf_signatario"):
        if getattr(cfg, nome):
            v[nome] = (getattr(cfg, nome), "configurações")
    return v


# ── Respostas ────────────────────────────────────────────────────────────────────────────────────────

class MatrizResumo(BaseModel):
    id: int
    nome_arquivo: str
    enviada_em: datetime
    enviada_por: str
    encontrados: list[str]
    faltando: list[str]
    desconhecidos: list[str]
    em_condicao: bool


class Marcador(BaseModel):
    nome: str
    descricao: str
    obrigatorio: bool


class MatrizDoContrato(BaseModel):
    modelo: str
    em_uso: MatrizResumo | None
    marcadores: list[Marcador]


class Campo(BaseModel):
    nome: str
    descricao: str
    valor: str
    origem: str


class DocumentoGerado(BaseModel):
    id: int
    numero: str
    gerado_em: datetime
    gerado_por: str


class AbaDoDocumento(BaseModel):
    modelo: str
    recorrente: bool | None
    matriz: MatrizResumo | None
    problema: str | None
    """Por que ainda não dá para gerar (sem matriz, matriz com erro, contrato não recorrente)."""
    numero: str
    """O número já reservado ou o próximo da sequência."""
    campos: list[Campo]
    gerado: DocumentoGerado | None


class Geracao(BaseModel):
    valores: dict[str, str]
    gerado_por: str | None = Field(default=None, max_length=200)
    """Só sem login."""


class ConfiguracaoResposta(BaseModel):
    proximo_numero: int
    ultimo_usado: str | None
    signatario: str | None
    cargo_signatario: str | None
    cpf_signatario: str | None
    vencimento: int
    excedente_dp: Decimal


class Configuracao(BaseModel):
    proximo_numero: int = Field(ge=1, le=99999)
    signatario: str | None = Field(default=None, max_length=200)
    cargo_signatario: str | None = Field(default=None, max_length=100)
    cpf_signatario: str | None = Field(default=None, max_length=14)
    vencimento: int = Field(ge=1, le=31)
    excedente_dp: Decimal = Field(ge=0, max_digits=12, decimal_places=2)


def _numero(numero: int, ano: int) -> str:
    return f"{numero}.{ano}"


def _resumo(m: MatrizDeContrato) -> MatrizResumo:
    return MatrizResumo(id=m.id, nome_arquivo=m.nome_arquivo, enviada_em=m.enviada_em, enviada_por=m.enviada_por,
                        encontrados=list(m.encontrados), faltando=list(m.faltando), desconhecidos=list(m.desconhecidos),
                        em_condicao=not m.faltando and not m.desconhecidos)


def _matriz_em_uso(sessao: Session) -> MatrizDeContrato | None:
    return sessao.scalars(
        sa.select(MatrizDeContrato).options(defer(MatrizDeContrato.conteudo_base64))
        .where(MatrizDeContrato.modelo == MODELO.value)
        .order_by(MatrizDeContrato.enviada_em.desc(), MatrizDeContrato.id.desc()).limit(1)
    ).first()


def _problema_da_matriz(m: MatrizDeContrato | None) -> str | None:
    if m is None:
        return "Ainda não há matriz do contrato recorrente: suba o Word em Configurações › Serviços e contratos."
    partes = []
    if m.faltando:
        partes.append("faltam " + ", ".join("{{" + n + "}}" for n in m.faltando))
    if m.desconhecidos:
        partes.append("marcadores desconhecidos " + ", ".join("{{" + n + "}}" for n in m.desconhecidos))
    return f"A matriz em uso não serve: {'; '.join(partes)}. Corrija e suba de novo." if partes else None


def _disposicao(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return f'attachment; filename="{sem_acento.replace(chr(34), "")}"'


def _seguro(nome: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", nome).strip()[:80] or "Cliente"


def roteador_do_documento_de_contrato(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["contratos"])

    def _contrato(sessao: Session, contrato_id: int) -> Contrato:
        c = sessao.get(Contrato, contrato_id)
        if c is None:
            raise HTTPException(404, "contrato não encontrado")
        return c

    def _gerado(sessao: Session, contrato_id: int) -> DocumentoDeContrato | None:
        return sessao.scalars(
            sa.select(DocumentoDeContrato).where(DocumentoDeContrato.contrato_id == contrato_id)
            .order_by(DocumentoDeContrato.id.desc()).limit(1)
        ).first()

    def _aba(sessao: Session, c: Contrato, hoje: date) -> AbaDoDocumento:
        m = _matriz_em_uso(sessao)
        gerado = _gerado(sessao, c.id)
        cfg = _configuracao(sessao)
        sugeridos = valores_sugeridos(sessao, c, hoje)
        nomes = list(m.encontrados) if m is not None else list(regra.MARCADORES)
        if gerado is not None:  # o que foi gerado vale mais que a sugestão
            sugeridos.update({n: (v, "gerado") for n, v in gerado.valores.items() if n != "numero"})
        problema = _problema_da_matriz(m)
        if c.recorrente is False:
            problema = "Este contrato é não recorrente: o modelo dele (Não recorrente v1.1) ainda não gera pelo CRM."
        numero = _numero(gerado.numero, gerado.ano) if gerado is not None else _numero(cfg.proximo_numero, hoje.year)
        return AbaDoDocumento(
            modelo=MODELO.value, recorrente=c.recorrente, matriz=_resumo(m) if m is not None else None,
            problema=problema, numero=numero,
            campos=[Campo(nome=n, descricao=regra.MARCADORES.get(n, "marcador desconhecido"),
                          valor=numero if n == "numero" else sugeridos.get(n, ("", "digitar"))[0],
                          origem="sequência" if n == "numero" else sugeridos.get(n, ("", "digitar"))[1])
                    for n in nomes],
            gerado=DocumentoGerado(id=gerado.id, numero=f"CONT CCE RJ1 {_numero(gerado.numero, gerado.ano)}",
                                   gerado_em=gerado.atualizado_em, gerado_por=gerado.gerado_por) if gerado else None,
        )

    @r.get("/api/contratos/{contrato_id}/documento", response_model=AbaDoDocumento)
    def ver(contrato_id: int, hoje: date | None = None,
            sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDoDocumento:
        return _aba(sessao, _contrato(sessao, contrato_id), hoje or date.today())

    @r.post("/api/contratos/{contrato_id}/documento", response_model=AbaDoDocumento)
    def gerar(contrato_id: int, corpo: Geracao, hoje: date | None = None,
              sessao: Session = Depends(obter_sessao, scope="function")) -> AbaDoDocumento:
        hoje = hoje or date.today()
        c = _contrato(sessao, contrato_id)
        if c.recorrente is False:
            raise HTTPException(409, "Este contrato é não recorrente: o modelo dele ainda não gera pelo CRM.")
        m = _matriz_em_uso(sessao)
        problema = _problema_da_matriz(m)
        if problema:
            raise HTTPException(409, problema)
        gerado = _gerado(sessao, c.id)
        if gerado is not None and c.situacao is not SituacaoContrato.AGUARDANDO_ASSINATURA:
            raise HTTPException(409, "O contrato já foi assinado: o documento não muda. Baixe o que foi gerado.")
        valores = {n: (corpo.valores.get(n) or "").strip() for n in m.encontrados if n != "numero"}
        faltam = [n for n, v in valores.items() if not v]
        if faltam:
            raise HTTPException(422, "preencha " + ", ".join(regra.MARCADORES.get(n, n) for n in faltam))
        quem = (quem_fez((corpo.gerado_por or "").strip()) or "").strip() or "sem login"
        if gerado is None:
            cfg = sessao.get(ConfiguracaoDeContrato, 1, with_for_update=True) or _configuracao(sessao)
            numero = cfg.proximo_numero
            usados = set(sessao.scalars(sa.select(DocumentoDeContrato.numero).where(
                DocumentoDeContrato.ano == hoje.year, DocumentoDeContrato.numero >= numero)))
            while numero in usados:  # alguém pôs o próximo num número já usado: pula, nunca repete
                numero += 1
            cfg.proximo_numero = numero + 1
            gerado = DocumentoDeContrato(contrato_id=c.id, numero=numero, ano=hoje.year, matriz_id=m.id,
                                         valores={}, gerado_por=quem[:200])
            sessao.add(gerado)
        gerado.matriz_id, gerado.gerado_por = m.id, quem[:200]
        gerado.valores = {**valores, "numero": _numero(gerado.numero, gerado.ano)}
        sessao.flush()
        return _aba(sessao, c, hoje)

    @r.get("/api/documentos-de-contrato/{documento_id}/docx")
    def baixar(documento_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> Response:
        d = sessao.get(DocumentoDeContrato, documento_id)
        if d is None:
            raise HTTPException(404, "documento não encontrado")
        m = sessao.get(MatrizDeContrato, d.matriz_id)
        conteudo = regra.preencher(base64.b64decode(m.conteudo_base64), d.valores)
        cliente = _seguro(d.valores.get("razao_social", "Cliente"))
        nome = f"{cliente} - CONT CCE RJ1 {_numero(d.numero, d.ano)} - BPO.docx"
        return Response(conteudo, media_type=DOCX, headers={"Content-Disposition": _disposicao(nome), "Cache-Control": "no-store"})

    # ── Configurações › Serviços e contratos ──────────────────────────────────────────────────────

    @r.get("/api/documentos-de-contrato/matriz", response_model=MatrizDoContrato)
    def ver_matriz(sessao: Session = Depends(obter_sessao, scope="function")) -> MatrizDoContrato:
        m = _matriz_em_uso(sessao)
        return MatrizDoContrato(
            modelo=MODELO.value, em_uso=_resumo(m) if m is not None else None,
            marcadores=[Marcador(nome=n, descricao=d, obrigatorio=n in regra.OBRIGATORIOS) for n, d in regra.MARCADORES.items()],
        )

    @r.post("/api/documentos-de-contrato/matriz", response_model=MatrizResumo)
    async def subir_matriz(request: Request, nome_arquivo: str = Query(min_length=1, max_length=200),
                           enviada_por: str | None = Query(default=None, max_length=200),
                           sessao: Session = Depends(obter_sessao, scope="function")) -> MatrizResumo:
        """O corpo é o .docx. Fica gravada mesmo com marcador faltando, para a tela mostrar o que corrigir; nesse caso
        não é usada para gerar."""
        if not nome_arquivo.lower().endswith(".docx"):
            raise HTTPException(422, "a matriz precisa ser um Word .docx")
        dados = await request.body()
        if not dados:
            raise HTTPException(400, "nenhum arquivo enviado")
        if len(dados) > LIMITE_DA_MATRIZ:
            raise HTTPException(413, f"arquivo grande demais (o limite é {LIMITE_DA_MATRIZ // (1024 * 1024)} MB)")
        try:
            exame = regra.examinar(dados)
        except regra.MatrizIlegivel as falha:
            raise HTTPException(422, str(falha)) from falha
        quem = (quem_fez((enviada_por or "").strip()) or "").strip() or "sem login"
        m = MatrizDeContrato(modelo=MODELO.value, nome_arquivo=nome_arquivo, conteudo_base64=base64.b64encode(dados).decode(),
                             enviada_em=agora(), enviada_por=quem[:200], encontrados=exame.encontrados,
                             faltando=exame.faltando, desconhecidos=exame.desconhecidos)
        sessao.add(m)
        sessao.flush()
        return _resumo(m)

    @r.get("/api/documentos-de-contrato/matriz/{matriz_id}/docx")
    def baixar_matriz(matriz_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> Response:
        m = sessao.get(MatrizDeContrato, matriz_id)
        if m is None:
            raise HTTPException(404, "matriz não encontrada")
        return Response(base64.b64decode(m.conteudo_base64), media_type=DOCX,
                        headers={"Content-Disposition": _disposicao(m.nome_arquivo), "Cache-Control": "no-store"})

    def _configuracao_resposta(sessao: Session, c: ConfiguracaoDeContrato) -> ConfiguracaoResposta:
        ultimo = sessao.execute(sa.select(DocumentoDeContrato.numero, DocumentoDeContrato.ano)
                                .order_by(DocumentoDeContrato.ano.desc(), DocumentoDeContrato.numero.desc()).limit(1)).first()
        return ConfiguracaoResposta(
            proximo_numero=c.proximo_numero, ultimo_usado=f"CONT CCE RJ1 {_numero(*ultimo)}" if ultimo else None,
            signatario=c.signatario, cargo_signatario=c.cargo_signatario, cpf_signatario=c.cpf_signatario,
            vencimento=c.vencimento, excedente_dp=c.excedente_dp,
        )

    @r.get("/api/documentos-de-contrato/configuracao", response_model=ConfiguracaoResposta)
    def ver_configuracao(sessao: Session = Depends(obter_sessao, scope="function")) -> ConfiguracaoResposta:
        return _configuracao_resposta(sessao, _configuracao(sessao))

    @r.put("/api/documentos-de-contrato/configuracao", response_model=ConfiguracaoResposta)
    def editar_configuracao(corpo: Configuracao, sessao: Session = Depends(obter_sessao, scope="function")) -> ConfiguracaoResposta:
        ano = date.today().year
        maior = sessao.scalar(sa.select(sa.func.max(DocumentoDeContrato.numero)).where(DocumentoDeContrato.ano == ano))
        if maior is not None and corpo.proximo_numero <= maior:
            raise HTTPException(422, f"o CONT CCE RJ1 {maior}.{ano} já foi usado: o próximo precisa ser maior que {maior}")
        cpf = re.sub(r"\D", "", corpo.cpf_signatario or "")
        if cpf and len(cpf) != 11:
            raise HTTPException(422, "CPF de quem assina com 11 dígitos")
        c = _configuracao(sessao)
        c.proximo_numero, c.vencimento, c.excedente_dp = corpo.proximo_numero, corpo.vencimento, corpo.excedente_dp
        c.signatario = (corpo.signatario or "").strip() or None
        c.cargo_signatario = (corpo.cargo_signatario or "").strip() or None
        c.cpf_signatario = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if cpf else None
        sessao.flush()
        return _configuracao_resposta(sessao, c)

    return r
