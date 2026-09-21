"""Os indicadores do funil — e, tão importante quanto, o que eles se recusam a dizer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from crm.domain.indicadores import calcular
from crm.domain.listas import Situacao


@dataclass
class Op:
    situacao: Situacao
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    data_aceite: date | None = None


D = Decimal


class TestEmAberto:
    def test_soma_o_que_ainda_nao_foi_decidido(self):
        ind = calcular([
            Op(Situacao.ENVIAR_PROPOSTA, D("1000"), D("13000")),
            Op(Situacao.EM_AVALIACAO, D("2000"), D("26000")),
            Op(Situacao.ON_HOLD, D("500"), D("6500")),
        ])
        assert ind.em_aberto.quantas == 3
        assert ind.em_aberto.valor_mensal == D("3500")
        assert ind.em_aberto.valor_anual == D("45500")

    def test_decidida_nao_entra_em_aberto(self):
        """Usa o conceito do domínio: se as situações mudarem, a conta muda junto."""
        ind = calcular([
            Op(Situacao.ACEITA, D("1000")), Op(Situacao.RECUSADA, D("1000")),
            Op(Situacao.PERDIDO, D("1000")),
        ])
        assert ind.em_aberto.quantas == 0

    def test_funil_vazio_soma_zero_e_nao_quebra(self):
        ind = calcular([])
        assert (ind.em_aberto.quantas, ind.aceitas.quantas) == (0, 0)
        assert ind.em_aberto.valor_mensal == D("0")


class TestAceitas:
    def test_soma_so_as_aceitas(self):
        ind = calcular([
            Op(Situacao.ACEITA, D("1000"), D("13000")),
            Op(Situacao.RECUSADA, D("9999"), D("99999")),
        ])
        assert ind.aceitas.quantas == 1
        assert ind.aceitas.valor_mensal == D("1000")

    def test_conta_quantas_nao_tem_preco_mensal(self):
        """Consultoria de valor único: o mensal cobre só parte do conjunto, e o
        número que diz quanto é o que impede o total de enganar."""
        ind = calcular([
            Op(Situacao.ACEITA, D("1000"), D("13000")),
            Op(Situacao.ACEITA, None, D("30000")),
            Op(Situacao.ACEITA, None, D("40000")),
        ])
        assert ind.aceitas.sem_preco_mensal == 2
        assert ind.aceitas.com_preco_mensal == 1
        # O que não tem mensal ainda entra no anual.
        assert ind.aceitas.valor_anual == D("83000")

    def test_conta_as_que_tem_data_de_aceite(self):
        ind = calcular([
            Op(Situacao.ACEITA, data_aceite=date(2026, 4, 1)),
            Op(Situacao.ACEITA),
        ])
        assert ind.aceitas_com_data_de_aceite == 1


class TestOQueNaoSeCalcula:
    """Um indicador sem definição devolve o motivo, não um número que parece certo."""

    def test_conversao_nunca_e_calculada_enquanto_o_denominador_nao_for_definido(self):
        ind = calcular([Op(Situacao.ACEITA), Op(Situacao.RECUSADA)])

        assert ind.taxa_de_conversao.calculavel is False
        assert "denominador" in ind.taxa_de_conversao.motivo

    def test_ciclo_explica_quantas_datas_faltam(self):
        ind = calcular([Op(Situacao.ACEITA)] * 40)

        assert ind.ciclo_medio.calculavel is False
        assert "0 de 40" in ind.ciclo_medio.motivo

    def test_ciclo_com_parte_das_datas_ainda_nao_e_calculavel(self):
        """Uma média sobre parte das aceitas seria enviesada pelas que foram
        preenchidas primeiro."""
        ind = calcular([Op(Situacao.ACEITA, data_aceite=date(2026, 4, 1)), Op(Situacao.ACEITA)])

        assert ind.ciclo_medio.calculavel is False
        assert "1 de 2" in ind.ciclo_medio.motivo

    def test_ciclo_com_todas_as_datas_ainda_pede_a_base_do_calculo(self):
        """Mesmo completo, a base — contar a partir de quando — não está registrada."""
        ind = calcular([Op(Situacao.ACEITA, data_aceite=date(2026, 4, 1))])

        assert ind.ciclo_medio.calculavel is False
        assert "a partir de quando" in ind.ciclo_medio.motivo

    def test_sem_aceitas_o_ciclo_diz_isso(self):
        ind = calcular([Op(Situacao.RECUSADA)])

        assert "Ainda não há proposta aceita" in ind.ciclo_medio.motivo
