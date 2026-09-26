"""MRR dos contratos registrados: o atual, o movimento e o que fica de fora."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D
from itertools import count

import pytest

from crm.domain.listas import IniciativaDoEncerramento as I
from crm.domain.listas import SituacaoContrato as S
from crm.domain.listas import TipoDeEventoDeContrato as T
from crm.domain.mrr import movimento, mrr_atual, mrr_em

_id = count(1)
HOJE = date(2026, 9, 25)


@dataclass
class Ev:
    tipo: T
    data_do_evento: date
    preco_mensal_anterior: D | None = None
    preco_mensal_novo: D | None = None
    iniciativa: I | None = None
    id: int = field(default_factory=lambda: next(_id))


@dataclass
class C:
    preco_mensal: D | None
    data_inicio: date | None = date(2026, 1, 15)
    situacao: S = S.ATIVO
    eventos: list[Ev] = field(default_factory=list)
    id: int = field(default_factory=lambda: next(_id))


class TestMrrAtual:
    def test_soma_so_os_ativos_e_separa_o_suspenso(self):
        m = mrr_atual([C(D("1000")), C(D("2000")), C(D("500"), situacao=S.SUSPENSO),
                       C(D("9"), situacao=S.AGUARDANDO_ASSINATURA, data_inicio=None), C(D("7"), situacao=S.ENCERRADO)])
        assert (m.valor, m.contratos, m.suspenso_valor, m.suspenso_contratos) == (D("3000"), 2, D("500"), 1)

    def test_contrato_sem_preco_mensal_fica_de_fora_e_e_contado(self):
        m = mrr_atual([C(D("1000")), C(None), C(D("0"))])
        assert (m.valor, m.contratos, m.sem_preco_mensal) == (D("1000"), 1, 2)

    def test_sem_contrato_nenhum_e_zero_nao_erro(self):
        assert mrr_atual([]).valor == D("0.00")


class TestMovimento:
    def test_contrato_novo_no_periodo_entra_como_novo(self):
        m = movimento([C(D("1000"), data_inicio=date(2026, 9, 10))], date(2026, 9, 1), HOJE, HOJE)
        assert (m.mrr_inicio, m.novo, m.mrr_fim) == (D("0"), D("1000"), D("1000"))
        assert m.nrr is None and m.grr is None  # sem MRR no início, não há o que medir

    def test_novo_usa_o_preco_da_assinatura_nao_o_atual(self):
        c = C(D("1200"), data_inicio=date(2026, 9, 2), eventos=[Ev(T.REAJUSTE, date(2026, 9, 20), D("1000"), D("1200"))])
        m = movimento([c], date(2026, 9, 1), HOJE, HOJE)
        assert m.novo == D("1000") and m.reajuste == D("200") and m.mrr_fim == D("1200")

    def test_expansao_reajuste_e_contracao(self):
        c = C(D("1000"), data_inicio=date(2026, 1, 15), eventos=[
            Ev(T.EXPANSAO, date(2026, 9, 5), D("700"), D("1000")),
        ])
        d = C(D("1500"), eventos=[Ev(T.REAJUSTE, date(2026, 9, 6), D("1400"), D("1500"))])
        e = C(D("400"), eventos=[Ev(T.CONTRACAO, date(2026, 9, 7), D("600"), D("400"))])
        m = movimento([c, d, e], date(2026, 9, 1), HOJE, HOJE)
        assert (m.expansao, m.reajuste, m.contracao) == (D("300"), D("100"), D("200"))
        # atual = 1000 + 1500 + 400 = 2900; líquido do período = +300 +100 −200 = +200; logo início = 2700
        assert m.mrr_inicio == D("2700") and m.mrr_fim == D("2900")
        assert m.nrr == D("107.4") and m.grr == D("92.6")

    def test_churn_se_separa_por_iniciativa(self):
        cli = C(D("1000"), situacao=S.ENCERRADO, eventos=[Ev(T.ENCERRAMENTO, date(2026, 9, 10), iniciativa=I.CLIENTE)])
        cri = C(D("500"), situacao=S.ENCERRADO, eventos=[Ev(T.ENCERRAMENTO, date(2026, 9, 12), iniciativa=I.CRITERIO)])
        fica = C(D("2500"))
        m = movimento([cli, cri, fica], date(2026, 9, 1), HOJE, HOJE)
        assert (m.churn_cliente, m.churn_criterio, m.churn) == (D("1000"), D("500"), D("1500"))
        assert (m.mrr_inicio, m.mrr_fim) == (D("4000"), D("2500"))
        assert m.grr == D("62.5") and m.nrr == D("62.5")

    def test_nrr_ignora_contrato_que_nasceu_no_periodo(self):
        velho = C(D("1000"))
        novo = C(D("2000"), data_inicio=date(2026, 9, 5), eventos=[Ev(T.EXPANSAO, date(2026, 9, 20), D("1000"), D("2000"))])
        m = movimento([velho, novo], date(2026, 9, 1), HOJE, HOJE)
        assert m.expansao == D("1000") and m.nrr == D("100.0")  # a expansão do novo não infla o NRR

    def test_mrr_do_passado_desfaz_o_que_veio_depois(self):
        c = C(D("1500"), eventos=[Ev(T.REAJUSTE, date(2026, 9, 20), D("1000"), D("1500"))])
        assert mrr_em([c], date(2026, 9, 10), HOJE) == D("1000")
        assert mrr_em([c], date(2026, 9, 20), HOJE) == D("1500")

    def test_contrato_encerrado_conta_no_mrr_do_passado(self):
        c = C(D("1000"), situacao=S.ENCERRADO, eventos=[Ev(T.ENCERRAMENTO, date(2026, 9, 10), iniciativa=I.CLIENTE)])
        assert mrr_em([c], date(2026, 9, 9), HOJE) == D("1000")
        assert mrr_em([c], date(2026, 9, 10), HOJE) == D("0")

    def test_periodo_invertido_e_data_futura_sao_recusados(self):
        with pytest.raises(ValueError):
            movimento([], date(2026, 9, 10), date(2026, 9, 1), HOJE)
        with pytest.raises(ValueError):
            mrr_em([], date(2026, 12, 1), HOJE)

    def test_a_conta_fecha(self):
        """início + novo + expansão + reajuste − contração − churn = fim."""
        cs = [C(D("1000")), C(D("800"), data_inicio=date(2026, 9, 3)),
              C(D("1300"), eventos=[Ev(T.EXPANSAO, date(2026, 9, 8), D("1000"), D("1300"))]),
              C(D("600"), situacao=S.ENCERRADO, eventos=[Ev(T.ENCERRAMENTO, date(2026, 9, 9), iniciativa=I.CLIENTE)])]
        m = movimento(cs, date(2026, 9, 1), HOJE, HOJE)
        assert m.mrr_inicio + m.novo + m.expansao + m.reajuste - m.contracao - m.churn == m.mrr_fim
