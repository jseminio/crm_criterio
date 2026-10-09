"""Tarefa do atualizador de 09/10/2026: as premissas salvas do plano de MRR vão para 13 parcelas."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

from sqlalchemy.orm import Session

from crm.db.modelos import ContratoPrevistoDoPlano, PlanoDeMrr
from crm.manutencao.tarefas import premissas_em_13_parcelas as tarefa


def _plano(**k) -> PlanoDeMrr:
    base = dict(
        id=1, meta_liquida=D("250000"), inicio=date(2026, 9, 1), fim=date(2027, 6, 30), inicio_da_projecao=date(2026, 10, 1),
        ponto_de_partida=D("26000"), mrr_de_partida=D("252341"), churn_anual_pct=D("12"), bpo_ticket=D("7000"),
        bpo_teto=D("5"), contabil_vagas=D("4"), atipico_vagas=D("2"), escada_prazo_meses=3, plus_acrescimo=D("3000"),
        plus_pct=D("80"), cfo_acrescimo=D("6000"), cfo_pct=D("30"), alerta_bpo_por_mes=D("2"), previsto_bpo_por_mes=D("3"),
        otimista_bpo_por_mes=D("5"), alerta_ticket_contabil=D("2903.28"), previsto_ticket_contabil=D("3500"),
        otimista_ticket_contabil=D("5000"), alerta_com_previstos=True, previsto_com_previstos=True,
        otimista_com_previstos=True, alterado_por="Eduardo",
    )
    return PlanoDeMrr(**(base | k))


def test_converte_os_valores_em_reais_uma_vez_so(engine):
    with Session(engine) as s:
        s.add(_plano())
        s.add(ContratoPrevistoDoPlano(descricao="Atípico", mes=date(2026, 11, 1), valor=D("18000"), atipico=True))
        s.commit()
        assert "1 plano(s) e 1 contrato(s)" in tarefa.executar(s)
        s.commit()
        p = s.get(PlanoDeMrr, 1)
        assert (p.meta_liquida, p.ponto_de_partida, p.mrr_de_partida) == (D("270833.33"), D("28166.67"), D("273369.42"))
        assert (p.bpo_ticket, p.plus_acrescimo, p.cfo_acrescimo) == (D("7583.33"), D("3250.00"), D("6500.00"))
        assert (p.alerta_ticket_contabil, p.previsto_ticket_contabil, p.otimista_ticket_contabil) == (
            D("3145.22"), D("3791.67"), D("5416.67"))
        assert (p.bpo_teto, p.plus_pct, p.escada_prazo_meses) == (D("5"), D("80"), 3)  # contagem e % não mudam
        assert s.query(ContratoPrevistoDoPlano).one().valor == D("19500.00")
        assert tarefa.executar(s).startswith("nada a converter")  # de novo: não converte duas vezes
        assert s.get(PlanoDeMrr, 1).meta_liquida == D("270833.33")


def test_sem_plano_salvo_vale_o_padrao_ja_convertido(engine):
    with Session(engine) as s:
        assert tarefa.executar(s).startswith("nada a converter")
