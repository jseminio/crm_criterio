from decimal import Decimal as D

import pytest

from crm.domain.classificacao import PARAMETROS
from crm.domain.parametros import (
    CARGOS, PORTES, CelulaDeMix, LinhaDeParametros,
    construir_parametros, construir_parametros_de_rentabilidade, custo_hora_por_porte,
    erros_de_mix, erros_de_pesos,
)
from crm.domain.rentabilidade import PARAMETROS_DE_RENTABILIDADE

# A matriz de horas e mix de equipe por Porte, lida célula a célula da imagem de 28/09/2026
# ("MATRIZ DE HORAS E MIX DE EQUIPE — por PORTE do cliente"), conferida a ponto de reproduzir
# exatamente o custo_hora hoje hardcoded em `rentabilidade.PARAMETROS_DE_RENTABILIDADE`.
_MIX_POR_PORTE = {
    "Micro": {"Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.02",
              "Analista Sênior": "0.47", "Analista Pleno": "0.50", "Analista Júnior": "0"},
    "Pequeno": {"Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.02",
                "Analista Sênior": "0.47", "Analista Pleno": "0.50", "Analista Júnior": "0"},
    "Médio": {"Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.08",
              "Analista Sênior": "0.30", "Analista Pleno": "0.51", "Analista Júnior": "0.10"},
    "Grande": {"Sócio Sênior": "0.01", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.09",
               "Analista Sênior": "0.30", "Analista Pleno": "0.43", "Analista Júnior": "0.16"},
    "Extra Grande": {"Sócio Sênior": "0.02", "Sócio Júnior/Gerente": "0.05", "Supervisor/Especialista": "0.13",
                      "Analista Sênior": "0.30", "Analista Pleno": "0.30", "Analista Júnior": "0.20"},
}


def mix_padrao() -> list[CelulaDeMix]:
    return [
        CelulaDeMix(porte=porte, cargo=cargo, mix_percentual=D(valor))
        for porte, cargos in _MIX_POR_PORTE.items()
        for cargo, valor in cargos.items()
    ]


def linha_padrao(**o) -> LinhaDeParametros:
    base = dict(
        peso_receita=D("0.20"), peso_rentabilidade=D("0.25"), peso_cross_sell=D("0.12"),
        peso_complexidade=D("0.12"), peso_disciplina=D("0.09"), peso_risco=D("0.07"), peso_adimplencia=D("0.15"),
        corte_a=D("3.95"), corte_b=D("3.35"), trava_de_adimplencia=2, churn_alto=4,
        imposto=D("0.11"), teto_de_atrito=D("1.5"),
        atrito_nota_1=D("0"), atrito_nota_2=D("0.05"), atrito_nota_3=D("0.10"), atrito_nota_4=D("0.30"), atrito_nota_5=D("0.50"),
        corte_margem_2=D("0.30"), corte_margem_3=D("0.45"), corte_margem_4=D("0.60"), corte_margem_5=D("0.70"),
        horas_micro=5, horas_pequeno=10, horas_medio=16, horas_grande=40, horas_extra_grande=80,
        taxa_socio_senior=D("93.75"), taxa_socio_junior=D("106.25"), taxa_supervisor=D("75.00"),
        taxa_analista_senior=D("50.00"), taxa_analista_pleno=D("31.25"), taxa_analista_junior=D("18.75"),
    )
    return LinhaDeParametros(**{**base, **o})


def test_cargos_e_portes_batem_com_a_imagem_e_a_regua():
    assert CARGOS == ("Sócio Sênior", "Sócio Júnior/Gerente", "Supervisor/Especialista",
                       "Analista Sênior", "Analista Pleno", "Analista Júnior")
    assert PORTES == ("Micro", "Pequeno", "Médio", "Grande", "Extra Grande")


def test_construir_parametros_reproduz_a_planilha():
    p = construir_parametros(linha_padrao(), versao="teste-v1")
    assert p.peso_receita == PARAMETROS.peso_receita
    assert p.peso_rentabilidade == PARAMETROS.peso_rentabilidade
    assert p.peso_cross_sell == PARAMETROS.peso_cross_sell
    assert p.peso_complexidade == PARAMETROS.peso_complexidade
    assert p.peso_disciplina == PARAMETROS.peso_disciplina
    assert p.peso_risco == PARAMETROS.peso_risco
    assert p.peso_adimplencia == PARAMETROS.peso_adimplencia
    assert p.corte_a == PARAMETROS.corte_a and p.corte_b == PARAMETROS.corte_b
    assert p.trava_de_adimplencia == PARAMETROS.trava_de_adimplencia
    assert p.churn_alto == PARAMETROS.churn_alto
    assert p.versao == "teste-v1"


def test_custo_hora_por_porte_reproduz_a_matriz_da_imagem():
    custo = custo_hora_por_porte(linha_padrao(), mix_padrao())
    assert custo["Micro"] == D("41.6875")
    assert custo["Pequeno"] == D("41.6875")
    assert custo["Médio"] == D("39.875")
    assert custo["Grande"] == D("40.1875")
    assert custo["Extra Grande"] == D("45.0625")
    # Bate com o que hoje está hardcoded em rentabilidade.py — a matriz não inventa número novo.
    assert custo == PARAMETROS_DE_RENTABILIDADE.custo_hora


def test_construir_parametros_de_rentabilidade_reproduz_a_planilha():
    p = construir_parametros_de_rentabilidade(linha_padrao(), mix_padrao(), versao="teste-v1")
    assert p.horas_base == PARAMETROS_DE_RENTABILIDADE.horas_base
    assert p.custo_hora == PARAMETROS_DE_RENTABILIDADE.custo_hora
    assert p.fator_de_atrito == PARAMETROS_DE_RENTABILIDADE.fator_de_atrito
    assert p.teto_de_atrito == PARAMETROS_DE_RENTABILIDADE.teto_de_atrito
    assert p.imposto == PARAMETROS_DE_RENTABILIDADE.imposto
    assert p.cortes_de_margem == PARAMETROS_DE_RENTABILIDADE.cortes_de_margem


def test_pesos_certos_nao_dao_erro():
    assert erros_de_pesos(linha_padrao()) == []


def test_pesos_errados_apontam_o_problema():
    erros = erros_de_pesos(linha_padrao(peso_receita=D("0.25")))
    assert len(erros) == 1 and "105.00%" in erros[0]


def test_mix_certo_nao_da_erro():
    assert erros_de_mix(mix_padrao()) == []


def test_mix_errado_por_porte_aponta_o_problema():
    mix = [c for c in mix_padrao() if not (c.porte == "Micro" and c.cargo == "Analista Júnior")]
    mix.append(CelulaDeMix(porte="Micro", cargo="Analista Júnior", mix_percentual=D("0.10")))
    erros = erros_de_mix(mix)
    assert len(erros) == 1 and "Micro" in erros[0] and "110.00%" in erros[0]


def test_mix_com_cargo_faltando_aponta_o_problema():
    mix = [c for c in mix_padrao() if not (c.porte == "Grande" and c.cargo == "Analista Júnior")]
    erros = erros_de_mix(mix)
    assert any("Grande" in e and "Analista Júnior" in e for e in erros)
