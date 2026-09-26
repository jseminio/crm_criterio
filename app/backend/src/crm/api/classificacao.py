"""API da classificação da carteira (Etapa 3): classe, Score, alertas e eixo de ação por grupo, mais o ISC.

Somente leitura. Lê o **snapshot mais recente** de cada grupo; o ISC é recalculado aqui com a mesma regra
da carga (`crm.domain.classificacao`), nunca copiado da planilha. A nota de rentabilidade vem da planilha
(defeito 7.2 pendente) e a resposta avisa disso.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Callable, Iterator

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from crm.db.modelos import ClassificacaoDoGrupo, Contrato, GrupoEconomico
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
        itens = [
            ItemDaCarteira(
                grupo_id=c.grupo_id, grupo_nome=nome, receita_mensal=c.receita_mensal, score=c.score, classe=c.classe,
                classe_efetiva=c.classe_efetiva, alerta_de_churn=c.alerta_de_churn, em_cobranca=c.em_cobranca,
                eixo_de_acao=c.eixo_de_acao, semaforo=c.semaforo, churn=c.churn, sem_contrato_ativo=c.grupo_id not in ativos,
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
        if calculado and calculado.fora_do_isc:
            avisos.append(f"{calculado.fora_do_isc} grupo(s) sem nota de churn ficaram fora do ISC.")
        primeira = linhas[0][0]
        return ClassificacaoDaCarteira(
            referencia=max(c.referencia for c, _ in linhas), versao_dos_parametros=primeira.versao_dos_parametros,
            isc=IscResposta(**{k: getattr(calculado, k) for k in IscResposta.model_fields}) if calculado else None,
            por_classe=dict(sorted(por_classe.items())), itens=itens, avisos=avisos,
        )

    return r
