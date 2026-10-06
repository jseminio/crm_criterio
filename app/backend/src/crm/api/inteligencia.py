"""Funil comercial › Inteligência de Conversão (aprovado por Eduardo em 03/10/2026), Entrega 1: a
meta líquida, o plano por motor (previsto, realizado e ajuste) e as premissas, que só o
Administrador muda (permissão "Configurações: metas") e vão para o histórico de alterações. Os
cenários de ticket saem da aba Oportunidades e passam a ser por serviço. Regras em
`crm.domain.plano_de_mrr`."""

from __future__ import annotations

import calendar
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from math import ceil
from statistics import median
from typing import Literal
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.api import sucesso
from crm.api.acesso import quem_fez
from crm.api.classificacao import parametros_vigentes
from crm.db.base import agora
from crm.db.modelos import (
    Contrato, ContratoPrevistoDoPlano, InvestimentoEmMidia, Lead, Oportunidade, PlanoDeMrr,
)
from crm.domain import fases_do_cliente as fases
from crm.domain import mrr as regras_de_mrr
from crm.domain import plano_de_mrr as regras
from crm.domain.listas import AderenciaDaPromessa, MotivoDeDescarte, MotivoRecusa, TipoCanal, TipoDeEventoDeContrato
from crm.domain.recortes import cenarios_de_ticket

__all__ = ["montar_fases", "premissas_vigentes", "roteador_de_inteligencia"]

D = Decimal
ZERO = D("0")
_CAMPOS = (
    "meta_liquida", "inicio", "fim", "inicio_da_projecao", "ponto_de_partida", "mrr_de_partida", "churn_anual_pct",
    "bpo_ticket", "bpo_teto", "contabil_vagas", "atipico_vagas", "escada_prazo_meses", "plus_acrescimo", "plus_pct",
    "cfo_acrescimo", "cfo_pct",
    # as quatro fases (04/10/2026): opcionais
    "taxa_lead_reuniao_pct", "taxa_reuniao_proposta_pct", "taxa_conversao_pct", "icp_alvo_pct", "indicacoes_por_mes",
    "primeiro_contato_horas", "ciclo_alvo_dias", "aderencia_alvo_pct",
)


def premissas_vigentes(sessao: Session) -> tuple[regras.Premissas, PlanoDeMrr | None]:
    """As premissas gravadas, ou as padrão de `PADRAO`; os contratos previstos vêm sempre da tabela."""
    linha = sessao.get(PlanoDeMrr, 1)
    previstos = tuple(
        regras.ContratoPrevisto(c.descricao, c.mes, c.valor, c.atipico)
        for c in sessao.scalars(sa.select(ContratoPrevistoDoPlano).order_by(ContratoPrevistoDoPlano.mes, ContratoPrevistoDoPlano.id))
    )
    if linha is None:
        p = regras.PADRAO
        return regras.Premissas(**{**{k: getattr(p, k) for k in regras.Premissas.__dataclass_fields__}, "contratos_previstos": previstos}), None
    cenario = lambda n: regras.Cenario(
        getattr(linha, f"{n}_bpo_por_mes"), getattr(linha, f"{n}_ticket_contabil"), getattr(linha, f"{n}_com_previstos"),
    )
    return regras.Premissas(
        **{k: getattr(linha, k) for k in _CAMPOS},
        alerta=cenario("alerta"), previsto=cenario("previsto"), otimista=cenario("otimista"),
        contratos_previstos=previstos,
    ), linha


# ---------------------------------------------------------------- esquemas

class CenarioPremissa(BaseModel):
    bpo_por_mes: Decimal = Field(ge=0)
    ticket_contabil: Decimal = Field(ge=0)
    com_contratos_previstos: bool


class ContratoPrevistoPremissa(BaseModel):
    descricao: str = Field(min_length=1, max_length=120)
    mes: date
    valor: Decimal = Field(gt=0)
    atipico: bool = False


class PremissasDoPlano(BaseModel):
    meta_liquida: Decimal = Field(gt=0)
    inicio: date
    fim: date
    inicio_da_projecao: date
    ponto_de_partida: Decimal = Field(ge=0)
    mrr_de_partida: Decimal = Field(ge=0)
    churn_anual_pct: Decimal = Field(ge=0, le=100)
    bpo_ticket: Decimal = Field(ge=0)
    bpo_teto: Decimal = Field(ge=0)
    contabil_vagas: Decimal = Field(ge=0)
    atipico_vagas: Decimal = Field(ge=1)
    escada_prazo_meses: int = Field(ge=1, le=24)
    plus_acrescimo: Decimal = Field(ge=0)
    plus_pct: Decimal = Field(ge=0, le=100)
    cfo_acrescimo: Decimal = Field(ge=0)
    cfo_pct: Decimal = Field(ge=0, le=100)
    alerta: CenarioPremissa
    previsto: CenarioPremissa
    otimista: CenarioPremissa
    contratos_previstos: list[ContratoPrevistoPremissa] = Field(default_factory=list, max_length=50)
    taxa_lead_reuniao_pct: Decimal | None = Field(default=None, gt=0, le=100)
    taxa_reuniao_proposta_pct: Decimal | None = Field(default=None, gt=0, le=100)
    taxa_conversao_pct: Decimal | None = Field(default=None, gt=0, le=100)
    icp_alvo_pct: Decimal | None = Field(default=None, gt=0, le=100)
    indicacoes_por_mes: Decimal | None = Field(default=None, ge=0)
    primeiro_contato_horas: Decimal | None = Field(default=None, gt=0)
    ciclo_alvo_dias: Decimal | None = Field(default=None, gt=0)
    aderencia_alvo_pct: Decimal | None = Field(default=None, gt=0, le=100)


class PremissasResposta(PremissasDoPlano):
    alterado_por: str | None = None
    alterado_em: datetime | None = None


class LinhaPrevistaResposta(BaseModel):
    mes: date
    contabil: Decimal
    bpo: Decimal
    escada: Decimal
    churn: Decimal
    acumulado: Decimal
    contratos_bpo: Decimal
    contratos_contabil: Decimal


class CenarioResposta(BaseModel):
    nome: Literal["alerta", "previsto", "otimista"]
    contabil: Decimal
    bpo: Decimal
    escada: Decimal
    churn: Decimal
    bruto: Decimal
    liquido: Decimal
    percentual_da_meta: Decimal | None
    linhas: list[LinhaPrevistaResposta]


class LinhaRealizadaResposta(BaseModel):
    mes: date
    novo_contabil: Decimal
    novo_bpo: Decimal
    escada: Decimal
    outros: Decimal
    perdas: Decimal
    acumulado: Decimal
    contratos_contabil: int
    contratos_bpo: int


class SituacaoResposta(BaseModel):
    chave: Literal["no_ritmo", "atencao", "abaixo"]
    percentual: Decimal | None


class MetaResposta(BaseModel):
    meta_liquida: Decimal
    realizado: Decimal
    """Acréscimo líquido do início do plano até hoje."""
    previsto_ate_hoje: Decimal
    """O previsto acumulado, proporcional aos dias corridos do mês."""
    alerta_ate_hoje: Decimal
    situacao: SituacaoResposta
    percentual_da_meta: Decimal
    meses_restantes: int
    ritmo_necessario: Decimal | None
    """Quanto falta para a meta ÷ os meses depois do corrente. `None` sem mês restante."""


class MotorResposta(BaseModel):
    motor: Literal["bpo", "contabil", "escada", "perdas", "outros"]
    rotulo: str
    previsto_no_plano: Decimal | None
    previsto_ate_hoje: Decimal | None
    realizado: Decimal
    situacao: SituacaoResposta | None
    ajuste: str


class PlanoResposta(BaseModel):
    hoje: date
    premissas: PremissasResposta
    meta: MetaResposta
    cenarios: list[CenarioResposta]
    realizado: list[LinhaRealizadaResposta]
    motores: list[MotorResposta]
    aviso: str | None


class CenariosDoServico(BaseModel):
    servico: str
    contratos: int
    contratos_recorrentes: int
    limite_do_atipico: Decimal | None = None
    conservador: Decimal | None = None
    base: Decimal | None = None
    otimista: Decimal | None = None
    atipicos: int = 0
    atipico_minimo: Decimal | None = None
    atipico_medio: Decimal | None = None
    atipico_maximo: Decimal | None = None


# ---------------------------------------------------------------- cálculo

def _proporcional(proj: regras.Projecao, partida: Decimal, hoje: date) -> Decimal:
    """O acumulado previsto em `hoje`: o do mês anterior mais a fração dos dias corridos do mês."""
    mes = hoje.replace(day=1)
    anterior = proj.acumulado_em(date(mes.year - (mes.month == 1), (mes.month - 2) % 12 + 1, 1), partida)
    no_mes = proj.acumulado_em(mes, partida)
    fracao = D(hoje.day) / D(calendar.monthrange(hoje.year, hoje.month)[1])
    return (anterior + (no_mes - anterior) * fracao).quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _do_motor_ate_hoje(proj: regras.Projecao, campo: str, hoje: date) -> Decimal:
    mes = hoje.replace(day=1)
    fracao = D(hoje.day) / D(calendar.monthrange(hoje.year, hoje.month)[1])
    total = ZERO
    for l in proj.linhas:
        if l.mes < mes:
            total += getattr(l, campo)
        elif l.mes == mes:
            total += getattr(l, campo) * fracao
    return total.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def _reais(v: Decimal) -> str:
    inteiro = f"{v.quantize(D('1'), rounding=ROUND_HALF_UP):,.0f}".replace(",", ".")
    return f"R$ {inteiro}"


def _num(v: Decimal) -> str:
    return f"{v.quantize(D('0.1'), rounding=ROUND_HALF_UP)}".replace(".", ",").removesuffix(",0")


def _ajuste_de_volume(falta: Decimal, meses_restantes: int, ticket: Decimal, teto: Decimal, nome_do_teto: str) -> str:
    if falta <= 0:
        return "No ritmo do previsto: nenhum ajuste."
    if meses_restantes <= 0:
        return f"Faltam {_reais(falta)} e o prazo acabou."
    por_mes = falta / meses_restantes
    if ticket <= 0:
        return f"Faltam {_reais(falta)}: {_reais(por_mes)} por mês até o fim do prazo."
    contratos = por_mes / ticket
    texto = f"Faltam {_reais(falta)}: {_num(contratos)} contratos/mês no ticket de {_reais(ticket)} até o fim do prazo"
    if contratos > teto:
        return texto + f", acima do teto de {_num(teto)} ({nome_do_teto}). Precisa de mais capacidade ou de outro motor."
    return texto + f" (teto: {_num(teto)}, {nome_do_teto})."


def montar_plano(sessao: Session, hoje: date) -> PlanoResposta:
    p, linha = premissas_vigentes(sessao)
    projecoes = {n: regras.projetar(p, n) for n in regras.CENARIOS}
    prev = projecoes["previsto"]

    registrados = list(sessao.scalars(sa.select(Contrato)))
    imposto = parametros_vigentes(sessao)[1].imposto
    em_bruto = regras_de_mrr.em_bruto(registrados, imposto)
    motor = {
        c.id: regras.motor_do_contrato(c.oportunidade.servico if c.oportunidade else None, c.escopo) for c in registrados
    }
    por_motor = regras.contratos_por_motor(em_bruto, lambda c: motor[c.id])
    ate = min(hoje, p.fim)
    realizado = regras.realizar(por_motor, p.inicio, ate) if ate >= p.inicio else []
    acumulado = realizado[-1].acumulado if realizado else ZERO

    previsto_ate_hoje = _proporcional(prev, p.ponto_de_partida, ate)
    alerta_ate_hoje = _proporcional(projecoes["alerta"], p.ponto_de_partida, ate)
    mes_corrente = ate.replace(day=1)
    restantes = len(regras.meses(regras._proximo(mes_corrente), p.fim))
    falta = max(p.meta_liquida - acumulado, ZERO)
    meta = MetaResposta(
        meta_liquida=p.meta_liquida,
        realizado=acumulado,
        previsto_ate_hoje=previsto_ate_hoje,
        alerta_ate_hoje=alerta_ate_hoje,
        situacao=SituacaoResposta(**vars(regras.situacao(acumulado, previsto_ate_hoje))),
        percentual_da_meta=(acumulado / p.meta_liquida * 100).quantize(D("0.1")),
        meses_restantes=restantes,
        ritmo_necessario=(falta / restantes).quantize(D("0.01")) if restantes else None,
    )

    soma = lambda campo: sum((getattr(l, campo) for l in realizado), ZERO)
    real_bpo, real_contabil, real_escada = soma("novo_bpo"), soma("novo_contabil"), soma("escada")
    real_perdas, real_outros = soma("perdas"), soma("outros")
    previsto_bpo, previsto_contabil = _do_motor_ate_hoje(prev, "bpo", ate), _do_motor_ate_hoje(prev, "contabil", ate)
    previsto_escada, previsto_churn = _do_motor_ate_hoje(prev, "escada", ate), _do_motor_ate_hoje(prev, "churn", ate)
    sit = lambda r, pv: SituacaoResposta(**vars(regras.situacao(r, pv))) if pv > 0 else None
    perdas_sit = None
    if previsto_churn > 0:
        # Perder menos que o previsto é bom: compara o previsto com o realizado, não o contrário.
        perdas_sit = SituacaoResposta(**vars(regras.situacao(previsto_churn, real_perdas))) if real_perdas > 0 else SituacaoResposta(chave="no_ritmo", percentual=None)
    motores = [
        MotorResposta(
            motor="bpo", rotulo="BPO Financeiro", previsto_no_plano=prev.bpo, previsto_ate_hoje=previsto_bpo,
            realizado=real_bpo, situacao=sit(real_bpo, previsto_bpo),
            ajuste=_ajuste_de_volume(prev.bpo - real_bpo, restantes, p.bpo_ticket, p.bpo_teto, "a célula de BPO"),
        ),
        MotorResposta(
            motor="contabil", rotulo="Contábil", previsto_no_plano=prev.contabil, previsto_ate_hoje=previsto_contabil,
            realizado=real_contabil, situacao=sit(real_contabil, previsto_contabil),
            ajuste=_ajuste_de_volume(
                prev.contabil - real_contabil, restantes, p.previsto.ticket_contabil, p.contabil_vagas, "vagas de onboarding",
            ),
        ),
        MotorResposta(
            motor="escada", rotulo="Escada (upgrade de BPO)", previsto_no_plano=prev.escada, previsto_ate_hoje=previsto_escada,
            realizado=real_escada, situacao=sit(real_escada, previsto_escada),
            ajuste=(
                "A escada começa quando a primeira turma de BPO completar o prazo do upgrade."
                if previsto_escada <= 0 else
                "No ritmo do previsto: nenhum ajuste." if real_escada >= previsto_escada else
                f"Faltam {_reais(previsto_escada - real_escada)} de upgrade: confira as reuniões de resultado dos "
                "clientes de BPO que já completaram o prazo."
            ),
        ),
        MotorResposta(
            motor="perdas", rotulo="Churn e contração", previsto_no_plano=prev.churn, previsto_ate_hoje=previsto_churn,
            realizado=real_perdas, situacao=perdas_sit,
            ajuste=(
                "Dentro da premissa de churn." if real_perdas <= previsto_churn else
                f"Perdas {_reais(real_perdas - previsto_churn)} acima da premissa: veja os encerramentos na Carteira."
            ),
        ),
        MotorResposta(
            motor="outros", rotulo="Reajuste e outras expansões", previsto_no_plano=None, previsto_ate_hoje=None,
            realizado=real_outros, situacao=None,
            ajuste="Fora do plano: entra no realizado, mas não tem previsto.",
        ),
    ]

    premissas = PremissasResposta(
        **{k: getattr(p, k) for k in _CAMPOS},
        alerta=CenarioPremissa(**vars(p.alerta)), previsto=CenarioPremissa(**vars(p.previsto)),
        otimista=CenarioPremissa(**vars(p.otimista)),
        contratos_previstos=[ContratoPrevistoPremissa(**vars(c)) for c in p.contratos_previstos],
        alterado_por=linha.alterado_por if linha else None, alterado_em=linha.alterado_em if linha else None,
    )
    cenarios = [
        CenarioResposta(
            nome=n, contabil=x.contabil, bpo=x.bpo, escada=x.escada, churn=x.churn, bruto=x.bruto, liquido=x.liquido,
            percentual_da_meta=x.percentual_da_meta, linhas=[LinhaPrevistaResposta(**vars(l)) for l in x.linhas],
        )
        for n, x in projecoes.items()
    ]
    da_carteira = any(c.anterior_ao_crm for c in registrados)
    return PlanoResposta(
        hoje=hoje, premissas=premissas, meta=meta, cenarios=cenarios,
        realizado=[LinhaRealizadaResposta(**vars(l)) for l in realizado], motores=motores,
        aviso=None if da_carteira else (
            "A carteira anterior ao CRM não foi carregada: o churn dela não aparece no realizado."
        ),
    )


# ---------------------------------------------------------------- rotas

def roteador_de_inteligencia(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["inteligência de conversão"])

    @r.get("/api/inteligencia/plano", response_model=PlanoResposta)
    def ver(sessao: Session = Depends(obter_sessao, scope="function"), hoje: date | None = None) -> PlanoResposta:
        """O plano de MRR: meta, cenários, realizado mês a mês e o ajuste por motor. `hoje` existe para teste."""
        return montar_plano(sessao, hoje or date.today())

    @r.put("/api/inteligencia/plano", response_model=PlanoResposta)
    def mudar(corpo: PremissasDoPlano, sessao: Session = Depends(obter_sessao, scope="function"), hoje: date | None = None) -> PlanoResposta:
        """Grava as premissas (todas de uma vez) e substitui os contratos previstos."""
        if corpo.fim <= corpo.inicio:
            raise HTTPException(422, "O fim do prazo precisa ser depois do início.")
        if not corpo.inicio <= corpo.inicio_da_projecao <= corpo.fim:
            raise HTTPException(422, "O início da projeção precisa ficar dentro do prazo da meta.")
        for previsto in corpo.contratos_previstos:
            if not corpo.inicio_da_projecao.replace(day=1) <= previsto.mes <= corpo.fim:
                raise HTTPException(422, f"O contrato previsto “{previsto.descricao}” está fora dos meses projetados.")
        valores = {
            **corpo.model_dump(include=set(_CAMPOS)),
            "inicio": corpo.inicio.replace(day=1),
            "inicio_da_projecao": corpo.inicio_da_projecao.replace(day=1),
        }
        for n in regras.CENARIOS:
            c = getattr(corpo, n)
            valores |= {f"{n}_bpo_por_mes": c.bpo_por_mes, f"{n}_ticket_contabil": c.ticket_contabil,
                        f"{n}_com_previstos": c.com_contratos_previstos}
        linha = sessao.get(PlanoDeMrr, 1)
        if linha is None:
            linha = PlanoDeMrr(id=1, **valores)
            sessao.add(linha)
        else:
            for k, v in valores.items():
                setattr(linha, k, v)
        linha.alterado_por = quem_fez("") or None
        linha.alterado_em = agora()
        novos = [(c.descricao.strip(), c.mes.replace(day=1), c.valor, c.atipico) for c in corpo.contratos_previstos]
        atuais = list(sessao.scalars(sa.select(ContratoPrevistoDoPlano).order_by(ContratoPrevistoDoPlano.id)))
        if [(c.descricao, c.mes, c.valor, c.atipico) for c in atuais] != novos:
            for c in atuais:
                sessao.delete(c)
            for descricao, mes, valor, atipico in novos:
                sessao.add(ContratoPrevistoDoPlano(descricao=descricao, mes=mes, valor=valor, atipico=atipico))
        sessao.flush()
        return montar_plano(sessao, hoje or date.today())

    @r.get("/api/inteligencia/cenarios-de-ticket", response_model=list[CenariosDoServico])
    def cenarios_por_servico(sessao: Session = Depends(obter_sessao, scope="function")) -> list[CenariosDoServico]:
        """Os cenários de ticket separados por serviço: o atípico de um serviço não é o de outro."""
        por_servico: dict[str, list[Oportunidade]] = {}
        for o in sessao.scalars(sa.select(Oportunidade)):
            if o.situacao.ganha:
                por_servico.setdefault(o.servico or "Sem serviço", []).append(o)
        lista = []
        for servico, itens in por_servico.items():
            recorrentes = sum(1 for o in itens if o.preco_mensal is not None and o.preco_mensal > 0)
            if not recorrentes:
                continue
            c = cenarios_de_ticket(itens)
            extra = {} if c is None else {
                "limite_do_atipico": c.limite_do_atipico, "conservador": c.conservador, "base": c.base,
                "otimista": c.otimista, "atipicos": c.atipicos, "atipico_minimo": c.atipico_minimo,
                "atipico_medio": c.atipico_medio, "atipico_maximo": c.atipico_maximo,
            }
            lista.append(CenariosDoServico(servico=servico, contratos=len(itens), contratos_recorrentes=recorrentes, **extra))
        lista.sort(key=lambda x: (-x.contratos_recorrentes, x.servico))
        return lista

    @r.get("/api/inteligencia/fases", response_model=FasesResposta)
    def ver_fases(sessao: Session = Depends(obter_sessao, scope="function"), mes: date | None = None, hoje: date | None = None) -> FasesResposta:
        """As quatro fases do cliente no mês (padrão: o corrente): cadeia, gargalo, KPIs e ajuste."""
        dia = hoje or date.today()
        return montar_fases(sessao, mes or dia, dia)

    return r


# ---------------------------------------------------------------- as quatro fases (04/10/2026)

FUSO = ZoneInfo("America/Sao_Paulo")
FORA_DO_ICP = {MotivoDeDescarte.PORTE_ABAIXO, MotivoDeDescarte.SEGMENTO, MotivoDeDescarte.ORCAMENTO,
               MotivoDeDescarte.SERVICO_PONTUAL}
"""Descartado por estes motivos = lead fora do perfil (ICP). Os demais leads do mês contam como no ICP."""
INDICACAO = {TipoCanal.SOCIOS, TipoCanal.PARCEIROS, TipoCanal.ADVOGADOS, TipoCanal.CARTEIRA, TipoCanal.COLABORADORES}
"""Canais que são indicação: alguém de dentro ou de fora trouxe o lead."""


class TaxaResposta(BaseModel):
    valor: Decimal | None
    origem: Literal["premissa", "historico", "sem_dado"]


class IndicadorDaFase(BaseModel):
    rotulo: str
    unidade: Literal["numero", "pct", "reais", "horas", "dias"]
    previsto: Decimal | None
    realizado: Decimal | None
    nota: str | None = None


class FaseResposta(BaseModel):
    chave: Literal["atracao", "engajamento", "conversao", "pos_venda"]
    titulo: str
    pergunta: str
    kpi: IndicadorDaFase
    apoio: list[IndicadorDaFase]
    situacao: SituacaoResposta | None
    ajuste: str


class EtapaDaCadeia(BaseModel):
    chave: str
    rotulo: str
    previsto: Decimal | None
    realizado: Decimal | None
    taxa_prevista: Decimal | None
    """Para a etapa seguinte, em %."""
    taxa_realizada: Decimal | None


class FasesResposta(BaseModel):
    mes: date
    meses: list[date]
    """Os meses do plano, para escolher."""
    mes_fechado: bool
    tem_previsto: bool
    cadeia: list[EtapaDaCadeia]
    gargalo: str | None
    gargalo_texto: str | None
    fases: list[FaseResposta]
    taxas: dict[str, TaxaResposta]
    aviso: str | None


def _dia_local(v: datetime | date | None) -> date | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=ZoneInfo("UTC"))).astimezone(FUSO).date()
    return v


def _num(v: int | Decimal | None) -> Decimal | None:
    return None if v is None else Decimal(v)


def _texto_num(v: Decimal) -> str:
    return f"{v.quantize(D('0.1'), rounding=ROUND_HALF_UP)}".replace(".", ",").removesuffix(",0")


def montar_fases(sessao: Session, mes: date, hoje: date) -> FasesResposta:
    p, _ = premissas_vigentes(sessao)
    mes = mes.replace(day=1)
    ini = mes
    fim_do_mes = regras._proximo(mes) - timedelta(days=1)
    fim = min(fim_do_mes, hoje)
    passou = ini <= hoje
    janela_ini = date(ini.year - (ini.month <= 3), (ini.month - 4) % 12 + 1, 1)
    janela_fim = ini - timedelta(days=1)
    dentro = lambda d, a, b: d is not None and a <= d <= b

    # ---- leads, reuniões, propostas
    leads = list(sessao.scalars(sa.select(Lead)))
    def leads_de(a, b):
        return [l for l in leads if dentro(_dia_local(l.criado_em), a, b)]
    def no_icp(lista):
        return [l for l in lista if l.motivo_descarte not in FORA_DO_ICP]
    def reunioes_de(a, b):
        return [l for l in leads if dentro(_dia_local(l.reuniao_marcada_para), a, b)]
    oportunidades = list(sessao.scalars(sa.select(Oportunidade)))
    def colocadas(a, b):
        return [o for o in oportunidades if dentro(o.data_colocacao, a, b)]
    def conversao_de(lista):
        decididas = [o for o in lista if o.situacao.decidida]
        return fases.proporcao(sum(1 for o in decididas if o.situacao.ganha), len(decididas))

    hist_icp = no_icp(leads_de(janela_ini, janela_fim))
    hist_reunioes = reunioes_de(janela_ini, janela_fim)
    taxas = {
        "conversao": fases.taxa(p.taxa_conversao_pct, conversao_de(colocadas(janela_ini, janela_fim))),
        "reuniao_proposta": fases.taxa(
            p.taxa_reuniao_proposta_pct,
            fases.proporcao(sum(1 for l in hist_reunioes if l.convertido_em_id), len(hist_reunioes)),
        ),
        "lead_reuniao": fases.taxa(p.taxa_lead_reuniao_pct, fases.proporcao(len(hist_reunioes), len(hist_icp))),
    }

    # ---- previsto do plano no mês
    prev = regras.projetar(p, "previsto")
    linhas = {l.mes: l for l in prev.linhas}
    lp = linhas.get(mes)
    contratos_prev = (lp.contratos_bpo + lp.contratos_contabil) if lp else None
    mrr_prev = (lp.contabil + lp.bpo + lp.escada) if lp else None
    cadeia_prev = fases.cadeia_prevista(contratos_prev, mrr_prev, taxas["conversao"], taxas["reuniao_proposta"], taxas["lead_reuniao"])

    # ---- realizado
    registrados = list(sessao.scalars(sa.select(Contrato)))
    em_bruto = regras_de_mrr.em_bruto(registrados, parametros_vigentes(sessao)[1].imposto)
    motor = {c.id: regras.motor_do_contrato(c.oportunidade.servico if c.oportunidade else None, c.escopo) for c in registrados}
    por_motor = regras.contratos_por_motor(em_bruto, lambda c: motor[c.id])
    lr = regras.realizar(por_motor, ini, fim)[0] if passou else None

    leads_mes = leads_de(ini, fim) if passou else []
    icp_mes = no_icp(leads_mes)
    reunioes_mes = reunioes_de(ini, fim) if passou else []
    propostas_mes = colocadas(ini, fim) if passou else []
    real = lambda v: v if passou else None
    cadeia_real = {
        "leads_icp": real(D(len(icp_mes))),
        "reunioes": real(D(len(reunioes_mes))),
        "propostas": real(D(len(propostas_mes))),
        "contratos": real(D(lr.contratos_bpo + lr.contratos_contabil)) if lr else None,
        "mrr_novo": (lr.novo_contabil + lr.novo_bpo + lr.escada) if lr else None,
    }
    taxas_prev_seq = [taxas["lead_reuniao"].valor, taxas["reuniao_proposta"].valor, taxas["conversao"].valor, None, None]
    chaves = [c for c, _ in fases.ETAPAS]
    etapas = []
    for i, (chave, rotulo) in enumerate(fases.ETAPAS):
        prox = chaves[i + 1] if i + 1 < len(chaves) - 1 else None
        taxa_real = fases.proporcao(cadeia_real[prox], cadeia_real[chave]) if prox and cadeia_real[chave] is not None and cadeia_real[prox] is not None else None
        etapas.append(EtapaDaCadeia(chave=chave, rotulo=rotulo, previsto=cadeia_prev[chave], realizado=cadeia_real[chave],
                                    taxa_prevista=taxas_prev_seq[i], taxa_realizada=taxa_real))
    pior = fases.gargalo([fases.Etapa(e.chave, e.rotulo, e.previsto, e.realizado) for e in etapas])
    gargalo_texto = None
    if pior is not None:
        pct = fases.proporcao(pior.realizado, pior.previsto)
        gargalo_texto = f"Gargalo: {pior.rotulo.lower()}, com {_texto_num(pct)}% do previsto no mês."

    sit = lambda r, pv: SituacaoResposta(**vars(regras.situacao(r, pv))) if r is not None and pv is not None and pv > 0 else None

    # ---- 1. Atração
    pct_icp = fases.proporcao(len(icp_mes), len(leads_mes)) if passou else None
    indicacoes = D(sum(1 for l in leads_mes if l.tipo_canal in INDICACAO)) if passou else None
    pagos = sum(1 for l in leads_mes if l.tipo_canal is TipoCanal.TRAFEGO_PAGO)
    investido = sum((i.valor for i in sessao.scalars(sa.select(InvestimentoEmMidia).where(InvestimentoEmMidia.mes == mes.strftime("%Y-%m")))), D("0"))
    cpl = (investido / pagos).quantize(D("0.01")) if passou and pagos and investido > 0 else None
    k_atr = IndicadorDaFase(rotulo="Leads no ICP no mês", unidade="numero", previsto=cadeia_prev["leads_icp"], realizado=cadeia_real["leads_icp"])
    if k_atr.previsto is None:
        aj_atr = "Sem previsto: o mês está fora da projeção do plano ou falta a taxa do funil (premissa ou histórico)."
    elif k_atr.realizado is not None and k_atr.realizado < k_atr.previsto:
        aj_atr = f"Faltaram {ceil(k_atr.previsto - k_atr.realizado)} leads no ICP para o previsto do mês."
        if p.icp_alvo_pct and pct_icp is not None and pct_icp < p.icp_alvo_pct:
            aj_atr += (f" O problema também é qualidade: {_texto_num(100 - pct_icp)}% dos leads ficaram fora do ICP. "
                       "Corte os canais que trazem lead fora do perfil antes de aumentar o volume.")
    else:
        aj_atr = "No ritmo do previsto: nenhum ajuste."
    atracao = FaseResposta(
        chave="atracao", titulo="Atração", pergunta="Trazemos gente certa em volume?", kpi=k_atr,
        apoio=[
            IndicadorDaFase(rotulo="% dos leads dentro do ICP", unidade="pct", previsto=p.icp_alvo_pct, realizado=pct_icp),
            IndicadorDaFase(rotulo="Leads por indicação", unidade="numero", previsto=p.indicacoes_por_mes, realizado=indicacoes),
            IndicadorDaFase(rotulo="Custo por lead (tráfego pago)", unidade="reais", previsto=None, realizado=cpl,
                            nota=None if cpl is not None else "sem investimento em mídia lançado no mês"),
        ],
        situacao=sit(k_atr.realizado, k_atr.previsto), ajuste=aj_atr,
    )

    # ---- 2. Engajamento (aderência medida desde 04/10/2026)
    taxa_lr_real = fases.proporcao(len(reunioes_mes), len(icp_mes)) if passou else None
    respondidos = [l for l in leads_mes if l.aderencia is not None]
    bate = sum(1 for l in respondidos if l.aderencia is AderenciaDaPromessa.BATE)
    em_parte = sum(1 for l in respondidos if l.aderencia is AderenciaDaPromessa.EM_PARTE)
    aderencia = fases.proporcao(bate, len(respondidos)) if passou else None
    primeiras = []
    for l in leads_mes:
        contato = l.primeiro_contato_em or l.primeiro_contato_pelo_sdr
        if contato is not None and l.criado_em is not None:
            t0 = l.criado_em if l.criado_em.tzinfo else l.criado_em.replace(tzinfo=ZoneInfo("UTC"))
            t1 = contato if contato.tzinfo else contato.replace(tzinfo=ZoneInfo("UTC"))
            primeiras.append(max((t1 - t0).total_seconds() / 3600, 0))
    horas = D(str(round(median(primeiras), 1))) if primeiras else None
    perdidos = None
    if passou:
        perdidos = D(
            sum(1 for l in leads if l.motivo_descarte is MotivoDeDescarte.EXPECTATIVA and dentro(_dia_local(l.descartado_em), ini, fim))
            + sum(1 for o in propostas_mes if o.motivo_recusa is MotivoRecusa.EXPECTATIVA)
        )
    k_eng = IndicadorDaFase(rotulo="Aderência da promessa", unidade="pct", previsto=p.aderencia_alvo_pct, realizado=aderencia,
                            nota=None if aderencia is not None else "nenhum lead do mês com a aderência respondida")
    apoio_lr = IndicadorDaFase(rotulo="Lead no ICP → reunião", unidade="pct", previsto=taxas["lead_reuniao"].valor, realizado=taxa_lr_real)
    partes = []
    if k_eng.previsto is not None and aderencia is not None and aderencia < k_eng.previsto:
        nao_aderentes = len(respondidos) - bate
        partes.append(f"{nao_aderentes} de {len(respondidos)} leads não encontraram o que a peça prometeu.")
    por_origem: dict[str, list] = {}
    for l in respondidos:
        origem = l.campanha or l.canal or (l.tipo_canal.value if l.tipo_canal else None)
        if origem:
            por_origem.setdefault(origem, []).append(l)
    candidatas = [(fases.proporcao(sum(1 for l in ls if l.aderencia is AderenciaDaPromessa.BATE), len(ls)), o, len(ls))
                  for o, ls in por_origem.items() if len(ls) >= 2]
    if candidatas:
        pct, origem, n = min(candidatas)
        if pct < 100:
            partes.append(f"Revise primeiro a peça de “{origem}”: aderência de {_texto_num(pct)}% em {n} respostas.")
    temas: dict[str, int] = {}
    for l in respondidos:
        for t in l.aderencia_sobre or []:
            temas[t] = temas.get(t, 0) + 1
    if temas:
        tema, vezes = max(temas.items(), key=lambda x: (x[1], x[0]))
        partes.append(f"A expectativa erra mais em {tema.lower()} ({vezes} {'vez' if vezes == 1 else 'vezes'}).")
    if apoio_lr.previsto is not None and apoio_lr.realizado is not None and apoio_lr.realizado < apoio_lr.previsto:
        partes.append(f"Só {_texto_num(apoio_lr.realizado)}% dos leads no ICP chegaram a reunião (previsto "
                      f"{_texto_num(apoio_lr.previsto)}%): corrija a peça antes de investir mais em Atração.")
    if p.primeiro_contato_horas and horas is not None and horas > p.primeiro_contato_horas:
        partes.append(f"O primeiro contato leva {_texto_num(horas)} h; o alvo é {_texto_num(p.primeiro_contato_horas)} h.")
    if passou and not respondidos:
        partes.append("Responda a aderência no primeiro contato de cada lead para medir o Engajamento.")
    engajamento = FaseResposta(
        chave="engajamento", titulo="Engajamento", pergunta="A promessa bate com o 1º contato?", kpi=k_eng,
        apoio=[
            apoio_lr,
            IndicadorDaFase(rotulo="Aderência parcial (em parte)", unidade="pct", previsto=None,
                            realizado=fases.proporcao(em_parte, len(respondidos)) if passou else None),
            IndicadorDaFase(rotulo="Tempo até o 1º contato (mediana)", unidade="horas", previsto=p.primeiro_contato_horas, realizado=horas,
                            nota=None if horas is not None or not passou else "sem primeiro contato registrado no mês"),
            IndicadorDaFase(rotulo="Perdidos por expectativa", unidade="numero", previsto=None, realizado=perdidos),
        ],
        situacao=sit(k_eng.realizado, k_eng.previsto) or sit(apoio_lr.realizado, apoio_lr.previsto),
        ajuste=" ".join(partes) or "No ritmo do previsto: nenhum ajuste.",
    )

    # ---- 3. Conversão
    def novos(m):
        return [c for c in por_motor[m] if dentro(c.data_inicio, ini, fim)] if passou else []
    contabeis = [c.preco_mensal for c in novos(regras.MOTOR_CONTABIL) if c.preco_mensal]
    normais = [v for v in contabeis if v <= 3 * p.previsto.ticket_contabil]
    ticket = (sum(normais, D("0")) / len(normais)).quantize(D("0.01")) if normais else None
    aceitas = [o for o in oportunidades if o.situacao.ganha and dentro(o.data_aceite, ini, fim) and o.data_colocacao] if passou else []
    ciclo = D(str(round(sum((o.data_aceite - o.data_colocacao).days for o in aceitas) / len(aceitas)))) if aceitas else None
    k_conv = IndicadorDaFase(rotulo="Contratos no mês", unidade="numero", previsto=contratos_prev, realizado=cadeia_real["contratos"])
    if contratos_prev is None:
        aj_conv = "Sem previsto: o mês está fora da projeção do plano."
    elif lr is None:
        aj_conv = "O mês ainda não começou."
    else:
        faltas = []
        f_bpo = lp.contratos_bpo - lr.contratos_bpo
        if f_bpo > 0:
            n = ceil(f_bpo)
            proximo = min(p.previsto.bpo_por_mes, p.bpo_teto) + n
            cabe = "cabe na célula" if proximo <= p.bpo_teto else "passa do teto da célula: precisa de mais capacidade"
            faltas.append(f"Faltou {n} BPO Financeiro (−{_reais(n * p.bpo_ticket)}). Com {_texto_num(proximo)} no mês "
                          f"seguinte o desvio está coberto, e {cabe} (teto de {_texto_num(p.bpo_teto)}).")
        f_ctb = lp.contratos_contabil - lr.contratos_contabil
        if f_ctb > 0:
            faltas.append(f"Faltaram {ceil(f_ctb)} contratos contábeis; o onboarding comporta {_texto_num(p.contabil_vagas)} por mês.")
        if ticket is not None and ticket > p.previsto.ticket_contabil:
            faltas.append(f"O ticket contábil de {_reais(ticket)} está acima do previsto ({_reais(p.previsto.ticket_contabil)}).")
        aj_conv = " ".join(faltas) or "No ritmo do previsto: nenhum ajuste."
    conversao = FaseResposta(
        chave="conversao", titulo="Conversão", pergunta="Fechamos no ritmo e no preço?", kpi=k_conv,
        apoio=[
            IndicadorDaFase(rotulo="Conversão (aceitas ÷ decididas)", unidade="pct", previsto=taxas["conversao"].valor,
                            realizado=conversao_de(propostas_mes) if passou else None),
            IndicadorDaFase(rotulo="Ticket contábil normal", unidade="reais", previsto=p.previsto.ticket_contabil, realizado=ticket),
            IndicadorDaFase(rotulo="Ciclo de venda", unidade="dias", previsto=p.ciclo_alvo_dias, realizado=ciclo),
        ],
        situacao=sit(k_conv.realizado, k_conv.previsto), ajuste=aj_conv,
    )

    # ---- 4. Pós-venda
    nrr_real = None
    if passou:
        try:
            nrr_real = regras_de_mrr.movimento(em_bruto, ini, fim, hoje).nrr
        except ValueError:
            nrr_real = None
    nrr_prev = upg_prev = None
    if lp:
        carteira = p.mrr_de_partida + (prev.acumulado_em(regras.meses(p.inicio_da_projecao, mes)[-2], p.ponto_de_partida)
                                        if mes > p.inicio_da_projecao else p.ponto_de_partida) - p.ponto_de_partida
        if carteira > 0:
            nrr_prev = ((carteira - lp.churn + lp.escada) / carteira * 100).quantize(D("0.1"))
        i = len(regras.meses(p.inicio_da_projecao, mes)) - 1
        bpo_mes = min(p.previsto.bpo_por_mes, p.bpo_teto)
        upg = D("0")
        if p.escada_prazo_meses and i >= p.escada_prazo_meses:
            upg += bpo_mes * p.plus_pct / 100
        if p.escada_prazo_meses and i >= 2 * p.escada_prazo_meses:
            upg += bpo_mes * p.plus_pct / 100 * p.cfo_pct / 100
        upg_prev = upg.quantize(D("0.1"))
    upgrades = None
    if passou:
        upgrades = D(0)
        for c in por_motor[regras.MOTOR_BPO]:
            for ev in c.eventos:
                if (ev.tipo in (TipoDeEventoDeContrato.EXPANSAO, TipoDeEventoDeContrato.ADITIVO) and dentro(ev.data_do_evento, ini, fim)
                        and ev.preco_mensal_novo and ev.preco_mensal_anterior and ev.preco_mensal_novo > ev.preco_mensal_anterior):
                    upgrades += 1
    corrente = ini <= hoje <= fim_do_mes
    em_dia_total = sucesso.reunioes_em_dia(sessao, hoje) if corrente else None
    pct_em_dia = fases.proporcao(*em_dia_total) if em_dia_total else None
    k_pos = IndicadorDaFase(rotulo="NRR do mês", unidade="pct", previsto=nrr_prev, realizado=nrr_real)
    partes = []
    if lr is not None and lp is not None and lr.perdas > lp.churn:
        partes.append(f"Perdas de {_reais(lr.perdas)} acima da premissa de churn ({_reais(lp.churn)}): veja os encerramentos na Carteira.")
    if em_dia_total and em_dia_total[0] < em_dia_total[1]:
        vencidas = em_dia_total[1] - em_dia_total[0]
        partes.append(f"{vencidas} {'cliente está' if vencidas == 1 else 'clientes estão'} com reunião de resultado vencida: "
                      "é nela que se vende o upgrade da escada.")
    pos_venda = FaseResposta(
        chave="pos_venda", titulo="Pós-venda", pergunta="O cliente fica, cresce e indica?", kpi=k_pos,
        apoio=[
            IndicadorDaFase(rotulo="Churn no mês", unidade="reais", previsto=lp.churn if lp else None, realizado=lr.perdas if lr else None),
            IndicadorDaFase(rotulo="Upgrades na escada", unidade="numero", previsto=upg_prev, realizado=upgrades),
            IndicadorDaFase(rotulo="Reuniões de resultado em dia", unidade="pct", previsto=D(100) if corrente else None, realizado=pct_em_dia,
                            nota=None if corrente else "só no mês corrente"),
        ],
        situacao=sit(k_pos.realizado, k_pos.previsto), ajuste=" ".join(partes) or "Nenhum ajuste no número.",
    )

    return FasesResposta(
        mes=mes, meses=regras.meses(p.inicio, p.fim), mes_fechado=fim_do_mes < hoje, tem_previsto=lp is not None,
        cadeia=etapas, gargalo=pior.chave if pior else None, gargalo_texto=gargalo_texto,
        fases=[atracao, engajamento, conversao, pos_venda],
        taxas={k: TaxaResposta(valor=t.valor, origem=t.origem) for k, t in taxas.items()},
        aviso=None if lp else "Este mês está fora da projeção do plano: só o realizado aparece.",
    )
