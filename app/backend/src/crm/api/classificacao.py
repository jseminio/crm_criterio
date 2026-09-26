"""API da classificação da carteira (Etapa 3): classe, Score, alertas e eixo de ação por grupo, mais o ISC.

Somente leitura. Lê o **snapshot mais recente** de cada grupo; o ISC é recalculado aqui com a mesma regra
da carga (`crm.domain.classificacao`), nunca copiado da planilha. A nota de rentabilidade vem da planilha
(defeito 7.2 pendente) e a resposta avisa disso.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Iterator

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.db.modelos import ClassificacaoDoGrupo, Contrato, Empresa, GrupoEconomico
from crm.db.base import agora
from crm.domain import classificacao as regra
from crm.domain.listas import SituacaoContrato

AVISO_DA_PLANILHA = (
    "A nota de rentabilidade vem da planilha de saúde da carteira, sem recálculo: a regra de atrito/disciplina "
    "ainda está pendente de validação (defeito 7.2)."
)

AVISO_RECALCULADA = (
    "A rentabilidade foi recalculada no CRM com a disciplina invertida (6 − disciplina), corrigindo o defeito 7.2 "
    "da planilha (decisão de 26/09/2026). As demais notas vêm da planilha de saúde da carteira."
)


class EmpresaDoGrupo(BaseModel):
    id: int
    razao_social: str
    cnpj: str | None
    mensalidade: Decimal | None
    """Preço mensal dos contratos ativos e suspensos da empresa; `None` se não há contrato ligado a ela."""


class NotasDoGrupo(BaseModel):
    receita: Decimal
    rentabilidade: Decimal
    complexidade: Decimal
    disciplina: Decimal
    risco: Decimal
    cross_sell: Decimal
    adimplencia: Decimal
    semaforo: int
    churn: int | None
    rentabilidade_da_planilha: bool
    atribuido_por: str | None
    motivo: str | None
    registrado_em: datetime


class ItemDaCarteira(BaseModel):
    grupo_id: int
    grupo_nome: str
    receita_mensal: Decimal
    score: Decimal
    classe: str
    classe_efetiva: str
    alerta_de_churn: str | None
    em_cobranca: bool
    eixo_de_acao: str
    semaforo: int
    churn: int | None
    sem_contrato_ativo: bool
    empresas: list[EmpresaDoGrupo] = []
    notas: NotasDoGrupo
    """O grupo não tem contrato ativo hoje (ex.: baixado depois da referência)."""


class IscResposta(BaseModel):
    valor: Decimal
    zona: str
    componente_classe: Decimal
    componente_semaforo: Decimal
    componente_churn: Decimal
    receita_total: Decimal
    grupos: int
    fora_do_isc: int


class ClassificacaoDaCarteira(BaseModel):
    referencia: date | None
    versao_dos_parametros: str | None
    isc: IscResposta | None
    por_classe: dict[str, int]
    itens: list[ItemDaCarteira]
    avisos: list[str]


def _notas(c: ClassificacaoDoGrupo) -> NotasDoGrupo:
    return NotasDoGrupo(
        receita=c.nota_receita, rentabilidade=c.nota_rentabilidade, complexidade=c.complexidade, disciplina=c.disciplina,
        risco=c.risco_tecnico, cross_sell=c.cross_sell, adimplencia=c.adimplencia, semaforo=c.semaforo, churn=c.churn,
        rentabilidade_da_planilha=c.rentabilidade_da_planilha, atribuido_por=c.atribuido_por, motivo=c.motivo,
        registrado_em=c.registrado_em,
    )


Nota = Decimal


class EdicaoDeNotas(BaseModel):
    """As notas humanas de um grupo. Só o que vier preenchido muda; o resto copia da leitura anterior."""

    autor: str = Field(min_length=2, max_length=120)
    motivo: str = Field(min_length=3, max_length=500)
    complexidade: Decimal | None = Field(default=None, ge=1, le=5)
    disciplina: Decimal | None = Field(default=None, ge=1, le=5)
    risco: Decimal | None = Field(default=None, ge=1, le=5)
    cross_sell: Decimal | None = Field(default=None, ge=1, le=5)
    adimplencia: Decimal | None = Field(default=None, ge=1, le=5)
    semaforo: int | None = Field(default=None, ge=1, le=3)
    churn: int | None = Field(default=None, ge=1, le=5)


class ResultadoDaEdicao(BaseModel):
    item: ItemDaCarteira
    isc: IscResposta | None
    avisos: list[str]


class LeituraDoHistorico(BaseModel):
    id: int
    referencia: date
    revisao: int
    registrado_em: datetime
    fonte: str
    atribuido_por: str | None
    motivo: str | None
    score: Decimal
    classe_efetiva: str
    eixo_de_acao: str
    notas: NotasDoGrupo


def roteador(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(prefix="/api/carteira", tags=["carteira"])

    @r.get("/classificacao", response_model=ClassificacaoDaCarteira)
    def classificacao(sessao: Session = Depends(obter_sessao)) -> ClassificacaoDaCarteira:
        todas = sessao.execute(
            sa.select(ClassificacaoDoGrupo, GrupoEconomico.nome)
            .join(GrupoEconomico, GrupoEconomico.id == ClassificacaoDoGrupo.grupo_id)
            .where(GrupoEconomico.fundido_em_id.is_(None))
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc())
        ).all()
        vistos: set[int] = set()
        linhas = []
        for c, nome in todas:  # a leitura mais recente de cada grupo: referência maior, depois revisão maior
            if c.grupo_id not in vistos:
                vistos.add(c.grupo_id)
                linhas.append((c, nome))
        linhas.sort(key=lambda x: x[0].receita_mensal, reverse=True)
        if not linhas:
            return ClassificacaoDaCarteira(referencia=None, versao_dos_parametros=None, isc=None, por_classe={},
                                           itens=[], avisos=[])
        ativos = set(sessao.scalars(
            sa.select(Contrato.grupo_id).where(Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
        ))
        mensal = {
            e: v for e, v in sessao.execute(
                sa.select(Contrato.empresa_id, sa.func.sum(Contrato.preco_mensal))
                .where(Contrato.empresa_id.is_not(None),
                       Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
                .group_by(Contrato.empresa_id)
            )
        }
        empresas: dict[int, list[EmpresaDoGrupo]] = {}
        for e in sessao.scalars(
            sa.select(Empresa).where(Empresa.grupo_id.in_(vistos)).order_by(Empresa.razao_social)
        ):
            empresas.setdefault(e.grupo_id, []).append(
                EmpresaDoGrupo(id=e.id, razao_social=e.razao_social, cnpj=e.cnpj, mensalidade=mensal.get(e.id))
            )
        itens = [
            ItemDaCarteira(
                grupo_id=c.grupo_id, grupo_nome=nome, receita_mensal=c.receita_mensal, score=c.score, classe=c.classe,
                classe_efetiva=c.classe_efetiva, alerta_de_churn=c.alerta_de_churn, em_cobranca=c.em_cobranca,
                eixo_de_acao=c.eixo_de_acao, semaforo=c.semaforo, churn=c.churn, sem_contrato_ativo=c.grupo_id not in ativos,
                empresas=empresas.get(c.grupo_id, []), notas=_notas(c),
            )
            for c, nome in linhas
        ]
        calculado = regra.isc(regra.Unidade(c.receita_mensal, c.classe, c.semaforo, c.churn) for c, _ in linhas)
        por_classe: dict[str, int] = {}
        for i in itens:
            por_classe[i.classe] = por_classe.get(i.classe, 0) + 1
        da_planilha = [nome for c, nome in linhas if c.rentabilidade_da_planilha]
        if len(da_planilha) == len(linhas):
            avisos = [AVISO_DA_PLANILHA]
        else:
            avisos = [AVISO_RECALCULADA]
            if da_planilha:
                avisos.append(f"{len(da_planilha)} grupo(s) mantiveram a nota de rentabilidade da planilha, porque os honorários "
                              "das empresas não fecham com a receita oficial: " + ", ".join(da_planilha) + ".")
        parados = [i.grupo_nome for i in itens if i.sem_contrato_ativo]
        if parados:
            avisos.append(f"{len(parados)} grupo(s) sem contrato ativo hoje continuam no snapshot da referência: "
                          + ", ".join(parados) + ".")
        editados = [nome for c, nome in linhas if c.atribuido_por]
        if editados:
            avisos.append(f"{len(editados)} grupo(s) com nota editada à mão depois da carga: " + ", ".join(editados) + ".")
        if calculado and calculado.fora_do_isc:
            avisos.append(f"{calculado.fora_do_isc} grupo(s) sem nota de churn ficaram fora do ISC.")
        primeira = linhas[0][0]
        return ClassificacaoDaCarteira(
            referencia=max(c.referencia for c, _ in linhas), versao_dos_parametros=primeira.versao_dos_parametros,
            isc=IscResposta(**{k: getattr(calculado, k) for k in IscResposta.model_fields}) if calculado else None,
            por_classe=dict(sorted(por_classe.items())), itens=itens, avisos=avisos,
        )

    def _ultima(sessao: Session, grupo_id: int) -> ClassificacaoDoGrupo | None:
        return sessao.scalars(
            sa.select(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == grupo_id)
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc()).limit(1)
        ).first()

    @r.post("/grupos/{grupo_id}/notas", response_model=ResultadoDaEdicao, status_code=201)
    def editar_notas(grupo_id: int, corpo: EdicaoDeNotas, sessao: Session = Depends(obter_sessao)) -> ResultadoDaEdicao:
        """Grava uma **nova leitura** com as notas alteradas; a anterior não é tocada (snapshot imutável).

        Score, classe, alerta e eixo são recalculados. **A nota de rentabilidade não muda**: o CRM não guarda porte
        nem insumos por empresa para refazer a margem, e a resposta avisa quando complexidade, disciplina ou risco mudam.
        """
        grupo = sessao.get(GrupoEconomico, grupo_id)
        if grupo is None:
            raise HTTPException(404, "grupo não encontrado")
        if grupo.fundido_em_id is not None:
            raise HTTPException(409, "grupo fundido em outro: edite o grupo que ficou")
        anterior = _ultima(sessao, grupo_id)
        if anterior is None:
            raise HTTPException(409, "o grupo ainda não tem classificação carregada")
        mudou = corpo.model_dump(exclude={"autor", "motivo"}, exclude_none=True)
        if not mudou:
            raise HTTPException(422, "informe ao menos uma nota para alterar")
        novas = regra.Notas(
            receita=anterior.nota_receita, rentabilidade=anterior.nota_rentabilidade,
            complexidade=mudou.get("complexidade", anterior.complexidade), disciplina=mudou.get("disciplina", anterior.disciplina),
            risco=mudou.get("risco", anterior.risco_tecnico), cross_sell=mudou.get("cross_sell", anterior.cross_sell),
            adimplencia=mudou.get("adimplencia", anterior.adimplencia), semaforo=mudou.get("semaforo", anterior.semaforo),
            churn=mudou.get("churn", anterior.churn),
        )
        hoje = date.today()
        revisao = 1 + (sessao.scalar(
            sa.select(sa.func.max(ClassificacaoDoGrupo.revisao)).where(
                ClassificacaoDoGrupo.grupo_id == grupo_id, ClassificacaoDoGrupo.referencia == hoje)
        ) or 0)
        pontos = regra.score(novas)
        letra = regra.classe(pontos)
        nova = ClassificacaoDoGrupo(
            grupo_id=grupo_id, referencia=hoje, revisao=revisao, fonte="Edição manual no CRM",
            versao_dos_parametros=regra.PARAMETROS.versao, atribuido_por=corpo.autor.strip(), motivo=corpo.motivo.strip(),
            receita_mensal=anterior.receita_mensal, margem=anterior.margem, horas_por_mes=anterior.horas_por_mes,
            rentabilidade_da_planilha=anterior.rentabilidade_da_planilha,
            nota_receita=novas.receita, nota_rentabilidade=novas.rentabilidade, complexidade=novas.complexidade,
            disciplina=novas.disciplina, risco_tecnico=novas.risco, cross_sell=novas.cross_sell, adimplencia=novas.adimplencia,
            semaforo=novas.semaforo, churn=novas.churn, score=pontos.quantize(Decimal("0.0001")), classe=letra,
            classe_efetiva=regra.classe_efetiva(letra, novas), alerta_de_churn=regra.alerta_de_churn(letra, novas),
            em_cobranca=regra.cobranca(novas), eixo_de_acao=regra.eixo_de_acao(letra, novas),
        )
        sessao.add(nova)
        sessao.commit()
        avisos = []
        if {"complexidade", "disciplina", "risco"} & mudou.keys():
            avisos.append("A nota de rentabilidade não foi recalculada: o CRM ainda não guarda os insumos de porte por empresa.")
        atual = classificacao(sessao)
        item = next(i for i in atual.itens if i.grupo_id == grupo_id)
        return ResultadoDaEdicao(item=item, isc=atual.isc, avisos=avisos)

    @r.get("/grupos/{grupo_id}/historico", response_model=list[LeituraDoHistorico])
    def historico(grupo_id: int, sessao: Session = Depends(obter_sessao)) -> list[LeituraDoHistorico]:
        linhas = sessao.scalars(
            sa.select(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == grupo_id)
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc())
        ).all()
        return [
            LeituraDoHistorico(
                id=c.id, referencia=c.referencia, revisao=c.revisao, registrado_em=c.registrado_em, fonte=c.fonte,
                atribuido_por=c.atribuido_por, motivo=c.motivo, score=c.score, classe_efetiva=c.classe_efetiva,
                eixo_de_acao=c.eixo_de_acao, notas=_notas(c),
            )
            for c in linhas
        ]

    return r
