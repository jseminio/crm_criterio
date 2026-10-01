"""O preço sugerido da proposta e o bruto/líquido (01/10/2026).

**Preço sugerido** — a mesma conta do "honorário calculado" da Carteira (decisão de Eduardo):

    horas  = horas-base do porte × (1 + atrito das notas)
    custo  = horas × custo/hora do porte
    bruto  = custo ÷ (1 − imposto − margem alvo)
    líquido sugerido = bruto × (1 − imposto)

Cliente novo ainda não tem nota de **disciplina**: entra 3, neutra (a mesma premissa do questionário).

**Bruto e líquido** — prática nova da Critério para a Reforma Tributária: a proposta mostra o valor
líquido (o que vai no contrato) e o bruto com a alíquota estimada, para o cliente não se surpreender.
O bruto é líquido ÷ (1 − alíquota), **arredondado ao múltiplo de R$ 50 mais próximo** (aprovado por
Eduardo: a NRH, 6.900 líquido, saiu com 7.750 bruto; 6.900 ÷ 0,89 = 7.752,81).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from crm.domain import avaliacao as regra_de_avaliacao
from crm.domain.rentabilidade import ParametrosDeRentabilidade

__all__ = [
    "DISCIPLINA_DO_NOVO", "PrecoSugerido", "preco_sugerido", "bruto_de", "arredondar_50",
    "reais", "reais_sem_centavos_se_inteiro", "faturamento_por_extenso",
]

D = Decimal
DISCIPLINA_DO_NOVO = 3
NOTA_SEM_INFORMACAO = 3
_CENTAVO = D("0.01")


@dataclass(frozen=True)
class PrecoSugerido:
    porte: str
    horas_base: Decimal
    complexidade: int
    complexidade_informada: bool
    risco: int
    risco_informado: bool
    disciplina: int
    atrito: Decimal
    horas: Decimal
    custo_hora: Decimal
    custo: Decimal
    imposto: Decimal
    margem_alvo: Decimal
    bruto: Decimal
    liquido: Decimal


def arredondar_50(valor: Decimal) -> Decimal:
    return (D(valor) / 50).quantize(D(1), rounding=ROUND_HALF_UP) * 50


def bruto_de(liquido: Decimal, imposto: Decimal) -> Decimal:
    if not D(0) <= imposto < 1:
        raise ValueError("a alíquota precisa ficar entre 0% e 100%")
    return arredondar_50(D(liquido) / (1 - imposto)).quantize(_CENTAVO)


def preco_sugerido(
    *, porte: str, complexidade: int | None, risco: int | None, margem_minima: Decimal, margem_alvo: Decimal,
    p: ParametrosDeRentabilidade,
) -> PrecoSugerido | None:
    """`None` sem porte da régua (sem volumetria não há horas para precificar)."""
    if porte not in p.horas_base:
        return None
    cx = complexidade if complexidade is not None else NOTA_SEM_INFORMACAO
    rk = risco if risco is not None else NOTA_SEM_INFORMACAO
    r = regra_de_avaliacao.rentabilidade_do_grupo(
        honorario=D(0), porte=porte, complexidade=D(cx), disciplina=D(DISCIPLINA_DO_NOVO), risco=D(rk),
        margem_minima=margem_minima, margem_alvo=margem_alvo, p=p,
    )
    base = p.horas_base[porte]
    return PrecoSugerido(
        porte=porte, horas_base=base, complexidade=cx, complexidade_informada=complexidade is not None,
        risco=rk, risco_informado=risco is not None, disciplina=DISCIPLINA_DO_NOVO,
        atrito=(r.horas / base - 1).quantize(D("0.0001"), rounding=ROUND_HALF_UP),
        horas=r.horas, custo_hora=p.custo_hora[porte].quantize(_CENTAVO, rounding=ROUND_HALF_UP),
        custo=r.custo_de_servir, imposto=p.imposto, margem_alvo=margem_alvo, bruto=r.honorario_calculado,
        liquido=(r.honorario_calculado * (1 - p.imposto)).quantize(_CENTAVO, rounding=ROUND_HALF_UP),
    )


def _milhar(inteiro: int) -> str:
    return f"{inteiro:,}".replace(",", ".")


def reais(valor: Decimal) -> str:
    """6900 → "6.900,00"."""
    v = D(valor).quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    inteiro, centavos = divmod(abs(v) * 100, 100)
    return ("-" if v < 0 else "") + f"{_milhar(int(inteiro))},{int(centavos):02d}"


def reais_sem_centavos_se_inteiro(valor: Decimal) -> str:
    """4500 → "4.500"; 4500,50 → "4.500,50" (como as caixas de honorário das propostas)."""
    v = D(valor).quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    return _milhar(int(v)) if v == v.to_integral_value() else reais(v)


def _uma_casa(v: Decimal) -> str:
    t = f"{v.quantize(D('0.1'), rounding=ROUND_HALF_UP)}".replace(".", ",")
    return t[:-2] if t.endswith(",0") else t


def faturamento_por_extenso(valor: Decimal) -> str:
    """4.800.000 → "R$ 4,8 milhões"; 1.000.000 → "R$ 1 milhão"; 350.000 → "R$ 350 mil"."""
    v = D(valor)
    if v >= 1_000_000_000:
        n = _uma_casa(v / 1_000_000_000)
        return f"R$ {n} {'bilhão' if n == '1' else 'bilhões'}"
    if v >= 1_000_000:
        n = _uma_casa(v / 1_000_000)
        return f"R$ {n} {'milhão' if n == '1' else 'milhões'}"
    if v >= 1_000:
        return f"R$ {_uma_casa(v / 1_000)} mil"
    return f"R$ {reais(v)}"
