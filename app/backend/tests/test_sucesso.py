"""Funil do Sucesso do Cliente (02/10/2026): etapas, checklist e reuniões de resultado pela classe."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import ClassificacaoDoGrupo, Contrato, GrupoEconomico, Perfil, ReuniaoDeResultado, Usuario
from crm.domain import sucesso as regra
from crm.domain.listas import SituacaoContrato

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}
HOJE = date.today()


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


# ------------------------------------------------------------------ regra


@pytest.mark.parametrize("dia, meses, esperado", [
    (date(2026, 1, 31), 1, date(2026, 2, 28)),
    (date(2028, 1, 31), 1, date(2028, 2, 29)),
    (date(2026, 11, 15), 3, date(2027, 2, 15)),
    (date(2026, 10, 2), 12, date(2027, 10, 2)),
])
def test_mais_meses_cai_no_ultimo_dia_do_mes_curto(dia, meses, esperado):
    assert regra.mais_meses(dia, meses) == esperado


def test_devida_conta_da_ultima_e_sem_nenhuma_conta_da_entrada_em_curso():
    hoje = date(2026, 10, 2)
    linhas = regra.devidas(["mensal", "anual"], {"mensal": date(2026, 8, 20)}, date(2026, 6, 1), hoje)
    mensal, anual = linhas
    assert (mensal.proxima, mensal.atrasada, mensal.dias_de_atraso) == (date(2026, 9, 20), True, 12)
    assert (anual.ultima, anual.proxima, anual.atrasada, anual.dias_de_atraso) == (None, date(2027, 6, 1), False, None)


def test_sem_nenhuma_registrada_e_sem_data_de_entrada_conta_como_atrasada():
    (anual,) = regra.devidas(["anual"], {}, None, date(2026, 10, 2))
    assert (anual.proxima, anual.atrasada, anual.dias_de_atraso) == (None, True, None)


def test_vence_no_dia_ainda_esta_em_dia():
    (m,) = regra.devidas(["mensal"], {"mensal": date(2026, 9, 2)}, None, date(2026, 10, 2))
    assert (m.proxima, m.atrasada) == (date(2026, 10, 2), False)


def test_ordem_segue_o_fluxograma_e_nao_a_da_cadencia():
    assert [d.tipo for d in regra.devidas(["anual", "mensal"], {}, HOJE, HOJE)] == ["mensal", "anual"]


def test_cadencia_padrao_e_a_recomendacao_aceita():
    assert regra.CADENCIA_PADRAO == {
        "A": ("mensal", "bimestral", "trimestral", "anual"), "B": ("trimestral", "anual"), "C": ("anual",),
    }


# ------------------------------------------------------------------ API


def _leitura(grupo_id: int, classe: str, referencia: date = date(2026, 9, 1), revisao: int = 1) -> ClassificacaoDoGrupo:
    um = D("3")
    return ClassificacaoDoGrupo(
        grupo_id=grupo_id, referencia=referencia, revisao=revisao, fonte="teste", versao_dos_parametros="v1",
        receita_mensal=D("10000"), nota_receita=um, nota_rentabilidade=um, complexidade=um, disciplina=um,
        risco_tecnico=um, cross_sell=um, adimplencia=um, semaforo=1, score=D("0.5"), classe=classe,
        classe_efetiva=classe, eixo_de_acao="Manter",
    )


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        comercial = Perfil(nome="Comercial", permissoes=["funil.ver"])
        s.add(comercial)
        antigo = GrupoEconomico(nome="Antigo A")  # anterior ao CRM, classe A (B na leitura mais velha)
        novo = GrupoEconomico(nome="Novo")  # contrato novo, aguardando assinatura
        sem_classe = GrupoEconomico(nome="Sem classe")
        encerrado = GrupoEconomico(nome="Encerrado")
        s.add_all([antigo, novo, sem_classe, encerrado])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=comercial.id))
        s.add_all([
            Contrato(grupo_id=antigo.id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO, preco_mensal=D("5000")),
            Contrato(grupo_id=antigo.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("1000")),
            Contrato(grupo_id=novo.id, situacao=SituacaoContrato.AGUARDANDO_ASSINATURA),
            Contrato(grupo_id=sem_classe.id, anterior_ao_crm=True, situacao=SituacaoContrato.ATIVO),
            Contrato(grupo_id=encerrado.id, anterior_ao_crm=True, situacao=SituacaoContrato.ENCERRADO),
            _leitura(antigo.id, "B", date(2026, 6, 1)),
            _leitura(antigo.id, "A"),
        ])
        s.commit()
        return {"antigo": antigo.id, "novo": novo.id, "sem_classe": sem_classe.id, "encerrado": encerrado.id}


@pytest.fixture
def cliente(engine, ids):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


def _grupo(cliente, grupo_id: int) -> dict:
    return next(g for g in cliente.get("/api/sucesso/funil", headers=ADMIN).json()["grupos"] if g["grupo_id"] == grupo_id)


def test_entram_os_grupos_com_contrato_valendo_na_etapa_certa(cliente, ids):
    f = cliente.get("/api/sucesso/funil", headers=ADMIN).json()
    assert [e["chave"] for e in f["etapas"]] == ["contrato", "handover", "kickoff", "em_curso"]
    por_nome = {g["nome"]: g for g in f["grupos"]}
    assert set(por_nome) == {"Antigo A", "Novo", "Sem classe"}
    assert (por_nome["Novo"]["etapa"], por_nome["Novo"]["situacao"]) == ("contrato", None)
    antigo = por_nome["Antigo A"]
    assert (antigo["etapa"], antigo["classe"], antigo["situacao"]) == ("em_curso", "A", "atrasada")
    assert [r["tipo"] for r in antigo["reunioes"]] == ["mensal", "bimestral", "trimestral", "anual"]
    assert all(r["proxima"] is None and r["atrasada"] for r in antigo["reunioes"])  # nenhuma registrada ainda
    assert (por_nome["Sem classe"]["situacao"], por_nome["Sem classe"]["reunioes"]) == ("sem_classe", [])
    assert len(f["checklist"]["kickoff"]) == 5 and f["cadencia"]["C"] == ["anual"]


def test_checklist_e_concluir_etapa_ate_entrar_em_curso(cliente, ids):
    g = ids["novo"]
    r = cliente.post(f"/api/sucesso/grupos/{g}/concluir-etapa", headers=ADMIN)
    assert r.status_code == 422 and "Faltam 3 itens" in r.json()["detail"]
    r = cliente.patch(f"/api/sucesso/grupos/{g}/itens", headers=ADMIN, json={"item": "kyc", "feito": True})
    assert r.status_code == 422 and "não é da etapa" in r.json()["detail"]
    for etapa in ("contrato", "handover", "kickoff"):
        for item, _ in regra.CHECKLIST[etapa]:
            r = cliente.patch(f"/api/sucesso/grupos/{g}/itens", headers=ADMIN, json={"item": item, "feito": True})
            assert r.status_code == 200, r.text
        r = cliente.post(f"/api/sucesso/grupos/{g}/concluir-etapa", headers=ADMIN)
        assert r.status_code == 200, r.text
    grupo = r.json()
    assert (grupo["etapa"], grupo["em_curso_desde"], grupo["situacao"]) == ("em_curso", HOJE.isoformat(), "sem_classe")
    r = cliente.post(f"/api/sucesso/grupos/{g}/concluir-etapa", headers=ADMIN)
    assert r.status_code == 422 and "já está em curso" in r.json()["detail"]
    hist = cliente.get("/api/historico", headers=ADMIN, params={"tabela": "jornada_do_cliente"}).json()
    assert hist and {h["usuario_nome"] for h in hist} == {"Eduardo Luiz"}


def test_desmarcar_item_impede_concluir(cliente, ids):
    g = ids["novo"]
    for item, _ in regra.CHECKLIST["contrato"]:
        cliente.patch(f"/api/sucesso/grupos/{g}/itens", headers=ADMIN, json={"item": item, "feito": True})
    r = cliente.patch(f"/api/sucesso/grupos/{g}/itens", headers=ADMIN, json={"item": "assinatura", "feito": False})
    assert sorted(r.json()["itens_feitos"]) == ["contrato", "proposta"]
    r = cliente.post(f"/api/sucesso/grupos/{g}/concluir-etapa", headers=ADMIN)
    assert r.status_code == 422 and "Assinar o contrato comercial" in r.json()["detail"]


def test_registrar_reuniao_tira_o_atraso_daquele_tipo(cliente, ids, engine):
    g = ids["antigo"]
    ontem = HOJE - timedelta(days=1)
    r = cliente.post(f"/api/sucesso/grupos/{g}/reunioes", headers=ADMIN, json={
        "tipo": "mensal", "data": ontem.isoformat(), "participantes": "Gestor e diretor financeiro",
        "decisoes": "Renegociar a dívida bancária", "proximos_passos": "  ", "dashboard": None,
    })
    assert r.status_code == 201, r.text
    mensal = next(x for x in r.json()["reunioes"] if x["tipo"] == "mensal")
    assert (mensal["ultima"], mensal["proxima"], mensal["atrasada"]) == (ontem.isoformat(), regra.mais_meses(ontem, 1).isoformat(), False)
    assert r.json()["situacao"] == "atrasada"  # as outras três continuam sem registro
    lista = cliente.get(f"/api/sucesso/grupos/{g}/reunioes", headers=ADMIN).json()
    assert (lista[0]["decisoes"], lista[0]["proximos_passos"], lista[0]["registrada_por"]) == (
        "Renegociar a dívida bancária", None, "Eduardo Luiz")
    with Session(engine) as s:
        for tipo in ("bimestral", "trimestral", "anual"):
            s.add(ReuniaoDeResultado(grupo_id=g, tipo=tipo, data=ontem))
        s.commit()
    assert _grupo(cliente, g)["situacao"] == "em_dia"


@pytest.mark.parametrize("grupo, corpo, trecho", [
    ("antigo", {"tipo": "semanal", "data": HOJE.isoformat()}, "Tipo de reunião desconhecido"),
    ("antigo", {"tipo": "mensal", "data": (HOJE + timedelta(days=1)).isoformat()}, "não pode ser futura"),
    ("novo", {"tipo": "mensal", "data": HOJE.isoformat()}, "depois do kickoff"),
])
def test_reuniao_recusada(cliente, ids, grupo, corpo, trecho):
    r = cliente.post(f"/api/sucesso/grupos/{ids[grupo]}/reunioes", headers=ADMIN, json=corpo)
    assert r.status_code == 422 and trecho in r.json()["detail"]


def test_grupo_fora_do_funil_da_404(cliente, ids):
    r = cliente.patch(f"/api/sucesso/grupos/{ids['encerrado']}/itens", headers=ADMIN, json={"item": "proposta", "feito": True})
    assert r.status_code == 404


def test_mudar_a_cadencia_muda_as_reunioes_cobradas(cliente, ids):
    r = cliente.put("/api/sucesso/cadencia", headers=ADMIN, json={"cadencia": {"A": ["anual", "trimestral"]}})
    assert r.status_code == 200, r.text
    assert r.json()["cadencia"]["A"] == ["trimestral", "anual"] and r.json()["alterado_por"] == "Eduardo Luiz"
    assert r.json()["cadencia"]["B"] == ["trimestral", "anual"]
    assert [x["tipo"] for x in _grupo(cliente, ids["antigo"])["reunioes"]] == ["trimestral", "anual"]


@pytest.mark.parametrize("corpo, trecho", [
    ({"cadencia": {"A": []}}, "ao menos uma"),
    ({"cadencia": {"D": ["anual"]}}, "Classe desconhecida"),
    ({"cadencia": {"B": ["semanal"]}}, "tipo de reunião desconhecido"),
])
def test_cadencia_validada(cliente, corpo, trecho):
    r = cliente.put("/api/sucesso/cadencia", headers=ADMIN, json=corpo)
    assert r.status_code == 422 and trecho in r.json()["detail"]


def test_sem_permissao_nao_ve_nem_mexe(cliente, ids):
    assert cliente.get("/api/sucesso/funil", headers=KARINE).status_code == 403
    assert cliente.post(f"/api/sucesso/grupos/{ids['antigo']}/reunioes", headers=KARINE,
                        json={"tipo": "mensal", "data": HOJE.isoformat()}).status_code == 403
    assert cliente.put("/api/sucesso/cadencia", headers=KARINE, json={"cadencia": {"A": ["anual"]}}).status_code == 403
