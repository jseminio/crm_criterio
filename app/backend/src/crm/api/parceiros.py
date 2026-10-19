"""A tela Parceiros (19/10/2026, amostra aprovada por Eduardo): menu próprio, no padrão do Funil comercial — Kanban e
Grade, filtros com período, indicadores com composição e exportação para Excel. As contas ficam em
`crm.domain.parceiros`; aqui só se carrega e se grava.

Quem aprova e marca pago o fee é quem tem "Parceiros: aprovar e pagar fee" — o sócio da conta, por decisão de Eduardo.
"""

from __future__ import annotations

import io
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.api.acesso import quem_fez
from crm.db.base import agora
from crm.db.modelos import Contrato, Empresa, FeeDeParceiro, FollowUpDeParceiro, GrupoEconomico, Oportunidade, Parceiro, Recebimento
from crm.domain import parceiros as regras
from crm.domain.servicos import linha_do_servico
from crm.carga.lacunas_contato import cnpj_valido
from crm.domain.listas import (
    AcordoDoParceiro,
    EtapaDoParceiro,
    MotivoDeIndicacaoRecusada,
    NivelDeParceiro,
    Origem,
    ResultadoDoFollowUp,
    Situacao,
    SituacaoContrato,
    SituacaoDoFee,
    SituacaoGrupo,
    TipoCanal,
    TipoDePessoa,
)

__all__ = ["roteador_de_parceiros"]

CANAIS_DE_PARCEIRO = (TipoCanal.PARCEIROS, TipoCanal.ADVOGADOS)
"""Os tipos de canal cujo texto (`canal`) a conferência liga ao cadastro de Parceiros."""


# ------------------------------------------------------------------ esquemas

class ParceiroResumo(BaseModel):
    id: int
    nome: str
    tipo_pessoa: str
    nivel: str
    acordo: str
    etapa: str
    socio_responsavel: str | None
    indicacoes: int
    abertas: int
    fechadas: int
    mrr: Decimal
    pontual: Decimal
    proximo_follow_up: str | None = None
    proximo_follow_up_em: date | None = None


class ParceiroEntrada(BaseModel):
    nome: str = Field(min_length=1, max_length=120)
    tipo_pessoa: TipoDePessoa = TipoDePessoa.PJ
    documento: str | None = Field(default=None, max_length=20)
    tipo: str | None = Field(default=None, max_length=60)
    nivel: NivelDeParceiro = NivelDeParceiro.INDICADOR
    etapa_manual: EtapaDoParceiro = EtapaDoParceiro.MAPEADO
    acordo: AcordoDoParceiro = AcordoDoParceiro.SEM_ACORDO
    contrato_assinado_em: date | None = None
    regra_combinada: str | None = Field(default=None, max_length=400)
    combinado_por: str | None = Field(default=None, max_length=60)
    combinado_em: date | None = None
    socio_responsavel: str | None = Field(default=None, max_length=60)
    perfil_pedido: str | None = Field(default=None, max_length=400)
    contato: str | None = Field(default=None, max_length=200)
    observacao: str | None = None
    proximo_follow_up: str | None = Field(default=None, max_length=200)
    proximo_follow_up_em: date | None = None


class ParceiroEdicao(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=120)
    tipo_pessoa: TipoDePessoa | None = None
    documento: str | None = Field(default=None, max_length=20)
    tipo: str | None = Field(default=None, max_length=60)
    nivel: NivelDeParceiro | None = None
    etapa_manual: EtapaDoParceiro | None = None
    acordo: AcordoDoParceiro | None = None
    contrato_assinado_em: date | None = None
    regra_combinada: str | None = Field(default=None, max_length=400)
    combinado_por: str | None = Field(default=None, max_length=60)
    combinado_em: date | None = None
    socio_responsavel: str | None = Field(default=None, max_length=60)
    perfil_pedido: str | None = Field(default=None, max_length=400)
    contato: str | None = Field(default=None, max_length=200)
    observacao: str | None = None
    proximo_follow_up: str | None = Field(default=None, max_length=200)
    proximo_follow_up_em: date | None = None


class IndicacaoDoParceiro(BaseModel):
    oportunidade_id: int
    nome: str
    grupo: str | None
    grupo_id: int
    situacao: str
    recebida_em: date | None
    validada_em: date | None
    recusada: str | None
    vinculo_ate: date | None
    mensal: Decimal | None
    anual: Decimal | None
    mrr: Decimal


class FeeResposta(BaseModel):
    id: int
    parceiro_id: int
    parceiro: str
    oportunidade_id: int
    oportunidade: str
    grupo: str | None
    regra: str
    competencia: date
    base: Decimal
    calculado: Decimal
    valor_aprovado: Decimal | None
    situacao: str
    decidido_por: str | None
    decidido_em: datetime | None
    pago_em: date | None
    motivo: str | None


class FollowUpResposta(BaseModel):
    id: int
    feito_em: date
    resultado: str
    nota: str | None
    registrado_por: str | None


class FollowUpEntrada(BaseModel):
    """Registrar follow-up feito (19/10/2026): o que aconteceu e, no mesmo passo, o próximo."""

    feito_em: date
    resultado: ResultadoDoFollowUp
    nota: str | None = Field(default=None, max_length=2000)
    proximo_follow_up: str | None = Field(default=None, max_length=200)
    proximo_follow_up_em: date | None = None


class ParceiroDetalhe(BaseModel):
    id: int
    nome: str
    tipo_pessoa: str
    documento: str | None
    tipo: str | None
    nivel: str
    etapa: str
    etapa_manual: str
    acordo: str
    contrato_assinado_em: date | None
    regra_combinada: str | None
    combinado_por: str | None
    combinado_em: date | None
    socio_responsavel: str | None
    perfil_pedido: str | None
    contato: str | None
    observacao: str | None
    textos_do_canal: list[str]
    indicacoes: list[IndicacaoDoParceiro]
    fees: list[FeeResposta]
    proximo_follow_up: str | None
    proximo_follow_up_em: date | None
    cadencia_meses: int
    """A cadência sugerida do nível, em meses."""
    follow_ups: list[FollowUpResposta]


class IndicadoresDosParceiros(BaseModel):
    ativos: int
    indicacoes: int
    conversao: Decimal | None
    mrr: Decimal
    sem_contrato: int
    fees: Decimal
    fees_quantos: int
    sem_follow_up: int
    follow_up_atrasado: int
    explicacoes: dict[str, str]


class ItemDaComposicaoResposta(BaseModel):
    parceiro: str
    detalhe: str
    valor: Decimal
    referencia: str | None


class EtapaEntrada(BaseModel):
    etapa: EtapaDoParceiro


class IndicacaoEntrada(BaseModel):
    oportunidade_id: int
    recebida_em: date | None = None
    validada_em: date | None = None


class IndicacaoEdicao(BaseModel):
    recebida_em: date | None = None
    validada_em: date | None = None
    recusada: MotivoDeIndicacaoRecusada | None = None


class TextoSemParceiro(BaseModel):
    texto: str
    tipo_canal: str
    oportunidades: int
    sugestao_id: int | None


class LigarTexto(BaseModel):
    texto: str = Field(min_length=1)
    parceiro_id: int


class Aprovacao(BaseModel):
    valor: Decimal = Field(ge=0)


class Recusa(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)


class Pagamento(BaseModel):
    pago_em: date


class ResultadoDoCalculo(BaseModel):
    novos: int


class ParceiroNome(BaseModel):
    id: int
    nome: str
    tipo: str | None


class OportunidadeEncontrada(BaseModel):
    id: int
    nome: str
    grupo: str | None
    situacao: str
    canal: str | None
    parceiro: str | None


class EmpresaNovaIndicada(BaseModel):
    nome: str = Field(min_length=2, max_length=200)
    cnpj: str | None = Field(default=None, max_length=20)


class IndicacaoRegistrada(BaseModel):
    """O botão Registrar indicação (19/10/2026): a empresa da base ou uma nova, o serviço de interesse, quem falar no
    cliente e a autorização do cliente para o contato (LGPD), que é obrigatória."""

    empresa_id: int | None = None
    empresa_nova: EmpresaNovaIndicada | None = None
    servico: str = Field(min_length=2, max_length=120)
    recebida_em: date | None = None
    contato_nome: str | None = Field(default=None, max_length=120)
    contato_meio: str | None = Field(default=None, max_length=200)
    autorizado_pelo_cliente: bool


class AlertaDaIndicacao(BaseModel):
    tipo: Literal["ja_cliente", "em_negociacao", "outro_parceiro"]
    motivo_sugerido: str
    texto: str


class LinhaDoRelatorioResposta(BaseModel):
    empresa: str
    indicada_em: date | None
    etapa: str
    proximo_passo: str | None
    servico_contratado: str | None


class FeeDoRelatorio(BaseModel):
    empresa: str
    competencia: date
    valor: Decimal
    situacao: str


class RelatorioDoParceiro(BaseModel):
    parceiro_id: int
    parceiro: str
    contato: str | None
    mes: str
    emitido_em: date
    responsavel: str | None
    indicacoes: int
    novas_no_mes: int
    viraram_cliente: int
    fee_pago_no_mes: Decimal
    linhas: list[LinhaDoRelatorioResposta]
    fees: list[FeeDoRelatorio]


# ------------------------------------------------------------------ apoio

def _hoje() -> date:
    """O dia da conta de Dormente e do vínculo. Função à parte para o teste fixar a data."""
    return date.today()


def _fee(f: FeeDeParceiro) -> FeeResposta:
    return FeeResposta(
        id=f.id, parceiro_id=f.parceiro_id, parceiro=f.parceiro.nome, oportunidade_id=f.oportunidade_id,
        oportunidade=f.oportunidade.nome, grupo=f.oportunidade.grupo.nome if f.oportunidade.grupo else None,
        regra=f.regra.value, competencia=f.competencia, base=f.base, calculado=f.calculado,
        valor_aprovado=f.valor_aprovado, situacao=f.situacao.value, decidido_por=f.decidido_por,
        decidido_em=f.decidido_em, pago_em=f.pago_em, motivo=f.motivo,
    )


def _indicacoes_por_parceiro(sessao: Session) -> dict[int, list[Oportunidade]]:
    por = defaultdict(list)
    for o in sessao.scalars(sa.select(Oportunidade).where(Oportunidade.parceiro_id.is_not(None))):
        por[o.parceiro_id].append(o)
    return por


def _resumos(sessao: Session, busca: str | None, nivel: list[NivelDeParceiro] | None,
             acordo: list[AcordoDoParceiro] | None, periodo: regras.Periodo, hoje: date) -> list[regras.ResumoDoParceiro]:
    consulta = sa.select(Parceiro).order_by(Parceiro.nome)
    if busca:
        consulta = consulta.where(Parceiro.nome.ilike(f"%{busca.strip()}%"))
    if nivel:
        consulta = consulta.where(Parceiro.nivel.in_(nivel))
    if acordo:
        consulta = consulta.where(Parceiro.acordo.in_(acordo))
    por = _indicacoes_por_parceiro(sessao)
    return [regras.resumir(p, por.get(p.id, []), periodo, hoje) for p in sessao.scalars(consulta)]


def _resposta(r: regras.ResumoDoParceiro) -> ParceiroResumo:
    return ParceiroResumo(
        id=r.id, nome=r.nome, tipo_pessoa=r.tipo_pessoa, nivel=r.nivel, acordo=r.acordo, etapa=r.etapa.value,
        socio_responsavel=r.socio_responsavel, indicacoes=r.quantas, abertas=r.abertas, fechadas=r.fechadas,
        mrr=r.mrr, pontual=r.pontual,
        proximo_follow_up=r.proximo_follow_up, proximo_follow_up_em=r.proximo_follow_up_em,
    )


def _fees_a_aprovar(sessao: Session) -> list[FeeDeParceiro]:
    return list(sessao.scalars(
        sa.select(FeeDeParceiro).where(FeeDeParceiro.situacao == SituacaoDoFee.A_APROVAR)
        .order_by(FeeDeParceiro.competencia, FeeDeParceiro.id)
    ))


def _documento(texto: str | None) -> str | None:
    if texto is None:
        return None
    digitos = "".join(c for c in texto if c.isdigit())
    return digitos or None


def _detalhe(sessao: Session, p: Parceiro, hoje: date) -> ParceiroDetalhe:
    indicacoes = list(sessao.scalars(
        sa.select(Oportunidade).where(Oportunidade.parceiro_id == p.id)
        .order_by(Oportunidade.indicacao_recebida_em.desc().nulls_last(), Oportunidade.data_colocacao.desc().nulls_last())
    ))
    fees = sessao.scalars(sa.select(FeeDeParceiro).where(FeeDeParceiro.parceiro_id == p.id)
                          .order_by(FeeDeParceiro.competencia.desc(), FeeDeParceiro.id.desc()))
    return ParceiroDetalhe(
        id=p.id, nome=p.nome, tipo_pessoa=p.tipo_pessoa.value, documento=p.documento, tipo=p.tipo, nivel=p.nivel.value,
        etapa=regras.etapa_do_parceiro(p.etapa_manual, p.acordo, indicacoes, hoje).value,
        etapa_manual=p.etapa_manual.value, acordo=p.acordo.value, contrato_assinado_em=p.contrato_assinado_em,
        regra_combinada=p.regra_combinada, combinado_por=p.combinado_por, combinado_em=p.combinado_em,
        socio_responsavel=p.socio_responsavel, perfil_pedido=p.perfil_pedido, contato=p.contato,
        observacao=p.observacao, textos_do_canal=list(p.textos_do_canal or []),
        indicacoes=[
            IndicacaoDoParceiro(
                oportunidade_id=o.id, nome=o.nome, grupo=o.grupo.nome if o.grupo else None, grupo_id=o.grupo_id,
                situacao=o.situacao.value, recebida_em=regras.data_da_indicacao(o), validada_em=o.indicacao_validada_em,
                recusada=o.indicacao_recusada.value if o.indicacao_recusada else None, vinculo_ate=regras.vinculo_ate(o),
                mensal=o.preco_mensal, anual=o.preco_anual, mrr=regras.mrr_da_indicacao(o),
            )
            for o in indicacoes
        ],
        fees=[_fee(f) for f in fees],
        proximo_follow_up=p.proximo_follow_up, proximo_follow_up_em=p.proximo_follow_up_em,
        cadencia_meses=regras.MESES_DE_CADENCIA[p.nivel],
        follow_ups=[FollowUpResposta(id=f.id, feito_em=f.feito_em, resultado=f.resultado.value, nota=f.nota,
                                     registrado_por=f.registrado_por)
                    for f in sessao.scalars(sa.select(FollowUpDeParceiro).where(FollowUpDeParceiro.parceiro_id == p.id)
                                            .order_by(FollowUpDeParceiro.feito_em.desc(), FollowUpDeParceiro.id.desc()))],
    )


def _alertas(sessao: Session, grupo: GrupoEconomico, parceiro: Parceiro) -> list[AlertaDaIndicacao]:
    """Cláusula 2.2: já cliente, já em negociação ou já apresentada por outro. Só avisa; quem decide é a validação."""
    alertas = []
    ativo = sessao.scalar(sa.select(sa.func.count()).select_from(Contrato).where(
        Contrato.grupo_id == grupo.id, Contrato.situacao == SituacaoContrato.ATIVO))
    if ativo or grupo.situacao is SituacaoGrupo.CLIENTE:
        alertas.append(AlertaDaIndicacao(
            tipo="ja_cliente", motivo_sugerido=MotivoDeIndicacaoRecusada.JA_CLIENTE.value,
            texto=f"{grupo.nome} já é cliente da Critério."))
    for o in sessao.scalars(sa.select(Oportunidade).where(Oportunidade.grupo_id == grupo.id)):
        if o.parceiro_id is not None and o.parceiro_id != parceiro.id and o.indicacao_recusada is None:
            outro = sessao.get(Parceiro, o.parceiro_id)
            alertas.append(AlertaDaIndicacao(
                tipo="outro_parceiro", motivo_sugerido=MotivoDeIndicacaoRecusada.OUTRO_PARCEIRO.value,
                texto=f"\"{o.nome}\" já foi indicada por {outro.nome if outro else 'outro parceiro'}"
                      f"{f' em {regras.data_da_indicacao(o):%d/%m/%Y}' if regras.data_da_indicacao(o) else ''}."))
        elif not o.situacao.decidida and o.parceiro_id is None:
            desde = o.data_colocacao
            alertas.append(AlertaDaIndicacao(
                tipo="em_negociacao", motivo_sugerido=MotivoDeIndicacaoRecusada.EM_NEGOCIACAO.value,
                texto=f"\"{o.nome}\" está em {o.situacao.value.lower()}{f' desde {desde:%d/%m/%Y}' if desde else ''}."))
    return alertas


def _fim_do_mes(mes: str) -> tuple[date, date]:
    try:
        ano, m = (int(x) for x in mes.split("-"))
        inicio = date(ano, m, 1)
    except ValueError as falha:
        raise HTTPException(422, "mês no formato AAAA-MM") from falha
    fim = (date(ano + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)
    return inicio, fim


def _relatorio(sessao: Session, p: Parceiro, mes: str) -> RelatorioDoParceiro:
    inicio, fim = _fim_do_mes(mes)
    linhas = sessao.execute(
        sa.select(Oportunidade, GrupoEconomico.nome).join(GrupoEconomico, GrupoEconomico.id == Oportunidade.grupo_id)
        .where(Oportunidade.parceiro_id == p.id)
    ).all()
    do_periodo = [(o, g) for o, g in linhas if (d := regras.data_da_indicacao(o)) is None or d <= fim]
    do_periodo.sort(key=lambda par: regras.data_da_indicacao(par[0]) or date.min, reverse=True)
    fees = [f for f in sessao.scalars(sa.select(FeeDeParceiro).where(FeeDeParceiro.parceiro_id == p.id)
                                      .order_by(FeeDeParceiro.competencia.desc()))
            if f.situacao is not SituacaoDoFee.RECUSADO and f.competencia <= fim]
    situacao = {SituacaoDoFee.A_APROVAR: "Em aprovação", SituacaoDoFee.APROVADO: "Aprovado, a pagar"}
    return RelatorioDoParceiro(
        parceiro_id=p.id, parceiro=p.nome, contato=p.contato, mes=mes, emitido_em=_hoje(),
        responsavel=p.socio_responsavel,
        indicacoes=len(do_periodo),
        novas_no_mes=sum(1 for o, _ in do_periodo if (d := regras.data_da_indicacao(o)) and inicio <= d <= fim),
        viraram_cliente=sum(1 for o, _ in do_periodo if o.situacao.ganha and o.indicacao_recusada is None),
        fee_pago_no_mes=sum((f.valor_aprovado or f.calculado for f in fees
                             if f.pago_em and inicio <= f.pago_em <= fim), Decimal("0")),
        linhas=[LinhaDoRelatorioResposta(**regras.linha_do_relatorio(o, g, fim, _hoje()).__dict__) for o, g in do_periodo],
        fees=[FeeDoRelatorio(empresa=f.oportunidade.grupo.nome, competencia=f.competencia,
                             valor=f.valor_aprovado or f.calculado,
                             situacao=f"Pago em {f.pago_em:%d/%m/%Y}" if f.pago_em else situacao[f.situacao])
              for f in fees],
    )


def _planilha(resumos: list[regras.ResumoDoParceiro]) -> bytes:
    colunas = ["Parceiro", "PF/PJ", "Nível", "Acordo", "Etapa", "Sócio", "Indicações", "Abertas", "Fechadas",
               "MRR originado", "Pontual", "Próximo follow-up", "Data do follow-up"]
    larguras = [30, 7, 13, 20, 13, 14, 11, 9, 9, 15, 13, 36, 14]
    wb = Workbook()
    ws = wb.active
    ws.title = "Parceiros"
    for col, titulo in enumerate(colunas, start=1):
        c = ws.cell(row=1, column=col, value=titulo)
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="F2F2F2")
        ws.column_dimensions[c.column_letter].width = larguras[col - 1]
    for n, r in enumerate(resumos, start=2):
        for col, valor in enumerate((r.nome, r.tipo_pessoa, r.nivel, r.acordo, r.etapa.value, r.socio_responsavel,
                                     r.quantas, r.abertas, r.fechadas), start=1):
            ws.cell(row=n, column=col, value=valor)
        for col, valor in ((10, r.mrr), (11, r.pontual)):
            ws.cell(row=n, column=col, value=float(valor)).number_format = "R$ #,##0.00"
        ws.cell(row=n, column=12, value=r.proximo_follow_up)
        ws.cell(row=n, column=13, value=r.proximo_follow_up_em).number_format = "DD/MM/YYYY"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:M{max(len(resumos) + 1, 1)}"
    saida = io.BytesIO()
    wb.save(saida)
    return saida.getvalue()


# ------------------------------------------------------------------ rotas

def roteador_de_parceiros(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["parceiros"])
    Sessao = Depends(obter_sessao, scope="function")

    def filtros(
        busca: str | None = None,
        nivel: list[NivelDeParceiro] | None = Query(default=None),
        acordo: list[AcordoDoParceiro] | None = Query(default=None),
        data_tipo: Literal["indicacao", "fechamento"] = "indicacao",
        data_de: date | None = None,
        data_ate: date | None = None,
        hoje: date | None = None,
    ) -> dict:
        return {"busca": busca, "nivel": nivel, "acordo": acordo,
                "periodo": regras.Periodo(data_de, data_ate, data_tipo), "hoje": hoje or _hoje()}

    @r.get("/api/parceiros", response_model=list[ParceiroResumo])
    def listar(f: dict = Depends(filtros), sessao: Session = Sessao) -> list[ParceiroResumo]:
        return [_resposta(x) for x in _resumos(sessao, **f)]

    @r.get("/api/parceiros/exportar")
    def exportar(f: dict = Depends(filtros), sessao: Session = Sessao) -> Response:
        return Response(
            _planilha(_resumos(sessao, **f)),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="parceiros-{date.today():%Y-%m-%d}.xlsx"'},
        )

    @r.get("/api/parceiros/indicadores", response_model=IndicadoresDosParceiros)
    def ver_indicadores(f: dict = Depends(filtros), sessao: Session = Sessao) -> IndicadoresDosParceiros:
        fees = _fees_a_aprovar(sessao)
        valores = regras.indicadores(_resumos(sessao, **f), fees, f["hoje"])
        return IndicadoresDosParceiros(**valores, fees_quantos=len(fees), explicacoes=regras.INDICADORES)

    @r.get("/api/parceiros/indicadores/composicao", response_model=list[ItemDaComposicaoResposta])
    def ver_composicao(
        indicador: Literal["ativos", "indicacoes", "conversao", "mrr", "sem_contrato", "fees", "sem_follow_up"],
        f: dict = Depends(filtros), sessao: Session = Sessao,
    ) -> list[ItemDaComposicaoResposta]:
        itens = regras.composicao(indicador, _resumos(sessao, **f), _fees_a_aprovar(sessao), f["hoje"])
        return [ItemDaComposicaoResposta(parceiro=i.parceiro, detalhe=i.detalhe, valor=i.valor, referencia=i.referencia)
                for i in itens]

    # conferência: os textos de canal antigos, sem parceiro
    @r.get("/api/parceiros/conferencia", response_model=list[TextoSemParceiro])
    def conferencia(sessao: Session = Sessao) -> list[TextoSemParceiro]:
        linhas = sessao.execute(
            sa.select(Oportunidade.canal, Oportunidade.tipo_canal, sa.func.count())
            .where(Oportunidade.parceiro_id.is_(None), Oportunidade.tipo_canal.in_(CANAIS_DE_PARCEIRO),
                   Oportunidade.canal.is_not(None), Oportunidade.canal != "")
            .group_by(Oportunidade.canal, Oportunidade.tipo_canal)
            .order_by(sa.func.count().desc(), Oportunidade.canal)
        ).all()
        sugestoes: dict[str, int] = {}
        for p in sessao.scalars(sa.select(Parceiro)):
            for t in [p.nome, *(p.textos_do_canal or [])]:
                sugestoes.setdefault(t.strip().casefold(), p.id)
        return [TextoSemParceiro(texto=t, tipo_canal=tc.value, oportunidades=n,
                                 sugestao_id=sugestoes.get(t.strip().casefold())) for t, tc, n in linhas]

    @r.post("/api/parceiros/conferencia", response_model=ParceiroDetalhe)
    def ligar_texto(corpo: LigarTexto, sessao: Session = Sessao) -> ParceiroDetalhe:
        """Liga ao parceiro todas as oportunidades sem parceiro com aquele texto de canal. A data da indicação fica a
        da originação; a validação fica em branco, para o sócio confirmar o que já tinha vínculo."""
        p = sessao.get(Parceiro, corpo.parceiro_id)
        if p is None:
            raise HTTPException(404, "Parceiro não encontrado")
        oportunidades = list(sessao.scalars(
            sa.select(Oportunidade).where(Oportunidade.parceiro_id.is_(None), Oportunidade.canal == corpo.texto,
                                          Oportunidade.tipo_canal.in_(CANAIS_DE_PARCEIRO))
        ))
        if not oportunidades:
            raise HTTPException(404, "Nenhuma oportunidade sem parceiro com esse texto de canal")
        for o in oportunidades:
            o.parceiro_id = p.id
            o.indicacao_recebida_em = o.indicacao_recebida_em or o.data_colocacao
        if corpo.texto not in (p.textos_do_canal or []):
            p.textos_do_canal = [*(p.textos_do_canal or []), corpo.texto]
        sessao.flush()
        return _detalhe(sessao, p, _hoje())

    @r.get("/api/parceiros/nomes", response_model=list[ParceiroNome])
    def nomes(sessao: Session = Sessao) -> list[ParceiroNome]:
        """A lista de parceiros para o campo Canal da oportunidade e do lead, sem exigir acesso ao Funil de Parceiros."""
        return [ParceiroNome(id=p.id, nome=p.nome, tipo=p.tipo)
                for p in sessao.scalars(sa.select(Parceiro).order_by(Parceiro.nome))]

    @r.get("/api/parceiros/oportunidades", response_model=list[OportunidadeEncontrada])
    def buscar_oportunidades(busca: str = Query(min_length=2), sessao: Session = Sessao) -> list[OportunidadeEncontrada]:
        """Para ligar uma indicação: busca pelo nome da oportunidade ou do grupo, sem exigir acesso ao Funil."""
        termo = f"%{busca.strip()}%"
        linhas = sessao.execute(
            sa.select(Oportunidade, GrupoEconomico.nome, Parceiro.nome)
            .join(GrupoEconomico, GrupoEconomico.id == Oportunidade.grupo_id)
            .outerjoin(Parceiro, Parceiro.id == Oportunidade.parceiro_id)
            .where(sa.or_(Oportunidade.nome.ilike(termo), GrupoEconomico.nome.ilike(termo)))
            .order_by(Oportunidade.data_colocacao.desc().nulls_last(), Oportunidade.id.desc())
            .limit(20)
        ).all()
        return [OportunidadeEncontrada(id=o.id, nome=o.nome, grupo=g, situacao=o.situacao.value, canal=o.canal, parceiro=pn)
                for o, g, pn in linhas]

    # fees
    @r.get("/api/parceiros/fees", response_model=list[FeeResposta])
    def listar_fees(situacao: list[SituacaoDoFee] | None = Query(default=None), sessao: Session = Sessao) -> list[FeeResposta]:
        consulta = sa.select(FeeDeParceiro).order_by(FeeDeParceiro.competencia.desc(), FeeDeParceiro.id.desc())
        if situacao:
            consulta = consulta.where(FeeDeParceiro.situacao.in_(situacao))
        return [_fee(f) for f in sessao.scalars(consulta)]

    @r.post("/api/parceiros/fees/calcular", response_model=ResultadoDoCalculo)
    def calcular(sessao: Session = Sessao) -> ResultadoDoCalculo:
        """Cria, como "A aprovar", os fees que faltam nas indicações fechadas, pelos recebidos importados do Omie."""
        novos = 0
        indicacoes = sessao.scalars(sa.select(Oportunidade).where(Oportunidade.parceiro_id.is_not(None)))
        for o in indicacoes:
            if not o.situacao.ganha:
                continue
            recebidos = sessao.execute(
                sa.select(Recebimento.competencia, sa.func.sum(Recebimento.valor))
                .where(Recebimento.grupo_id == o.grupo_id, Recebimento.ativo.is_(True))
                .group_by(Recebimento.competencia)
            ).all()
            ja = set(sessao.scalars(sa.select(FeeDeParceiro.competencia).where(FeeDeParceiro.oportunidade_id == o.id)))
            for c in regras.calcular_fees(o, [(c, Decimal(v)) for c, v in recebidos], ja):
                sessao.add(FeeDeParceiro(parceiro_id=o.parceiro_id, oportunidade_id=o.id, regra=c.regra,
                                         competencia=c.competencia, base=c.base, calculado=c.calculado))
                novos += 1
        sessao.flush()
        return ResultadoDoCalculo(novos=novos)

    def _fee_ou_404(sessao: Session, fee_id: int) -> FeeDeParceiro:
        f = sessao.get(FeeDeParceiro, fee_id)
        if f is None:
            raise HTTPException(404, "Fee não encontrado")
        return f

    @r.post("/api/parceiros/fees/{fee_id}/aprovar", response_model=FeeResposta)
    def aprovar(fee_id: int, corpo: Aprovacao, sessao: Session = Sessao) -> FeeResposta:
        f = _fee_ou_404(sessao, fee_id)
        if f.situacao is not SituacaoDoFee.A_APROVAR:
            raise HTTPException(409, f"Este fee já está {f.situacao.value.lower()}")
        f.situacao, f.valor_aprovado = SituacaoDoFee.APROVADO, corpo.valor.quantize(Decimal("0.01"))
        f.decidido_por, f.decidido_em = quem_fez(None), agora()
        sessao.flush()
        return _fee(f)

    @r.post("/api/parceiros/fees/{fee_id}/recusar", response_model=FeeResposta)
    def recusar(fee_id: int, corpo: Recusa, sessao: Session = Sessao) -> FeeResposta:
        f = _fee_ou_404(sessao, fee_id)
        if f.situacao is not SituacaoDoFee.A_APROVAR:
            raise HTTPException(409, f"Este fee já está {f.situacao.value.lower()}")
        f.situacao, f.motivo = SituacaoDoFee.RECUSADO, corpo.motivo
        f.decidido_por, f.decidido_em = quem_fez(None), agora()
        sessao.flush()
        return _fee(f)

    @r.post("/api/parceiros/fees/{fee_id}/pago", response_model=FeeResposta)
    def pagar(fee_id: int, corpo: Pagamento, sessao: Session = Sessao) -> FeeResposta:
        f = _fee_ou_404(sessao, fee_id)
        if f.situacao is not SituacaoDoFee.APROVADO:
            raise HTTPException(409, "Só fee aprovado pode ser marcado pago")
        f.situacao, f.pago_em = SituacaoDoFee.PAGO, corpo.pago_em
        sessao.flush()
        return _fee(f)

    # relatório mensal ao parceiro
    @r.get("/api/parceiros/relatorios", response_model=list[RelatorioDoParceiro])
    def relatorios(mes: str, sessao: Session = Sessao) -> list[RelatorioDoParceiro]:
        """Os relatórios do mês de todos os parceiros com alguma indicação até o fim do mês, um por página."""
        saida = []
        for p in sessao.scalars(sa.select(Parceiro).order_by(Parceiro.nome)):
            rel = _relatorio(sessao, p, mes)
            if rel.indicacoes:
                saida.append(rel)
        return saida

    @r.get("/api/parceiros/{parceiro_id}/relatorio", response_model=RelatorioDoParceiro)
    def relatorio(parceiro_id: int, mes: str, sessao: Session = Sessao) -> RelatorioDoParceiro:
        return _relatorio(sessao, _parceiro_ou_404(sessao, parceiro_id), mes)

    @r.get("/api/parceiros/{parceiro_id}/alertas", response_model=list[AlertaDaIndicacao])
    def alertas(parceiro_id: int, empresa_id: int, sessao: Session = Sessao) -> list[AlertaDaIndicacao]:
        p = _parceiro_ou_404(sessao, parceiro_id)
        e = sessao.get(Empresa, empresa_id)
        if e is None:
            raise HTTPException(404, "Empresa não encontrada")
        return _alertas(sessao, e.grupo, p)

    @r.post("/api/parceiros/{parceiro_id}/indicacoes/registrar", response_model=ParceiroDetalhe, status_code=201)
    def registrar(parceiro_id: int, corpo: IndicacaoRegistrada, sessao: Session = Sessao) -> ParceiroDetalhe:
        """Cria a oportunidade no Funil comercial em "Enviar proposta", com Tipo de canal Parceiros, o parceiro ligado e
        a data da indicação. A validação fica para o sócio."""
        p = _parceiro_ou_404(sessao, parceiro_id)
        if not corpo.autorizado_pelo_cliente:
            raise HTTPException(422, "Sem a autorização do cliente para o contato (LGPD), a indicação não entra")
        if (corpo.empresa_id is None) == (corpo.empresa_nova is None):
            raise HTTPException(422, "Escolha uma empresa da base ou cadastre uma nova")
        if corpo.empresa_id is not None:
            empresa = sessao.get(Empresa, corpo.empresa_id)
            if empresa is None:
                raise HTTPException(404, "Empresa não encontrada")
            grupo = empresa.grupo
        else:
            nome = " ".join(corpo.empresa_nova.nome.split())
            cnpj = _documento(corpo.empresa_nova.cnpj)
            if cnpj is not None:
                if not cnpj_valido(cnpj):
                    raise HTTPException(422, "CNPJ inválido")
                if sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == cnpj)) is not None:
                    raise HTTPException(409, "Este CNPJ já está na base: escolha a empresa na busca")
            grupo = sessao.scalar(sa.select(GrupoEconomico).where(
                sa.func.lower(GrupoEconomico.nome) == nome.casefold(), GrupoEconomico.fundido_em_id.is_(None)))
            if grupo is None:
                grupo = GrupoEconomico(nome=nome, situacao=SituacaoGrupo.PROSPECT, origem=Origem.CRM)
                sessao.add(grupo)
                sessao.flush()
            empresa = Empresa(grupo_id=grupo.id, razao_social=nome, cnpj=cnpj)
            sessao.add(empresa)
            sessao.flush()
        recebida = corpo.recebida_em or _hoje()
        contato = " · ".join(x for x in (corpo.contato_nome, corpo.contato_meio) if x)
        registro = (f"Indicada por {p.nome} em {recebida:%d/%m/%Y}. O cliente autorizou o contato da Critério (LGPD); "
                    f"registrado por {quem_fez(None) or 'quem usou a tela'} em {_hoje():%d/%m/%Y}.")
        sessao.add(Oportunidade(
            grupo_id=grupo.id, empresa_id=empresa.id, nome=f"{corpo.servico} — {empresa.nome_fantasia or empresa.razao_social}",
            servico=corpo.servico, linha_servico=linha_do_servico(corpo.servico), situacao=Situacao.ENVIAR_PROPOSTA,
            tipo_canal=TipoCanal.PARCEIROS, canal=p.nome, data_colocacao=recebida, origem=Origem.CRM,
            parceiro_id=p.id, indicacao_recebida_em=recebida,
            observacao=f"{registro}\nContato indicado: {contato}" if contato else registro,
        ))
        sessao.flush()
        return _detalhe(sessao, p, _hoje())

    # cadastro
    def _parceiro_ou_404(sessao: Session, parceiro_id: int) -> Parceiro:
        p = sessao.get(Parceiro, parceiro_id)
        if p is None:
            raise HTTPException(404, "Parceiro não encontrado")
        return p

    def _nome_livre(sessao: Session, nome: str, menos: int | None = None) -> None:
        existente = sessao.scalar(sa.select(Parceiro).where(sa.func.lower(Parceiro.nome) == nome.strip().lower()))
        if existente is not None and existente.id != menos:
            raise HTTPException(409, f"Já existe um parceiro chamado {existente.nome}")

    @r.post("/api/parceiros", response_model=ParceiroDetalhe, status_code=201)
    def criar(corpo: ParceiroEntrada, sessao: Session = Sessao) -> ParceiroDetalhe:
        _nome_livre(sessao, corpo.nome)
        if not corpo.etapa_manual.manual:
            raise HTTPException(422, "A etapa marcada à mão só pode ser Mapeado, Qualificado ou Estratégico")
        dados = corpo.model_dump()
        dados["nome"], dados["documento"] = corpo.nome.strip(), _documento(corpo.documento)
        p = Parceiro(**dados, textos_do_canal=[])
        sessao.add(p)
        sessao.flush()
        return _detalhe(sessao, p, _hoje())

    @r.get("/api/parceiros/{parceiro_id}", response_model=ParceiroDetalhe)
    def ver(parceiro_id: int, sessao: Session = Sessao) -> ParceiroDetalhe:
        return _detalhe(sessao, _parceiro_ou_404(sessao, parceiro_id), _hoje())

    @r.patch("/api/parceiros/{parceiro_id}", response_model=ParceiroDetalhe)
    def editar(parceiro_id: int, corpo: ParceiroEdicao, sessao: Session = Sessao) -> ParceiroDetalhe:
        p = _parceiro_ou_404(sessao, parceiro_id)
        mudancas = corpo.model_dump(exclude_unset=True)
        if "nome" in mudancas:
            _nome_livre(sessao, mudancas["nome"], p.id)
            mudancas["nome"] = mudancas["nome"].strip()
        if "documento" in mudancas:
            mudancas["documento"] = _documento(mudancas["documento"])
        if "etapa_manual" in mudancas and not mudancas["etapa_manual"].manual:
            raise HTTPException(422, "A etapa marcada à mão só pode ser Mapeado, Qualificado ou Estratégico")
        for campo, valor in mudancas.items():
            if campo in {"nome", "tipo_pessoa", "nivel", "etapa_manual", "acordo"} and valor is None:
                continue
            setattr(p, campo, valor)
        sessao.flush()
        return _detalhe(sessao, p, _hoje())

    @r.post("/api/parceiros/{parceiro_id}/follow-ups", response_model=ParceiroDetalhe, status_code=201)
    def registrar_follow_up(parceiro_id: int, corpo: FollowUpEntrada, sessao: Session = Sessao) -> ParceiroDetalhe:
        """Grava o follow-up feito no histórico e marca o próximo. Sem próximo informado, fica o que já estava."""
        p = _parceiro_ou_404(sessao, parceiro_id)
        sessao.add(FollowUpDeParceiro(parceiro_id=p.id, feito_em=corpo.feito_em, resultado=corpo.resultado,
                                      nota=(corpo.nota or "").strip() or None, registrado_por=quem_fez(None)))
        if corpo.proximo_follow_up is not None or corpo.proximo_follow_up_em is not None:
            p.proximo_follow_up = (corpo.proximo_follow_up or "").strip() or None
            p.proximo_follow_up_em = corpo.proximo_follow_up_em
        sessao.flush()
        return _detalhe(sessao, p, _hoje())

    @r.post("/api/parceiros/{parceiro_id}/etapa", response_model=ParceiroDetalhe)
    def mover(parceiro_id: int, corpo: EtapaEntrada, sessao: Session = Sessao) -> ParceiroDetalhe:
        """O arrasto do Kanban. Só as etapas manuais aceitam; as outras mudam sozinhas pelos dados."""
        p = _parceiro_ou_404(sessao, parceiro_id)
        if not corpo.etapa.manual:
            raise HTTPException(
                422, f"{corpo.etapa.value} muda sozinha pelos dados: contrato assinado, indicação validada, proposta "
                     "enviada ou seis meses sem indicação. À mão, só Mapeado, Qualificado e Estratégico.")
        p.etapa_manual = corpo.etapa
        sessao.flush()
        detalhe = _detalhe(sessao, p, _hoje())
        if detalhe.etapa != corpo.etapa.value:
            raise HTTPException(
                409, f"Ficou marcado {corpo.etapa.value}, mas os dados mantêm {p.nome} em {detalhe.etapa}.")
        return detalhe

    @r.post("/api/parceiros/{parceiro_id}/indicacoes", response_model=ParceiroDetalhe)
    def ligar_indicacao(parceiro_id: int, corpo: IndicacaoEntrada, sessao: Session = Sessao) -> ParceiroDetalhe:
        p = _parceiro_ou_404(sessao, parceiro_id)
        o = sessao.get(Oportunidade, corpo.oportunidade_id)
        if o is None:
            raise HTTPException(404, "Oportunidade não encontrada")
        if o.parceiro_id is not None and o.parceiro_id != p.id:
            outro = sessao.get(Parceiro, o.parceiro_id)
            raise HTTPException(409, f"Essa oportunidade já foi indicada por {outro.nome if outro else 'outro parceiro'}")
        o.parceiro_id = p.id
        o.indicacao_recebida_em = corpo.recebida_em or o.indicacao_recebida_em or o.data_colocacao or date.today()
        o.indicacao_validada_em = corpo.validada_em
        if o.tipo_canal is None:
            o.tipo_canal, o.canal = TipoCanal.PARCEIROS, o.canal or p.nome
        sessao.flush()
        return _detalhe(sessao, p, _hoje())

    @r.patch("/api/parceiros/indicacoes/{oportunidade_id}", response_model=ParceiroDetalhe)
    def editar_indicacao(oportunidade_id: int, corpo: IndicacaoEdicao, sessao: Session = Sessao) -> ParceiroDetalhe:
        o = sessao.get(Oportunidade, oportunidade_id)
        if o is None or o.parceiro_id is None:
            raise HTTPException(404, "Indicação não encontrada")
        for campo, valor in corpo.model_dump(exclude_unset=True).items():
            setattr(o, {"recebida_em": "indicacao_recebida_em", "validada_em": "indicacao_validada_em",
                        "recusada": "indicacao_recusada"}[campo], valor)
        sessao.flush()
        return _detalhe(sessao, sessao.get(Parceiro, o.parceiro_id), _hoje())

    @r.post("/api/parceiros/indicacoes/{oportunidade_id}/desligar", response_model=ParceiroDetalhe)
    def desligar(oportunidade_id: int, sessao: Session = Sessao) -> ParceiroDetalhe:
        """Desfaz a ligação feita por engano. Indicação com fee calculado não se desliga: o fee guarda o vínculo."""
        o = sessao.get(Oportunidade, oportunidade_id)
        if o is None or o.parceiro_id is None:
            raise HTTPException(404, "Indicação não encontrada")
        if sessao.scalar(sa.select(sa.func.count()).select_from(FeeDeParceiro)
                         .where(FeeDeParceiro.oportunidade_id == o.id)):
            raise HTTPException(409, "Esta indicação já tem fee calculado. Recuse o fee em vez de desligar.")
        p = sessao.get(Parceiro, o.parceiro_id)
        o.parceiro_id = None
        o.indicacao_validada_em = o.indicacao_recusada = None
        sessao.flush()
        return _detalhe(sessao, p, _hoje())

    return r
