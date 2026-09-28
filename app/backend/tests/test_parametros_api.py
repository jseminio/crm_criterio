"""API dos parâmetros editáveis do Score e da Rentabilidade (28/09/2026)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm.api.app import criar_app

PESOS = dict(
    peso_receita="0.20", peso_rentabilidade="0.25", peso_cross_sell="0.12", peso_complexidade="0.12",
    peso_disciplina="0.09", peso_risco="0.07", peso_adimplencia="0.15",
)
RENTABILIDADE = dict(
    imposto="0.11", teto_de_atrito="1.5",
    atrito_nota_1="0", atrito_nota_2="0.05", atrito_nota_3="0.10", atrito_nota_4="0.30", atrito_nota_5="0.50",
    corte_margem_2="0.30", corte_margem_3="0.45", corte_margem_4="0.60", corte_margem_5="0.70",
)
HORAS = dict(horas_micro=5, horas_pequeno=10, horas_medio=16, horas_grande=40, horas_extra_grande=80)
TAXAS = dict(
    taxa_socio_senior="93.75", taxa_socio_junior="106.25", taxa_supervisor="75.00",
    taxa_analista_senior="50.00", taxa_analista_pleno="31.25", taxa_analista_junior="18.75",
)
MIX_POR_PORTE = {
    "Micro": {"Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.02",
              "Analista Sênior": "0.47", "Analista Pleno": "0.50", "Analista Júnior": "0"},
    "Pequeno": {"Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.02",
                "Analista Sênior": "0.47", "Analista Pleno": "0.50", "Analista Júnior": "0"},
    "Médio": {"Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.08",
              "Analista Sênior": "0.30", "Analista Pleno": "0.51", "Analista Júnior": "0.10"},
    "Grande": {"Sócio Sênior": "0.01", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.09",
               "Analista Sênior": "0.30", "Analista Pleno": "0.43", "Analista Júnior": "0.16"},
    "Extra Grande": {"Sócio Sênior": "0.02", "Sócio Júnior/Gerente": "0.05", "Supervisor/Especialista": "0.13",
                      "Analista Sênior": "0.30", "Analista Pleno": "0.30", "Analista Júnior": "0.20"},
}


def mix_padrao() -> list[dict]:
    return [
        {"porte": porte, "cargo": cargo, "mix_percentual": valor}
        for porte, cargos in MIX_POR_PORTE.items()
        for cargo, valor in cargos.items()
    ]


def corpo_padrao(**o) -> dict:
    base = {
        "autor": "Eduardo Luiz", "motivo": "Teste", **PESOS, "corte_a": "3.95", "corte_b": "3.35",
        "trava_de_adimplencia": 2, "churn_alto": 4, **RENTABILIDADE, **HORAS, **TAXAS, "mix": mix_padrao(),
    }
    return {**base, **o}


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def test_sem_versao_gravada_devolve_409(cliente):
    assert cliente.get("/api/carteira/parametros").status_code == 409


def test_grava_e_le_a_versao(cliente):
    r = cliente.post("/api/carteira/parametros", json=corpo_padrao())
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["autor"] == "Eduardo Luiz" and len(corpo["mix"]) == 30
    # custo/hora ponderado é calculado, bate com a matriz da imagem/planilha
    assert Decimal(corpo["custo_hora"]["Micro"]) == Decimal("41.6875")
    assert Decimal(corpo["custo_hora"]["Extra Grande"]) == Decimal("45.0625")

    lido = cliente.get("/api/carteira/parametros").json()
    assert lido["id"] == corpo["id"]


def test_edicao_vira_versao_nova_sem_apagar_a_anterior(cliente, sessao):
    from crm.db.modelos import VersaoDeParametros

    primeira = cliente.post("/api/carteira/parametros", json=corpo_padrao()).json()
    segunda = cliente.post("/api/carteira/parametros", json=corpo_padrao(peso_receita="0.25", peso_rentabilidade="0.20")).json()
    assert segunda["id"] != primeira["id"]
    assert cliente.get("/api/carteira/parametros").json()["id"] == segunda["id"]
    assert sessao.get(VersaoDeParametros, primeira["id"]) is not None  # a antiga continua no banco


def test_pesos_que_nao_somam_100_sao_recusados(cliente):
    r = cliente.post("/api/carteira/parametros", json=corpo_padrao(peso_receita="0.30"))
    assert r.status_code == 422 and "100%" in r.text


def test_mix_que_nao_soma_100_por_porte_e_recusado(cliente):
    mix = [c for c in mix_padrao() if not (c["porte"] == "Grande" and c["cargo"] == "Analista Júnior")]
    mix.append({"porte": "Grande", "cargo": "Analista Júnior", "mix_percentual": "0.50"})
    r = cliente.post("/api/carteira/parametros", json=corpo_padrao(mix=mix))
    assert r.status_code == 422 and "Grande" in r.text


def test_notas_editadas_depois_de_uma_versao_nova_usam_os_pesos_novos(cliente, sessao):
    from datetime import date
    from crm.db.modelos import ClassificacaoDoGrupo, GrupoEconomico
    from crm.domain import classificacao as regra
    from crm.domain.listas import SituacaoGrupo

    g = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    sessao.add(g); sessao.flush()
    n = regra.Notas(receita=5, rentabilidade=1, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=3, semaforo=1, churn=1)
    pontos = regra.score(n)
    sessao.add(ClassificacaoDoGrupo(
        grupo_id=g.id, referencia=date(2026, 7, 31), revisao=1, fonte="teste", versao_dos_parametros=regra.PARAMETROS.versao,
        receita_mensal=Decimal("1000"), nota_receita=n.receita, nota_rentabilidade=n.rentabilidade,
        complexidade=n.complexidade, disciplina=n.disciplina, risco_tecnico=n.risco, cross_sell=n.cross_sell,
        adimplencia=n.adimplencia, semaforo=n.semaforo, churn=n.churn, score=pontos, classe=regra.classe(pontos),
        classe_efetiva=regra.classe_efetiva(regra.classe(pontos), n), alerta_de_churn=None,
        em_cobranca=False, eixo_de_acao="x",
    ))
    sessao.commit()

    # Troca o peso de Receita (20%) quase todo pra Rentabilidade — a nota de Rentabilidade é 1 (ruim),
    # a de Receita é 5 (boa): o Score deve cair depois da troca.
    antes = cliente.post(f"/api/carteira/grupos/{g.id}/notas", json={"autor": "Eduardo Luiz", "motivo": "antes", "churn": 2}).json()
    score_antes = Decimal(antes["item"]["score"])

    cliente.post("/api/carteira/parametros", json=corpo_padrao(peso_receita="0.01", peso_rentabilidade="0.44"))
    depois = cliente.post(f"/api/carteira/grupos/{g.id}/notas", json={"autor": "Eduardo Luiz", "motivo": "depois", "churn": 3}).json()
    score_depois = Decimal(depois["item"]["score"])

    assert score_depois < score_antes
    hist = cliente.get(f"/api/carteira/grupos/{g.id}/historico").json()
    assert hist[0]["notas"] is not None  # só confere que o histórico segue íntegro com 3 leituras
    assert len(hist) == 3
