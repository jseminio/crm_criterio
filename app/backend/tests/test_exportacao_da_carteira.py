import io
from datetime import date, datetime, timezone
from decimal import Decimal as D

import openpyxl

from crm.relatorios.exportacao_da_carteira import (
    EmpresaDaExportacao, LinhaDeHistorico, ParametrosDaPlanilha, gerar_planilha,
)


def linha(**o) -> LinhaDeHistorico:
    base = dict(
        grupo_id=1, grupo_nome="Alfa", referencia=date(2026, 7, 31), revisao=1,
        registrado_em=datetime(2026, 7, 31, 12, 0, tzinfo=timezone.utc), fonte="teste",
        atribuido_por=None, motivo=None, receita_mensal=D("1000.00"), margem=D("0.4200"), horas_por_mes=D("12.50"),
        nota_receita=D("5"), nota_rentabilidade=D("1"), complexidade=D("3"), disciplina=D("3"),
        risco_tecnico=D("3"), cross_sell=D("3"), adimplencia=D("3"), semaforo=1, churn=1,
        score=D("3.5000"), classe="B", classe_efetiva="B1", alerta_de_churn=None, em_cobranca=False,
        eixo_de_acao="Sem urgência de churn",
    )
    return LinhaDeHistorico(**{**base, **o})


def empresa(razao: str, cnpj: str | None = None, mensalidade: str | None = None) -> EmpresaDaExportacao:
    return EmpresaDaExportacao(razao_social=razao, cnpj=cnpj, mensalidade=D(mensalidade) if mensalidade else None)


def parametros(**o) -> ParametrosDaPlanilha:
    base = dict(
        corte_a=D("3.95"), corte_b=D("3.35"), trava_de_adimplencia=2, churn_alto=4,
        peso_receita=D("0.20"), peso_rentabilidade=D("0.25"), peso_adimplencia=D("0.15"),
        peso_complexidade=D("0.12"), peso_cross_sell=D("0.12"), peso_disciplina=D("0.09"), peso_risco=D("0.07"),
    )
    return ParametrosDaPlanilha(**{**base, **o})


def _abrir(conteudo: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(io.BytesIO(conteudo), data_only=False)


def _coluna_a(ws, linhas) -> list:
    return [ws.cell(row=r, column=1).value for r in linhas]


def test_tres_abas_na_ordem_do_modelo():
    wb = _abrir(gerar_planilha([linha()], parametros()))
    assert wb.sheetnames == ["Histórico da Carteira", "Parâmetros", "Critérios e Fórmulas"]


def test_aba_de_parametros_traz_os_pesos_e_cortes():
    wb = _abrir(gerar_planilha([linha()], parametros()))
    ws = wb["Parâmetros"]
    assert ws["B2"].value == 3.95 and ws["B3"].value == 3.35
    assert ws["B4"].value == 2 and ws["B5"].value == 4
    assert ws["B8"].value == 0.20 and ws["B9"].value == 0.25 and ws["B14"].value == 0.07


def test_cabecalho_na_ordem_do_modelo_com_rentabilidade_logo_depois_do_score():
    ws = _abrir(gerar_planilha([linha()], parametros()))["Histórico da Carteira"]
    cabecalho = [ws.cell(row=4, column=c).value for c in range(1, 28)]
    assert cabecalho[:5] == ["Grupo / Empresa", "Tipo", "Nº CNPJs / CNPJ", "Receita (R$/mês)", "Horas/mês"]
    i = cabecalho.index("Score")
    assert cabecalho[i + 1] == "Rentabilidade (Margem %)"
    assert cabecalho[-1] == "Motivo"


def test_linha_do_grupo_traz_valores_e_formulas_vivas():
    ws = _abrir(gerar_planilha([linha()], parametros()))["Histórico da Carteira"]
    assert ws["A5"].value == "▸ Alfa" and ws["B5"].value == "Grupo"
    assert ws["D5"].value == 1000.0 and ws["E5"].value == 12.5
    assert ws["F5"].value == 5.0  # nota receita
    assert ws["O5"].value == (
        "=F5*Parâmetros!$B$8 + G5*Parâmetros!$B$9 + L5*Parâmetros!$B$10"
        " + (6-H5)*Parâmetros!$B$11 + K5*Parâmetros!$B$12 + I5*Parâmetros!$B$13"
        " + (6-J5)*Parâmetros!$B$14"
    )
    assert ws["P5"].value == 0.42 and ws["P5"].number_format == "0.00%"  # margem, valor — não fórmula
    assert ws["Q5"].value == '=IF(O5>=Parâmetros!$B$2,"A",IF(O5>=Parâmetros!$B$3,"B","C"))'
    assert ws["R5"].value == '=Q5&N5&IF(L5<=Parâmetros!$B$4," (TRAVADO)","")'
    assert ws["S5"].value == '=IF(OR(M5="",M5<Parâmetros!$B$5),"",IF(Q5="C","⚑","⚠"))'
    assert ws["T5"].value == '=IF(L5<=Parâmetros!$B$4,"$$$","")'
    assert ws["U5"].value == (
        '=IF(T5="$$$","Cobrança — sem tratamento preferencial",'
        'IF(AND(S5="⚠",Q5="A"),"Reter já (crítico)",'
        'IF(AND(S5="⚠",Q5="B"),"Reter / vigiar",'
        'IF(S5="⚑","Saída organizada","Sem urgência de churn"))))'
    )


def test_os_textos_do_eixo_de_acao_sao_os_mesmos_do_dominio():
    """Se o domínio renomear um eixo, a fórmula da planilha precisa acompanhar."""
    from crm.domain import classificacao as regra

    formula = _abrir(gerar_planilha([linha()], parametros()))["Histórico da Carteira"]["U5"].value
    for adimplencia, churn, letra in ((1, 1, "A"), (3, 5, "A"), (3, 5, "B"), (3, 5, "C"), (3, 1, "A")):
        n = regra.Notas(receita=3, rentabilidade=3, complexidade=3, disciplina=3, risco=3, cross_sell=3,
                        adimplencia=adimplencia, semaforo=1, churn=churn)
        assert f'"{regra.eixo_de_acao(letra, n)}"' in formula


def test_sem_margem_nem_horas_as_celulas_ficam_vazias():
    ws = _abrir(gerar_planilha([linha(margem=None, horas_por_mes=None, churn=None)], parametros()))["Histórico da Carteira"]
    assert ws["E5"].value is None and ws["P5"].value is None and ws["M5"].value is None


def test_datas_usam_o_codigo_de_formato_que_o_excel_entende():
    ws = _abrir(gerar_planilha([linha()], parametros()))["Histórico da Carteira"]
    assert ws["V5"].number_format == "DD/MM/YYYY"
    assert ws["X5"].number_format == "DD/MM/YYYY HH:MM"


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


def test_empresas_aparecem_uma_vez_depois_da_leitura_mais_recente_do_grupo():
    linhas = [linha(grupo_id=1, grupo_nome="Alfa", revisao=1), linha(grupo_id=1, grupo_nome="Alfa", revisao=2),
              linha(grupo_id=2, grupo_nome="Beta", revisao=1)]
    empresas = {1: [empresa("Alfa Ltda", "11111111000191", "1500.00"), empresa("Alfa Serviços")],
                2: [empresa("Beta SA", "22222222000191", "800.00")]}
    ws = _abrir(gerar_planilha(linhas, parametros(), empresas))["Histórico da Carteira"]

    assert _coluna_a(ws, range(5, 11)) == [
        "▸ Alfa", "▸ Alfa", "    • Alfa Ltda", "    • Alfa Serviços", "▸ Beta", "    • Beta SA",
    ]
    assert [ws.cell(row=r, column=2).value for r in range(5, 11)] == ["Grupo", "Grupo", "Empresa", "Empresa", "Grupo", "Empresa"]
    assert ws["C5"].value == 2 and ws["C9"].value == 1  # nº de CNPJs na linha do grupo
    assert ws["C7"].value == "11111111000191" and ws["D7"].value == 1500.0
    assert ws["D8"].value is None  # sem contrato ativo, sem mensalidade inventada
    assert ws["O7"].value is None  # linha de empresa não tem Score
    assert [ws.cell(row=r, column=23).value for r in (5, 6, 9)] == [1, 2, 1]  # revisão


def test_grupos_com_o_mesmo_nome_nao_se_misturam():
    linhas = [linha(grupo_id=1, grupo_nome="Alfa"), linha(grupo_id=2, grupo_nome="Alfa")]
    empresas = {1: [empresa("Do primeiro")], 2: [empresa("Do segundo")]}
    ws = _abrir(gerar_planilha(linhas, parametros(), empresas))["Histórico da Carteira"]
    assert _coluna_a(ws, range(5, 9)) == ["▸ Alfa", "    • Do primeiro", "▸ Alfa", "    • Do segundo"]


def test_sem_empresas_so_as_linhas_de_grupo():
    ws = _abrir(gerar_planilha([linha(), linha(grupo_id=2, grupo_nome="Beta")], parametros()))["Histórico da Carteira"]
    assert _coluna_a(ws, range(5, 8)) == ["▸ Alfa", "▸ Beta", None]
    assert ws["C5"].value == 0


def test_motivo_e_atribuido_por_vazios_nao_quebram_a_planilha():
    ws = _abrir(gerar_planilha([linha(atribuido_por=None, motivo=None)], parametros()))["Histórico da Carteira"]
    assert not ws["Z5"].value and not ws["AA5"].value


def test_cabecalho_nao_promete_formula_onde_ha_valor():
    ws = _abrir(gerar_planilha([linha()], parametros()))["Histórico da Carteira"]
    assert "Rentabilidade" not in ws["A2"].value


def test_aba_de_criterios_documenta_formulas_e_lacunas():
    ws = _abrir(gerar_planilha([linha()], parametros()))["Critérios e Fórmulas"]
    rotulos = [ws.cell(row=r, column=2).value for r in range(3, 12)]
    textos = " ".join(str(ws.cell(row=r, column=3).value) for r in range(3, 12))
    assert {"Score", "Classe", "Classe Efetiva", "Alerta", "$$$", "Eixo de Ação", "Histórico"} <= set(rotulos)
    assert "precedência" in textos
    assert "EM BRANCO" in textos  # a lacuna de margem/horas por empresa está documentada
