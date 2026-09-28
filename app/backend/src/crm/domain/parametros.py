"""Os parâmetros do Score e da Rentabilidade como dado editável, versionado (28/09/2026).

Até aqui, pesos, cortes e a matriz de horas/custo por Porte eram constantes fixas em
`classificacao.Parametros` e `rentabilidade.ParametrosDeRentabilidade` — certas porque vieram
das planilhas auditadas (`Classificacao_Grupo_COMPLETO.xlsx`, aba "Parâmetros", e a matriz de
horas e mix de equipe por Porte que produz o custo/hora ponderado), mas fixas no código. Decisão
de Eduardo em 28/09/2026: **estes números podem variar**, então viram linha de banco — uma nova
edição grava uma **versão nova**, nunca sobrescreve (mesmo princípio de `ClassificacaoDoGrupo`),
o que mantém `versao_dos_parametros` de cada classificação antiga apontando para algo estável.

Este módulo é só regra pura: monta os dois `Parametros` de domínio a partir de uma linha (que
tanto pode vir do banco quanto de um teste), e valida o que precisa fechar 100% antes de gravar.
Nada aqui fala com o banco.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from crm.domain.classificacao import Parametros
from crm.domain.porte import Porte
from crm.domain.rentabilidade import ParametrosDeRentabilidade

__all__ = [
    "CARGOS", "PORTES", "LinhaDeParametros", "CelulaDeMix",
    "construir_parametros", "construir_parametros_de_rentabilidade",
    "erros_de_pesos", "erros_de_mix",
]

D = Decimal

#: Os seis cargos da matriz de horas e mix de equipe, na ordem da planilha-imagem de 28/09/2026.
CARGOS: tuple[str, ...] = (
    "Sócio Sênior", "Sócio Júnior/Gerente", "Supervisor/Especialista",
    "Analista Sênior", "Analista Pleno", "Analista Júnior",
)

#: Os cinco Portes, na ordem da régua (`crm.domain.porte.Porte`).
PORTES: tuple[str, ...] = tuple(p.value for p in Porte)


@dataclass(frozen=True)
class LinhaDeParametros:
    """Os campos escalares de uma versão — tudo que não é a matriz de mix."""

    peso_receita: Decimal
    peso_rentabilidade: Decimal
    peso_cross_sell: Decimal
    peso_complexidade: Decimal
    peso_disciplina: Decimal
    peso_risco: Decimal
    peso_adimplencia: Decimal
    corte_a: Decimal
    corte_b: Decimal
    trava_de_adimplencia: int
    churn_alto: int

    imposto: Decimal
    teto_de_atrito: Decimal
    atrito_nota_1: Decimal
    atrito_nota_2: Decimal
    atrito_nota_3: Decimal
    atrito_nota_4: Decimal
    atrito_nota_5: Decimal
    corte_margem_2: Decimal
    corte_margem_3: Decimal
    corte_margem_4: Decimal
    corte_margem_5: Decimal

    horas_micro: int
    horas_pequeno: int
    horas_medio: int
    horas_grande: int
    horas_extra_grande: int

    taxa_socio_senior: Decimal
    taxa_socio_junior: Decimal
    taxa_supervisor: Decimal
    taxa_analista_senior: Decimal
    taxa_analista_pleno: Decimal
    taxa_analista_junior: Decimal


@dataclass(frozen=True)
class CelulaDeMix:
    """Uma célula da matriz: quanto do tempo de um cargo entra no atendimento de um Porte."""

    porte: str
    cargo: str
    mix_percentual: Decimal


def _pesos(l: LinhaDeParametros) -> dict[str, Decimal]:
    return {
        "Receita": l.peso_receita, "Rentabilidade": l.peso_rentabilidade, "Cross-sell": l.peso_cross_sell,
        "Complexidade": l.peso_complexidade, "Disciplina": l.peso_disciplina, "Risco técnico": l.peso_risco,
        "Adimplência": l.peso_adimplencia,
    }


def erros_de_pesos(l: LinhaDeParametros, *, tolerancia: Decimal = D("0.0005")) -> list[str]:
    """Os sete pesos do Score precisam somar 100% — devolve o problema, não corrige sozinho."""
    soma = sum(_pesos(l).values(), D(0))
    if abs(soma - 1) > tolerancia:
        return [f"Os pesos do Score somam {soma * 100:.2f}%, não 100%."]
    return []


def erros_de_mix(mix: list[CelulaDeMix], *, tolerancia: Decimal = D("0.0005")) -> list[str]:
    """O mix de cada Porte precisa somar 100% entre os seis cargos."""
    por_porte: dict[str, Decimal] = {p: D(0) for p in PORTES}
    cargos_vistos: dict[str, set[str]] = {p: set() for p in PORTES}
    erros = []
    for c in mix:
        if c.porte not in por_porte:
            erros.append(f"Porte {c.porte!r} não é um dos cinco da régua.")
            continue
        if c.cargo not in CARGOS:
            erros.append(f"Cargo {c.cargo!r} não é um dos seis da matriz.")
            continue
        por_porte[c.porte] += c.mix_percentual
        cargos_vistos[c.porte].add(c.cargo)
    for porte in PORTES:
        faltando = set(CARGOS) - cargos_vistos[porte]
        if faltando:
            erros.append(f"{porte}: falta o mix de {', '.join(sorted(faltando))}.")
        elif abs(por_porte[porte] - 1) > tolerancia:
            erros.append(f"{porte}: o mix soma {por_porte[porte] * 100:.2f}%, não 100%.")
    return erros


def construir_parametros(l: LinhaDeParametros, *, versao: str) -> Parametros:
    """Os parâmetros que `crm.domain.classificacao` usa para Score, classe e trava."""
    return Parametros(
        versao=versao,
        peso_receita=l.peso_receita, peso_rentabilidade=l.peso_rentabilidade, peso_cross_sell=l.peso_cross_sell,
        peso_complexidade=l.peso_complexidade, peso_disciplina=l.peso_disciplina, peso_risco=l.peso_risco,
        peso_adimplencia=l.peso_adimplencia, corte_a=l.corte_a, corte_b=l.corte_b,
        trava_de_adimplencia=l.trava_de_adimplencia, churn_alto=l.churn_alto,
    )


def _taxas(l: LinhaDeParametros) -> dict[str, Decimal]:
    return {
        "Sócio Sênior": l.taxa_socio_senior, "Sócio Júnior/Gerente": l.taxa_socio_junior,
        "Supervisor/Especialista": l.taxa_supervisor, "Analista Sênior": l.taxa_analista_senior,
        "Analista Pleno": l.taxa_analista_pleno, "Analista Júnior": l.taxa_analista_junior,
    }


def custo_hora_por_porte(l: LinhaDeParametros, mix: list[CelulaDeMix]) -> dict[str, Decimal]:
    """O custo/hora ponderado de cada Porte: soma, por cargo, da taxa × o mix daquele Porte.

    É a mesma conta da coluna "Custo/hora ponderado" da matriz — só que calculada, nunca digitada
    solta, para nunca destoar da taxa e do mix que a produziram.
    """
    taxas = _taxas(l)
    custo = {p: D(0) for p in PORTES}
    for c in mix:
        if c.porte in custo and c.cargo in taxas:
            custo[c.porte] += taxas[c.cargo] * c.mix_percentual
    return custo


def construir_parametros_de_rentabilidade(
    l: LinhaDeParametros, mix: list[CelulaDeMix], *, versao: str,
) -> ParametrosDeRentabilidade:
    """Os parâmetros que `crm.domain.rentabilidade` usa para margem, atrito e nota."""
    horas_base = {
        "Micro": D(l.horas_micro), "Pequeno": D(l.horas_pequeno), "Médio": D(l.horas_medio),
        "Grande": D(l.horas_grande), "Extra Grande": D(l.horas_extra_grande),
    }
    return ParametrosDeRentabilidade(
        versao=versao, horas_base=horas_base, custo_hora=custo_hora_por_porte(l, mix),
        fator_de_atrito={1: l.atrito_nota_1, 2: l.atrito_nota_2, 3: l.atrito_nota_3, 4: l.atrito_nota_4, 5: l.atrito_nota_5},
        teto_de_atrito=l.teto_de_atrito, imposto=l.imposto,
        cortes_de_margem=(l.corte_margem_2, l.corte_margem_3, l.corte_margem_4, l.corte_margem_5),
    )
