from decimal import Decimal as D

import pytest

from crm.domain import avaliacao as a
from crm.domain.rentabilidade import PARAMETROS_DE_RENTABILIDADE as P


@pytest.mark.parametrize("sims,nota", [(0, 1), (1, 2), (2, 3), (3, 3), (4, 4), (5, 5), (6, 5)])
def test_complexidade_igual_a_tela(sims, nota):
    assert a.nota_de_complexidade(sims) == nota


@pytest.mark.parametrize("sims,nota", [(0, 5), (1, 4), (2, 3), (3, 2), (4, 1), (5, 1)])
def test_risco_igual_a_tela(sims, nota):
    assert a.nota_de_risco(sims) == nota


@pytest.mark.parametrize("sims,nota", [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 5)])
def test_cross_sell_igual_a_tela(sims, nota):
    assert a.nota_de_cross_sell(sims) == nota


@pytest.mark.parametrize("meses,extra1,extra2,nota", [
    (3, False, False, 5), (2, False, False, 4), (2, True, False, 3), (0, True, True, 1), (0, False, False, 2),
])
def test_disciplina_e_adimplencia_furo_por_furo(meses, extra1, extra2, nota):
    assert a.nota_de_disciplina(meses, extra1, extra2) == nota
    assert a.nota_de_adimplencia(meses, extra1, extra2) == nota


def test_notas_so_das_abas_preenchidas_e_ids_desconhecidos_nao_contam():
    respostas = {
        "complexidade": ["holding", "auditoria", "item_que_nao_existe"],
        "inadimplencia": {"meses_em_dia": 1, "em_negociacao": True, "ja_suspenso": False},
    }
    assert a.notas_das_respostas(respostas) == {"complexidade": 3, "adimplencia": 2}
    assert a.abas_preenchidas(respostas) == ["complexidade", "inadimplencia"]


def test_aba_revista_sem_nada_marcado_conta_como_preenchida():
    assert a.abas_preenchidas({"risco": []}) == ["risco"]
    assert a.notas_das_respostas({"risco": []}) == {"risco": 5}
    assert a.abas_preenchidas(None) == []


def _r(honorario, porte, c, d, r, minimo="0.60", alvo="0.70"):
    return a.rentabilidade_do_grupo(
        honorario=D(honorario), porte=porte, complexidade=D(c), disciplina=D(d), risco=D(r),
        margem_minima=D(minimo), margem_alvo=D(alvo), p=P,
    )


def test_honorario_calculado_da_exatamente_a_margem_alvo():
    r = _r("3200", "Médio", 3, 3, 3)
    assert r.horas == D("20.8") and r.custo_de_servir == D("829.40")
    assert r.honorario_calculado == D("4365.26")
    h = r.honorario_calculado
    assert abs((h - h * P.imposto - r.custo_de_servir) / h - D("0.70")) < D("0.0001")


@pytest.mark.parametrize("honorario,porte,c,d,r,margem,calculado,defasagem,revisao", [
    ("5200", "Médio", 3, 4, 2, "0.7428", "4029.47", "0.2905", False),
    ("1900", "Pequeno", 2, 5, 1, "0.6596", "2303.78", "-0.1753", False),
    ("7500", "Grande", 4, 2, 4, "0.4828", "16075.00", "-0.5334", True),
    ("1900", "Médio", 2, 5, 1, "0.5374", "3525.79", "-0.4611", True),
])
def test_casos_da_amostra_aprovada(honorario, porte, c, d, r, margem, calculado, defasagem, revisao):
    res = _r(honorario, porte, c, d, r)
    assert res.margem == D(margem)
    assert res.honorario_calculado == D(calculado)
    assert res.defasagem == D(defasagem)
    assert res.revisao_de_honorarios is revisao


def test_abaixo_do_alvo_mas_acima_do_minimo_nao_pede_revisao():
    assert _r("3200", "Médio", 3, 3, 3).revisao_de_honorarios is False  # 63,1%


def test_sem_honorario_nao_ha_margem_nem_revisao():
    r = _r("0", "Médio", 3, 3, 3)
    assert r.margem is None and r.defasagem == D("-1.0000") and r.revisao_de_honorarios is False


def test_alvo_mais_imposto_nao_pode_chegar_a_100_por_cento():
    with pytest.raises(ValueError):
        _r("1000", "Médio", 3, 3, 3, alvo="0.89")
