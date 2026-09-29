"""Avaliação de um grupo por período: das respostas do painel Avaliar às notas, e a
rentabilidade do grupo contra a janela desejada (29/09/2026, pedido de Eduardo).

As regras de nota são as mesmas da tela (`AvaliacaoDeNotas.tsx`): a tela mostra a nota ao vivo,
este módulo é quem vale no "Calcular este cliente" e no "Calcular carteira". Mudou uma, muda a outra.

Rentabilidade no **nível do grupo** (decisão de Eduardo, 29/09/2026): horas pelo porte do grupo, que
já considera o número de empresas, e atrito pelas notas. Difere da planilha, que soma horas empresa
por empresa — esperado.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from crm.domain.rentabilidade import Empresa, ParametrosDeRentabilidade, margem_da_empresa

__all__ = [
    "ABAS", "FATORES_COMPLEXIDADE", "FATORES_RISCO", "FATORES_CROSS_SELL",
    "nota_de_complexidade", "nota_de_risco", "nota_de_cross_sell", "nota_de_disciplina", "nota_de_adimplencia",
    "notas_das_respostas", "abas_preenchidas", "RentabilidadeDoGrupo", "rentabilidade_do_grupo",
]

ABAS = ("complexidade", "risco", "disciplina", "cross_sell", "inadimplencia", "porte")
"""As seis abas que alguém preenche. Receita e Rentabilidade são calculadas."""

FATORES_COMPLEXIDADE = frozenset(
    {"holding", "centros_de_custo", "plano_de_contas", "auditoria", "regimes", "parcelamento_complexidade"}
)
FATORES_RISCO = frozenset(
    {"auto_de_infracao", "parcelamento_atraso", "obrigacao_atrasada", "certificado_vencendo", "passivo_sem_provisao"}
)
FATORES_CROSS_SELL = frozenset(
    {"mais_de_uma_linha", "empresa_do_grupo_fora", "interesse_formal", "porte_comporta", "gancho_societario"}
)


def nota_de_complexidade(sims: int) -> int:
    if sims == 0:
        return 1
    if sims == 1:
        return 2
    if sims <= 3:
        return 3
    if sims == 4:
        return 4
    return 5


def nota_de_risco(sims: int) -> int:
    """Mais fator = nota mais alta, como na Complexidade: o Score inverte (6 − nota) e o atrito cresce
    com a nota. Até 29/09/2026 saía invertida (0 fatores = 5), e a inversão do Score vinha por cima."""
    return min(5, 1 + sims)


def nota_de_cross_sell(sims: int) -> int:
    return min(5, 1 + sims)


def _por_furos(meses_bons: int, *furos_extras: bool) -> int:
    furos = (3 - meses_bons) + sum(furos_extras)
    return max(1, 5 - furos)


def nota_de_disciplina(meses_no_prazo: int, cobranca_dobrada: bool, atraso_recorrente: bool) -> int:
    return _por_furos(meses_no_prazo, cobranca_dobrada, atraso_recorrente)


def nota_de_adimplencia(meses_em_dia: int, em_negociacao: bool, ja_suspenso: bool) -> int:
    return _por_furos(meses_em_dia, em_negociacao, ja_suspenso)


def abas_preenchidas(respostas: dict[str, Any] | None) -> list[str]:
    """Aba presente no rascunho = revista por alguém neste período, mesmo sem nada marcado."""
    return [a for a in ABAS if respostas and a in respostas]


def notas_das_respostas(respostas: dict[str, Any]) -> dict[str, int]:
    """As notas das abas preenchidas; aba ausente não aparece (quem chama usa a nota atual)."""
    notas: dict[str, int] = {}
    if "complexidade" in respostas:
        notas["complexidade"] = nota_de_complexidade(len(set(respostas["complexidade"]) & FATORES_COMPLEXIDADE))
    if "risco" in respostas:
        notas["risco"] = nota_de_risco(len(set(respostas["risco"]) & FATORES_RISCO))
    if "cross_sell" in respostas:
        notas["cross_sell"] = nota_de_cross_sell(len(set(respostas["cross_sell"]) & FATORES_CROSS_SELL))
    if "disciplina" in respostas:
        d = respostas["disciplina"]
        notas["disciplina"] = nota_de_disciplina(d["meses_no_prazo"], d["cobranca_dobrada"], d["atraso_recorrente"])
    if "inadimplencia" in respostas:
        i = respostas["inadimplencia"]
        notas["adimplencia"] = nota_de_adimplencia(i["meses_em_dia"], i["em_negociacao"], i["ja_suspenso"])
    return notas


@dataclass(frozen=True)
class RentabilidadeDoGrupo:
    horas: Decimal
    custo_de_servir: Decimal
    margem: Decimal | None
    """Com o honorário praticado. `None` sem honorário."""
    honorario_calculado: Decimal
    """O honorário que daria exatamente a margem alvo."""
    defasagem: Decimal | None
    """(praticado − calculado) ÷ calculado. Negativo = cobra abaixo do modelo; positivo está tudo bem."""
    revisao_de_honorarios: bool
    """Margem com o praticado abaixo da mínima da janela."""


def _nota_inteira(nota: Decimal) -> int:
    # As notas humanas são inteiras; a tabela de atrito é por nota inteira (1 a 5).
    return int(Decimal(nota).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def rentabilidade_do_grupo(
    *, honorario: Decimal, porte: str, complexidade: Decimal, disciplina: Decimal, risco: Decimal,
    margem_minima: Decimal, margem_alvo: Decimal, p: ParametrosDeRentabilidade,
) -> RentabilidadeDoGrupo:
    """margem = (honorário − imposto − custo) ÷ honorário, logo o honorário da margem alvo é
    custo ÷ (1 − imposto − alvo). A disciplina entra invertida (6 − nota), como no Score."""
    divisor = 1 - p.imposto - margem_alvo
    if divisor <= 0:
        raise ValueError("margem alvo + imposto precisa ficar abaixo de 100%")
    m = margem_da_empresa(
        Empresa(honorario=honorario, porte=porte, complexidade=_nota_inteira(complexidade),
                disciplina=_nota_inteira(disciplina), risco=_nota_inteira(risco)),
        inverter_disciplina=True, p=p,
    )
    calculado = (m.custo_de_servir / divisor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    defasagem = ((honorario - calculado) / calculado).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if calculado > 0 else None
    margem = m.margem.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP) if m.margem is not None else None
    return RentabilidadeDoGrupo(
        horas=m.horas, custo_de_servir=m.custo_de_servir.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        margem=margem, honorario_calculado=calculado, defasagem=defasagem,
        revisao_de_honorarios=margem is not None and margem < margem_minima,
    )
