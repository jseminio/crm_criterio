"""Classificação da carteira: fórmulas da especificação, com os números da planilha de 31/07/2026."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from crm.domain.classificacao import (
    PARAMETROS, Notas, Unidade, alerta_de_churn, classe, classe_efetiva, cobranca, eixo_de_acao, isc, score,
)


def N(rec=3, rent=3, comp=3, disc=3, risco=3, cross=3, adimp=5, sem=1, churn=1):
    return Notas(receita=rec, rentabilidade=rent, complexidade=comp, disciplina=disc, risco=risco,
                 cross_sell=cross, adimplencia=adimp, semaforo=sem, churn=churn)


class TestScore:
    def test_tudo_3_com_adimplencia_5(self):
        # 0,60 + 0,75 + 0,36 + 0,36 + 0,27 + 0,21 + 0,75 = 3,30
        assert score(N()) == D("3.30")

    def test_melhor_cliente_possivel_e_5_em_tudo_e_1_nos_invertidos(self):
        assert score(N(5, 5, 1, 5, 1, 5, 5)) == D("5.00")

    def test_pior_possivel_e_1(self):
        assert score(N(1, 1, 5, 1, 5, 1, 1)) == D("1.00")

    def test_complexidade_e_risco_entram_invertidos(self):
        assert score(N(comp=1)) > score(N(comp=5)) and score(N(risco=1)) > score(N(risco=5))

    @pytest.mark.parametrize("campo,valor", [("rec", 0), ("rent", 6), ("adimp", 0)])
    def test_nota_fora_de_1_a_5_e_recusada(self, campo, valor):
        with pytest.raises(ValueError, match="1 a 5"):
            score(N(**{campo: valor}))

    def test_semaforo_e_churn_tem_faixa_propria(self):
        with pytest.raises(ValueError, match="semáforo"):
            score(N(sem=4))
        with pytest.raises(ValueError, match="churn"):
            score(N(churn=6))

    def test_os_pesos_somam_100_por_cento(self):
        p = PARAMETROS
        assert p.peso_receita + p.peso_rentabilidade + p.peso_cross_sell + p.peso_complexidade + p.peso_disciplina + p.peso_risco + p.peso_adimplencia == D("1.00")


class TestClasse:
    @pytest.mark.parametrize("s,esperada", [("3.95", "A"), ("3.9499", "B"), ("3.35", "B"), ("3.3499", "C"), ("5", "A"), ("1", "C")])
    def test_cortes_fixos_no_limite(self, s, esperada):
        assert classe(D(s)) == esperada

    def test_o_semaforo_vira_sufixo(self):
        assert classe_efetiva("A", N(sem=1)) == "A1" and classe_efetiva("C", N(sem=3)) == "C3"

    def test_trava_de_inadimplencia_marca_mas_nao_rebaixa(self):
        assert classe_efetiva("B", N(adimp=2, sem=3)) == "B3 (TRAVADO)"
        assert classe_efetiva("B", N(adimp=3, sem=3)) == "B3"
        assert cobranca(N(adimp=2)) and cobranca(N(adimp=1)) and not cobranca(N(adimp=3))


class TestAlertaEEixo:
    def test_churn_alto_em_A_ou_B_e_alerta_de_reter_e_em_C_e_de_saida(self):
        assert alerta_de_churn("A", N(churn=4)) == "⚠" and alerta_de_churn("B", N(churn=5)) == "⚠"
        assert alerta_de_churn("C", N(churn=4)) == "⚑"
        assert alerta_de_churn("A", N(churn=3)) is None and alerta_de_churn("A", N(churn=None)) is None

    @pytest.mark.parametrize("letra,notas,esperado", [
        ("A", N(churn=5), "Reter já (crítico)"),
        ("B", N(churn=5), "Reter / vigiar"),
        ("C", N(churn=5), "Saída organizada"),
        ("A", N(churn=1), "Sem urgência de churn"),
        ("C", N(churn=1), "Sem urgência de churn"),
        ("A", N(churn=5, adimp=1), "Cobrança — sem tratamento preferencial"),   # cobrança vence o churn
        ("C", N(churn=5, adimp=2), "Cobrança — sem tratamento preferencial"),
    ])
    def test_eixo_de_acao_na_ordem_de_precedencia(self, letra, notas, esperado):
        assert eixo_de_acao(letra, notas) == esperado


class TestIsc:
    def u(self, receita, cl, sem, churn):
        return Unidade(D(receita), cl, sem, churn)

    def test_um_grupo_A_controlado_sem_churn_e_100(self):
        r = isc([self.u(1000, "A", 1, 1)])
        assert r.valor == D("100") and r.zona == "saudável"

    def test_um_grupo_C_critico_com_churn_5_e_zero(self):
        r = isc([self.u(1000, "C", 3, 5)])
        assert r.valor == D("6.6") and r.zona == "crítica"   # só a classe C (20 × 33%) conta

    def test_pondera_pela_receita(self):
        # 75% da receita em A/1/1 (100), 25% em C/3/5: classe 80, semáforo 75, churn 75
        r = isc([self.u(750, "A", 1, 1), self.u(250, "C", 3, 5)])
        assert (r.componente_classe, r.componente_semaforo, r.componente_churn) == (D("80"), D("75"), D("75"))
        assert r.valor == D("80") * D("0.33") + D("75") * D("0.33") + D("75") * D("0.34")

    def test_zonas_35_e_65(self):
        assert isc([self.u(1, "B", 2, 3)]).zona == "atenção"

    def test_grupo_sem_churn_fica_fora_e_e_contado(self):
        r = isc([self.u(1000, "A", 1, 1), self.u(9000, "C", 3, None)])
        assert (r.grupos, r.fora_do_isc, r.receita_total) == (1, 1, D("1000")) and r.valor == D("100")

    def test_sem_nenhum_completo_nao_calcula_nem_devolve_zero(self):
        assert isc([]) is None and isc([self.u(1000, "A", 1, None)]) is None
