"""Recortes por dimensão e cenários de ticket — os números que Eduardo já validou à mão."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal as D

import pytest

from crm.domain.listas import Situacao, TipoCanal
from crm.domain.recortes import cenarios_de_ticket, recortar


@dataclass
class Op:
    situacao: Situacao
    servico: str | None = None
    captador: str | None = None
    tipo_canal: TipoCanal | None = None
    preco_mensal: D | None = None


def aceita(valor, servico="BPO Contábil", **kw):
    return Op(Situacao.ACEITA, servico=servico, preco_mensal=None if valor is None else D(str(valor)), **kw)


#: Os 19 contratos recorrentes de 2026 (data de colocação), na base de 25/09/2026.
DEZENOVE = [750, 800, 800, 1621, 1621, 1621, 1630, 2000, 2450, 2450, 3000, 3500, 3500,
            4500, "6538.46", "6593", "6884.62", 15000, 40000]


class TestRecortar:
    def test_agrupa_por_servico_e_calcula_conversao_e_ticket(self):
        linhas = recortar([
            aceita(1000), aceita(3000), Op(Situacao.RECUSADA, servico="BPO Contábil"),
            Op(Situacao.EM_AVALIACAO, servico="BPO Contábil"),
            aceita(500, servico="Consultoria"),
        ], "servico")
        bpo = next(l for l in linhas if l.chave == "BPO Contábil")
        assert (bpo.propostas, bpo.aceitas, bpo.decididas, bpo.em_aberto) == (4, 2, 3, 1)
        assert bpo.conversao == D("66.7")
        assert (bpo.recorrentes, bpo.valor_mensal, bpo.ticket_medio, bpo.mediana) == (2, D("4000"), D("2000.00"), D("2000.00"))

    def test_sem_valor_vira_rotulo_explicito_e_valor_unico_nao_e_recorrente(self):
        linhas = recortar([aceita(None, servico=None), aceita(0, servico=None)], "servico")
        assert [l.chave for l in linhas] == ["(não informado)"]
        assert linhas[0].recorrentes == 0 and linhas[0].ticket_medio is None

    def test_canal_usa_o_valor_do_enum_e_ordena_por_volume(self):
        linhas = recortar([aceita(1, tipo_canal=TipoCanal.SOCIOS), aceita(1, tipo_canal=TipoCanal.SOCIOS), aceita(1)], "tipo_canal")
        assert [l.chave for l in linhas] == [TipoCanal.SOCIOS.value, "(não informado)"]

    def test_dimensao_invalida_e_recusada(self):
        with pytest.raises(ValueError):
            recortar([], "cor")


class TestCenarios:
    def test_reproduz_os_numeros_dos_19_contratos_de_2026(self):
        c = cenarios_de_ticket([aceita(v) for v in DEZENOVE])
        assert c.contratos == 19 and c.atipicos == 2
        assert c.limite_do_atipico == D("7350.00")
        assert c.conservador == D("2450.00")
        assert c.base == D("2956.42")
        assert c.otimista == D("3500.00")
        assert (c.atipico_minimo, c.atipico_medio, c.atipico_maximo) == (D("15000"), D("27500.00"), D("40000"))

    def test_sem_atipico_nao_inventa_atipico(self):
        c = cenarios_de_ticket([aceita(v) for v in (1000, 1100, 1200, 1300)])
        assert c.atipicos == 0 and c.atipico_medio is None

    def test_conservador_e_a_mediana_sem_os_atipicos(self):
        # mediana de todos = 300; sem o atípico (5000): 100, 200, 300, 900 -> mediana 250
        c = cenarios_de_ticket([aceita(v) for v in (100, 200, 300, 900, 5000)])
        assert c.atipicos == 1
        assert (c.conservador, c.base) == (D("250.00"), D("375.00"))

    def test_conservador_nunca_passa_do_base(self):
        """Regressão: com 100, 1.000, 1.000, 1.000 (+ o atípico 10.000) a mediana
        (1.000) passava da média (775) e o conservador saía maior que o base."""
        c = cenarios_de_ticket([aceita(v) for v in (100, 1000, 1000, 1000, 10000)])
        assert c.base == D("775.00")
        assert c.conservador == D("775.00")

    def test_otimista_nunca_fica_abaixo_do_base(self):
        # 1, 1, 1, 1, 3: nada é atípico (limite 3); terceiro quartil 1, média 1,40
        c = cenarios_de_ticket([aceita(v) for v in (1, 1, 1, 1, 3)])
        assert c.atipicos == 0
        assert (c.conservador, c.base, c.otimista) == (D("1.00"), D("1.40"), D("1.40"))

    @pytest.mark.parametrize(
        "valores",
        [
            (100, 1000, 1000, 1000, 10000),
            (1, 1000, 1000, 1000, 1000, 1000),
            (1, 1, 1, 1, 3),
            (1000, 1100, 1200, 1300),
            DEZENOVE,
        ],
    )
    def test_os_tres_cenarios_ficam_sempre_em_ordem(self, valores):
        c = cenarios_de_ticket([aceita(v) for v in valores])
        assert c.conservador <= c.base <= c.otimista

    def test_poucos_contratos_nao_geram_cenario(self):
        assert cenarios_de_ticket([aceita(1000), aceita(2000), aceita(3000)]) is None

    def test_so_conta_aceita_com_preco_mensal(self):
        assert cenarios_de_ticket([Op(Situacao.RECUSADA, preco_mensal=D("9")) for _ in range(6)]) is None
