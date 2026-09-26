"""Margem e nota de rentabilidade (Etapa 3, item 4), traduzidas da planilha de rentabilidade.

    horas_ajustadas = horas_base(porte) × (1 + atrito)
    atrito          = mín(f(complexidade) + f(indisciplina) + f(risco), teto)
    custo_de_servir = horas_ajustadas × custo_hora(porte)
    margem          = (honorário − imposto − custo_de_servir) ÷ honorário

**Defeito 7.2, decisão explícita.** A planilha documenta que indisciplina é o inverso da nota de
Disciplina (`6 − disciplina`, e 5 = cliente ótimo, como no Score), mas a fórmula viva da aba "5. Margem"
indexa a tabela com a disciplina direta. `inverter_disciplina=True` segue a documentação e o Score;
`False` reproduz a fórmula viva. Nada aqui grava classificação: é só cálculo, para comparar as duas.

Grupo: honorário e custo **somam**; a margem é recalculada sobre os totais, nunca média das margens.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

D = Decimal

__all__ = ["ParametrosDeRentabilidade", "PARAMETROS_DE_RENTABILIDADE", "Empresa", "Margem", "atrito", "margem_da_empresa", "margem_do_grupo", "nota_de_rentabilidade"]


@dataclass(frozen=True)
class ParametrosDeRentabilidade:
    versao: str
    horas_base: dict[str, Decimal]
    custo_hora: dict[str, Decimal]
    fator_de_atrito: dict[int, Decimal]
    """Acréscimo de horas por nota 1 a 5, igual nos três quesitos."""
    teto_de_atrito: Decimal
    imposto: Decimal
    cortes_de_margem: tuple[Decimal, Decimal, Decimal, Decimal]
    """Margem mínima das notas 2, 3, 4 e 5."""


PARAMETROS_DE_RENTABILIDADE = ParametrosDeRentabilidade(
    versao="2026-07-planilha-rentabilidade-v1",
    horas_base={"Micro": D(5), "Pequeno": D(10), "Médio": D(16), "Grande": D(40), "Extra Grande": D(80)},
    custo_hora={"Micro": D("41.6875"), "Pequeno": D("41.6875"), "Médio": D("39.875"),
                "Grande": D("40.1875"), "Extra Grande": D("45.0625")},
    fator_de_atrito={1: D("0"), 2: D("0.05"), 3: D("0.10"), 4: D("0.30"), 5: D("0.50")},
    teto_de_atrito=D("1.5"), imposto=D("0.11"),
    cortes_de_margem=(D("0.30"), D("0.45"), D("0.60"), D("0.70")),
)


@dataclass(frozen=True)
class Empresa:
    honorario: Decimal
    porte: str
    complexidade: int
    disciplina: int
    risco: int
    ajuste_manual_de_horas: Decimal | None = None
    """Quando preenchido, substitui as horas-base da matriz."""


@dataclass(frozen=True)
class Margem:
    honorario: Decimal
    horas: Decimal
    custo_de_servir: Decimal
    margem: Decimal | None
    nota: int | None


def atrito(e: Empresa, *, inverter_disciplina: bool, p: ParametrosDeRentabilidade = PARAMETROS_DE_RENTABILIDADE) -> Decimal:
    for nome, v in (("complexidade", e.complexidade), ("disciplina", e.disciplina), ("risco", e.risco)):
        if not 1 <= v <= 5:
            raise ValueError(f"nota de {nome} precisa ir de 1 a 5 (veio {v})")
    indisciplina = 6 - e.disciplina if inverter_disciplina else e.disciplina
    soma = p.fator_de_atrito[e.complexidade] + p.fator_de_atrito[indisciplina] + p.fator_de_atrito[e.risco]
    return min(soma, p.teto_de_atrito)


def nota_de_rentabilidade(margem: Decimal | None, p: ParametrosDeRentabilidade = PARAMETROS_DE_RENTABILIDADE) -> int | None:
    if margem is None:
        return None
    return 1 + sum(margem >= corte for corte in p.cortes_de_margem)


def _margem(honorario: Decimal, horas: Decimal, custo: Decimal, p: ParametrosDeRentabilidade) -> Margem:
    if honorario <= 0 or custo <= 0:
        return Margem(honorario, horas, custo, None, None)
    m = (honorario - honorario * p.imposto - custo) / honorario
    return Margem(honorario, horas, custo, m, nota_de_rentabilidade(m, p))


def _horas_e_custo(e: Empresa, inverter_disciplina: bool, p: ParametrosDeRentabilidade) -> tuple[Decimal, Decimal]:
    base = e.ajuste_manual_de_horas if e.ajuste_manual_de_horas and e.ajuste_manual_de_horas > 0 else p.horas_base[e.porte]
    horas = base * (1 + atrito(e, inverter_disciplina=inverter_disciplina, p=p))
    return horas, horas * p.custo_hora[e.porte]


def margem_da_empresa(e: Empresa, *, inverter_disciplina: bool, p: ParametrosDeRentabilidade = PARAMETROS_DE_RENTABILIDADE) -> Margem:
    horas, custo = _horas_e_custo(e, inverter_disciplina, p)
    return _margem(e.honorario, horas, custo, p)


def margem_do_grupo(empresas: list[Empresa], *, inverter_disciplina: bool, p: ParametrosDeRentabilidade = PARAMETROS_DE_RENTABILIDADE) -> Margem:
    horas = custo = honorario = D(0)
    for e in empresas:
        h, c = _horas_e_custo(e, inverter_disciplina, p)
        horas += h; custo += c; honorario += e.honorario
    return _margem(honorario, horas, custo, p)
