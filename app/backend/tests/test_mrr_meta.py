"""MRR contra o KPI oficial (02/10/2026): meta R$ 400 mil, alerta abaixo de R$ 200 mil."""

from decimal import Decimal as D

import pytest

from crm.domain.mrr import contra_a_meta


@pytest.mark.parametrize("valor, esperado", [
    (D("0"), "abaixo_do_alerta"),
    (D("199999.99"), "abaixo_do_alerta"),
    (D("200000"), "entre"),
    (D("226341.20"), "entre"),
    (D("399999.99"), "entre"),
    (D("400000"), "na_meta"),
    (D("450000"), "na_meta"),
])
def test_faixas_do_kpi(valor, esperado):
    assert contra_a_meta(valor) == esperado
