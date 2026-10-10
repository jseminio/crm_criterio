"""Plano de MRR da aba Inteligência de Conversão (aprovado por Eduardo em 03/10/2026).

**A meta é acréscimo líquido sobre a receita atual**: a venda nova e a escada precisam superar o
churn. Três motores:

- **BPO Financeiro**: o volume. Entra a `bpo_ticket` por cliente, `bpo_por_mes` clientes por mês no
  cenário, até o teto da célula (`bpo_teto`), que tem onboarding próprio.
- **Contábil**: limitado pelo onboarding, `contabil_vagas` por mês. Um contrato **atípico** ocupa
  `atipico_vagas` vagas. Os **contratos previstos** (o pipeline que já se conhece) entram no mês
  deles, ocupando as vagas; as que sobram entram no ticket do cenário.
- **Escada**: cada cliente de BPO Financeiro sobe para o BPO Plus `escada_prazo_meses` depois de
  entrar (`plus_pct` deles, `+plus_acrescimo`) e para o CFO as a Service outro prazo depois
  (`cfo_pct` dos que subiram, `+cfo_acrescimo`).

O **churn** é `churn_anual_pct ÷ 12` ao mês sobre a carteira do começo de cada mês: a de partida
mais o que o plano já acrescentou.

Três cenários com as mesmas regras e números diferentes: **alerta** (abaixo dele, o ajuste entra
em ação), **previsto** (o compromisso) e **otimista** (o alvo de esforço). O previsto acumulado
parte do `ponto_de_partida`: o que já estava realizado quando o plano foi feito.

**Realizado** = o movimento do MRR dos contratos do CRM (as regras de `crm.domain.mrr`, em bruto),
mês a mês, separado por motor pelo serviço do contrato. A escada realizada é a expansão em contrato
de BPO; reajuste e expansão de contrato contábil vão em "outros movimentos".

Funções puras: não tocam no banco.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from crm.domain.mrr import ItemDoMovimento, _fluxos, itens_do_movimento

__all__ = [
    "itens_do_realizado", "linha_do_plano",
    "CENARIOS", "MOTOR_BPO", "MOTOR_CONTABIL", "PADRAO", "Cenario", "ContratoPrevisto", "LinhaPrevista",
    "LinhaRealizada", "Premissas", "contratos_por_motor", "Projecao", "Situacao", "meses", "motor_do_contrato", "projetar",
    "realizar", "situacao",
]

D = Decimal
ZERO = D("0")
CENTAVOS = D("0.01")
MOTOR_BPO = "bpo"
MOTOR_CONTABIL = "contabil"
CENARIOS = ("alerta", "previsto", "otimista")


@dataclass(frozen=True)
class Cenario:
    bpo_por_mes: Decimal
    ticket_contabil: Decimal
    com_contratos_previstos: bool


@dataclass(frozen=True)
class ContratoPrevisto:
    descricao: str
    mes: date
    valor: Decimal
    atipico: bool


@dataclass(frozen=True)
class Premissas:
    meta_liquida: Decimal
    inicio: date
    """Começo da contagem do realizado (o dia 1 do mês)."""
    fim: date
    """Último dia do prazo da meta."""
    inicio_da_projecao: date
    """O primeiro mês projetado (dia 1). Antes dele, o previsto é o ponto de partida."""
    ponto_de_partida: Decimal
    """Quanto já estava realizado quando o plano foi feito (antes da projeção)."""
    mrr_de_partida: Decimal
    """MRR da carteira no começo da projeção: a base do churn."""
    churn_anual_pct: Decimal
    bpo_ticket: Decimal
    bpo_teto: Decimal
    contabil_vagas: Decimal
    atipico_vagas: Decimal
    escada_prazo_meses: int
    plus_acrescimo: Decimal
    plus_pct: Decimal
    cfo_acrescimo: Decimal
    cfo_pct: Decimal
    alerta: Cenario
    previsto: Cenario
    otimista: Cenario
    contratos_previstos: tuple[ContratoPrevisto, ...] = ()
    # As quatro fases (04/10/2026). `None`: o previsto usa a taxa histórica do CRM.
    taxa_lead_reuniao_pct: Decimal | None = None
    taxa_reuniao_proposta_pct: Decimal | None = None
    taxa_conversao_pct: Decimal | None = None
    icp_alvo_pct: Decimal | None = None
    indicacoes_por_mes: Decimal | None = None
    primeiro_contato_horas: Decimal | None = None
    ciclo_alvo_dias: Decimal | None = None
    aderencia_alvo_pct: Decimal | None = None

    def cenario(self, nome: str) -> Cenario:
        return getattr(self, nome)


PADRAO = Premissas(
    # Em MRR com 13 parcelas (09/10/2026): os valores em reais de 03/10 × 13 ÷ 12, ao centavo.
    meta_liquida=D("270833.33"),
    inicio=date(2026, 9, 1),
    fim=date(2027, 6, 30),
    inicio_da_projecao=date(2026, 11, 1),
    ponto_de_partida=D("28166.67"),
    mrr_de_partida=D("273369.42"),
    churn_anual_pct=D("12"),
    bpo_ticket=D("7583.33"),
    bpo_teto=D("5"),
    contabil_vagas=D("4"),
    atipico_vagas=D("2"),
    escada_prazo_meses=3,
    plus_acrescimo=D("3250"),
    plus_pct=D("80"),
    cfo_acrescimo=D("6500"),
    cfo_pct=D("30"),
    alerta=Cenario(D("2"), D("3145.22"), False),
    previsto=Cenario(D("3"), D("3145.22"), True),
    otimista=Cenario(D("5"), D("5416.67"), True),
)
"""As premissas de Eduardo em 03/10/2026. Valem enquanto o Administrador não mudar na tela."""


def _q(v: Decimal) -> Decimal:
    return v.quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def _primeiro(d: date) -> date:
    return d.replace(day=1)


def _proximo(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def meses(de: date, ate: date) -> list[date]:
    """O dia 1 de cada mês de `de` a `ate`, inclusive."""
    lista, m = [], _primeiro(de)
    while m <= ate:
        lista.append(m)
        m = _proximo(m)
    return lista


@dataclass(frozen=True)
class LinhaPrevista:
    mes: date
    contabil: Decimal
    bpo: Decimal
    escada: Decimal
    churn: Decimal
    acumulado: Decimal
    """Acréscimo líquido acumulado ao fim do mês, a partir do ponto de partida."""
    contratos_bpo: Decimal
    contratos_contabil: Decimal


@dataclass(frozen=True)
class Projecao:
    cenario: str
    linhas: list[LinhaPrevista]
    contabil: Decimal
    bpo: Decimal
    escada: Decimal
    churn: Decimal
    bruto: Decimal
    """Ponto de partida + contábil + BPO + escada."""
    liquido: Decimal
    """O bruto menos o churn: o que a meta mede."""
    percentual_da_meta: Decimal | None

    def acumulado_em(self, mes: date, ponto_de_partida: Decimal) -> Decimal:
        """O acumulado previsto ao fim de `mes`; antes da projeção, o ponto de partida."""
        valor = ponto_de_partida
        for l in self.linhas:
            if l.mes <= mes:
                valor = l.acumulado
        return valor

    def do_motor_ate(self, motor: str, mes: date) -> Decimal:
        campo = {MOTOR_BPO: "bpo", MOTOR_CONTABIL: "contabil", "escada": "escada", "churn": "churn"}[motor]
        return sum((getattr(l, campo) for l in self.linhas if l.mes <= mes), ZERO)


def projetar(p: Premissas, nome: str) -> Projecao:
    c = p.cenario(nome)
    lista = meses(p.inicio_da_projecao, p.fim)
    bpo_por_mes = min(c.bpo_por_mes, p.bpo_teto)
    previstos = [x for x in p.contratos_previstos if c.com_contratos_previstos]
    prazo = p.escada_prazo_meses
    taxa_churn = p.churn_anual_pct / 100 / 12
    carteira = p.mrr_de_partida
    acumulado = p.ponto_de_partida
    linhas = []
    for i, mes in enumerate(lista):
        do_mes = [x for x in previstos if _primeiro(x.mes) == mes]
        vagas_ocupadas = sum((p.atipico_vagas if x.atipico else D(1)) for x in do_mes)
        vagas_livres = max(p.contabil_vagas - vagas_ocupadas, ZERO)
        contabil = sum((x.valor for x in do_mes), ZERO) + vagas_livres * c.ticket_contabil
        bpo = bpo_por_mes * p.bpo_ticket
        escada = ZERO
        if prazo > 0 and i >= prazo:
            escada += bpo_por_mes * p.plus_pct / 100 * p.plus_acrescimo
        if prazo > 0 and i >= 2 * prazo:
            escada += bpo_por_mes * p.plus_pct / 100 * p.cfo_pct / 100 * p.cfo_acrescimo
        churn = carteira * taxa_churn
        novo = contabil + bpo + escada
        carteira += novo - churn
        acumulado += novo - churn
        linhas.append(LinhaPrevista(
            mes, _q(contabil), _q(bpo), _q(escada), _q(churn), _q(acumulado),
            bpo_por_mes, len(do_mes) + vagas_livres,
        ))
    soma = lambda campo: sum((getattr(l, campo) for l in linhas), ZERO)
    contabil, bpo, escada, churn = soma("contabil"), soma("bpo"), soma("escada"), soma("churn")
    bruto = p.ponto_de_partida + contabil + bpo + escada
    liquido = bruto - churn
    pct = (liquido / p.meta_liquida * 100).quantize(D("0.1")) if p.meta_liquida > 0 else None
    return Projecao(nome, linhas, contabil, bpo, escada, churn, bruto, liquido, pct)


# ---------------------------------------------------------------- realizado

def _sem_acento(texto: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(ch) != "Mn")


_DO_BPO = ("bpo financeiro", "bpo plus", "cfo as a service", "cfo as service")


def motor_do_contrato(servico: str | None, escopo: str | None) -> str:
    """BPO quando o serviço (ou, sem ele, o escopo) é da escada do BPO Financeiro; senão, contábil."""
    for texto in (servico, escopo):
        if texto and any(t in _sem_acento(texto) for t in _DO_BPO):
            return MOTOR_BPO
    return MOTOR_CONTABIL


@dataclass(frozen=True)
class LinhaRealizada:
    mes: date
    novo_contabil: Decimal
    novo_bpo: Decimal
    escada: Decimal
    """Expansão em contrato de BPO."""
    outros: Decimal
    """Reajuste e expansão de contrato contábil."""
    perdas: Decimal
    """Churn (cliente e Critério) e contração."""
    acumulado: Decimal
    contratos_contabil: int = 0
    contratos_bpo: int = 0


def realizar(contratos_por_motor: dict[str, list], inicio: date, ate: date) -> list[LinhaRealizada]:
    """O movimento mês a mês de `inicio` até o dia `ate` (o mês corrente corta em `ate`).

    `contratos_por_motor`: os contratos em bruto, separados por `motor_do_contrato`.
    """
    linhas, acumulado = [], ZERO
    for mes in meses(inicio, ate):
        fim = min(_proximo(mes) - timedelta(days=1), ate)
        fl = {m: _fluxos(cs, mes, fim) for m, cs in contratos_por_motor.items()}
        vazio = (ZERO,) * 6
        n_c, e_c, r_c, c_c, x_c, k_c = fl.get(MOTOR_CONTABIL, vazio)
        n_b, e_b, r_b, c_b, x_b, k_b = fl.get(MOTOR_BPO, vazio)
        outros = e_c + r_c + r_b
        perdas = c_c + x_c + k_c + c_b + x_b + k_b
        acumulado += n_c + n_b + e_b + outros - perdas
        contar = lambda cs: sum(
            1 for c in cs if c.data_inicio is not None and mes <= c.data_inicio <= fim
            and getattr(c.situacao, "name", "") != "AGUARDANDO_ASSINATURA"
        )
        linhas.append(LinhaRealizada(
            mes, n_c, n_b, e_b, outros, perdas, acumulado,
            contar(contratos_por_motor.get(MOTOR_CONTABIL, [])), contar(contratos_por_motor.get(MOTOR_BPO, [])),
        ))
    return linhas


def linha_do_plano(motor: str, categoria: str) -> str:
    """Em que linha do plano um movimento cai — a mesma conta de `realizar`: novo de contábil e de BPO;
    expansão de BPO é a escada; reajuste e expansão de contábil, e reajuste de BPO, são "outros"; contração e
    churn são perdas."""
    if categoria in ("contracao", "churn_cliente", "churn_criterio"):
        return "perdas"
    if categoria == "novo":
        return "bpo" if motor == MOTOR_BPO else "contabil"
    if motor == MOTOR_BPO and categoria == "expansao":
        return "escada"
    return "outros"


def itens_do_realizado(contratos_por_motor: dict[str, list], inicio: date, ate: date) -> list[tuple[str, ItemDoMovimento]]:
    """Cada contrato ou evento que compõe o realizado do plano de `inicio` a `ate` (10/10/2026), com a linha
    do plano. Perdas somam negativo: a soma com sinal é o acumulado de `realizar`."""
    itens = []
    for motor, contratos in contratos_por_motor.items():
        for item in itens_do_movimento(contratos, inicio, ate):
            itens.append((linha_do_plano(motor, item.categoria), item))
    return itens


# ---------------------------------------------------------------- situação

@dataclass(frozen=True)
class Situacao:
    chave: str
    """"no_ritmo" (100% ou mais do previsto), "atencao" (90% a 99%) ou "abaixo" (menos de 90%)."""
    percentual: Decimal | None


def situacao(realizado: Decimal, previsto: Decimal) -> Situacao:
    if previsto <= 0:
        return Situacao("no_ritmo", None)
    pct = (realizado / previsto * 100).quantize(D("0.1"))
    chave = "no_ritmo" if pct >= 100 else "atencao" if pct >= 90 else "abaixo"
    return Situacao(chave, pct)


def contratos_por_motor(contratos: Iterable, motor_de) -> dict[str, list]:
    """Separa os contratos pela função `motor_de(contrato)`."""
    grupos: dict[str, list] = {MOTOR_BPO: [], MOTOR_CONTABIL: []}
    for c in contratos:
        grupos[motor_de(c)].append(c)
    return grupos
