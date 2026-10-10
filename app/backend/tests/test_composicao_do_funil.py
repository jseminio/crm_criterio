"""Composição dos números do funil (10/10/2026): cada card de Oportunidades abre a lista do que o compõe,
e a lista bate com o número — mesma conta, mesmos filtros."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import GrupoEconomico, Oportunidade
from crm.domain.listas import LinhaServico, Origem, Situacao, TipoCanal
from crm.domain.mrr import mensalizar

VOLUMETRIA = dict(documentos_fiscais_mes=1, lancamentos_contabeis_mes=1, pagamentos_mes=1, contas_bancarias=1,
                  conciliacoes_cartao_mes=1, empregados_clt=1, admissoes_desligamentos_mes=1, cnpjs_no_escopo=1,
                  tomadores_de_servico=1)


@pytest.fixture
def cliente(engine):
    with Session(engine) as s:
        alfa, beta = GrupoEconomico(nome="Grupo Alfa"), GrupoEconomico(nome="Beta")
        s.add_all([alfa, beta])
        s.flush()

        def op(n, g, situacao, **kw):
            return Oportunidade(grupo_id=g.id, nome=n, situacao=situacao, origem=Origem.CRM, chave_origem=n, **kw)

        s.add_all([
            op("Alfa BPO", alfa, Situacao.ENVIAR_PROPOSTA, captador="EL", tipo_canal=TipoCanal.SOCIOS, servico="BPO Contábil",
               preco_mensal=D("5000"), preco_anual=D("65000"), proxima_acao="ligar sexta", data_colocacao=date(2026, 3, 1),
               **VOLUMETRIA),
            op("Alfa DP", alfa, Situacao.ON_HOLD, captador="BO", tipo_canal=TipoCanal.PARCEIROS, servico="DP",
               preco_mensal=D("1200"), data_colocacao=date(2026, 3, 5)),
            op("Alfa Consultoria", alfa, Situacao.RECUSADA, captador="BO", tipo_canal=TipoCanal.PARCEIROS,
               servico="Consultoria", preco_anual=D("30000"), data_colocacao=date(2026, 5, 1)),
            op("Beta BPO", beta, Situacao.ACEITA, captador="EL", tipo_canal=TipoCanal.SOCIOS, servico="BPO Financeiro",
               linha_servico=LinhaServico.C1, preco_mensal=D("8000"), data_aceite=date(2026, 6, 1),
               data_colocacao=date(2026, 4, 1)),
            op("Beta Legalização", beta, Situacao.ACEITA, captador="EL", servico="Legalização",
               linha_servico=LinhaServico.C2, preco_mensal=D("900"), data_aceite=date(2026, 7, 1)),
        ])
        s.commit()
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def _itens(cliente, indicador, **params):
    r = cliente.get("/api/indicadores/composicao", params={"indicador": indicador, **params})
    assert r.status_code == 200, r.text
    return r.json()["itens"]


def test_em_aberto_e_aceitas_somam_o_card(cliente):
    card = cliente.get("/api/indicadores").json()
    for chave in ("em_aberto", "aceitas"):
        itens = _itens(cliente, chave)
        assert len(itens) == card[chave]["quantas"]
        assert sum(D(i["valor"] or 0) for i in itens) == D(card[chave]["valor_mensal"])
        assert sum(D(i["anual"] or 0) for i in itens) == D(card[chave]["valor_anual"])
    assert {i["nome"] for i in _itens(cliente, "em_aberto")} == {"Alfa BPO", "Alfa DP"}
    assert _itens(cliente, "aceitas")[0]["grupo"] == "Beta"


def test_ticket_lista_so_recorrentes_em_mrr(cliente):
    card = cliente.get("/api/indicadores").json()["ticket_recorrente"]
    itens = _itens(cliente, "ticket_recorrente")
    assert [i["nome"] for i in itens] == ["Beta BPO"]  # legalização é pontual
    assert D(itens[0]["valor"]) == mensalizar(D("8000")) == D(card["valor_mensal"])


def test_ciclo_medio_mostra_os_dias_e_quem_ficou_fora(cliente):
    card = cliente.get("/api/indicadores").json()["ciclo_medio"]
    itens = _itens(cliente, "ciclo_medio")
    na_media = [i for i in itens if i["entra"]]
    assert len(na_media) == card["amostra"] and D(na_media[0]["valor"]) == D("61")
    fora = [i for i in itens if not i["entra"]]
    assert len(fora) == card["aceitas_sem_as_duas_datas"] and "falta a data" in fora[0]["parte"]


def test_conversao_lista_as_decididas_e_marca_as_aceitas(cliente):
    card = cliente.get("/api/indicadores").json()["taxa_de_conversao"]
    itens = _itens(cliente, "taxa_de_conversao")
    assert len(itens) == card["decididas"] and sum(i["entra"] for i in itens) == card["aceitas"]


def test_cobertura_e_dependencia_contam_como_o_card(cliente):
    card = cliente.get("/api/indicadores").json()
    prox = _itens(cliente, "cobertura_proxima_acao")
    assert len(prox) == card["cobertura"]["em_aberto_total"]
    assert sum(i["entra"] for i in prox) == card["cobertura"]["em_aberto_com_proxima_acao"]
    vol = _itens(cliente, "cobertura_volumetria")
    assert sum(i["entra"] for i in vol) == card["cobertura"]["com_volumetria_completa"]
    assert len([i for i in vol if not i["entra"]][0]["falta"]) == 9
    dep = _itens(cliente, "dependencia_de_canal")
    assert sum(i["entra"] for i in dep) == card["dependencia_de_canal"]["da_rede_de_socios"]
    assert "(canal não informado)" in {i["parte"] for i in dep}


def test_segue_os_filtros_do_funil(cliente):
    assert {i["nome"] for i in _itens(cliente, "em_aberto", captador="BO")} == {"Alfa DP"}


def test_linha_do_recorte(cliente):
    linhas = cliente.get("/api/indicadores/recortes", params={"dimensao": "captador"}).json()
    el = next(l for l in linhas if l["chave"] == "EL")
    itens = _itens(cliente, "propostas", recorte="captador", chave="EL")
    assert len(itens) == el["propostas"] and sum(i["entra"] for i in itens) == el["aceitas"]


def test_indicador_desconhecido_e_recusado(cliente):
    assert cliente.get("/api/indicadores/composicao", params={"indicador": "xyz"}).status_code == 422
