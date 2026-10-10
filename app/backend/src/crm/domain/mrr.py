"""MRR dos contratos registrados no CRM, e o que o moveu num período.

**O que este número cobre — e o que não cobre.** O KPI oficial "MRR" é a receita
recorrente contratada da **carteira inteira** (R$ 226.341 em 19/09/2026, numa planilha
fora do CRM). Aqui entram os **contratos registrados no CRM**. Enquanto a carteira
anterior não for carregada, este MRR é **parcial** e **não deve ser comparado com a meta
de R$ 400 mil**. Com ela carregada (`importar_carteira.py`), o CRM compara com a meta e
com o alerta oficiais (02/10/2026, aprovado por Eduardo). A tela e a API dizem isso junto do número.

Regras (decisão de Eduardo em 26/09/2026: a vigência começa na assinatura):

- **MRR atual** = soma do preço mensal dos contratos **Ativos**. Suspenso aparece à parte:
  não fatura, mas ainda não saiu. Aguardando assinatura e Encerrado ficam fora.
- Contrato sem preço mensal (só anual) **não entra**: não se inventa "anual ÷ 12". A
  contagem de quem ficou de fora vai junto.
- **Movimento do período**, por evento e por assinatura (a **Correção** de um valor lançado
  errado **não conta**: não foi um movimento comercial):
  **novo** (assinado no período) · **expansão** (Expansão e Aditivo que aumentam) ·
  **reajuste** (Reajuste que aumenta) · **contração** (Contração e qualquer queda de preço) ·
  **churn** (Encerramento, pelo preço mensal que o contrato tinha), separado por
  **iniciativa**: cliente (churn de fato) e Critério (saída organizada).
- **NRR** = (início + expansão + reajuste − contração − churn) ÷ início, e **GRR** = (início −
  contração − churn) ÷ início, contando **só contratos que já existiam no início** do período.
  Sem MRR no início, não são calculáveis (nunca 0%).

MRR em qualquer data = MRR atual − o movimento líquido desde essa data. Só vale para datas
até hoje.

**13 parcelas por ano** (decisão de Eduardo em 09/10/2026): todo serviço recorrente — contábil, fiscal,
DP e BPO Financeiro — fatura 13 parcelas no ano. O MRR é a parcela mensal × 13 ÷ 12 (`PARCELAS_NO_ANO`),
no preço e nos eventos, em `em_bruto`, por onde passa todo cálculo de MRR do CRM. O contrato guarda a
parcela; o MRR é sempre calculado.

**Sempre em bruto** (02/10/2026, aprovado por Eduardo): o contrato marcado como líquido entra com o
imposto, `líquido ÷ (1 − imposto)`, ao centavo, no preço e nos eventos (`em_bruto`). Aqui não se
arredonda a R$ 50 como na proposta: o arredondamento é para o cliente ler, não para somar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Protocol

from crm.domain.listas import IniciativaDoEncerramento, SituacaoContrato, TipoDeEventoDeContrato

__all__ = [
    "ALERTA_DE_MRR", "CATEGORIAS_DO_MOVIMENTO", "ItemDoMovimento", "ItemDoMrr", "META_DE_MRR", "MrrAtual", "Movimento",
    "ativo_em", "contra_a_meta", "em_bruto", "itens_do_movimento", "itens_do_mrr", "mrr_atual", "movimento", "mrr_em",
    "preco_em",
]

META_DE_MRR = Decimal("433333.33")
"""KPI oficial "MRR" (planilha "KPI de Head de Novos Negócios"): meta de R$ 400 mil pela parcela, que em
MRR de 13 parcelas é R$ 433.333,33 (conversão aprovada por Eduardo em 10/10/2026, mesma régua do plano).
É o padrão: o valor que vale fica em Configurações › Metas (02/10/2026)."""
ALERTA_DE_MRR = Decimal("216666.67")
"""Abaixo disto, alerta (padrão): R$ 200 mil pela parcela, em MRR de 13 parcelas."""


def contra_a_meta(valor: Decimal, meta: Decimal = META_DE_MRR, alerta: Decimal = ALERTA_DE_MRR) -> str:
    """"abaixo_do_alerta" (< alerta), "entre" ou "na_meta" (>= meta). Só vale com a
    carteira inteira no CRM: com o MRR parcial, quem chama não compara."""
    if valor >= meta:
        return "na_meta"
    return "abaixo_do_alerta" if valor < alerta else "entre"

ZERO = Decimal("0.00")
CENTAVOS = Decimal("0.01")
PARCELAS_NO_ANO = 13
"""Parcelas que um serviço recorrente fatura no ano (09/10/2026). MRR = parcela × 13 ÷ 12."""


def mensalizar(parcela: Decimal | None) -> Decimal | None:
    """A parcela mensal do contrato em MRR: × 13 ÷ 12, ao centavo."""
    if parcela is None:
        return None
    return (Decimal(parcela) * PARCELAS_NO_ANO / 12).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
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
    grupo_id: int
    situacao: SituacaoContrato
    preco_mensal: Decimal | None
    data_inicio: date | None
    """`None` só na carteira anterior ao CRM: existe desde antes de qualquer período."""
    eventos: list[_Evento]


@dataclass(frozen=True)
class _EventoEmBruto:
    tipo: TipoDeEventoDeContrato
    data_do_evento: date
    preco_mensal_anterior: Decimal | None
    preco_mensal_novo: Decimal | None
    iniciativa: IniciativaDoEncerramento | None
    id: int


@dataclass(frozen=True)
class _ContratoEmBruto:
    id: int
    grupo_id: int
    situacao: SituacaoContrato
    preco_mensal: Decimal | None
    data_inicio: date | None
    eventos: list[_EventoEmBruto] = field(default_factory=list)


def em_bruto(contratos: Iterable[_Contrato], imposto: Decimal, *, em_mrr: bool = True) -> list[_ContratoEmBruto]:
    """Os contratos com os valores em bruto e em MRR: o marcado `base_do_valor == "liquido"` tem preço e
    eventos divididos por (1 − imposto); depois, todo valor vira MRR (× 13 ÷ 12, `mensalizar`).

    `em_mrr=False` fica na parcela em bruto, sem o 13 ÷ 12: é o que o caixa espera receber no mês
    (`crm.domain.recebimentos`)."""
    if not Decimal(0) <= imposto < 1:
        raise ValueError("o imposto precisa estar entre 0 e 100%")

    def converter(v: Decimal | None, liquido: bool) -> Decimal | None:
        if v is None:
            return None
        bruto = (Decimal(v) / (1 - imposto)).quantize(CENTAVOS, rounding=ROUND_HALF_UP) if liquido else Decimal(v)
        return mensalizar(bruto) if em_mrr else bruto

    lista = []
    for c in contratos:
        liq = getattr(c, "base_do_valor", None) == "liquido"
        lista.append(_ContratoEmBruto(
            c.id, c.grupo_id, c.situacao, converter(c.preco_mensal, liq), c.data_inicio,
            [_EventoEmBruto(e.tipo, e.data_do_evento, converter(e.preco_mensal_anterior, liq),
                            converter(e.preco_mensal_novo, liq), e.iniciativa, e.id) for e in c.eventos],
        ))
    return lista


@dataclass(frozen=True)
class MrrAtual:
    valor: Decimal
    contratos: int
    suspenso_valor: Decimal
    suspenso_contratos: int
    sem_preco_mensal: int
    """Ativos e suspensos sem preço mensal: ficaram de fora da soma."""
    grupos: int = 0
    """Quantos grupos (clientes) têm contrato ativo com preço mensal."""
    ticket_por_grupo: Decimal | None = None
    """Ticket médio da carteira: **receita mensal média por grupo** (decisão de Eduardo em
    23/09/2026: por grupo, na carteira inteira, não venda nova). Um grupo com várias empresas
    conta como **um**; cliente individual é um grupo de uma empresa. `None` sem contrato ativo."""
    mediana_por_grupo: Decimal | None = None
    """A mediana vai junto: 2 grupos respondem por ~38% do total, e a média sozinha engana."""


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


@dataclass(frozen=True)
class ItemDoMrr:
    """Um contrato na conta do MRR atual (10/10/2026): o que a lista "Ver composição" mostra.
    `parte`: "somado" (ativo com preço), "suspenso" (à parte) ou "sem_preco" (fora da soma)."""

    parte: str
    contrato_id: int
    grupo_id: int
    valor: Decimal | None


def itens_do_mrr(contratos: Iterable[_Contrato]) -> list[ItemDoMrr]:
    """Os contratos Ativos e Suspensos e onde cada um entra. `mrr_atual` soma esta mesma lista."""
    itens = []
    for c in contratos:
        if c.situacao not in (SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO):
            continue
        if c.preco_mensal is None or c.preco_mensal <= 0:
            itens.append(ItemDoMrr("sem_preco", c.id, c.grupo_id, None))
        elif c.situacao is SituacaoContrato.ATIVO:
            itens.append(ItemDoMrr("somado", c.id, c.grupo_id, c.preco_mensal))
        else:
            itens.append(ItemDoMrr("suspenso", c.id, c.grupo_id, c.preco_mensal))
    return itens


def mrr_atual(contratos: Iterable[_Contrato]) -> MrrAtual:
    valor = suspenso = ZERO
    ativos = suspensos = sem_preco = 0
    por_grupo: dict[int, Decimal] = {}
    for item in itens_do_mrr(contratos):
        if item.parte == "sem_preco":
            sem_preco += 1
        elif item.parte == "somado":
            valor += item.valor
            ativos += 1
            por_grupo[item.grupo_id] = por_grupo.get(item.grupo_id, ZERO) + item.valor
        else:
            suspenso += item.valor
            suspensos += 1
    totais = list(por_grupo.values())
    return MrrAtual(
        valor, ativos, suspenso, suspensos, sem_preco,
        grupos=len(totais),
        ticket_por_grupo=(valor / len(totais)).quantize(CENTAVOS) if totais else None,
        mediana_por_grupo=Decimal(median(totais)).quantize(CENTAVOS) if totais else None,
    )


def _preco_inicial(c: _Contrato) -> Decimal | None:
    """O preço mensal na assinatura: o "antes" do primeiro evento que o mudou."""
    for ev in sorted(c.eventos, key=lambda e: e.id):
        if ev.tipo is not T.CORRECAO and ev.preco_mensal_novo is not None and ev.preco_mensal_anterior is not None:
            return ev.preco_mensal_anterior
    return c.preco_mensal


CATEGORIAS_DO_MOVIMENTO = ("novo", "expansao", "reajuste", "contracao", "churn_cliente", "churn_criterio")
"""As linhas do movimento do MRR, na ordem da tela."""


@dataclass(frozen=True)
class ItemDoMovimento:
    """Um contrato ou evento que moveu o MRR: o que compõe cada linha do movimento (10/10/2026)."""

    categoria: str
    contrato_id: int
    grupo_id: int
    valor: Decimal
    data: date | None
    evento_id: int | None = None


def itens_do_movimento(
    contratos: Iterable[_Contrato], de: date, ate: date, *, so_existentes_em: date | None = None,
) -> list[ItemDoMovimento]:
    """Cada movimento com data em [de, ate], um por contrato ou evento. É daqui que saem as somas do
    movimento (`_fluxos`): a lista que a tela abre é a mesma conta do número."""
    itens: list[ItemDoMovimento] = []
    for c in contratos:
        if c.situacao is SituacaoContrato.AGUARDANDO_ASSINATURA:
            continue
        # Sem data de início = carteira anterior ao CRM: já existia, nunca é "novo".
        if so_existentes_em is not None and c.data_inicio is not None and c.data_inicio >= so_existentes_em:
            continue
        if c.data_inicio is not None and de <= c.data_inicio <= ate:
            inicial = _preco_inicial(c)
            if inicial and inicial > 0:
                itens.append(ItemDoMovimento("novo", c.id, c.grupo_id, inicial, c.data_inicio))
        for ev in c.eventos:
            if not (de <= ev.data_do_evento <= ate):
                continue
            if ev.tipo is T.CORRECAO:
                continue  # corrige um lançamento errado; o MRR do passado também já era o corrigido
            if ev.tipo is T.ENCERRAMENTO:
                # O preço não muda no encerramento: o que se perde é o que o contrato valia.
                # Se o contrato foi reajustado depois... não pode: encerrado não recebe evento.
                if c.preco_mensal and c.preco_mensal > 0:
                    cat = "churn_criterio" if ev.iniciativa is IniciativaDoEncerramento.CRITERIO else "churn_cliente"
                    itens.append(ItemDoMovimento(cat, c.id, c.grupo_id, c.preco_mensal, ev.data_do_evento, ev.id))
                continue
            if ev.preco_mensal_novo is None or ev.preco_mensal_anterior is None:
                continue
            delta = ev.preco_mensal_novo - ev.preco_mensal_anterior
            if delta > 0:
                cat = "reajuste" if ev.tipo is T.REAJUSTE else "expansao"
                itens.append(ItemDoMovimento(cat, c.id, c.grupo_id, delta, ev.data_do_evento, ev.id))
            elif delta < 0:
                itens.append(ItemDoMovimento("contracao", c.id, c.grupo_id, -delta, ev.data_do_evento, ev.id))
    return itens


def _fluxos(contratos: Iterable[_Contrato], de: date, ate: date, *, so_existentes_em: date | None = None):
    """Soma os movimentos com data em [de, ate]. Devolve (novo, expansao, reajuste, contracao, churn_cliente, churn_criterio)."""
    somas = dict.fromkeys(CATEGORIAS_DO_MOVIMENTO, ZERO)
    for item in itens_do_movimento(contratos, de, ate, so_existentes_em=so_existentes_em):
        somas[item.categoria] += item.valor
    return tuple(somas[c] for c in CATEGORIAS_DO_MOVIMENTO)


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


def ativo_em(c: _Contrato, dia: date) -> bool:
    """Se o contrato estava faturando ao fim de `dia`: assinado até lá (ou da carteira anterior) e sem
    encerramento até lá. Suspenso não fatura. Para a parcela esperada do mês (`crm.domain.recebimentos`)."""
    if c.situacao in (SituacaoContrato.AGUARDANDO_ASSINATURA, SituacaoContrato.SUSPENSO):
        return False
    if c.data_inicio is not None and c.data_inicio > dia:
        return False
    return not any(ev.tipo is T.ENCERRAMENTO and ev.data_do_evento <= dia for ev in c.eventos)


def preco_em(c: _Contrato, dia: date) -> Decimal | None:
    """O preço mensal ao fim de `dia`: o atual menos o que os eventos depois de `dia` mudaram (a Correção
    não volta: o passado também já era o corrigido, como em `mrr_em`)."""
    if c.preco_mensal is None:
        return None
    preco = c.preco_mensal
    for ev in c.eventos:
        if ev.data_do_evento <= dia or ev.tipo in (T.CORRECAO, T.ENCERRAMENTO):
            continue
        if ev.preco_mensal_novo is not None and ev.preco_mensal_anterior is not None:
            preco -= ev.preco_mensal_novo - ev.preco_mensal_anterior
    return preco
