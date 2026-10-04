"""Funil comercial › Inteligência de Conversão (aprovado por Eduardo em 03/10/2026), Entrega 1: a
meta líquida, o plano por motor (previsto, realizado e ajuste) e as premissas, que só o
Administrador muda (permissão "Configurações: metas") e vão para o histórico de alterações. Os
cenários de ticket saem da aba Oportunidades e passam a ser por serviço. Regras em
`crm.domain.plano_de_mrr`."""

from __future__ import annotations

import calendar
from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.api.acesso import quem_fez
from crm.api.classificacao import parametros_vigentes
from crm.db.base import agora
from crm.db.modelos import Contrato, ContratoPrevistoDoPlano, Oportunidade, PlanoDeMrr
from crm.domain import mrr as regras_de_mrr
from crm.domain import plano_de_mrr as regras
from crm.domain.recortes import cenarios_de_ticket

__all__ = ["premissas_vigentes", "roteador_de_inteligencia"]

D = Decimal
ZERO = D("0")
_CAMPOS = (
    "meta_liquida", "inicio", "fim", "inicio_da_projecao", "ponto_de_partida", "mrr_de_partida", "churn_anual_pct",
    "bpo_ticket", "bpo_teto", "contabil_vagas", "atipico_vagas", "escada_prazo_meses", "plus_acrescimo", "plus_pct",
    "cfo_acrescimo", "cfo_pct",
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
    def ver(sessao: Session = Depends(obter_sessao), hoje: date | None = None) -> PlanoResposta:
        """O plano de MRR: meta, cenários, realizado mês a mês e o ajuste por motor. `hoje` existe para teste."""
        return montar_plano(sessao, hoje or date.today())

    @r.put("/api/inteligencia/plano", response_model=PlanoResposta)
    def mudar(corpo: PremissasDoPlano, sessao: Session = Depends(obter_sessao), hoje: date | None = None) -> PlanoResposta:
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
    def cenarios_por_servico(sessao: Session = Depends(obter_sessao)) -> list[CenariosDoServico]:
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

    return r
