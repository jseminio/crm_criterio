"""MRR dos contratos registrados no CRM, e o que o moveu num período.

**O que este número cobre — e o que não cobre.** O KPI oficial "MRR" é a receita
recorrente contratada da **carteira inteira** (R$ 226.341 em 19/09/2026, numa planilha
fora do CRM). Aqui só entram os **contratos registrados no CRM**. Enquanto a carteira
anterior não for carregada (Etapa 3), este MRR é **parcial** e **não deve ser comparado
com a meta de R$ 400 mil**. A tela e a API dizem isso junto do número.

Regras (decisão de Eduardo em 26/09/2026: a vigência começa na assinatura):

- **MRR atual** = soma do preço mensal dos contratos **Ativos**. Suspenso aparece à parte:
  não fatura, mas ainda não saiu. Aguardando assinatura e Encerrado ficam fora.
- Contrato sem preço mensal (só anual) **não entra**: não se inventa "anual ÷ 12". A
  contagem de quem ficou de fora vai junto.
- **Movimento do período**, por evento e por assinatura:
  **novo** (assinado no período) · **expansão** (Expansão e Aditivo que aumentam) ·
  **reajuste** (Reajuste que aumenta) · **contração** (Contração e qualquer queda de preço) ·
  **churn** (Encerramento, pelo preço mensal que o contrato tinha), separado por
  **iniciativa**: cliente (churn de fato) e Critério (saída organizada).
- **NRR** = (início + expansão + reajuste − contração − churn) ÷ início, e **GRR** = (início −
  contração − churn) ÷ início, contando **só contratos que já existiam no início** do período.
  Sem MRR no início, não são calculáveis (nunca 0%).

MRR em qualquer data = MRR atual − o movimento líquido desde essa data. Só vale para datas
até hoje.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Protocol

from crm.domain.listas import IniciativaDoEncerramento, SituacaoContrato, TipoDeEventoDeContrato

__all__ = ["MrrAtual", "Movimento", "mrr_atual", "movimento", "mrr_em"]

ZERO = Decimal("0.00")
CENTAVOS = Decimal("0.01")
T = TipoDeEventoDeContrato


class _Evento(Protocol):
    tipo: TipoDeEventoDeContrato
    data_do_evento: date
    preco_mensal_anterior: Decimal | None
    preco_mensal_novo: Decimal | None
    iniciativa: IniciativaDoEncerramento | None
    id: int


class _Contrato(Protocol):
    id: int
    situacao: SituacaoContrato
    preco_mensal: Decimal | None
    data_inicio: date | None
    eventos: list[_Evento]


@dataclass(frozen=True)
class MrrAtual:
    valor: Decimal
    contratos: int
    suspenso_valor: Decimal
    suspenso_contratos: int
    sem_preco_mensal: int
    """Ativos e suspensos sem preço mensal: ficaram de fora da soma."""


@dataclass(frozen=True)
class Movimento:
    de: date
    ate: date
    mrr_inicio: Decimal
    novo: Decimal
    expansao: Decimal
    reajuste: Decimal
    contracao: Decimal
    churn_cliente: Decimal
    churn_criterio: Decimal
    mrr_fim: Decimal
    nrr: Decimal | None
    grr: Decimal | None

    @property
    def churn(self) -> Decimal:
        return self.churn_cliente + self.churn_criterio

    @property
    def variacao(self) -> Decimal:
        return self.mrr_fim - self.mrr_inicio


def mrr_atual(contratos: Iterable[_Contrato]) -> MrrAtual:
    valor = suspenso = ZERO
    ativos = suspensos = sem_preco = 0
    for c in contratos:
        if c.situacao not in (SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO):
            continue
        if c.preco_mensal is None or c.preco_mensal <= 0:
            sem_preco += 1
            continue
        if c.situacao is SituacaoContrato.ATIVO:
            valor += c.preco_mensal
            ativos += 1
        else:
            suspenso += c.preco_mensal
            suspensos += 1
    return MrrAtual(valor, ativos, suspenso, suspensos, sem_preco)


def _preco_inicial(c: _Contrato) -> Decimal | None:
    """O preço mensal na assinatura: o "antes" do primeiro evento que o mudou."""
    for ev in sorted(c.eventos, key=lambda e: e.id):
        if ev.preco_mensal_novo is not None and ev.preco_mensal_anterior is not None:
            return ev.preco_mensal_anterior
    return c.preco_mensal


def _fluxos(contratos: Iterable[_Contrato], de: date, ate: date, *, so_existentes_em: date | None = None):
    """Soma os movimentos com data em [de, ate]. Devolve (novo, expansao, reajuste, contracao, churn_cliente, churn_criterio)."""
    novo = expansao = reajuste = contracao = churn_c = churn_k = ZERO
    for c in contratos:
        if c.situacao is SituacaoContrato.AGUARDANDO_ASSINATURA or c.data_inicio is None:
            continue
        if so_existentes_em is not None and c.data_inicio >= so_existentes_em:
            continue
        if de <= c.data_inicio <= ate:
            inicial = _preco_inicial(c)
            if inicial and inicial > 0:
                novo += inicial
        for ev in c.eventos:
            if not (de <= ev.data_do_evento <= ate):
                continue
            if ev.tipo is T.ENCERRAMENTO:
                # O preço não muda no encerramento: o que se perde é o que o contrato valia.
                # Se o contrato foi reajustado depois... não pode: encerrado não recebe evento.
                if c.preco_mensal and c.preco_mensal > 0:
                    if ev.iniciativa is IniciativaDoEncerramento.CRITERIO:
                        churn_k += c.preco_mensal
                    else:
                        churn_c += c.preco_mensal
                continue
            if ev.preco_mensal_novo is None or ev.preco_mensal_anterior is None:
                continue
            delta = ev.preco_mensal_novo - ev.preco_mensal_anterior
            if delta > 0:
                if ev.tipo is T.REAJUSTE:
                    reajuste += delta
                else:
                    expansao += delta
            elif delta < 0:
                contracao += -delta
    return novo, expansao, reajuste, contracao, churn_c, churn_k


def _liquido(f) -> Decimal:
    novo, exp, rej, con, ch_c, ch_k = f
    return novo + exp + rej - con - ch_c - ch_k


def mrr_em(contratos: list[_Contrato], dia: date, hoje: date) -> Decimal:
    """O MRR ao fim de `dia` (`dia` ≤ hoje): o atual menos o que se moveu depois."""
    if dia > hoje:
        raise ValueError("só há MRR até hoje")
    return mrr_atual(contratos).valor - _liquido(_fluxos(contratos, dia + timedelta(days=1), hoje))


def movimento(contratos: Iterable[_Contrato], de: date, ate: date, hoje: date) -> Movimento:
    if de > ate:
        raise ValueError("o início do período não pode ser depois do fim")
    lista = list(contratos)
    inicio = mrr_em(lista, de - timedelta(days=1), hoje)
    fim = mrr_em(lista, ate, hoje)
    novo, exp, rej, con, ch_c, ch_k = _fluxos(lista, de, ate)

    # NRR/GRR: só quem já existia no início do período.
    e_novo, e_exp, e_rej, e_con, e_ch_c, e_ch_k = _fluxos(lista, de, ate, so_existentes_em=de)
    if inicio > 0:
        nrr = ((inicio + e_exp + e_rej - e_con - e_ch_c - e_ch_k) / inicio * 100).quantize(Decimal("0.1"))
        grr = ((inicio - e_con - e_ch_c - e_ch_k) / inicio * 100).quantize(Decimal("0.1"))
    else:
        nrr = grr = None
    return Movimento(de, ate, inicio, novo, exp, rej, con, ch_c, ch_k, fim, nrr, grr)
