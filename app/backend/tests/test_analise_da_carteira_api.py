"""API da análise da carteira escrita pela IA — contra um cliente Anthropic falso, sem rede."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.api.classificacao import ServicosDeAnalise
from crm.db.modelos import GrupoEconomico
from crm.domain import classificacao as regra
from crm.domain.listas import SituacaoGrupo


def _resposta(texto):
    uso = NS(input_tokens=800, output_tokens=150, cache_creation_input_tokens=0, cache_read_input_tokens=0,
             server_tool_use=None)
    return NS(content=[NS(type="text", text=texto)], usage=uso)


class ClienteFalso:
    def __init__(self, resposta=None, excecao=None):
        self.resposta = resposta
        self.excecao = excecao
        self.chamadas: list[dict] = []
        self.messages = NS(create=self._criar)

    def _criar(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.excecao:
            raise self.excecao
        return self.resposta


def _servicos(cliente_falso):
    return lambda: ServicosDeAnalise(cliente=lambda: cliente_falso, modelo="claude-sonnet-5")


def _snap(sessao: Session, grupo: GrupoEconomico, receita: str) -> None:
    n = regra.Notas(receita=3, rentabilidade=3, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=1, semaforo=1, churn=1)
    from datetime import date

    from crm.db.modelos import ClassificacaoDoGrupo
    pontos = regra.score(n); letra = regra.classe(pontos)
    sessao.add(ClassificacaoDoGrupo(
        grupo_id=grupo.id, referencia=date(2026, 7, 31), fonte="teste", versao_dos_parametros=regra.PARAMETROS.versao,
        receita_mensal=Decimal(receita), nota_receita=n.receita, nota_rentabilidade=n.rentabilidade,
        complexidade=n.complexidade, disciplina=n.disciplina, risco_tecnico=n.risco, cross_sell=n.cross_sell,
        adimplencia=n.adimplencia, semaforo=n.semaforo, churn=n.churn, score=pontos, classe=letra,
        classe_efetiva=regra.classe_efetiva(letra, n), alerta_de_churn=regra.alerta_de_churn(letra, n),
        em_cobranca=regra.cobranca(n), eixo_de_acao=regra.eixo_de_acao(letra, n),
    ))


@pytest.fixture
def grupo(sessao: Session) -> GrupoEconomico:
    g = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    sessao.add(g); sessao.flush()
    _snap(sessao, g, "1000")
    sessao.commit()
    return g


def _cliente_de_teste(engine, servicos_de_analise):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return TestClient(criar_app(fabrica, servicos_de_analise=servicos_de_analise))


def test_sem_geracao_ainda_devolve_none(engine, grupo):
    cliente = _cliente_de_teste(engine, _servicos(ClienteFalso()))
    with cliente:
        assert cliente.get("/api/carteira/analise").json() is None


def test_gera_grava_e_devolve_a_analise(engine, grupo):
    falso = ClienteFalso(resposta=_resposta("A carteira está travada por inadimplência."))
    cliente = _cliente_de_teste(engine, _servicos(falso))
    with cliente:
        r = cliente.post("/api/carteira/analise", json={"autor": "Eduardo Luiz"})
        assert r.status_code == 201, r.text
        corpo = r.json()
        assert corpo["texto"] == "A carteira está travada por inadimplência."
        assert corpo["gerada_por"] == "Eduardo Luiz" and corpo["modelo"] == "claude-sonnet-5"
        assert Decimal(corpo["custo_usd"]) > 0
        assert cliente.get("/api/carteira/analise").json()["texto"] == corpo["texto"]


def test_o_pedido_leva_os_numeros_calculados(engine, grupo):
    falso = ClienteFalso(resposta=_resposta("texto"))
    cliente = _cliente_de_teste(engine, _servicos(falso))
    with cliente:
        cliente.post("/api/carteira/analise", json={"autor": "Eduardo Luiz"})
    pedido = falso.chamadas[0]["messages"][0]["content"]
    assert "Alfa" in pedido and "1.000,00" in pedido  # o único grupo, travado por adimplência ≤ 2
    assert falso.chamadas[0]["model"] == "claude-sonnet-5"


def test_gerar_sem_autor_e_recusado(engine, grupo):
    cliente = _cliente_de_teste(engine, _servicos(ClienteFalso(resposta=_resposta("x"))))
    with cliente:
        assert cliente.post("/api/carteira/analise", json={"autor": "E"}).status_code == 422
        assert cliente.post("/api/carteira/analise", json={}).status_code == 422


def test_falha_da_ia_vira_502_sem_gravar_nada(engine, grupo):
    falso = ClienteFalso(excecao=RuntimeError("boom"))
    cliente = _cliente_de_teste(engine, _servicos(falso))
    with cliente:
        r = cliente.post("/api/carteira/analise", json={"autor": "Eduardo Luiz"})
        assert r.status_code == 502
        assert cliente.get("/api/carteira/analise").json() is None


def test_sem_classificacao_carregada_e_recusado(engine):
    cliente = _cliente_de_teste(engine, _servicos(ClienteFalso(resposta=_resposta("x"))))
    with cliente:
        assert cliente.post("/api/carteira/analise", json={"autor": "Eduardo Luiz"}).status_code == 409
