import io
from datetime import date, datetime, timezone
from decimal import Decimal as D

import openpyxl

from crm.relatorios.exportacao_da_carteira import LinhaDeHistorico, ParametrosDaPlanilha, gerar_planilha


def linha(**o) -> LinhaDeHistorico:
    base = dict(
        grupo_nome="Alfa", referencia=date(2026, 7, 31), revisao=1,
        registrado_em=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc), fonte="teste",
        atribuido_por=None, motivo=None, receita_mensal=D("1000.00"),
        nota_receita=D("5"), nota_rentabilidade=D("1"), complexidade=D("3"), disciplina=D("3"),
        risco_tecnico=D("3"), cross_sell=D("3"), adimplencia=D("3"), semaforo=1, churn=1,
        score=D("3.5000"), classe="B", classe_efetiva="B1", alerta_de_churn=None, em_cobranca=False,
        eixo_de_acao="Sem urgência de churn",
    )
    return LinhaDeHistorico(**{**base, **o})


def parametros(**o) -> ParametrosDaPlanilha:
    base = dict(
        corte_a=D("3.95"), corte_b=D("3.35"), trava_de_adimplencia=2, churn_alto=4,
        peso_receita=D("0.20"), peso_rentabilidade=D("0.25"), peso_adimplencia=D("0.15"),
        peso_complexidade=D("0.12"), peso_cross_sell=D("0.12"), peso_disciplina=D("0.09"), peso_risco=D("0.07"),
    )
    return ParametrosDaPlanilha(**{**base, **o})


def _abrir(conteudo: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(io.BytesIO(conteudo), data_only=False)


def test_tres_abas_na_ordem_do_modelo():
    wb = _abrir(gerar_planilha([linha()], parametros()))
    assert wb.sheetnames == ["Histórico da Carteira", "Parâmetros", "Critérios e Fórmulas"]


def test_aba_de_parametros_traz_os_pesos_e_cortes():
    wb = _abrir(gerar_planilha([linha()], parametros()))
    ws = wb["Parâmetros"]
    assert ws["B2"].value == 3.95 and ws["B3"].value == 3.35
    assert ws["B4"].value == 2 and ws["B5"].value == 4
    assert ws["B8"].value == 0.20 and ws["B9"].value == 0.25 and ws["B14"].value == 0.07


def test_linha_de_dados_traz_valores_e_formulas_vivas():
    wb = _abrir(gerar_planilha([linha()], parametros()))
    ws = wb["Histórico da Carteira"]
    assert ws["A5"].value == "Alfa"
    assert ws["I5"].value == 5.0  # nota receita
    assert ws["R5"].value == (
        "=I5*Parâmetros!$B$8 + J5*Parâmetros!$B$9 + O5*Parâmetros!$B$10"
        " + (6-K5)*Parâmetros!$B$11 + N5*Parâmetros!$B$12 + L5*Parâmetros!$B$13"
        " + (6-M5)*Parâmetros!$B$14"
    )
    assert ws["S5"].value == '=IF(R5>=Parâmetros!$B$2,"A",IF(R5>=Parâmetros!$B$3,"B","C"))'


def test_a_formula_do_score_recalcula_igual_ao_dominio():
    """A mesma conta de `crm.domain.classificacao.score`, aplicada à mão sobre os valores da linha."""
    from crm.domain import classificacao as regra

    n = regra.Notas(receita=5, rentabilidade=1, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=3, semaforo=1, churn=1)
    esperado = regra.score(n)

    p = parametros()
    calculado = (
        float(n.receita) * float(p.peso_receita) + float(n.rentabilidade) * float(p.peso_rentabilidade)
        + float(n.adimplencia) * float(p.peso_adimplencia) + (6 - float(n.complexidade)) * float(p.peso_complexidade)
        + float(n.cross_sell) * float(p.peso_cross_sell) + float(n.disciplina) * float(p.peso_disciplina)
        + (6 - float(n.risco)) * float(p.peso_risco)
    )
    assert round(calculado, 4) == float(esperado)


def test_multiplas_linhas_multiplos_grupos_ficam_em_sequencia():
    linhas = [linha(grupo_nome="Alfa", revisao=1), linha(grupo_nome="Alfa", revisao=2), linha(grupo_nome="Beta", revisao=1)]
    wb = _abrir(gerar_planilha(linhas, parametros()))
    ws = wb["Histórico da Carteira"]
    assert [ws.cell(row=r, column=1).value for r in (5, 6, 7)] == ["Alfa", "Alfa", "Beta"]
    assert [ws.cell(row=r, column=3).value for r in (5, 6, 7)] == [1, 2, 1]


def test_motivo_e_atribuido_por_vazios_nao_quebram_a_planilha():
    wb = _abrir(gerar_planilha([linha(atribuido_por=None, motivo=None)], parametros()))
    ws = wb["Histórico da Carteira"]
    assert not ws["F5"].value and not ws["G5"].value


def test_aba_de_criterios_documenta_o_que_nao_e_formula():
    wb = _abrir(gerar_planilha([linha()], parametros()))
    ws = wb["Critérios e Fórmulas"]
    textos = " ".join(str(ws.cell(row=r, column=3).value) for r in range(3, 9))
    assert "Eixo de ação" in [ws.cell(row=r, column=2).value for r in range(3, 9)]
    assert "precedência" in textos
