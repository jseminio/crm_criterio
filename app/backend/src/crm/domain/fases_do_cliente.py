"""As quatro fases do cliente na Inteligência de Conversão (amostra aprovada por Eduardo em
03/10/2026; pedido de construção em 04/10/2026): **Atração, Engajamento, Conversão e Pós-venda**,
cada uma com um KPI principal, previsto × realizado e o ajuste.

- **Cadeia do funil no mês**: leads no ICP → reuniões → propostas → contratos → MRR novo. O previsto
  sai **do fim para o começo**: os contratos e o MRR novo do plano (cenário previsto); propostas =
  contratos ÷ conversão; reuniões = propostas ÷ (reunião → proposta); leads no ICP = reuniões ÷
  (lead no ICP → reunião).
- **Taxas**: a premissa do Administrador, se houver; senão a **histórica** do CRM nos três meses
  fechados antes do mês; sem base, "sem dado" — e o previsto que depende dela também fica sem dado.
- **Gargalo**: a etapa da cadeia com a menor proporção realizado ÷ previsto (abaixo de 100%).
- **Situação**: a mesma do plano (no ritmo, atenção, abaixo; `crm.domain.plano_de_mrr.situacao`).
- **Ajuste**: texto de regra fixa, nunca sugestão de IA.

Funções puras: não tocam no banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

__all__ = ["ETAPAS", "Etapa", "Taxa", "cadeia_prevista", "gargalo", "proporcao", "taxa"]

D = Decimal
ETAPAS = (
    ("leads_icp", "Leads no ICP"),
    ("reunioes", "Reuniões"),
    ("propostas", "Propostas"),
    ("contratos", "Contratos"),
    ("mrr_novo", "MRR novo"),
)


@dataclass(frozen=True)
class Taxa:
    valor: Decimal | None
    """Em %."""
    origem: str
    """"premissa", "historico" ou "sem_dado"."""


def proporcao(numerador: int | Decimal, denominador: int | Decimal) -> Decimal | None:
    """Em %, com uma casa; `None` sem denominador."""
    if not denominador:
        return None
    return (D(numerador) / D(denominador) * 100).quantize(D("0.1"), rounding=ROUND_HALF_UP)


def taxa(premissa: Decimal | None, historico: Decimal | None) -> Taxa:
    if premissa is not None and premissa > 0:
        return Taxa(D(premissa), "premissa")
    if historico is not None and historico > 0:
        return Taxa(historico, "historico")
    return Taxa(None, "sem_dado")


def _dividir(v: Decimal | None, t: Taxa) -> Decimal | None:
    if v is None or t.valor is None or t.valor <= 0:
        return None
    return (v / (t.valor / 100)).quantize(D("0.1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Etapa:
    chave: str
    rotulo: str
    previsto: Decimal | None
    realizado: Decimal | None


def cadeia_prevista(contratos: Decimal | None, mrr_novo: Decimal | None, conversao: Taxa,
                    reuniao_proposta: Taxa, lead_reuniao: Taxa) -> dict[str, Decimal | None]:
    """O previsto de cada etapa, do fim para o começo."""
    propostas = _dividir(contratos, conversao)
    reunioes = _dividir(propostas, reuniao_proposta)
    leads = _dividir(reunioes, lead_reuniao)
    return {"leads_icp": leads, "reunioes": reunioes, "propostas": propostas, "contratos": contratos, "mrr_novo": mrr_novo}


def gargalo(etapas: list[Etapa]) -> Etapa | None:
    """A etapa mais atrasada em proporção ao previsto; `None` quando todas estão no previsto ou não há
    como comparar."""
    pior, menor = None, D(100)
    for e in etapas:
        if e.previsto is None or e.previsto <= 0 or e.realizado is None:
            continue
        p = e.realizado / e.previsto * 100
        if p < menor:
            pior, menor = e, p
    return pior
