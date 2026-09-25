"""Os indicadores do funil — e, tão importante quanto, o que eles se recusam a dizer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from crm.domain.indicadores import calcular
from crm.domain.listas import Situacao, TipoCanal


@dataclass
class Op:
    situacao: Situacao
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    data_colocacao: date | None = None
    data_aceite: date | None = None
    proxima_acao: str | None = None
    tipo_canal: TipoCanal | None = None
    documentos_fiscais_mes: int | None = None
    lancamentos_contabeis_mes: int | None = None
    pagamentos_mes: int | None = None
    contas_bancarias: int | None = None
    conciliacoes_cartao_mes: int | None = None
    empregados_clt: int | None = None
    admissoes_desligamentos_mes: int | None = None
    cnpjs_no_escopo: int | None = None
    tomadores_de_servico: int | None = None
    grupo_id: int = 0


#: Os nove direcionadores preenchidos — para os testes de "ficha completa".
VOLUMETRIA_COMPLETA = dict(
    documentos_fiscais_mes=100, lancamentos_contabeis_mes=200, pagamentos_mes=50,
    contas_bancarias=2, conciliacoes_cartao_mes=100, empregados_clt=10,
    admissoes_desligamentos_mes=2, cnpjs_no_escopo=1, tomadores_de_servico=10,
)


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


class TestCicloMedioDeVendas:
    """Decisão de Eduardo em 23/09/2026: originação → aceite."""

    def test_sem_aceitas_nao_e_calculavel(self):
        ind = calcular([Op(Situacao.RECUSADA)])

        assert ind.ciclo_medio.calculavel is False
        assert ind.ciclo_medio.dias is None
        assert ind.ciclo_medio.amostra == 0

    def test_aceita_sem_as_duas_datas_fica_fora_nao_vira_zero(self):
        """Sem isto, uma aceita sem data pareceria "fechou na hora" em vez de
        "não dá para medir esta"."""
        ind = calcular([
            Op(Situacao.ACEITA, data_colocacao=date(2026, 3, 1), data_aceite=date(2026, 3, 11)),
            Op(Situacao.ACEITA, data_colocacao=date(2026, 3, 1)),  # sem data de aceite
        ])

        assert ind.ciclo_medio.calculavel is True
        assert ind.ciclo_medio.amostra == 1
        assert ind.ciclo_medio.aceitas_sem_as_duas_datas == 1
        assert ind.ciclo_medio.dias == D("10.0")

    def test_media_de_varias_aceitas(self):
        ind = calcular([
            Op(Situacao.ACEITA, data_colocacao=date(2026, 1, 1), data_aceite=date(2026, 1, 11)),  # 10
            Op(Situacao.ACEITA, data_colocacao=date(2026, 1, 1), data_aceite=date(2026, 1, 21)),  # 20
        ])

        assert ind.ciclo_medio.dias == D("15.0")
        assert ind.ciclo_medio.amostra == 2


class TestCobertura:
    """"Aumentar os pontos de contato" virando número — documento-de-negocio.md, seção 12.5."""

    def test_percentual_com_proxima_acao_considera_so_em_aberto(self):
        ind = calcular([
            Op(Situacao.ENVIAR_PROPOSTA, proxima_acao="Ligar"),
            Op(Situacao.ON_HOLD),  # em aberto, sem próxima ação
            Op(Situacao.ACEITA),  # decidida — fora da conta de "em aberto"
        ])

        assert ind.cobertura.em_aberto_total == 2
        assert ind.cobertura.em_aberto_com_proxima_acao == 1
        assert ind.cobertura.percentual_com_proxima_acao == D("50.0")

    def test_string_vazia_nao_conta_como_proxima_acao(self):
        ind = calcular([Op(Situacao.ENVIAR_PROPOSTA, proxima_acao="  ")])

        assert ind.cobertura.em_aberto_com_proxima_acao == 0

    def test_sem_nenhuma_em_aberto_nao_calcula(self):
        ind = calcular([Op(Situacao.ACEITA)])

        assert ind.cobertura.percentual_com_proxima_acao is None

    def test_ficha_completa_exige_os_nove_direcionadores(self):
        completa = Op(Situacao.ENVIAR_PROPOSTA, **VOLUMETRIA_COMPLETA)
        incompleta = Op(Situacao.ENVIAR_PROPOSTA, **{**VOLUMETRIA_COMPLETA, "cnpjs_no_escopo": None})

        ind = calcular([completa, incompleta])

        assert ind.cobertura.com_volumetria_completa == 1
        assert ind.cobertura.total == 2
        assert ind.cobertura.percentual_com_volumetria_completa == D("50.0")


class TestDependenciaDeCanal:
    """Insight já identificado em documento-de-negocio.md: 56% da rede dos sócios em 19/09/2026."""

    def test_conta_so_o_canal_socios(self):
        ind = calcular([
            Op(Situacao.ENVIAR_PROPOSTA, tipo_canal=TipoCanal.SOCIOS),
            Op(Situacao.ENVIAR_PROPOSTA, tipo_canal=TipoCanal.SOCIOS),
            Op(Situacao.ENVIAR_PROPOSTA, tipo_canal=TipoCanal.PARCEIROS),
            Op(Situacao.ENVIAR_PROPOSTA, tipo_canal=None),
        ])

        assert ind.dependencia_de_canal.da_rede_de_socios == 2
        assert ind.dependencia_de_canal.total == 4
        assert ind.dependencia_de_canal.percentual == D("50.0")

    def test_funil_vazio_nao_calcula(self):
        ind = calcular([])

        assert ind.dependencia_de_canal.percentual is None


class TestTicketRecorrente:
    def _aceita(self, valor, grupo=0):
        return Op(situacao=Situacao.ACEITA, preco_mensal=None if valor is None else D(valor), grupo_id=grupo)

    def test_media_e_mediana_so_das_aceitas_com_preco_mensal(self):
        t = calcular([
            self._aceita("1000", 1), self._aceita("2000", 2), self._aceita("9000", 3),
            self._aceita(None, 4),                         # valor único: fora
            self._aceita("0", 5),                          # pro bono: fora
            Op(situacao=Situacao.ENVIAR_PROPOSTA, preco_mensal=D("50000")),  # em aberto: fora
        ]).ticket_recorrente
        assert (t.quantas, t.clientes) == (3, 3)
        assert t.valor_mensal == D("12000")
        assert t.ticket_medio == D("4000.00") and t.mediana == D("2000.00")

    def test_mostra_o_peso_do_maior_contrato(self):
        t = calcular([self._aceita("40000", 1), self._aceita("2000", 2), self._aceita("2000", 3)]).ticket_recorrente
        assert t.maior_valor == D("40000") and t.participacao_do_maior == D("90.9")

    def test_conta_clientes_distintos(self):
        t = calcular([self._aceita("1000", 7), self._aceita("3000", 7), self._aceita("2000", 8)]).ticket_recorrente
        assert (t.quantas, t.clientes) == (3, 2)

    def test_mediana_de_quantidade_par(self):
        assert calcular([self._aceita("1000", 1), self._aceita("2000", 2)]).ticket_recorrente.mediana == D("1500.00")

    def test_sem_nenhuma_nao_e_calculavel_nem_zero(self):
        t = calcular([self._aceita(None, 1)]).ticket_recorrente
        assert not t.calculavel and t.ticket_medio is None and t.mediana is None
