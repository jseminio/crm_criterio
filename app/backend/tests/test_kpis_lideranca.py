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


def test_churn_da_base_no_ano_por_grupos_e_por_faturamento(cliente):
    c = _kpis(cliente)["churn"]
    assert c["titulo"] == "Churn da base no ano"
    assert D(c["valor"]) == D("50.0")  # por grupos: Saiu, de uma base de 2 (Antigo e Saiu) em 31/12/2025
    x = c["extras"]
    assert x["grupos"] == 2 and x["grupos_perdidos"] == 1 and x["grupos_perdidos_no_mes"] == 1
    # Por faturamento: MRR da base em 31/12 = Antigo 12.000 (antes da expansão) + Saiu 6.000, × 13 ÷ 12; Saiu levou 6.500
    assert D(x["mrr_de_partida"]) == D("19500.00") and D(x["mrr_perdido"]) == D("6500.00")
    assert D(x["faturamento_pct"]) == D("33.3") and D(x["mrr_perdido_no_mes"]) == D("6500.00")
    assert "perdidos em 2025" in c["falta"][0]  # sem encerramento em 2025: sem baseline


def test_nenhum_indicador_tem_numero_no_nome(cliente):
    titulos = [k["titulo"] for k in _kpis(cliente).values()]
    assert titulos == ["MRR novo no mês", "Ticket médio mensal", "Upsell sobre o MRR", "Churn da base no ano",
                       "Churn de quem entrou em 2026", "Cobertura de relacionamento", "Integralidade do cadastro"]


def _grupo_com_contrato(engine, nome, inicio, anuncio, saida, preco, anterior=False):
    with Session(engine) as s:
        g = GrupoEconomico(nome=nome)
        s.add(g)
        s.flush()
        ct = Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D(preco), data_inicio=inicio,
                      anterior_ao_crm=anterior)
        s.add(ct)
        s.flush()
        if anuncio:
            s.add(EventoDeContrato(contrato_id=ct.id, tipo=T.ENCERRAMENTO, data_do_evento=anuncio, data_da_saida=saida))
        s.commit()


def test_o_ano_acumula_a_base_e_quem_entrou_e_saiu_no_ano_tem_o_seu_card(engine, cliente):
    """Decisão de Eduardo em 13/10/2026: churn por coorte (base de 31/12) e, à parte, quem entrou no ano; cada card
    por grupos e por faturamento."""
    _grupo_com_contrato(engine, "Maio", date(2025, 1, 1), date(2026, 5, 27), date(2026, 8, 31), "1200")
    _grupo_com_contrato(engine, "Relâmpago", date(2026, 3, 2), date(2026, 8, 14), date(2026, 10, 13), "2400")
    k = _kpis(cliente)
    c = k["churn"]
    assert (c["extras"]["grupos"], c["extras"]["grupos_perdidos"], c["extras"]["grupos_perdidos_no_mes"]) == (3, 2, 1)
    assert D(c["valor"]) == D("66.7")
    # 20.800 de base (19.500 + Maio 1.300); perdeu Saiu 6.500 + Maio 1.300
    assert D(c["extras"]["mrr_perdido"]) == D("7800.00") and D(c["extras"]["faturamento_pct"]) == D("37.5")
    entram = {i["grupo"]: i for i in c["itens"] if i["entra"]}
    assert set(entram) == {"Maio", "Saiu"}  # o Relâmpago não estava na base
    assert entram["Maio"]["detalhe"] == "anunciou em 27/05/2026 · sai em 31/08/2026"
    assert entram["Saiu"]["detalhe"].endswith("· no mês")
    assert [i["grupo"] for i in c["itens"] if not i["entra"]] == ["Antigo"]

    n = k["churn_novos"]
    assert n["titulo"] == "Churn de quem entrou em 2026" and n["unidade"] == "%"
    assert D(n["valor"]) == D("50.0")  # Relâmpago, de 2 (Novo e Relâmpago)
    x = n["extras"]
    assert (x["grupos"], x["grupos_perdidos"], x["grupos_perdidos_no_mes"]) == (2, 1, 0)  # pediu em agosto
    assert D(x["mrr_de_partida"]) == D("5200.00") and D(x["mrr_perdido"]) == D("2600.00") and D(x["faturamento_pct"]) == D("50.0")
    assert D(x["tempo_medio_meses"]) == D("5.4")
    assert [(i["grupo"], i["entra"]) for i in n["itens"]] == [("Relâmpago", True), ("Novo", False)]
    assert n["itens"][0]["detalhe"] == "entrou em 03/2026 · anunciou em 14/08/2026 · sai em 13/10/2026"


def test_a_contracao_entra_no_faturamento_e_nao_nos_grupos(engine, cliente):
    """Contração incluída (13/10/2026), como 1 − GRR: o grupo fica, mas o faturamento perdido conta."""
    with Session(engine) as s:
        antigo = s.query(GrupoEconomico).filter_by(nome="Antigo").one()
        velho = s.query(Contrato).filter_by(grupo_id=antigo.id, anterior_ao_crm=True).one()
        velho.preco_mensal = D("10200")
        s.add(EventoDeContrato(contrato_id=velho.id, tipo=T.CONTRACAO, data_do_evento=date(2026, 10, 12),
                               preco_mensal_anterior=D("13200"), preco_mensal_novo=D("10200")))
        s.commit()
    c = _kpis(cliente)["churn"]
    assert D(c["valor"]) == D("50.0") and c["extras"]["grupos_perdidos"] == 1  # o Antigo segue cliente
    # Saiu 6.500 + contração do Antigo 3.000 × 13 ÷ 12 = 3.250, sobre 19.500
    assert D(c["extras"]["mrr_perdido"]) == D("9750.00") and D(c["extras"]["faturamento_pct"]) == D("50.0")
    contracao = [i for i in c["itens"] if i["secao"] == "Contração na base (o grupo ficou)"]
    assert [(i["grupo"], i["detalhe"], D(i["valor"])) for i in contracao] == [("Antigo", "contração em 12/10/2026", D("3250.00"))]


def test_encerrar_um_de_dois_contratos_e_contracao_e_nao_churn(engine, cliente):
    with Session(engine) as s:
        antigo = s.query(GrupoEconomico).filter_by(nome="Antigo").one()
        cross = s.query(Contrato).filter_by(grupo_id=antigo.id, data_inicio=date(2026, 10, 5)).one()
        s.add(EventoDeContrato(contrato_id=cross.id, tipo=T.ENCERRAMENTO, data_do_evento=date(2026, 10, 18)))
        s.commit()
    c = _kpis(cliente)["churn"]
    assert c["extras"]["grupos_perdidos"] == 1  # só o Saiu: o Antigo segue com o contrato da carteira anterior


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
    for chave in ("churn", "churn_novos"):
        churn = k[chave]
        assert len(churn["itens"]) == churn["extras"]["grupos"]  # um item por grupo da coorte
        assert sum(D(i["valor"]) for i in churn["itens"] if i["entra"]) == D(churn["extras"]["mrr_perdido"])
        assert sum(D(i["valor"]) for i in churn["itens"] if not i["entra"]) + D(churn["extras"]["mrr_perdido"]) \
            == D(churn["extras"]["mrr_de_partida"])
    cob = k["cobertura"]
    assert sum(i["entra"] for i in cob["itens"]) == cob["extras"]["em_dia"] and len(cob["itens"]) == cob["extras"]["total"]


def test_mes_que_nao_comecou_e_recusado(cliente):
    r = cliente.get("/api/inteligencia/kpis-lideranca", headers=ADMIN, params={"mes": "2026-12", "hoje": HOJE})
    assert r.status_code == 422
