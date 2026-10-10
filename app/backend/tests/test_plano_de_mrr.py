"""Inteligência de Conversão, Entrega 1 (03/10/2026): o plano de MRR — previsto por cenário,
realizado por motor, ajuste — e as premissas, que só o Administrador muda."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal as D

import pytest
from sqlalchemy import select as sa_select
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import (
    Contrato, ContratoPrevistoDoPlano, EventoDeContrato, GrupoEconomico, Oportunidade, Perfil, PlanoDeMrr, Usuario,
)
from crm.domain import plano_de_mrr as regras
from crm.domain.listas import LinhaServico, Situacao, SituacaoContrato, TipoDeEventoDeContrato as T

PIPELINE = (
    regras.ContratoPrevisto("atípico", date(2026, 11, 1), D("18000"), True),
    regras.ContratoPrevisto("normal", date(2026, 11, 1), D("5500"), False),
    regras.ContratoPrevisto("atípico", date(2026, 12, 1), D("16000"), True),
)


# Premissas como Eduardo aprovou em 03/10/2026, pela parcela. Desde 09/10/2026 o padrão está em MRR com
# 13 parcelas (× 13 ÷ 12); estas ficam para conferir a conta mostrada a ele naquele dia.
ANTIGO = replace(
    regras.PADRAO, meta_liquida=D("250000"), ponto_de_partida=D("26000"), mrr_de_partida=D("252341"),
    bpo_ticket=D("7000"), plus_acrescimo=D("3000"), cfo_acrescimo=D("6000"),
    alerta=regras.Cenario(D("2"), D("2903.28"), False), previsto=regras.Cenario(D("3"), D("2903.28"), True),
    otimista=regras.Cenario(D("5"), D("5000"), True),
)


# ---------------------------------------------------------------- regras

def test_os_tres_cenarios_de_03_10_batem_com_a_conta_mostrada_a_eduardo():
    p = replace(ANTIGO, contratos_previstos=PIPELINE)
    alerta, previsto, otimista = (regras.projetar(p, n) for n in regras.CENARIOS)
    assert (alerta.liquido, alerta.percentual_da_meta) == (D("233636.22"), D("93.5"))
    assert (previsto.liquido, previsto.percentual_da_meta) == (D("325725.25"), D("130.3"))
    assert (otimista.liquido, otimista.percentual_da_meta) == (D("518120.88"), D("207.2"))
    assert (previsto.bpo, previsto.contabil, previsto.escada) == (D("168000.00"), D("117888.56"), D("44640.00"))


def test_premissas_em_13_parcelas_mantem_o_percentual_da_meta():
    """09/10/2026: tudo em reais × 13 ÷ 12 — os cenários sobem 8,33% e o percentual da meta não muda."""
    em_mrr = tuple(replace(c, valor=(c.valor * 13 / 12).quantize(D("0.01"))) for c in PIPELINE)
    p = replace(regras.PADRAO, contratos_previstos=em_mrr)
    assert regras.PADRAO.meta_liquida == D("270833.33")
    assert [regras.projetar(p, n).percentual_da_meta for n in regras.CENARIOS] == [D("93.5"), D("130.3"), D("207.2")]
    assert regras.projetar(p, "previsto").liquido == D("352868.95")


def test_o_atipico_ocupa_duas_vagas_do_onboarding_contabil():
    p = replace(ANTIGO, contratos_previstos=PIPELINE)
    nov, dez, jan = regras.projetar(p, "previsto").linhas[:3]
    assert nov.contabil == D("18000") + D("5500") + D("2903.28")  # 2 + 1 vagas ocupadas, sobra 1
    assert dez.contabil == D("16000") + 2 * D("2903.28")
    assert jan.contabil == 4 * D("2903.28")
    assert regras.projetar(p, "alerta").linhas[0].contabil == 4 * D("2903.28")  # o alerta não conta o pipeline


def test_a_escada_sobe_a_cada_prazo_e_o_bpo_respeita_o_teto():
    p = replace(ANTIGO, otimista=regras.Cenario(D("9"), D("5000"), False))
    linhas = regras.projetar(p, "otimista").linhas
    assert linhas[0].bpo == 5 * D("7000")  # 9 pedidos, teto 5
    assert [l.escada for l in linhas[:4]] == [0, 0, 0, D("12000.00")]  # 5 × 80% × R$ 3 mil no 4º mês
    assert linhas[6].escada == D("12000") + D("7200")  # e 30% deles sobem para o CFO no 7º


def test_motor_do_contrato_pelo_servico_ou_pelo_escopo():
    assert regras.motor_do_contrato("BPO Financeiro", None) == "bpo"
    assert regras.motor_do_contrato(None, "CFO as a Service — plano 3") == "bpo"
    assert regras.motor_do_contrato("Contabilidade", "BPO Plus") == "bpo"
    assert regras.motor_do_contrato("Contabilidade", None) == "contabil"
    assert regras.motor_do_contrato(None, None) == "contabil"


@pytest.mark.parametrize("realizado, previsto, chave", [
    (D("100"), D("100"), "no_ritmo"), (D("95"), D("100"), "atencao"), (D("89"), D("100"), "abaixo"), (D("5"), D("0"), "no_ritmo"),
])
def test_situacao_pelos_cortes_de_90_e_100(realizado, previsto, chave):
    assert regras.situacao(realizado, previsto).chave == chave


# ---------------------------------------------------------------- API

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


@pytest.fixture
def base(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        comercial = Perfil(nome="Comercial", permissoes=["funil.ver"])
        s.add(comercial)
        g = GrupoEconomico(nome="Grupo Alfa")
        s.add(g)
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=comercial.id))
        s.add(Contrato(grupo_id=g.id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("200000")))
        bpo = Oportunidade(grupo_id=g.id, nome="bpo", servico="BPO Financeiro", situacao=Situacao.ACEITA, preco_mensal=D("7000"),
                          linha_servico=LinhaServico.C1)
        contabil = Oportunidade(grupo_id=g.id, nome="ctb", servico="Contabilidade", situacao=Situacao.ACEITA, preco_mensal=D("3000"),
                               linha_servico=LinhaServico.C1)
        s.add_all([bpo, contabil])
        s.flush()
        c_bpo = Contrato(grupo_id=g.id, oportunidade_id=bpo.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("10000"),
                         data_inicio=date(2026, 9, 10))
        s.add(c_bpo)
        s.add(Contrato(grupo_id=g.id, oportunidade_id=contabil.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("3000"),
                       data_inicio=date(2026, 10, 2)))
        s.flush()
        s.add(EventoDeContrato(contrato_id=c_bpo.id, tipo=T.EXPANSAO, data_do_evento=date(2026, 9, 25),
                               preco_mensal_anterior=D("7000"), preco_mensal_novo=D("10000")))
        s.add(ContratoPrevistoDoPlano(descricao="Atípico do pipeline (nov)", mes=date(2026, 11, 1), valor=D("18000"), atipico=True))
        s.commit()


@pytest.fixture
def cliente(engine, base):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


def test_quem_ve_o_funil_ve_o_plano_com_o_realizado_por_motor(cliente):
    r = cliente.get("/api/inteligencia/plano", headers=KARINE, params={"hoje": "2026-10-04"})
    assert r.status_code == 200, r.text
    plano = r.json()
    assert D(plano["premissas"]["meta_liquida"]) == D("270833.33")  # 250 mil × 13 ÷ 12 (09/10/2026)
    assert plano["premissas"]["alterado_em"] is None  # padrão, ninguém mudou
    assert [c["descricao"] for c in plano["premissas"]["contratos_previstos"]] == ["Atípico do pipeline (nov)"]
    set_, out = plano["realizado"]
    assert (D(set_["novo_bpo"]), D(set_["escada"]), set_["contratos_bpo"]) == (D("7583.33"), D("3250.00"), 1)  # MRR com 13 parcelas (09/10/2026)
    assert (D(out["novo_contabil"]), out["contratos_contabil"]) == (D("3250.00"), 1)
    assert D(plano["meta"]["realizado"]) == D("14083.33")  # 13.000 × 13 ÷ 12
    assert plano["meta"]["meses_restantes"] == 8  # nov a jun
    assert D(plano["meta"]["previsto_ate_hoje"]) == D("28166.67")  # antes da projeção: o ponto de partida
    assert plano["meta"]["situacao"]["chave"] == "abaixo"
    motores = {m["motor"]: m for m in plano["motores"]}
    assert D(motores["bpo"]["realizado"]) == D("7583.33")
    assert "contratos/mês" in motores["bpo"]["ajuste"]
    assert [c["nome"] for c in plano["cenarios"]] == ["alerta", "previsto", "otimista"]


def test_a_composicao_do_realizado_soma_a_meta_e_cada_motor(cliente):
    plano = cliente.get("/api/inteligencia/plano", headers=KARINE, params={"hoje": "2026-10-04"}).json()
    r = cliente.get("/api/inteligencia/plano/realizado", headers=KARINE, params={"hoje": "2026-10-04"})
    assert r.status_code == 200, r.text
    itens = r.json()
    assert sum(D(i["valor"]) for i in itens) == D(plano["meta"]["realizado"])
    for m in plano["motores"]:
        soma = sum((D(i["valor"]) for i in itens if i["linha"] == m["motor"]), D("0"))
        assert abs(soma) == D(m["realizado"]), m["motor"]
    assert [(i["linha"], i["categoria"]) for i in itens] == [("bpo", "novo"), ("escada", "expansao"), ("contabil", "novo")]
    assert itens[0]["grupo"] == "Grupo Alfa"


def test_so_o_administrador_muda_as_premissas_e_fica_registrado(cliente):
    premissas = cliente.get("/api/inteligencia/plano", headers=ADMIN).json()["premissas"]
    premissas.pop("alterado_por"), premissas.pop("alterado_em")
    premissas["previsto"]["bpo_por_mes"] = "4"
    premissas["contratos_previstos"] = []
    assert cliente.put("/api/inteligencia/plano", headers=KARINE, json=premissas).status_code == 403
    r = cliente.put("/api/inteligencia/plano", headers=ADMIN, json=premissas, params={"hoje": "2026-10-04"})
    assert r.status_code == 200, r.text
    novo = r.json()
    assert D(novo["premissas"]["previsto"]["bpo_por_mes"]) == 4
    assert novo["premissas"]["contratos_previstos"] == []
    assert novo["premissas"]["alterado_por"]
    previsto = next(c for c in novo["cenarios"] if c["nome"] == "previsto")
    assert D(previsto["bpo"]) == D("242666.56")  # 4 × R$ 7.583,33 × 8 meses


def test_premissa_incoerente_e_recusada_com_o_motivo(cliente):
    premissas = cliente.get("/api/inteligencia/plano", headers=ADMIN).json()["premissas"]
    premissas.pop("alterado_por"), premissas.pop("alterado_em")
    premissas["contratos_previstos"] = [{"descricao": "x", "mes": "2028-01-01", "valor": "1000", "atipico": False}]
    r = cliente.put("/api/inteligencia/plano", headers=ADMIN, json=premissas)
    assert r.status_code == 422 and "fora dos meses projetados" in r.json()["detail"]


def test_cenarios_de_ticket_por_servico(cliente):
    r = cliente.get("/api/inteligencia/cenarios-de-ticket", headers=KARINE)
    assert r.status_code == 200, r.text
    servicos = {c["servico"]: c for c in r.json()}
    assert set(servicos) == {"BPO Financeiro", "Contabilidade"}
    assert servicos["BPO Financeiro"]["base"] is None  # menos de 4 contratos: sem base


def test_sem_linha_gravada_nao_ha_plano_no_banco(engine, cliente):
    with Session(engine) as s:
        assert s.get(PlanoDeMrr, 1) is None


# ---------------------------------------------------------------- as quatro fases (04/10/2026)

from crm.domain import fases_do_cliente as fases  # noqa: E402
from crm.db.modelos import Lead  # noqa: E402
from crm.domain.listas import MotivoDeDescarte, SituacaoLead, TipoCanal  # noqa: E402


def test_cadeia_prevista_do_fim_para_o_comeco_e_sem_taxa_fica_sem_dado():
    t = lambda v: fases.taxa(None, D(v))
    c = fases.cadeia_prevista(D("6"), D("47403"), t("30"), t("83"), t("40"))
    assert (c["propostas"], c["reunioes"], c["leads_icp"]) == (D("20.0"), D("24.1"), D("60.3"))
    sem = fases.cadeia_prevista(D("6"), D("47403"), fases.taxa(None, None), t("83"), t("40"))
    assert sem["propostas"] is None and sem["leads_icp"] is None and sem["contratos"] == 6


def test_a_premissa_vale_sobre_o_historico():
    assert fases.taxa(D("35"), D("20")) == fases.Taxa(D("35"), "premissa")
    assert fases.taxa(None, D("20")).origem == "historico"


def test_gargalo_e_a_etapa_mais_atrasada():
    e = lambda c, p, r: fases.Etapa(c, c, None if p is None else D(p), None if r is None else D(r))
    pior = fases.gargalo([e("leads", 60, 54), e("reunioes", 24, 17), e("propostas", 20, 16), e("mrr", None, 5)])
    assert pior.chave == "reunioes"
    assert fases.gargalo([e("leads", 60, 70)]) is None


@pytest.fixture
def novembro(engine, base):
    with Session(engine) as s:
        g = s.scalars(sa_select(GrupoEconomico)).first()
        for nome, motivo, canal in (("a", None, TipoCanal.PARCEIROS), ("b", None, TipoCanal.TRAFEGO_PAGO),
                                    ("c", MotivoDeDescarte.PORTE_ABAIXO, TipoCanal.TRAFEGO_PAGO)):
            s.add(Lead(nome=nome, situacao=SituacaoLead.NOVO, tipo_canal=canal, motivo_descarte=motivo,
                       criado_em=datetime(2026, 11, 3, 15, tzinfo=timezone.utc),
                       reuniao_marcada_para=datetime(2026, 11, 10, 15, tzinfo=timezone.utc) if nome == "a" else None))
        for situacao in (Situacao.ACEITA, Situacao.PERDIDA):
            s.add(Oportunidade(grupo_id=g.id, nome="nov", situacao=situacao, data_colocacao=date(2026, 11, 4),
                               data_aceite=date(2026, 11, 14) if situacao is Situacao.ACEITA else None))
        bpo = Oportunidade(grupo_id=g.id, nome="bpo nov", servico="BPO Financeiro", situacao=Situacao.ACEITA, preco_mensal=D("7000"),
                          linha_servico=LinhaServico.C1)
        s.add(bpo)
        s.flush()
        s.add(Contrato(grupo_id=g.id, oportunidade_id=bpo.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("7000"),
                       data_inicio=date(2026, 11, 12)))
        s.commit()


def test_as_quatro_fases_do_mes_com_premissas_de_taxa(cliente, novembro):
    premissas = cliente.get("/api/inteligencia/plano", headers=ADMIN).json()["premissas"]
    premissas.pop("alterado_por"), premissas.pop("alterado_em")
    premissas |= {"taxa_conversao_pct": "30", "taxa_reuniao_proposta_pct": "80", "taxa_lead_reuniao_pct": "40", "icp_alvo_pct": "90"}
    assert cliente.put("/api/inteligencia/plano", headers=ADMIN, json=premissas).status_code == 200
    r = cliente.get("/api/inteligencia/fases", headers=KARINE, params={"mes": "2026-11-01", "hoje": "2026-11-20"})
    assert r.status_code == 200, r.text
    f = r.json()
    assert f["tem_previsto"] and not f["mes_fechado"]
    cadeia = {e["chave"]: e for e in f["cadeia"]}
    assert D(cadeia["leads_icp"]["realizado"]) == 2  # o descartado por porte fica fora do ICP
    assert D(cadeia["reunioes"]["realizado"]) == 1
    assert D(cadeia["propostas"]["realizado"]) == 2  # a do contrato BPO não tem data de colocação
    assert D(cadeia["contratos"]["realizado"]) == 1
    assert D(cadeia["contratos"]["previsto"]) == 6  # 3 BPO + 3 vagas contábeis (o atípico ocupa 2 de 4)
    assert D(cadeia["propostas"]["previsto"]) == 20  # 6 ÷ 30%
    assert f["gargalo"] is not None and f["gargalo_texto"].startswith("Gargalo:")
    assert (D(f["taxas"]["conversao"]["valor"]), f["taxas"]["conversao"]["origem"]) == (30, "premissa")
    por = {x["chave"]: x for x in f["fases"]}
    assert [x["chave"] for x in f["fases"]] == ["atracao", "engajamento", "conversao", "pos_venda"]
    atr = {a["rotulo"]: a for a in por["atracao"]["apoio"]}
    assert D(atr["% dos leads dentro do ICP"]["realizado"]) == D("66.7")
    assert D(atr["Leads por indicação"]["realizado"]) == 1
    assert "fora do ICP" in por["atracao"]["ajuste"]
    assert por["engajamento"]["kpi"]["realizado"] is None and "aderência respondida" in por["engajamento"]["kpi"]["nota"]
    assert "Responda a aderência" in por["engajamento"]["ajuste"]
    assert "Faltou 2 BPO Financeiro" in por["conversao"]["ajuste"]
    assert por["conversao"]["situacao"]["chave"] == "abaixo"


def test_mes_fora_da_projecao_mostra_so_o_realizado(cliente):
    f = cliente.get("/api/inteligencia/fases", headers=KARINE, params={"mes": "2026-10-01", "hoje": "2026-10-04"}).json()
    assert not f["tem_previsto"] and f["aviso"]
    assert all(e["previsto"] is None for e in f["cadeia"])
    assert f["meses"][0] == "2026-09-01" and f["meses"][-1] == "2027-06-01"



# ---------------------------------------------------------------- aderência e primeiro contato (04/10/2026)

from crm.domain.listas import AderenciaDaPromessa  # noqa: E402


def test_editar_a_aderencia_do_lead_e_bate_limpa_o_detalhe(cliente, engine):
    with Session(engine) as s:
        lead = Lead(nome="x", situacao=SituacaoLead.EM_CONTATO)
        s.add(lead)
        s.commit()
        lead_id = lead.id
    r = cliente.patch(f"/api/leads/{lead_id}", headers=ADMIN, json={
        "primeiro_contato_em": "2026-11-03T14:20:00-03:00", "aderencia": "Não bate",
        "aderencia_sobre": ["Preço", "Preço", "Prazo"], "aderencia_esperava": "  Achou que custava menos  ",
    })
    assert r.status_code == 200, r.text
    l = r.json()
    assert (l["aderencia"], l["aderencia_sobre"], l["aderencia_esperava"]) == ("Não bate", ["Preço", "Prazo"], "Achou que custava menos")
    assert l["primeiro_contato_em"].startswith("2026-11-03")
    l = cliente.patch(f"/api/leads/{lead_id}", headers=ADMIN, json={"aderencia": "Bate"}).json()
    assert (l["aderencia"], l["aderencia_sobre"], l["aderencia_esperava"]) == ("Bate", None, None)
    assert cliente.patch(f"/api/leads/{lead_id}", headers=ADMIN, json={"aderencia_sobre": ["Cor"]}).status_code == 422
    listas = cliente.get("/api/listas", headers=ADMIN).json()
    assert listas["aderencias"] == ["Bate", "Em parte", "Não bate"]
    assert "Esperava outra coisa (a promessa não bate)" in listas["motivos_de_descarte"]
    assert "Expectativa diferente da promessa" in listas["motivos_de_recusa"]


def test_engajamento_mede_a_aderencia_a_origem_e_o_tema(cliente, engine):
    criado = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)
    with Session(engine) as s:
        for i, (aderencia, sobre, campanha) in enumerate([
            (AderenciaDaPromessa.BATE, None, "Campanha A"), (AderenciaDaPromessa.BATE, None, "Campanha A"),
            (AderenciaDaPromessa.NAO_BATE, ["Preço"], "Campanha B"), (AderenciaDaPromessa.EM_PARTE, ["Preço", "Prazo"], "Campanha B"),
        ]):
            s.add(Lead(nome=f"l{i}", situacao=SituacaoLead.EM_CONTATO, criado_em=criado, campanha=campanha, aderencia=aderencia,
                       aderencia_sobre=sobre, primeiro_contato_em=datetime(2026, 11, 3, 12 + 2 * (i + 1), tzinfo=timezone.utc)))
        s.add(Lead(nome="perdido", situacao=SituacaoLead.DESCARTADO, criado_em=criado,
                   motivo_descarte=MotivoDeDescarte.EXPECTATIVA, descartado_em=datetime(2026, 11, 5, tzinfo=timezone.utc)))
        s.commit()
    premissas = cliente.get("/api/inteligencia/plano", headers=ADMIN).json()["premissas"]
    premissas.pop("alterado_por"), premissas.pop("alterado_em")
    premissas |= {"aderencia_alvo_pct": "80", "primeiro_contato_horas": "3"}
    assert cliente.put("/api/inteligencia/plano", headers=ADMIN, json=premissas).status_code == 200
    f = cliente.get("/api/inteligencia/fases", headers=KARINE, params={"mes": "2026-11-01", "hoje": "2026-11-20"}).json()
    eng = next(x for x in f["fases"] if x["chave"] == "engajamento")
    assert (D(eng["kpi"]["realizado"]), D(eng["kpi"]["previsto"])) == (50, 80)
    assert eng["situacao"]["chave"] == "abaixo"
    apoio = {a["rotulo"]: a for a in eng["apoio"]}
    assert D(apoio["Aderência parcial (em parte)"]["realizado"]) == 25
    assert D(apoio["Tempo até o 1º contato (mediana)"]["realizado"]) == 5  # 2, 4, 6 e 8 h
    assert D(apoio["Perdidos por expectativa"]["realizado"]) == 1
    assert "2 de 4 leads" in eng["ajuste"]
    assert "“Campanha B”: aderência de 0%" in eng["ajuste"]
    assert "erra mais em preço (2 vezes)" in eng["ajuste"]
    assert "o alvo é 3 h" in eng["ajuste"]
