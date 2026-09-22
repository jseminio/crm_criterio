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


class TestTaxaDeConversao:
    """Decisão de Eduardo em 22/09/2026: o denominador é só o que foi decidido."""

    def test_divide_aceitas_por_decididas_nao_por_todas(self):
        """Em aberto não entra em nenhum dos dois lados da conta."""
        ind = calcular([
            Op(Situacao.ACEITA), Op(Situacao.RECUSADA),
            Op(Situacao.ENVIAR_PROPOSTA),  # em aberto — de fora da conta
        ])

        assert (ind.taxa_de_conversao.aceitas, ind.taxa_de_conversao.decididas) == (1, 2)
        assert ind.taxa_de_conversao.percentual == D("50.0")
        assert ind.taxa_de_conversao.calculavel is True

    def test_arredonda_em_uma_casa_decimal(self):
        """40 aceitas em 105 decididas — o caso real de 2026, 22/09/2026."""
        ind = calcular(
            [Op(Situacao.ACEITA)] * 40
            + [Op(Situacao.RECUSADA)] * 65
        )

        assert ind.taxa_de_conversao.percentual == D("38.1")

    def test_sem_nenhuma_decidida_nao_e_calculavel(self):
        """Dividir por zero não pode virar 0% — pareceria que nada fechou."""
        ind = calcular([Op(Situacao.ENVIAR_PROPOSTA), Op(Situacao.ON_HOLD)])

        assert ind.taxa_de_conversao.calculavel is False
        assert ind.taxa_de_conversao.percentual is None

    def test_marca_abaixo_do_alerta_sob_30_por_cento(self):
        ind = calcular([Op(Situacao.ACEITA)] + [Op(Situacao.RECUSADA)] * 9)  # 10%

        assert ind.taxa_de_conversao.abaixo_do_alerta is True
        assert ind.taxa_de_conversao.atingiu_a_meta is False

    def test_marca_meta_atingida_a_partir_de_50_por_cento(self):
        ind = calcular([Op(Situacao.ACEITA)] * 5 + [Op(Situacao.RECUSADA)] * 5)  # 50%

        assert ind.taxa_de_conversao.atingiu_a_meta is True
        assert ind.taxa_de_conversao.abaixo_do_alerta is False

    def test_entre_alerta_e_meta_nao_marca_nenhum_dos_dois(self):
        ind = calcular([Op(Situacao.ACEITA)] * 4 + [Op(Situacao.RECUSADA)] * 6)  # 40%

        assert ind.taxa_de_conversao.abaixo_do_alerta is False
        assert ind.taxa_de_conversao.atingiu_a_meta is False


class TestOQueNaoSeCalcula:
    """Um indicador sem definição devolve o motivo, não um número que parece certo."""

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
