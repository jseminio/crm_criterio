"""Período de avaliação: rascunho por grupo, cálculo de um cliente sem mexer na carteira e cálculo
da carteira inteira só com todos completos (pedido de Eduardo, 29/09/2026)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import ClassificacaoDoGrupo, GrupoEconomico
from crm.domain import classificacao as regra
from crm.domain import porte as regras_de_porte
from crm.domain.listas import SituacaoGrupo

AUTOR = "Karine"
NOTAS = regra.Notas(receita=3, rentabilidade=3, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=5, semaforo=1, churn=1)
PORTE_PEQUENO = {"cnpjs_no_escopo": 1, "empregados_clt": 5, "servicos_contratados_alem_do_primeiro": 0,
                 "tem_consolidacao_de_grupo": False, "e_auditada": False}
ABAS_COMPLETAS = {
    "complexidade": ["holding"], "risco": [], "cross_sell": ["mais_de_uma_linha"],
    "disciplina": {"meses_no_prazo": 3, "cobranca_dobrada": False, "atraso_recorrente": False},
    "inadimplencia": {"meses_em_dia": 3, "em_negociacao": False, "ja_suspenso": False},
}


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def _grupo(sessao: Session, nome: str, receita: str = "3200", porte: str | None = None) -> GrupoEconomico:
    g = GrupoEconomico(nome=nome, situacao=SituacaoGrupo.CLIENTE, porte=porte)
    sessao.add(g)
    sessao.flush()
    pontos = regra.score(NOTAS)
    letra = regra.classe(pontos)
    sessao.add(ClassificacaoDoGrupo(
        grupo_id=g.id, referencia=date(2026, 8, 31), revisao=1, fonte="teste", versao_dos_parametros="v1",
        receita_mensal=Decimal(receita), nota_receita=NOTAS.receita, nota_rentabilidade=NOTAS.rentabilidade,
        complexidade=NOTAS.complexidade, disciplina=NOTAS.disciplina, risco_tecnico=NOTAS.risco,
        cross_sell=NOTAS.cross_sell, adimplencia=NOTAS.adimplencia, semaforo=1, churn=1, score=pontos, classe=letra,
        classe_efetiva=regra.classe_efetiva(letra, NOTAS), alerta_de_churn=None, em_cobranca=False,
        eixo_de_acao=regra.eixo_de_acao(letra, NOTAS),
    ))
    sessao.commit()
    return g


def _abrir(cliente, **janela):
    r = cliente.post("/api/carteira/periodo", json={"autor": AUTOR, "mes": "2026-10", **janela})
    assert r.status_code == 201, r.text
    return r.json()


def _porte_sugerido() -> str:
    return regras_de_porte.sugerir_porte(regras_de_porte.Volumetria(**PORTE_PEQUENO)).porte.value


def _rascunho(cliente, grupo_id, **abas):
    return cliente.put(f"/api/carteira/periodo/grupos/{grupo_id}/rascunho", json={"autor": AUTOR, **abas})


def _completar(cliente, grupo_id):
    r = _rascunho(cliente, grupo_id, **ABAS_COMPLETAS, porte={**PORTE_PEQUENO, "porte": _porte_sugerido()})
    assert r.status_code == 200, r.text


def _leituras(sessao: Session, grupo_id: int) -> int:
    return sessao.scalar(sa.select(sa.func.count()).select_from(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == grupo_id))


class TestAbrirPeriodo:
    def test_sem_periodo_a_janela_e_a_padrao(self, cliente, sessao):
        _grupo(sessao, "Alfa")
        assert cliente.get("/api/carteira/periodo").json() is None
        janela = cliente.get("/api/carteira/classificacao").json()["janela"]
        assert janela == {"margem_minima": "0.6000", "margem_alvo": "0.7000", "origem": "padrão"}

    def test_abre_com_a_janela_padrao_e_so_um_por_vez(self, cliente, sessao):
        _grupo(sessao, "Alfa")
        p = _abrir(cliente)
        assert p["mes_de_referencia"] == "2026-10-01" and p["margem_alvo"] == "0.7000"
        assert p["grupos"] == 1 and p["completos"] == 0 and p["abas"] == 6
        assert cliente.post("/api/carteira/periodo", json={"autor": AUTOR, "mes": "2026-11"}).status_code == 409

    @pytest.mark.parametrize("janela", [
        {"margem_minima": "0.75", "margem_alvo": "0.70"},  # mínima acima do alvo
        {"margem_minima": "0.60", "margem_alvo": "0.89"},  # alvo + imposto de 11% chega a 100%
    ])
    def test_janela_invalida_e_recusada(self, cliente, janela):
        assert cliente.post("/api/carteira/periodo", json={"autor": AUTOR, "mes": "2026-10", **janela}).status_code == 422

    def test_janela_do_periodo_pode_mudar_enquanto_aberto(self, cliente, sessao):
        _abrir(cliente)
        r = cliente.patch("/api/carteira/periodo/janela", json={"autor": AUTOR, "margem_minima": "0.55", "margem_alvo": "0.65"})
        assert r.status_code == 200 and r.json()["margem_minima"] == "0.5500"


class TestRascunho:
    def test_sem_periodo_aberto_nao_grava(self, cliente, sessao):
        g = _grupo(sessao, "Alfa")
        assert _rascunho(cliente, g.id, risco=[]).status_code == 409

    def test_grava_aos_poucos_sem_mexer_na_carteira(self, cliente, sessao):
        g = _grupo(sessao, "Alfa")
        _abrir(cliente)
        score = cliente.get("/api/carteira/classificacao").json()["itens"][0]["score"]
        assert _rascunho(cliente, g.id, complexidade=["holding", "auditoria"]).status_code == 200
        r = _rascunho(cliente, g.id, risco=["certificado_vencendo"])
        assert r.json()["preenchidas"] == ["complexidade", "risco"]
        assert r.json()["respostas"]["complexidade"] == ["holding", "auditoria"]  # a primeira gravação continua
        item = cliente.get("/api/carteira/classificacao").json()["itens"][0]
        assert item["score"] == score and item["rascunho"]["atualizado_por"] == AUTOR
        assert _leituras(sessao, g.id) == 1
        periodo = cliente.get("/api/carteira/periodo").json()
        assert periodo["pendentes"] == [{"grupo_id": g.id, "grupo_nome": "Alfa", "preenchidas": 2}]

    def test_aba_revista_sem_nada_marcado_conta(self, cliente, sessao):
        g = _grupo(sessao, "Alfa")
        _abrir(cliente)
        assert _rascunho(cliente, g.id, risco=[]).json()["preenchidas"] == ["risco"]

    def test_porte_diferente_da_sugestao_exige_justificativa(self, cliente, sessao):
        g = _grupo(sessao, "Alfa")
        _abrir(cliente)
        outro = next(p.value for p in regras_de_porte.Porte if p.value != _porte_sugerido())
        sem = _rascunho(cliente, g.id, porte={**PORTE_PEQUENO, "porte": outro})
        assert sem.status_code == 422 and "justificativa obrigatória" in sem.json()["detail"]
        com = _rascunho(cliente, g.id, porte={**PORTE_PEQUENO, "porte": outro, "justificativa": "Folha em três estados."})
        assert com.status_code == 200 and com.json()["respostas"]["porte"]["justificativa"] == "Folha em três estados."
        assert _rascunho(cliente, g.id, porte={**PORTE_PEQUENO, "porte": _porte_sugerido()}).status_code == 200

    def test_porte_desconhecido_e_recusado(self, cliente, sessao):
        g = _grupo(sessao, "Alfa")
        _abrir(cliente)
        assert _rascunho(cliente, g.id, porte={**PORTE_PEQUENO, "porte": "Gigante"}).status_code == 422


class TestCalcularEsteCliente:
    def test_mostra_o_resultado_sem_gravar_e_usa_a_nota_atual_nas_abas_pendentes(self, cliente, sessao):
        g = _grupo(sessao, "Alfa", receita="3200", porte="Médio")
        _abrir(cliente)
        _rascunho(cliente, g.id, complexidade=[], risco=[])  # complexidade 1, risco 1
        r = cliente.post(f"/api/carteira/periodo/grupos/{g.id}/simulacao")
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["pendentes"] == ["disciplina", "cross_sell", "inadimplencia", "porte"]
        assert s["notas_antes"]["complexidade"] == "3.00" and s["notas_depois"]["complexidade"] == "1"
        assert s["notas_depois"]["disciplina"] == "3.00"  # pendente: fica a da carteira
        assert Decimal(s["score_depois"]) > Decimal(s["score_antes"])
        assert s["rentabilidade"]["porte"] == "Médio"
        assert _leituras(sessao, g.id) == 1  # nada gravado

    def test_rentabilidade_usa_o_porte_do_rascunho(self, cliente, sessao):
        g = _grupo(sessao, "Alfa", receita="1900", porte="Pequeno")
        _abrir(cliente)
        _rascunho(cliente, g.id, porte={**PORTE_PEQUENO, "porte": "Médio", "justificativa": "Consolidação trimestral."})
        s = cliente.post(f"/api/carteira/periodo/grupos/{g.id}/simulacao").json()
        assert s["rentabilidade"]["porte"] == "Médio"


class TestCalcularCarteira:
    def test_recusa_enquanto_faltar_grupo_e_diz_quais(self, cliente, sessao):
        a = _grupo(sessao, "Alfa")
        _grupo(sessao, "Beta")
        _abrir(cliente)
        _completar(cliente, a.id)
        r = cliente.post("/api/carteira/periodo/calcular", json={"autor": AUTOR})
        assert r.status_code == 409 and "faltam 1 de 2 grupos: Beta" in r.json()["detail"]
        assert _leituras(sessao, a.id) == 1

    def test_com_todos_completos_aplica_tudo_e_fecha_o_periodo(self, cliente, sessao):
        a = _grupo(sessao, "Alfa", porte="Grande")
        b = _grupo(sessao, "Beta")
        _abrir(cliente, margem_minima="0.55", margem_alvo="0.65")
        _completar(cliente, a.id)
        _completar(cliente, b.id)
        r = cliente.post("/api/carteira/periodo/calcular", json={"autor": AUTOR})
        assert r.status_code == 200, r.text
        assert r.json()["grupos_calculados"] == 2 and r.json()["periodo"]["calculado_por"] == AUTOR
        assert cliente.get("/api/carteira/periodo").json() is None
        itens = {i["grupo_nome"]: i for i in cliente.get("/api/carteira/classificacao").json()["itens"]}
        alfa = itens["Alfa"]
        assert alfa["notas"]["complexidade"] == "2.00" and alfa["notas"]["risco"] == "1.00" and alfa["notas"]["cross_sell"] == "2.00"
        assert alfa["porte"]["porte"] == _porte_sugerido() and alfa["porte"]["porte_definido_por"] == AUTOR
        assert alfa["avaliacao"]["respostas"]["complexidade"] == ["holding"]
        assert alfa["rascunho"] is None
        assert _leituras(sessao, a.id) == 2
        janela = cliente.get("/api/carteira/classificacao").json()["janela"]
        assert janela == {"margem_minima": "0.5500", "margem_alvo": "0.6500", "origem": "último período"}

    def test_depois_de_calcular_o_proximo_periodo_repete_a_janela(self, cliente, sessao):
        a = _grupo(sessao, "Alfa")
        _abrir(cliente, margem_minima="0.55", margem_alvo="0.65")
        _completar(cliente, a.id)
        cliente.post("/api/carteira/periodo/calcular", json={"autor": AUTOR})
        p = cliente.post("/api/carteira/periodo", json={"autor": AUTOR, "mes": "2026-11"}).json()
        assert p["margem_minima"] == "0.5500" and p["margem_alvo"] == "0.6500"
        assert cliente.post("/api/carteira/periodo", json={"autor": AUTOR, "mes": "2026-10"}).status_code == 409


class TestRentabilidadeNaCarteira:
    def test_receita_calculada_e_defasagem(self, cliente, sessao):
        _grupo(sessao, "Épsilon", receita="3200", porte="Médio")
        r = cliente.get("/api/carteira/classificacao").json()["itens"][0]["rentabilidade_do_grupo"]
        assert r["honorario_calculado"] == "4365.26" and r["defasagem"] == "-0.2669"
        assert r["margem"] == "0.6308" and r["revisao_de_honorarios"] is False

    def test_abaixo_da_minima_do_periodo_pede_revisao(self, cliente, sessao):
        _grupo(sessao, "Épsilon", receita="3200", porte="Médio")
        _abrir(cliente, margem_minima="0.65", margem_alvo="0.70")
        r = cliente.get("/api/carteira/classificacao").json()["itens"][0]["rentabilidade_do_grupo"]
        assert r["revisao_de_honorarios"] is True

    def test_sem_porte_nao_ha_calculo(self, cliente, sessao):
        _grupo(sessao, "Alfa")
        assert cliente.get("/api/carteira/classificacao").json()["itens"][0]["rentabilidade_do_grupo"] is None
