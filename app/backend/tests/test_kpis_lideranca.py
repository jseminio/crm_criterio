"""KPIs da liderança (09/10/2026): MRR novo, ticket por grupo e CNPJ, upsell em dois tipos, churn de
clientes e cobertura de relacionamento — tudo em MRR com 13 parcelas — e só para o Administrador."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import (
    ClassificacaoDoGrupo, Contrato, Empresa, EventoDeContrato, GrupoEconomico, Oportunidade, Perfil,
    ReuniaoDeResultado, Usuario,
)
from crm.domain.listas import LinhaServico, Situacao, SituacaoContrato, TipoDeEventoDeContrato as T

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}
HOJE = "2026-10-20"


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


def _classe(grupo_id: int, classe: str) -> ClassificacaoDoGrupo:
    um = D("3")
    return ClassificacaoDoGrupo(
        grupo_id=grupo_id, referencia=date(2026, 9, 1), revisao=1, fonte="teste", versao_dos_parametros="v1",
        receita_mensal=D("10000"), nota_receita=um, nota_rentabilidade=um, complexidade=um, disciplina=um,
        risco_tecnico=um, cross_sell=um, adimplencia=um, semaforo=1, score=D("0.5"), classe=classe,
        classe_efetiva=classe, eixo_de_acao="Manter",
    )


@pytest.fixture
def base(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        comercial = Perfil(nome="Comercial", permissoes=["funil.ver", "configuracoes.metas"])
        antigo, novo, saiu = GrupoEconomico(nome="Antigo"), GrupoEconomico(nome="Novo"), GrupoEconomico(nome="Saiu")
        s.add_all([comercial, antigo, novo, saiu])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=comercial.id))
        e1, e2, e3 = (Empresa(grupo_id=g.id, razao_social=n) for g, n in ((antigo, "Antigo 1"), (antigo, "Antigo 2"), (novo, "Novo 1")))
        s.add_all([e1, e2, e3])
        s.flush()
        velho = Contrato(grupo_id=antigo.id, empresa_id=e1.id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO,
                         preco_mensal=D("13200"))
        cross = Contrato(grupo_id=antigo.id, empresa_id=e2.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("1200"),
                         data_inicio=date(2026, 10, 5))
        do_novo = Contrato(grupo_id=novo.id, empresa_id=e3.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("2400"),
                           data_inicio=date(2026, 10, 3))
        perdido = Contrato(grupo_id=saiu.id, situacao=SituacaoContrato.ENCERRADO, preco_mensal=D("6000"),
                           data_inicio=date(2025, 6, 1))
        s.add_all([velho, cross, do_novo, perdido])
        s.flush()
        s.add(EventoDeContrato(contrato_id=velho.id, tipo=T.EXPANSAO, data_do_evento=date(2026, 10, 10),
                               preco_mensal_anterior=D("12000"), preco_mensal_novo=D("13200")))
        s.add(EventoDeContrato(contrato_id=perdido.id, tipo=T.ENCERRAMENTO, data_do_evento=date(2026, 10, 15)))
        s.add(Oportunidade(grupo_id=antigo.id, nome="consultoria", servico="Consultoria", linha_servico=LinhaServico.C2,
                           situacao=Situacao.ACEITA, data_aceite=date(2026, 10, 8), preco_anual=D("24000")))
        s.add(Oportunidade(grupo_id=novo.id, nome="bpo", servico="BPO Financeiro", linha_servico=LinhaServico.C1,
                           situacao=Situacao.ACEITA, data_aceite=date(2026, 10, 9), preco_mensal=D("1200")))
        s.add_all([_classe(antigo.id, "A"), _classe(novo.id, "B")])
        s.add(ReuniaoDeResultado(grupo_id=antigo.id, tipo="mensal", data=date(2026, 10, 12)))
        s.commit()


@pytest.fixture
def cliente(engine, base):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


def _kpis(cliente, mes="2026-10", headers=ADMIN):
    r = cliente.get("/api/inteligencia/kpis-lideranca", headers=headers, params={"mes": mes, "hoje": HOJE})
    assert r.status_code == 200, r.text
    return {k["chave"]: k for k in r.json()["kpis"]}


def test_so_o_administrador_ve(cliente):
    r = cliente.get("/api/inteligencia/kpis-lideranca", headers=KARINE, params={"mes": "2026-10", "hoje": HOJE})
    assert r.status_code == 403  # mesmo com a permissão de metas


def test_mrr_novo_e_ticket_por_grupo_e_por_cnpj(cliente):
    k = _kpis(cliente)
    # 1.200 (cross-sell do Antigo) + 2.400 (Novo), × 13 ÷ 12
    assert D(k["mrr_novo"]["valor"]) == D("3900.00")
    assert "1 proposta(s) recorrente(s) aceita(s) no mês sem contrato (R$ 1.300,00/mês)" in k["mrr_novo"]["falta"][0]
    t = k["ticket"]["extras"]
    assert (t["mes_grupos"], t["mes_cnpjs"]) == (2, 2)
    assert D(t["mes_por_grupo"]) == D("1950.00") and D(t["mes_por_cnpj"]) == D("1950.00")


def test_upsell_recorrente_e_nao_recorrente_sobre_o_mrr_anterior(cliente):
    u = _kpis(cliente)["upsell"]
    # MRR em 30/09: Antigo 12.000 + Saiu 6.000 = 18.000, × 13 ÷ 12 = 19.500
    assert "R$ 19.500,00" in u["resumo"]
    # recorrente: expansão 1.200 + cross-sell 1.200, × 13 ÷ 12 = 2.600; pontual: consultoria 24.000
    assert D(u["extras"]["recorrente"]) == D("2600.00") and D(u["extras"]["recorrente_pct"]) == D("13.3")
    assert D(u["extras"]["nao_recorrente"]) == D("24000") and u["extras"]["pontuais"] == 1
    assert D(u["valor"]) == D("136.4") and u["falta"] == []


def test_churn_de_clientes_sobre_a_base_do_fim_do_ano(cliente):
    c = _kpis(cliente)["churn"]
    assert D(c["valor"]) == D("50.0")  # Saiu, de uma base de 2 (Antigo e Saiu) em 31/12/2025
    assert c["extras"]["base"] == 2 and c["extras"]["perdidos"] == 1
    assert "perdidos em 2025" in c["falta"][0]  # sem encerramento em 2025: sem baseline


def test_cobertura_conta_so_reuniao_realizada_na_janela_da_classe(cliente):
    c = _kpis(cliente)["cobertura"]
    assert D(c["valor"]) == D("50.0")  # Antigo (A) teve a mensal; Novo (B) não teve a trimestral
    # A composição traz quem conta (em dia, com a data) e quem ficou fora (10/10/2026).
    assert [(i["grupo"], i["entra"]) for i in c["itens"]] == [("Antigo", True), ("Novo (classe B)", False)]
    assert "reunião em 12/10/2026 (classe A)" == c["itens"][0]["detalhe"]


def test_cada_kpi_tem_explicacao_e_a_lista_bate_com_o_numero(cliente):
    k = _kpis(cliente)
    assert all(x["explicacao"] for x in k.values())
    assert sum(D(i["valor"]) for i in k["mrr_novo"]["itens"]) == D(k["mrr_novo"]["valor"])
    assert sum(D(i["valor"]) for i in k["ticket"]["itens"]) == D(k["mrr_novo"]["valor"])  # o ticket reparte o MRR novo
    ups = k["upsell"]
    assert sum(D(i["valor"]) for i in ups["itens"]) == D(ups["extras"]["recorrente"]) + D(ups["extras"]["nao_recorrente"])
    churn = k["churn"]
    assert sum(i["entra"] for i in churn["itens"]) == churn["extras"]["perdidos"]
    assert len(churn["itens"]) == churn["extras"]["base"]  # os perdidos estavam na base
    cob = k["cobertura"]
    assert sum(i["entra"] for i in cob["itens"]) == cob["extras"]["em_dia"] and len(cob["itens"]) == cob["extras"]["total"]


def test_mes_que_nao_comecou_e_recusado(cliente):
    r = cliente.get("/api/inteligencia/kpis-lideranca", headers=ADMIN, params={"mes": "2026-12", "hoje": HOJE})
    assert r.status_code == 422
