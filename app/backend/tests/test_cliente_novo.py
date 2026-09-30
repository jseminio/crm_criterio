"""Cliente novo na Carteira e valor em contrato como receita praticada (pedido de Eduardo, 30/09/2026).

- Receita praticada = soma das mensalidades dos contratos ativos e suspensos (critério do MRR);
  sem contrato com mensalidade no CRM, vale a receita da leitura (a da planilha).
- Grupo com contrato valendo e sem nenhuma leitura é "cliente novo": entra no período com 7 abas
  (a sétima é Saúde: semáforo e churn) e ganha a primeira leitura no "Calcular carteira", com a nota
  de Receita pelo porte e a de Rentabilidade pela margem do CRM.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import ClassificacaoDoGrupo, Contrato, GrupoEconomico
from crm.domain import classificacao as regra
from crm.domain.listas import SituacaoContrato as S
from crm.domain.listas import SituacaoGrupo

from test_periodo_api import ABAS_COMPLETAS, AUTOR, PORTE_PEQUENO, _abrir, _completar, _grupo, _porte_sugerido, _rascunho

SAUDE = {"semaforo": 1, "churn": 2}


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def _contrato(sessao: Session, grupo_id: int, mensal: str | None, situacao=S.ATIVO, inicio: date | None = None) -> None:
    sessao.add(Contrato(grupo_id=grupo_id, situacao=situacao, preco_mensal=Decimal(mensal) if mensal else None,
                        data_inicio=inicio))
    sessao.commit()


def _novo(sessao: Session, nome: str = "Zeta") -> GrupoEconomico:
    """1.500 ativo + 1.100 suspenso = 2.600 em 2 contratos; encerrado e sem mensalidade ficam de fora."""
    g = GrupoEconomico(nome=nome, situacao=SituacaoGrupo.CLIENTE)
    sessao.add(g)
    sessao.commit()
    _contrato(sessao, g.id, "1500", inicio=date(2026, 10, 10))
    _contrato(sessao, g.id, "1100", S.SUSPENSO, inicio=date(2026, 10, 20))
    _contrato(sessao, g.id, "900", S.ENCERRADO, inicio=date(2025, 1, 1))
    _contrato(sessao, g.id, None)
    return g


def _completar_novo(cliente, grupo_id):
    r = _rascunho(cliente, grupo_id, **ABAS_COMPLETAS, porte={**PORTE_PEQUENO, "porte": _porte_sugerido()}, saude=SAUDE)
    assert r.status_code == 200, r.text
    return r.json()


def _carteira(cliente) -> dict:
    return cliente.get("/api/carteira/classificacao").json()


class TestValorEmContrato:
    def test_receita_praticada_e_a_soma_das_mensalidades_ativas_e_suspensas(self, cliente, sessao):
        g = _grupo(sessao, "Alfa", receita="3200", porte="Médio")
        _contrato(sessao, g.id, "2500")
        _contrato(sessao, g.id, "1500", S.SUSPENSO)
        _contrato(sessao, g.id, "700", S.ENCERRADO)
        item = _carteira(cliente)["itens"][0]
        assert item["receita_em_contrato"] == "4000.00" and item["contratos"] == 2
        assert item["receita_mensal"] == "3200.00"  # a leitura não muda até o "Calcular carteira"
        assert item["rentabilidade_do_grupo"]["honorario_praticado"] == "4000.00"

    def test_sem_contrato_no_crm_vale_a_receita_da_planilha(self, cliente, sessao):
        _grupo(sessao, "Alfa", receita="3200", porte="Médio")
        item = _carteira(cliente)["itens"][0]
        assert item["receita_em_contrato"] is None and item["contratos"] == 0
        assert item["rentabilidade_do_grupo"]["honorario_praticado"] == "3200.00"

    def test_calcular_carteira_grava_o_valor_em_contrato_e_mantem_a_nota_de_receita(self, cliente, sessao):
        g = _grupo(sessao, "Alfa", receita="3200", porte="Médio")
        _contrato(sessao, g.id, "4000")
        _abrir(cliente)
        _completar(cliente, g.id)
        assert cliente.post("/api/carteira/periodo/calcular", json={"autor": AUTOR}).status_code == 200
        ultima = sessao.scalars(sa.select(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == g.id)
                                .order_by(ClassificacaoDoGrupo.id.desc())).first()
        assert ultima.receita_mensal == Decimal("4000.00") and ultima.nota_receita == 3


class TestClienteNovoNaCarteira:
    def test_aparece_como_novo_fora_do_isc(self, cliente, sessao):
        _grupo(sessao, "Alfa")
        g = _novo(sessao)
        carteira = _carteira(cliente)
        assert [i["grupo_nome"] for i in carteira["itens"]] == ["Alfa"]
        assert carteira["isc"]["grupos"] == 1
        novo = carteira["novos"][0]
        assert novo["grupo_id"] == g.id and novo["desde"] == "2026-10-10"
        assert novo["receita_em_contrato"] == "2600.00" and novo["contratos"] == 2
        assert novo["rentabilidade_do_grupo"] is None  # sem porte e sem notas ainda
        assert any("1 cliente(s) novo(s)" in a and "Zeta" in a for a in carteira["avisos"])

    def test_so_ele_na_carteira(self, cliente, sessao):
        _novo(sessao)
        carteira = _carteira(cliente)
        assert carteira["itens"] == [] and carteira["novos"][0]["grupo_nome"] == "Zeta"

    @pytest.mark.parametrize("caso", ["sem_contrato", "so_encerrado", "sem_mensalidade", "fundido"])
    def test_nao_e_novo(self, cliente, sessao, caso):
        g = GrupoEconomico(nome="Eta", situacao=SituacaoGrupo.CLIENTE)
        sessao.add(g)
        sessao.commit()
        if caso == "so_encerrado":
            _contrato(sessao, g.id, "900", S.ENCERRADO)
        elif caso == "sem_mensalidade":
            _contrato(sessao, g.id, None)
        elif caso == "fundido":
            _contrato(sessao, g.id, "900")
            outro = _grupo(sessao, "Alfa")
            g.fundido_em_id = outro.id
            sessao.commit()
        assert _carteira(cliente)["novos"] == []

    def test_entra_no_periodo_com_sete_abas(self, cliente, sessao):
        g = _novo(sessao)
        _abrir(cliente)
        r = _rascunho(cliente, g.id, **ABAS_COMPLETAS, porte={**PORTE_PEQUENO, "porte": _porte_sugerido()})
        assert r.status_code == 200 and len(r.json()["preenchidas"]) == 6
        periodo = cliente.get("/api/carteira/periodo").json()
        assert periodo["grupos"] == 1 and periodo["completos"] == 0
        assert periodo["pendentes"] == [{"grupo_id": g.id, "grupo_nome": "Zeta", "preenchidas": 6, "abas": 7, "novo": True}]
        assert "saude" not in _carteira(cliente)["novos"][0]["rascunho"]["preenchidas"]
        assert _completar_novo(cliente, g.id)["preenchidas"][-1] == "saude"
        assert cliente.get("/api/carteira/periodo").json()["completos"] == 1

    def test_saude_so_para_cliente_novo(self, cliente, sessao):
        g = _grupo(sessao, "Alfa")
        _abrir(cliente)
        r = _rascunho(cliente, g.id, saude=SAUDE)
        assert r.status_code == 422 and "só para cliente novo" in r.json()["detail"]

    @pytest.mark.parametrize("saude", [{"semaforo": 4, "churn": 1}, {"semaforo": 1, "churn": 0}, {"semaforo": 1}])
    def test_saude_fora_da_escala_e_recusada(self, cliente, sessao, saude):
        g = _novo(sessao)
        _abrir(cliente)
        assert _rascunho(cliente, g.id, saude=saude).status_code == 422

    def test_grupo_sem_leitura_e_sem_contrato_nao_e_avaliado(self, cliente, sessao):
        g = GrupoEconomico(nome="Eta", situacao=SituacaoGrupo.CLIENTE)
        sessao.add(g)
        sessao.commit()
        _abrir(cliente)
        assert _rascunho(cliente, g.id, risco=[]).status_code == 409


class TestCalcularClienteNovo:
    def test_simulacao_parcial_sem_score(self, cliente, sessao):
        g = _novo(sessao)
        _abrir(cliente)
        _rascunho(cliente, g.id, porte={**PORTE_PEQUENO, "porte": _porte_sugerido()}, risco=[])
        s = cliente.post(f"/api/carteira/periodo/grupos/{g.id}/simulacao").json()
        assert s["novo"] is True and s["notas_antes"] is None and s["score_antes"] is None
        assert s["score_depois"] is None and s["classe_depois"] is None
        assert s["notas_depois"]["receita"] == "1" and s["notas_depois"]["risco"] == "1"
        assert s["notas_depois"]["complexidade"] is None and s["rentabilidade"] is None
        assert "saude" in s["pendentes"] and "porte" not in s["pendentes"]

    def test_simulacao_completa_e_igual_ao_calculo(self, cliente, sessao):
        g = _novo(sessao)
        _abrir(cliente)
        _completar_novo(cliente, g.id)
        s = cliente.post(f"/api/carteira/periodo/grupos/{g.id}/simulacao").json()
        # Micro (o que o questionário de teste sugere), complexidade 2, disciplina 5, risco 1: 5,25 h,
        # custo 218,86; margem com 2.600 = (2.600 − 286 − 218,86) ÷ 2.600 = 80,6% → nota 5; Receita Micro = 1.
        assert s["rentabilidade"]["margem"] == "0.8058" and s["rentabilidade"]["honorario_calculado"] == "1151.89"
        esperadas = regra.Notas(receita=1, rentabilidade=5, complexidade=2, disciplina=5, risco=1, cross_sell=2,
                                adimplencia=5, semaforo=1, churn=2)
        pontos = regra.score(esperadas)
        assert Decimal(s["score_depois"]) == pontos.quantize(Decimal("0.0001"))
        assert s["classe_depois"] == regra.classe_efetiva(regra.classe(pontos), esperadas)
        assert _carteira(cliente)["novos"][0]["rentabilidade_do_grupo"]["margem"] == "0.8058"

        r = cliente.post("/api/carteira/periodo/calcular", json={"autor": AUTOR})
        assert r.status_code == 200 and r.json()["grupos_calculados"] == 1
        leitura = sessao.scalars(sa.select(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == g.id)).one()
        assert leitura.revisao == 1 and leitura.fonte == "Cálculo da carteira, período 10/2026"
        assert leitura.receita_mensal == Decimal("2600.00") and leitura.margem == Decimal("0.8058")
        assert (leitura.nota_receita, leitura.nota_rentabilidade, leitura.semaforo, leitura.churn) == (1, 5, 1, 2)
        assert leitura.score == Decimal(s["score_depois"]) and leitura.rentabilidade_da_planilha is False
        assert "porte" not in leitura.respostas_da_avaliacao and leitura.respostas_da_avaliacao["saude"] == SAUDE
        sessao.expire_all()
        assert sessao.get(GrupoEconomico, g.id).porte == _porte_sugerido()

        carteira = _carteira(cliente)
        assert carteira["novos"] == [] and carteira["itens"][0]["grupo_nome"] == "Zeta"
        assert Decimal(carteira["itens"][0]["notas"]["rentabilidade"]) == 5

    def test_calcular_carteira_espera_a_aba_saude_do_novo(self, cliente, sessao):
        a = _grupo(sessao, "Alfa")
        g = _novo(sessao)
        _abrir(cliente)
        _completar(cliente, a.id)
        _rascunho(cliente, g.id, **ABAS_COMPLETAS, porte={**PORTE_PEQUENO, "porte": _porte_sugerido()})
        r = cliente.post("/api/carteira/periodo/calcular", json={"autor": AUTOR})
        assert r.status_code == 409 and r.json()["detail"] == "faltam 1 de 2 grupos: Zeta"
        assert sessao.scalar(sa.select(sa.func.count()).select_from(ClassificacaoDoGrupo)) == 1
        _completar_novo(cliente, g.id)
        r = cliente.post("/api/carteira/periodo/calcular", json={"autor": AUTOR})
        assert r.status_code == 200 and r.json()["grupos_calculados"] == 2
