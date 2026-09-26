"""A fila de follow-up: classifica por data e faz a falta de próxima ação aparecer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from crm.domain.agenda import BALDES, montar
from crm.domain.listas import Situacao, SituacaoLead, Temperatura

HOJE = date(2026, 9, 25)


@dataclass
class Op:
    id: int
    nome: str = "Alfa BPO"
    situacao: Situacao = Situacao.ENVIAR_PROPOSTA
    temperatura: Temperatura | None = None
    captador: str | None = None
    preco_anual: Decimal | None = None
    proxima_acao: str | None = None
    proxima_acao_em: date | None = None
    data_colocacao: date | None = None


@dataclass
class Lead:
    id: int
    nome: str = "Maria"
    empresa_texto: str | None = None
    situacao: SituacaoLead = SituacaoLead.NOVO
    temperatura: Temperatura | None = None
    captador: str | None = None
    proxima_acao: str | None = None
    proxima_acao_em: date | None = None


def _baldes(ops, leads=()):
    return {i.id: i.balde for i in montar(oportunidades=[(o, "Grupo") for o in ops], leads=leads, hoje=HOJE)}


def test_classifica_cada_caso_no_balde_certo():
    b = _baldes([
        Op(1, proxima_acao="ligar", proxima_acao_em=date(2026, 9, 20)),
        Op(2, proxima_acao="ligar", proxima_acao_em=HOJE),
        Op(3, proxima_acao="ligar", proxima_acao_em=date(2026, 10, 2)),   # +7 exato
        Op(4, proxima_acao="ligar", proxima_acao_em=date(2026, 10, 3)),   # +8
        Op(5, proxima_acao="ligar"),
        Op(6),
        Op(7, proxima_acao="   "),  # só espaço = sem ação
    ])
    assert b == {1: "atrasada", 2: "hoje", 3: "proximos_7_dias", 4: "depois", 5: "sem_data", 6: "sem_acao", 7: "sem_acao"}


def test_ordem_dos_baldes_e_a_de_atencao():
    itens = montar(
        oportunidades=[(Op(1), "G"), (Op(2, proxima_acao="x", proxima_acao_em=date(2026, 9, 1)), "G"),
                       (Op(3, proxima_acao="x", proxima_acao_em=HOJE), "G")],
        leads=[], hoje=HOJE)
    assert [i.balde for i in itens] == ["atrasada", "hoje", "sem_acao"]
    assert list(BALDES) == ["atrasada", "hoje", "proximos_7_dias", "depois", "sem_data", "sem_acao"]


def test_atrasada_mostra_quantos_dias_e_a_mais_atrasada_vem_primeiro():
    itens = montar(oportunidades=[(Op(1, proxima_acao="a", proxima_acao_em=date(2026, 9, 24)), "G"),
                                  (Op(2, proxima_acao="a", proxima_acao_em=date(2026, 9, 10)), "G")], leads=[], hoje=HOJE)
    assert [(i.id, i.dias_de_atraso) for i in itens] == [(2, 15), (1, 1)]


def test_sem_acao_ordena_por_temperatura_e_depois_por_valor():
    itens = montar(oportunidades=[
        (Op(1, temperatura=Temperatura.FRIO, preco_anual=Decimal(900000)), "A"),
        (Op(2, temperatura=Temperatura.QUENTE, preco_anual=Decimal(100)), "B"),
        (Op(3, temperatura=Temperatura.QUENTE, preco_anual=Decimal(5000)), "C"),
        (Op(4), "D"),
    ], leads=[], hoje=HOJE)
    assert [i.id for i in itens] == [3, 2, 1, 4]


def test_idade_da_proposta_e_leads_entram_na_mesma_fila():
    itens = montar(oportunidades=[(Op(1, data_colocacao=date(2026, 9, 5)), "G")],
                   leads=[Lead(9, empresa_texto="Beta SA")], hoje=HOJE)
    op = next(i for i in itens if i.tipo == "oportunidade")
    lead = next(i for i in itens if i.tipo == "lead")
    assert op.dias_desde_o_envio == 20
    assert (lead.titulo, lead.subtitulo, lead.dias_desde_o_envio, lead.balde) == ("Beta SA", "Maria", None, "sem_acao")


def test_titulo_e_o_grupo_e_o_nome_da_proposta_vira_subtitulo_quando_difere():
    i = montar(oportunidades=[(Op(1, nome="Alfa - BPO"), "Alfa")], leads=[], hoje=HOJE)[0]
    assert (i.titulo, i.subtitulo) == ("Alfa", "Alfa - BPO")
    j = montar(oportunidades=[(Op(2, nome="Alfa"), "Alfa")], leads=[], hoje=HOJE)[0]
    assert j.subtitulo is None
