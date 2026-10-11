"""Reunião com o lead pelo Granola alimenta a proposta (amostra aprovada por Eduardo em 10/10/2026).

O resumo da nota [Potencial Cliente] vira sugestão de contextualização e de perfil; nada se grava até a
pessoa aplicar. Do lead guarda-se só o resumo, com a ciência da gravação. Dados fictícios."""

from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal as D

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.agente.contexto_da_proposta import sugerir_contexto
from crm.agente.sdr import Uso
from crm.api.app import criar_app
from crm.api.sucesso import ServicosDaAta
from crm.db.excluir_oportunidade import excluir
from crm.acesso.auditoria import _IGNORADOS  # noqa: PLC2701
from crm.db.modelos import Oportunidade, ReuniaoComLead
from crm.proposta.rascunho import FRASE_PADRAO
from test_ata_e_ajustes import ClienteFalso
from test_proposta import _entrada, _oportunidade_do_questionario, _subir
from test_questionario import FonteFalsa, linha

HOJE = date.today()
RESUMO = (
    "## Empresa e atividade\nDistribuidora de insumos hospitalares, matriz no Rio e filiais em Niterói e Campinas.\n"
    "## Dor principal\nO fechamento sai 20 dias depois do mês; a sócia decide sem o caixa da semana.\n"
    "## Sistema\nHoje lançam tudo no Omie. Regime: Lucro Real."
)
SUGESTAO = {
    "contextualizacao": "A Exemplo Alfa distribui insumos hospitalares. O fechamento sai 20 dias depois do mês.",
    "perfil": [
        {"campo": "sistema", "valor": "Omie", "trecho": "lançam tudo no Omie"},
        {"campo": "localidade", "valor": "Rio de Janeiro/RJ, Niterói/RJ e Campinas/SP", "trecho": "matriz no Rio"},
        {"campo": "regime", "valor": "Lucro Real", "trecho": "Regime: Lucro Real"},
        {"campo": "sistema", "valor": "SAP", "trecho": ""},          # repetido: fica o primeiro
        {"campo": "cor_preferida", "valor": "azul", "trecho": ""},   # fora da lista: a IA não cria campo
        {"campo": "funcionarios", "valor": "  ", "trecho": ""},      # vazio
    ],
    "para_a_carta": ["Dor: fechamento atrasado", " ", "Quem decide: Ana (sócia)"],
}


@pytest.fixture
def falso():
    return ClienteFalso(texto=json.dumps(SUGESTAO))


@pytest.fixture
def fabrica(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def cliente(fabrica, falso):
    fonte = FonteFalsa([linha()])
    app = criar_app(fabrica, fonte_de_questionarios=lambda: fonte,
                    servicos_da_ata=lambda: ServicosDaAta(cliente=lambda: falso))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def oid(cliente):
    _subir(cliente)
    return _oportunidade_do_questionario(cliente)


def _sugerir(cliente, oid, **extra):
    return cliente.post(f"/api/oportunidades/{oid}/proposta/reuniao-com-lead/sugestao", json={
        "matriz": "Contábil", "data": HOJE.isoformat(), "participantes": "Ana (sócia)", "resumo": RESUMO, **extra,
    })


def _guardar(cliente, oid, **extra):
    return cliente.post(f"/api/oportunidades/{oid}/proposta/reuniao-com-lead", json={
        "data": HOJE.isoformat(), "participantes": " Ana  (sócia) ", "resumo": RESUMO, "ciencia_da_gravacao": True,
        **extra,
    })


# ------------------------------------------------------------------ a sugestão da IA

def test_sugestao_limpa_o_que_a_ia_devolve_e_nao_grava_nada(cliente, oid, falso, engine):
    r = _sugerir(cliente, oid)
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["contextualizacao"].endswith("\n" + FRASE_PADRAO)  # a frase padrão sempre fecha
    assert [(p["campo"], p["valor"]) for p in s["perfil"]] == [
        ("sistema", "Omie"), ("localidade", "Rio de Janeiro/RJ, Niterói/RJ e Campinas/SP"), ("regime", "Lucro Real")]
    sistema, _, regime = s["perfil"]
    assert (sistema["rotulo"], sistema["atual"], sistema["diverge"]) == ("Sistema", "N/D", False)
    # O questionário diz Lucro Presumido: diverge, e a tela traz desmarcado.
    assert (regime["atual"], regime["diverge"]) == ("Lucro Presumido", True)
    assert "Movimentação" in s["nao_apareceu"] and "Sistema" not in s["nao_apareceu"]
    assert s["para_a_carta"] == ["Dor: fechamento atrasado", "Quem decide: Ana (sócia)"]
    assert s["custo_usd"] is not None
    pedido = falso.pedidos[0]["messages"][0]["content"]
    assert "Exemplo Alfa" in pedido and RESUMO in pedido and "- sistema: Sistema" in pedido
    assert "volume_documentos" not in pedido  # campo da matriz Financeiro
    with Session(engine) as s:
        assert s.scalar(sa.select(sa.func.count(ReuniaoComLead.id))) == 0


def test_resumo_curto_e_recusado(cliente, oid, falso):
    r = _sugerir(cliente, oid, resumo="reunião boa")
    assert r.status_code == 422 and "curto" in r.json()["detail"]
    assert falso.pedidos == []


@pytest.mark.parametrize("stop_reason, trecho", [("refusal", "recusou"), ("max_tokens", "cortada")])
def test_falha_da_ia_vira_mensagem_para_a_pessoa(cliente, oid, falso, stop_reason, trecho):
    falso.stop_reason = stop_reason
    r = _sugerir(cliente, oid)
    assert r.status_code == 502 and trecho in r.json()["detail"]


def test_contextualizacao_vazia_nao_ganha_so_a_frase_padrao():
    falso = ClienteFalso(texto=json.dumps({"contextualizacao": " ", "perfil": [], "para_a_carta": []}))
    s = sugerir_contexto(falso, "m", cliente="Alfa", servicos=[], campos={"sistema": "Sistema"}, data="10/10/2026",
                         participantes=None, resumo=RESUMO, uso=Uso(modelo="m"))
    assert s.contextualizacao == "" and s.perfil == []


# ------------------------------------------------------------------ aplicar e guardar

def test_aplicar_guarda_so_o_resumo_e_preenche_a_proposta(cliente, oid, engine):
    contexto = f"A Exemplo Alfa distribui insumos hospitalares.\n{FRASE_PADRAO}"
    r = _guardar(cliente, oid, contextualizacao=contexto, link_do_granola="https://notes.granola.ai/d/abc",
                 perfil={"sistema": "Omie", "localidade": " Rio  de Janeiro/RJ "})
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["rascunho"]["contextualizacao"] == contexto
    assert a["perfil"]["sistema"] == "Omie" and a["perfil"]["localidade"] == "Rio de Janeiro/RJ"
    assert a["perfil"]["regime"] == "Lucro Presumido"  # não marcado: o questionário fica
    assert sorted(a["perfil_da_reuniao"]) == ["localidade", "sistema"]
    [reuniao] = a["reunioes_com_o_lead"]
    assert reuniao["participantes"] == "Ana (sócia)" and reuniao["ciencia_da_gravacao"]
    assert reuniao["contextualizacao_aplicada"] and sorted(reuniao["campos_aplicados"]) == ["localidade", "sistema"]
    assert reuniao["resumo_do_granola"] == RESUMO
    # Reabrir a aba traz o mesmo; gerar a proposta leva o perfil da reunião.
    assert cliente.get(f"/api/oportunidades/{oid}/proposta").json()["perfil"]["sistema"] == "Omie"
    gerada = cliente.post(f"/api/oportunidades/{oid}/proposta", json=_entrada())
    assert gerada.status_code == 200, gerada.text
    with Session(engine) as s:
        assert s.scalar(sa.select(sa.func.count(ReuniaoComLead.id))) == 1
    assert "resumo_do_granola" in _IGNORADOS  # dado de cliente: fora do histórico de alterações


def test_manter_a_contextualizacao_atual(cliente, oid):
    antes = cliente.get(f"/api/oportunidades/{oid}/proposta").json()["rascunho"]["contextualizacao"]
    a = _guardar(cliente, oid, contextualizacao=None, perfil={"sistema": "Omie"}).json()
    assert a["rascunho"]["contextualizacao"] == antes
    assert not a["reunioes_com_o_lead"][0]["contextualizacao_aplicada"]


def test_reuniao_depois_da_proposta_gerada_traz_a_contextualizacao_nova(cliente, oid):
    assert cliente.post(f"/api/oportunidades/{oid}/proposta", json=_entrada()).status_code == 200
    a = _guardar(cliente, oid, contextualizacao=f"Nova.\n{FRASE_PADRAO}").json()
    assert a["rascunho"]["contextualizacao"].startswith("Nova.")
    assert D(a["rascunho"]["valor_contabil"]) == D("4500")  # o resto da última proposta fica


def test_a_reuniao_mais_nova_vale_por_cima(cliente, oid):
    _guardar(cliente, oid, data=(HOJE - timedelta(days=5)).isoformat(), perfil={"sistema": "SAP", "empresas": "2 empresas"})
    a = _guardar(cliente, oid, perfil={"sistema": "Omie"}).json()
    assert a["perfil"]["sistema"] == "Omie" and a["perfil"]["empresas"] == "2 empresas"
    assert [r["data"] for r in a["reunioes_com_o_lead"]] == [HOJE.isoformat(), (HOJE - timedelta(days=5)).isoformat()]


@pytest.mark.parametrize("extra, trecho", [
    ({"ciencia_da_gravacao": False}, "avisado"),
    ({"data": (HOJE + timedelta(days=1)).isoformat()}, "futura"),
    ({"resumo": "curto"}, "curto"),
    ({"perfil": {"cnpj": "00.000.000/0001-00"}}, "desconhecido"),
    ({"perfil": {"sistema": "x" * 121}}, "longo"),
])
def test_guardar_recusa_o_que_nao_vale(cliente, oid, engine, extra, trecho):
    r = _guardar(cliente, oid, **extra)
    assert r.status_code == 422 and trecho in r.text
    with Session(engine) as s:
        assert s.scalar(sa.select(sa.func.count(ReuniaoComLead.id))) == 0


def test_oportunidade_inexistente(cliente):
    assert _guardar(cliente, 9999).status_code == 404


def test_excluir_a_oportunidade_leva_a_reuniao(cliente, oid, engine):
    _guardar(cliente, oid)
    with Session(engine) as s:
        excluir(s, s.get(Oportunidade, oid), "duplicada")
        s.commit()
        assert s.scalar(sa.select(sa.func.count(ReuniaoComLead.id))) == 0
