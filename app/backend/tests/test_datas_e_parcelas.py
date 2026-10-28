"""Data de competência, início do pagamento e parcelas do não recorrente (Eduardo, 28/10/2026).

- a 13ª proporcional conta os avos desde a data de competência;
- o MRR, e o MRR novo, contam desde o início do pagamento (o primeiro recebimento);
- o não recorrente guarda parcelas de valores diferentes, que somam o valor total, e o recebido espera cada uma
  no mês do vencimento.
Sem as datas, tudo segue pela assinatura, como antes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import Contrato, GrupoEconomico, Oportunidade, Perfil
from crm.domain import parcelas as regra
from crm.domain.listas import LinhaServico, Situacao, SituacaoContrato

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


def _mrr(v: str) -> D:
    return (D(v) * 13 / 12).quantize(D("0.01"))


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        g = GrupoEconomico(nome="Delta")
        s.add(g)
        s.flush()
        recorrente = Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO, recorrente=True, preco_mensal=D("1200"),
                              base_do_valor="bruto", data_inicio=date(2026, 10, 5),
                              data_competencia=date(2026, 7, 1), data_inicio_pagamento=date(2026, 11, 10),
                              escopo="BPO Contábil")
        pontual = Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO, recorrente=False, preco_anual=D("30000"),
                           base_do_valor="bruto", data_inicio=date(2026, 10, 5), escopo="Consultoria")
        aceita = Oportunidade(grupo_id=g.id, nome="Legalização", servico="Legalização", situacao=Situacao.ACEITA,
                              linha_servico=LinhaServico.C2, preco_anual=D("9000"), data_aceite=date(2026, 10, 20),
                              data_competencia=date(2026, 11, 1), data_inicio_pagamento=date(2026, 11, 15),
                              parcelas=regra.gravar([regra.Parcela(date(2026, 11, 15), D("5000")),
                                                     regra.Parcela(date(2026, 12, 15), D("4000"))]))
        s.add_all([recorrente, pontual, aceita])
        s.commit()
        return {"recorrente": recorrente.id, "pontual": pontual.id, "aceita": aceita.id}


@pytest.fixture
def cliente(engine, ids):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


# ── Regras puras ──────────────────────────────────────────────────────────────────────────────────────

def test_sem_as_datas_vale_a_assinatura():
    class C:
        data_inicio = date(2026, 10, 5)
        data_competencia = None
        data_inicio_pagamento = None
        anterior_ao_crm = False
    assert regra.inicio_do_mrr(C) == regra.inicio_do_servico(C) == date(2026, 10, 5)
    C.data_competencia, C.data_inicio_pagamento = date(2026, 9, 1), date(2026, 11, 10)
    assert (regra.inicio_do_servico(C), regra.inicio_do_mrr(C)) == (date(2026, 9, 1), date(2026, 11, 10))


def test_carteira_anterior_ao_crm_nunca_vira_mrr_novo():
    class C:
        data_inicio = None
        data_inicio_pagamento = date(2026, 11, 10)
        anterior_ao_crm = True
    assert regra.inicio_do_mrr(C) is None


def test_a_soma_das_parcelas_tem_de_bater_com_o_total():
    p = [regra.Parcela(date(2026, 12, 10), D("15000")), regra.Parcela(date(2027, 1, 10), D("7500"))]
    assert "faltam R$ 7.500,00" in regra.problema_nas_parcelas(p, D("30000"))
    assert regra.problema_nas_parcelas(p + [regra.Parcela(date(2027, 2, 10), D("7500"))], D("30000")) is None
    assert "valor total" in regra.problema_nas_parcelas(p, None)
    assert regra.problema_nas_parcelas([], None) is None


# ── Contrato pela API ─────────────────────────────────────────────────────────────────────────────────

def test_grava_parcelas_desiguais_em_ordem_de_vencimento(cliente, ids):
    corpo = {"parcelas": [{"vencimento": "2027-01-10", "valor": "7500"}, {"vencimento": "2026-12-10", "valor": "15000"},
                          {"vencimento": "2027-02-10", "valor": "7500"}],
             "data_competencia": "2026-11-01", "data_inicio_pagamento": "2026-12-10"}
    r = cliente.patch(f"/api/contratos/{ids['pontual']}", json=corpo, headers=ADMIN)
    assert r.status_code == 200, r.text
    d = r.json()
    assert [p["vencimento"] for p in d["parcelas"]] == ["2026-12-10", "2027-01-10", "2027-02-10"]
    assert [D(p["valor"]) for p in d["parcelas"]] == [D("15000"), D("7500"), D("7500")]
    assert (d["data_competencia"], d["data_inicio_pagamento"]) == ("2026-11-01", "2026-12-10")
    # Salvar de novo o mesmo (a tela manda o rascunho inteiro) não é mudança.
    assert cliente.patch(f"/api/contratos/{ids['pontual']}", json=corpo, headers=ADMIN).status_code == 200


def test_recusa_parcelas_que_nao_somam_o_total(cliente, ids):
    r = cliente.patch(f"/api/contratos/{ids['pontual']}",
                      json={"parcelas": [{"vencimento": "2026-12-10", "valor": "10000"}]}, headers=ADMIN)
    assert r.status_code == 422 and "sobram" not in r.json()["detail"] and "faltam R$ 20.000,00" in r.json()["detail"]
    assert cliente.get(f"/api/contratos/{ids['pontual']}", headers=ADMIN).json()["parcelas"] is None


def test_lista_vazia_apaga_as_parcelas(cliente, ids):
    cliente.patch(f"/api/contratos/{ids['pontual']}",
                  json={"parcelas": [{"vencimento": "2026-12-10", "valor": "30000"}]}, headers=ADMIN)
    r = cliente.patch(f"/api/contratos/{ids['pontual']}", json={"parcelas": []}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["parcelas"] is None


def test_conversao_leva_as_datas_e_as_parcelas_da_oportunidade(cliente, ids):
    r = cliente.post(f"/api/oportunidades/{ids['aceita']}/converter-em-contrato", json={"recorrente": False}, headers=ADMIN)
    assert r.status_code in (200, 201), r.text
    c = r.json()
    assert (c["data_competencia"], c["data_inicio_pagamento"]) == ("2026-11-01", "2026-11-15")
    assert [D(p["valor"]) for p in c["parcelas"]] == [D("5000"), D("4000")]


def test_oportunidade_grava_as_datas_e_confere_as_parcelas(cliente, ids):
    url = f"/api/oportunidades/{ids['aceita']}"
    ruim = cliente.patch(url, json={"parcelas": [{"vencimento": "2026-11-15", "valor": "9500"}]}, headers=ADMIN)
    assert ruim.status_code == 422 and "sobram R$ 500,00" in ruim.json()["detail"]
    r = cliente.patch(url, json={"data_inicio_pagamento": "2026-12-01"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["data_inicio_pagamento"] == "2026-12-01"
    # Mudar o preço sem ajustar as parcelas é recusado: a soma deixaria de bater.
    assert cliente.patch(url, json={"preco_anual": "12000"}, headers=ADMIN).status_code == 422


# ── MRR e recebido ────────────────────────────────────────────────────────────────────────────────────

def test_mrr_comeca_no_primeiro_recebimento(cliente):
    # Assinado em 05/10, primeiro pagamento em 10/11: fora do MRR de outubro, MRR novo em novembro.
    outubro = cliente.get("/api/mrr", params={"hoje": "2026-10-20"}, headers=ADMIN).json()
    assert D(outubro["atual"]["valor"]) == 0
    mov = cliente.get("/api/mrr/movimento", params={"de": "2026-11-01", "ate": "2026-11-30", "hoje": "2026-11-20"},
                      headers=ADMIN).json()
    novos = [i for i in mov["itens"] if i["categoria"] == "novo"]
    assert [(i["data"], D(i["valor"])) for i in novos] == [("2026-11-10", _mrr("1200"))]
    carteira = cliente.get("/api/mrr/carteira", params={"hoje": "2026-10-20"}, headers=ADMIN).json()
    item = [i for g in carteira["itens"] for i in g["itens"] if i["escopo"] == "BPO Contábil"][0]
    assert item["parte"] == "a_comecar"


def test_recebido_espera_a_parcela_no_vencimento_e_a_13a_desde_a_competencia(cliente, ids):
    cliente.patch(f"/api/contratos/{ids['pontual']}",
                  json={"parcelas": [{"vencimento": "2026-11-10", "valor": "20000"},
                                     {"vencimento": "2026-12-10", "valor": "10000"}]}, headers=ADMIN)

    def esperado(competencia: str, escopo: str) -> D:
        r = cliente.get("/api/mrr/carteira", params={"hoje": "2026-12-20", "competencia": competencia},
                        headers=ADMIN).json()
        return sum((D(i["esperado"]) for g in r["itens"] for i in g["itens"] if i["escopo"] == escopo), D("0"))

    assert esperado("2026-10", "Consultoria") == 0
    assert esperado("2026-11", "Consultoria") == D("20000")
    assert esperado("2026-12", "Consultoria") == D("10000")
    # Recorrente: nada antes do primeiro pagamento; em dezembro, a parcela + 13ª com 6 avos (jul a dez, desde a
    # competência de 01/07), e não 3 (out a dez, desde a assinatura).
    assert esperado("2026-10", "BPO Contábil") == 0
    assert esperado("2026-11", "BPO Contábil") == D("1200")
    assert esperado("2026-12", "BPO Contábil") == D("1200") + D("600")


def test_contrato_gerado_usa_a_competencia(engine, ids):
    from crm.api.documento_de_contrato import valores_sugeridos

    with Session(engine) as s:
        v = valores_sugeridos(s, s.get(Contrato, ids["recorrente"]), date(2026, 10, 28))
    assert v["competencia_inicial"] == ("julho de 2026", "contrato")
