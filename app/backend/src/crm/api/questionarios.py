"""Rotas do questionário para proposta: buscar no site, ver o que entrou, resolver o que precisa de
alguém e abrir o PDF (pedido de Eduardo, 01/10/2026). Regras em `crm.questionario`."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from crm.db.base import agora
from crm.db.modelos import GrupoEconomico, Oportunidade, QuestionarioRecebido
from crm.domain.listas import SituacaoDoQuestionario
from crm.questionario import importacao
from crm.questionario.endereco import BuscaDeEndereco
from crm.questionario.fonte import (
    VARIAVEIS, BuscaFalhou, FonteDaFuncao, FonteDeQuestionarios, FonteSupabase, e_funcao, ler_configuracao,
)
from crm.questionario.leitura import ROTULOS_COMPLEXIDADE, ROTULOS_RISCO, inteiro_ou_nada

__all__ = ["roteador_de_questionarios", "fonte_real"]


def fonte_real() -> FonteDeQuestionarios | None:
    config = ler_configuracao()
    if config is None:
        return None
    return FonteDaFuncao(config) if e_funcao(config) else FonteSupabase(config)


class QuestionarioResumo(BaseModel):
    id: int
    recebido_em: datetime
    razao_social: str
    nome_fantasia: str | None
    cnpj: str
    contato_nome: str
    contato_cargo: str | None
    situacao: str
    cliente_novo: bool
    o_que_fez: str
    grupo_id: int | None
    grupo_nome: str | None
    oportunidade_id: int | None
    oportunidade_em_aberto_id: int | None
    porte_crm: str | None
    porte_site: str | None
    tem_pdf: bool


class ResultadoDaBusca(BaseModel):
    buscado_em: datetime
    novos: list[QuestionarioResumo]
    avisos: list[str]


class Resolucao(BaseModel):
    acao: Literal["anexar", "criar"]


class FatorDoQuestionario(BaseModel):
    id: str
    rotulo: str


class QuestionarioDaOportunidade(BaseModel):
    id: int
    recebido_em: datetime
    versao: str
    contato_nome: str
    contato_cargo: str | None
    contato_email: str | None
    contato_celular: str | None
    servicos: list[str]
    porte_crm: str | None
    porte_site: str | None
    pontuacao: str | None
    horas_base: int | None
    nota_complexidade: int
    fatores_complexidade: list[FatorDoQuestionario]
    nota_risco: int
    fatores_risco: list[FatorDoQuestionario]
    pontos_de_atencao: list[tuple[str, str]]
    notas_emitidas: int | None
    notas_recebidas: int | None
    tem_pdf: bool


def roteador_de_questionarios(
    obter_sessao: Callable[[], Iterator[Session]],
    fonte: Callable[[], FonteDeQuestionarios | None] = fonte_real,
    buscar_endereco: BuscaDeEndereco | None = None,
) -> APIRouter:
    """`buscar_endereco`: endereço pelo CNPJ ao importar (Karine, 01/10/2026). None = não busca."""
    r = APIRouter(tags=["questionário"])

    def _resumo(sessao: Session, q: QuestionarioRecebido) -> QuestionarioResumo:
        grupo = sessao.get(GrupoEconomico, q.grupo_id) if q.grupo_id else None
        return QuestionarioResumo(
            id=q.id, recebido_em=q.recebido_em, razao_social=q.razao_social, nome_fantasia=q.nome_fantasia,
            cnpj=q.cnpj, contato_nome=q.contato_nome, contato_cargo=q.contato_cargo, situacao=q.situacao.value,
            cliente_novo=q.cliente_novo, o_que_fez=q.o_que_fez, grupo_id=q.grupo_id,
            grupo_nome=grupo.nome if grupo else None, oportunidade_id=q.oportunidade_id,
            oportunidade_em_aberto_id=q.oportunidade_em_aberto_id, porte_crm=q.porte_crm, porte_site=q.porte_site,
            tem_pdf=bool(q.pdf_base64),
        )

    @r.post("/api/questionarios/buscar", response_model=ResultadoDaBusca)
    def buscar(sessao: Session = Depends(obter_sessao)) -> ResultadoDaBusca:
        """Traz do site o que ainda não foi importado. Cada questionário é gravado aqui **antes** de ser
        marcado lá: se a marca falhar, ele volta na próxima busca e só a marca é refeita."""
        origem = fonte()
        if origem is None:
            raise HTTPException(
                409, f"Falta configurar a busca: preencha {VARIAVEIS['url']} e {VARIAVEIS['chave']} no backend/.env "
                     "e reinicie o CRM.",
            )
        try:
            linhas = origem.novos()
        except BuscaFalhou as falha:
            raise HTTPException(502, str(falha)) from falha
        novos: list[QuestionarioRecebido] = []
        avisos: list[str] = []
        for linha in linhas:
            externo = str(linha.get("id", ""))
            q = sessao.scalar(sa.select(QuestionarioRecebido).where(QuestionarioRecebido.externo_id == externo))
            if q is None:
                try:
                    q = importacao.importar(sessao, linha, buscar_endereco)
                except (importacao.LinhaInvalida, KeyError, ValueError) as falha:
                    sessao.rollback()  # só esta linha: as anteriores já foram gravadas
                    avisos.append(f"Questionário {externo or 'sem id'} ficou de fora: {falha}. Ele continua no site.")
                    continue
                sessao.commit()
                novos.append(q)
            try:
                origem.marcar_importado(externo, agora())
                q.marcado_na_origem_em = agora()
                sessao.commit()
            except BuscaFalhou as falha:
                avisos.append(f"{q.razao_social}: entrou no CRM, mas {falha} Na próxima busca o CRM só tenta marcar de novo.")
        return ResultadoDaBusca(buscado_em=agora(), novos=[_resumo(sessao, q) for q in novos], avisos=avisos)

    @r.get("/api/questionarios", response_model=list[QuestionarioResumo])
    def listar(sessao: Session = Depends(obter_sessao), limite: int = Query(default=30, le=200)) -> list[QuestionarioResumo]:
        """Os mais recentes primeiro; os que precisam de alguém vêm antes de todos."""
        itens = sessao.scalars(
            sa.select(QuestionarioRecebido).order_by(
                (QuestionarioRecebido.situacao == SituacaoDoQuestionario.PRECISA_DE_VOCE).desc(),
                QuestionarioRecebido.recebido_em.desc(), QuestionarioRecebido.id.desc(),
            ).limit(limite)
        ).all()
        return [_resumo(sessao, q) for q in itens]

    def _questionario(sessao: Session, questionario_id: int) -> QuestionarioRecebido:
        q = sessao.get(QuestionarioRecebido, questionario_id)
        if q is None:
            raise HTTPException(404, "questionário não encontrado")
        return q

    @r.post("/api/questionarios/{questionario_id}/resolver", response_model=QuestionarioResumo)
    def resolver(questionario_id: int, corpo: Resolucao, sessao: Session = Depends(obter_sessao)) -> QuestionarioResumo:
        q = _questionario(sessao, questionario_id)
        try:
            if corpo.acao == "anexar":
                importacao.anexar(sessao, q)
            else:
                importacao.criar_nova(sessao, q)
        except ValueError as falha:
            raise HTTPException(409, str(falha)) from falha
        sessao.commit()
        return _resumo(sessao, q)

    @r.get("/api/questionarios/{questionario_id}/pdf")
    def pdf(questionario_id: int, sessao: Session = Depends(obter_sessao)) -> Response:
        q = _questionario(sessao, questionario_id)
        if not q.pdf_base64:
            raise HTTPException(404, "este questionário chegou sem PDF")
        try:
            conteudo = base64.b64decode(q.pdf_base64, validate=True)
        except (binascii.Error, ValueError) as falha:
            raise HTTPException(422, "o PDF deste questionário chegou corrompido") from falha
        return Response(
            conteudo, media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="questionario-{q.cnpj}.pdf"'},
        )

    @r.get("/api/oportunidades/{oportunidade_id}/questionario", response_model=QuestionarioDaOportunidade | None)
    def da_oportunidade(oportunidade_id: int, sessao: Session = Depends(obter_sessao)) -> QuestionarioDaOportunidade | None:
        """O questionário mais recente que criou ou foi anexado a esta oportunidade, se houver."""
        if sessao.get(Oportunidade, oportunidade_id) is None:
            raise HTTPException(404, "oportunidade não encontrada")
        q = sessao.scalars(
            sa.select(QuestionarioRecebido).where(QuestionarioRecebido.oportunidade_id == oportunidade_id)
            .order_by(QuestionarioRecebido.recebido_em.desc()).limit(1)
        ).first()
        if q is None:
            return None
        leitura = importacao.leitura_de(q)
        vol = q.respostas.get("vol") or {}
        inteiro = lambda k: inteiro_ou_nada(vol.get(k))  # noqa: E731
        return QuestionarioDaOportunidade(
            id=q.id, recebido_em=q.recebido_em, versao=q.versao, contato_nome=q.contato_nome,
            contato_cargo=q.contato_cargo, contato_email=q.contato_email, contato_celular=q.contato_celular,
            servicos=leitura.servicos, porte_crm=leitura.porte, porte_site=q.porte_site, pontuacao=leitura.pontuacao,
            horas_base=leitura.horas_base, nota_complexidade=leitura.nota_complexidade,
            fatores_complexidade=[FatorDoQuestionario(id=f, rotulo=ROTULOS_COMPLEXIDADE[f]) for f in leitura.fatores_complexidade],
            nota_risco=leitura.nota_risco,
            fatores_risco=[FatorDoQuestionario(id=f, rotulo=ROTULOS_RISCO[f]) for f in leitura.fatores_risco],
            pontos_de_atencao=leitura.pontos_de_atencao,
            notas_emitidas=inteiro("notas_emitidas"), notas_recebidas=inteiro("notas_recebidas"),
            tem_pdf=bool(q.pdf_base64),
        )

    return r
