"""MRR contra o KPI oficial (02/10/2026): meta R$ 400 mil e alerta R$ 200 mil pela parcela, em MRR de 13
parcelas desde 10/10/2026: R$ 433.333,33 e R$ 216.666,67."""

from decimal import Decimal as D

import pytest

from crm.domain.mrr import contra_a_meta


@pytest.mark.parametrize("valor, esperado", [
    (D("0"), "abaixo_do_alerta"),
    (D("216666.66"), "abaixo_do_alerta"),
    (D("216666.67"), "entre"),
    (D("279099.19"), "entre"),
    (D("433333.32"), "entre"),
    (D("433333.33"), "na_meta"),
    (D("450000"), "na_meta"),
])
def test_faixas_do_kpi(valor, esperado):
    assert contra_a_meta(valor) == esperado
