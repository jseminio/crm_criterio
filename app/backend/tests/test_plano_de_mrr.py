"""Inteligência de Conversão, Entrega 1 (03/10/2026): o plano de MRR — previsto por cenário,
realizado por motor, ajuste — e as premissas, que só o Administrador muda."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import (
    Contrato, ContratoPrevistoDoPlano, EventoDeContrato, GrupoEconomico, Oportunidade, Perfil, PlanoDeMrr, Usuario,
)
from crm.domain import plano_de_mrr as regras
from crm.domain.listas import Situacao, SituacaoContrato, TipoDeEventoDeContrato as T

PIPELINE = (
    regras.ContratoPrevisto("atípico", date(2026, 11, 1), D("18000"), True),
    regras.ContratoPrevisto("normal", date(2026, 11, 1), D("5500"), False),
    regras.ContratoPrevisto("atípico", date(2026, 12, 1), D("16000"), True),
)


# ---------------------------------------------------------------- regras

def test_os_tres_cenarios_de_03_10_batem_com_a_conta_mostrada_a_eduardo():
    p = replace(regras.PADRAO, contratos_previstos=PIPELINE)
    alerta, previsto, otimista = (regras.projetar(p, n) for n in regras.CENARIOS)
    assert (alerta.liquido, alerta.percentual_da_meta) == (D("233636.22"), D("93.5"))
    assert (previsto.liquido, previsto.percentual_da_meta) == (D("325725.25"), D("130.3"))
    assert (otimista.liquido, otimista.percentual_da_meta) == (D("518120.88"), D("207.2"))
    assert (previsto.bpo, previsto.contabil, previsto.escada) == (D("168000.00"), D("117888.56"), D("44640.00"))


def test_o_atipico_ocupa_duas_vagas_do_onboarding_contabil():
    p = replace(regras.PADRAO, contratos_previstos=PIPELINE)
    nov, dez, jan = regras.projetar(p, "previsto").linhas[:3]
    assert nov.contabil == D("18000") + D("5500") + D("2903.28")  # 2 + 1 vagas ocupadas, sobra 1
    assert dez.contabil == D("16000") + 2 * D("2903.28")
    assert jan.contabil == 4 * D("2903.28")
    assert regras.projetar(p, "alerta").linhas[0].contabil == 4 * D("2903.28")  # o alerta não conta o pipeline


def test_a_escada_sobe_a_cada_prazo_e_o_bpo_respeita_o_teto():
    p = replace(regras.PADRAO, otimista=regras.Cenario(D("9"), D("5000"), False))
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
        bpo = Oportunidade(grupo_id=g.id, nome="bpo", servico="BPO Financeiro", situacao=Situacao.ACEITA, preco_mensal=D("7000"))
        contabil = Oportunidade(grupo_id=g.id, nome="ctb", servico="Contabilidade", situacao=Situacao.ACEITA, preco_mensal=D("3000"))
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
    assert D(plano["premissas"]["meta_liquida"]) == 250000
    assert plano["premissas"]["alterado_em"] is None  # padrão, ninguém mudou
    assert [c["descricao"] for c in plano["premissas"]["contratos_previstos"]] == ["Atípico do pipeline (nov)"]
    set_, out = plano["realizado"]
    assert (D(set_["novo_bpo"]), D(set_["escada"]), set_["contratos_bpo"]) == (7000, 3000, 1)
    assert (D(out["novo_contabil"]), out["contratos_contabil"]) == (3000, 1)
    assert D(plano["meta"]["realizado"]) == 13000
    assert plano["meta"]["meses_restantes"] == 8  # nov a jun
    assert D(plano["meta"]["previsto_ate_hoje"]) == 26000  # antes da projeção: o ponto de partida
    assert plano["meta"]["situacao"]["chave"] == "abaixo"
    motores = {m["motor"]: m for m in plano["motores"]}
    assert D(motores["bpo"]["realizado"]) == 7000
    assert "contratos/mês" in motores["bpo"]["ajuste"]
    assert [c["nome"] for c in plano["cenarios"]] == ["alerta", "previsto", "otimista"]


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
    assert D(previsto["bpo"]) == 224000  # 4 × R$ 7 mil × 8 meses


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
