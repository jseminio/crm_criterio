from decimal import Decimal as D

import pytest

from crm.domain.rentabilidade import Empresa, atrito, margem_da_empresa, margem_do_grupo, nota_de_rentabilidade


def emp(**o):
    base = dict(honorario=D("3000"), porte="Médio", complexidade=3, disciplina=3, risco=3)
    return Empresa(**{**base, **o})


def test_atrito_soma_os_tres_quesitos():
    assert atrito(emp(), inverter_disciplina=True) == D("0.30")


def test_defeito_7_2_disciplina_5_so_muda_conforme_a_inversao():
    ordenado = emp(complexidade=1, risco=1, disciplina=5)
    assert atrito(ordenado, inverter_disciplina=True) == D("0")      # cliente ótimo, sem acréscimo
    assert atrito(ordenado, inverter_disciplina=False) == D("0.5")   # fórmula viva da planilha: penaliza o organizado


def test_teto_de_atrito():
    assert atrito(emp(complexidade=5, disciplina=1, risco=5), inverter_disciplina=True) == D("1.5")


def test_margem_da_empresa_media():
    m = margem_da_empresa(emp(), inverter_disciplina=True)
    # 16 h × 1,3 = 20,8 h × 39,875 = 829,40; margem = (3000 − 330 − 829,40) / 3000
    assert m.horas == D("20.8") and m.custo_de_servir == D("829.400")
    assert round(m.margem, 4) == D("0.6135") and m.nota == 4


def test_ajuste_manual_substitui_a_matriz():
    assert margem_da_empresa(emp(ajuste_manual_de_horas=D(10)), inverter_disciplina=True).horas == D("13.0")


def test_margem_do_grupo_e_sobre_os_totais_nao_media():
    a, b = emp(honorario=D("1000"), porte="Micro"), emp(honorario=D("9000"), porte="Grande")
    g = margem_do_grupo([a, b], inverter_disciplina=True)
    ma, mb = (margem_da_empresa(x, inverter_disciplina=True).margem for x in (a, b))
    assert g.honorario == D("10000") and g.margem != (ma + mb) / 2


def test_sem_honorario_ou_custo_nao_ha_margem():
    assert margem_da_empresa(emp(honorario=D(0)), inverter_disciplina=True).nota is None


@pytest.mark.parametrize("m,n", [("0.29", 1), ("0.30", 2), ("0.45", 3), ("0.60", 4), ("0.70", 5), (None, None)])
def test_cortes_da_nota(m, n):
    assert nota_de_rentabilidade(D(m) if m else None) == n


def test_nota_fora_da_escala_e_erro():
    with pytest.raises(ValueError):
        atrito(emp(disciplina=6), inverter_disciplina=True)
