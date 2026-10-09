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
    (date(2026, 8, 31), 6, date(2027, 2, 28)),
])
def test_mais_meses_cai_no_ultimo_dia_do_mes_curto(dia, meses, esperado):
    assert regra.mais_meses(dia, meses) == esperado


def test_devida_conta_da_ultima_e_sem_nenhuma_conta_da_entrada_em_curso():
    hoje = date(2026, 10, 2)
    linhas = regra.devidas(["mensal", "semestral"], {"mensal": date(2026, 8, 20)}, date(2026, 6, 1), hoje)
    mensal, semestral = linhas
    assert (mensal.proxima, mensal.atrasada, mensal.dias_de_atraso) == (date(2026, 9, 20), True, 12)
    # semestral sem nenhuma: 6 meses da entrada em curso (01/06 → 01/12)
    assert (semestral.ultima, semestral.proxima, semestral.atrasada, semestral.dias_de_atraso) == (
        None, date(2026, 12, 1), False, None)


def test_sem_nenhuma_registrada_e_sem_data_de_entrada_conta_como_atrasada():
    (semestral,) = regra.devidas(["semestral"], {}, None, date(2026, 10, 2))
    assert (semestral.proxima, semestral.atrasada, semestral.dias_de_atraso) == (None, True, None)


def test_vence_no_dia_ainda_esta_em_dia():
    (m,) = regra.devidas(["mensal"], {"mensal": date(2026, 9, 2)}, None, date(2026, 10, 2))
    assert (m.proxima, m.atrasada) == (date(2026, 10, 2), False)


def test_ordem_segue_o_fluxograma_e_nao_a_da_cadencia():
    assert [d.tipo for d in regra.devidas(["semestral", "mensal"], {}, HOJE, HOJE)] == ["mensal", "semestral"]


def test_um_tipo_antigo_nao_e_cobrado():
    assert regra.devidas(["anual", "bimestral"], {}, HOJE, HOJE) == []
    assert regra.tipo("anual") is None and regra.nome_do_tipo("anual") == "Anual"
    assert regra.nome_do_tipo("semestral") == "Semestral"


def test_cadencia_padrao_e_uma_reuniao_por_classe():
    # Eduardo, 03/10/2026: A mensal, B trimestral, C semestral; sem anual
    assert regra.CADENCIA_PADRAO == {"A": ("mensal",), "B": ("trimestral",), "C": ("semestral",)}
    assert [(t.chave, t.meses) for t in regra.TIPOS_DE_REUNIAO] == [("mensal", 1), ("trimestral", 3), ("semestral", 6)]
    # toda pauta leva as lacunas e o que vender; a semestral começa pela estratégia e os desafios
    assert all("Lacunas técnicas" in t.pauta[-1] for t in regra.TIPOS_DE_REUNIAO)
    assert regra.tipo("semestral").pauta[0] == "Entender a estratégia e os desafios da empresa"
    assert "análise vertical e horizontal" in regra.tipo("mensal").pauta[0]


@pytest.mark.parametrize("ultima, hoje, proxima, atrasada, dias", [
    (None, date(2026, 12, 2), date(2026, 12, 2), False, None),  # sem nenhuma: do início do funil
    (None, date(2026, 12, 5), date(2026, 12, 2), True, 3),
    (date(2026, 11, 30), date(2027, 1, 30), date(2027, 1, 30), False, None),
])
def test_bimestral_da_carteira_vence_a_cada_2_meses(ultima, hoje, proxima, atrasada, dias):
    d = regra.devida_da_carteira(ultima, hoje)
    assert (d.proxima, d.atrasada, d.dias_de_atraso) == (proxima, atrasada, dias)


PESSOAS = [("jefferson@x.com", "Jefferson Souza"), ("bruno@x.com", "Bruno Soares"), ("bruna@x.com", "Bruna Lima"),
           ("ana@x.com", "Ana Paula Reis"), ("ana.c@x.com", "Ana Costa"), ("jose@x.com", None)]


@pytest.mark.parametrize("citado, email", [
    ("Jefferson", "jefferson@x.com"),
    ("jefferson souza", "jefferson@x.com"),
    ("Bruno", "bruno@x.com"),  # "Bruno" não é "Bruna"
    ("Ana Paula", "ana@x.com"),
    ("Ana", None),  # duas Anas: a pessoa escolhe
    ("Carla", None),  # não cadastrada
    ("Souza", None),  # só o sobrenome não basta
    ("José", "jose@x.com"),  # sem nome, pelo e-mail; sem acento
    ("", None), (None, None),
])
def test_responsavel_citado_vira_quem_recebe_ajuste(citado, email):
    assert regra.achar_responsavel(citado, PESSOAS) == email


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


def _grupo(cliente, grupo_id: int, hoje: date | None = None) -> dict:
    params = {"hoje": hoje.isoformat()} if hoje else {}
    return next(g for g in cliente.get("/api/sucesso/funil", headers=ADMIN, params=params).json()["grupos"]
                if g["grupo_id"] == grupo_id)


def test_entram_os_grupos_com_contrato_valendo_na_etapa_certa(cliente, ids):
    f = cliente.get("/api/sucesso/funil", headers=ADMIN, params={"hoje": "2026-10-15"}).json()
    assert [e["chave"] for e in f["etapas"]] == ["contrato", "handover", "kickoff", "em_curso"]
    por_nome = {g["nome"]: g for g in f["grupos"]}
    assert set(por_nome) == {"Antigo A", "Novo", "Sem classe"}
    assert (por_nome["Novo"]["etapa"], por_nome["Novo"]["situacao"]) == ("contrato", None)
    antigo = por_nome["Antigo A"]
    assert (antigo["etapa"], antigo["classe"], antigo["situacao"]) == ("em_curso", "A", "em_dia")
    # Anterior ao CRM sem reunião registrada: conta do início do funil, 02/10/2026 (opção A).
    assert antigo["em_curso_desde"] == "2026-10-02"
    assert [(r["tipo"], r["proxima"], r["atrasada"]) for r in antigo["reunioes"]] == [("mensal", "2026-11-02", False)]
    assert antigo["mrr_bruto"] == "6500.00"  # os dois contratos ativos: 6.000 × 13 ÷ 12
    assert (por_nome["Sem classe"]["situacao"], por_nome["Sem classe"]["reunioes"]) == ("sem_classe", [])
    assert len(f["checklist"]["kickoff"]) == 5 and f["cadencia"] == {"A": ["mensal"], "B": ["trimestral"], "C": ["semestral"]}
    assert [t["chave"] for t in f["tipos"]] == ["mensal", "trimestral", "semestral"]
    assert f["tipos_antigos"] == {"bimestral": "Bimestral", "anual": "Anual"}
    assert f["intencao"]["C"].startswith("Entender a estratégia e os desafios")
    assert (f["carteira"]["nome"], f["carteira"]["proxima"], f["carteira"]["atrasada"]) == (
        "Bimestral da carteira", "2026-12-02", False)


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


def test_anterior_ao_crm_vence_a_partir_do_inicio_do_funil(cliente, ids):
    mensal = _grupo(cliente, ids["antigo"], date(2026, 11, 20))["reunioes"][0]
    assert (mensal["tipo"], mensal["proxima"], mensal["atrasada"], mensal["dias_de_atraso"]) == ("mensal", "2026-11-02", True, 18)


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
    lista = cliente.get(f"/api/sucesso/grupos/{g}/reunioes", headers=ADMIN).json()
    assert (lista[0]["decisoes"], lista[0]["proximos_passos"], lista[0]["registrada_por"]) == (
        "Renegociar a dívida bancária", None, "Eduardo Luiz")
    with Session(engine) as s:
        # reuniões de tipos antigos ficam no histórico, mas não contam pela mensal
        for tipo in ("bimestral", "trimestral", "anual"):
            s.add(ReuniaoDeResultado(grupo_id=g, tipo=tipo, data=date(2027, 5, 31)))
        s.commit()
    # Bem depois do início do funil: só não vence o que foi registrado.
    depois = date(2027, 6, 1)
    assert _grupo(cliente, g, depois)["situacao"] == "atrasada"
    with Session(engine) as s:
        s.add(ReuniaoDeResultado(grupo_id=g, tipo="mensal", data=date(2027, 5, 31)))
        s.commit()
    assert _grupo(cliente, g, depois)["situacao"] == "em_dia"


@pytest.mark.parametrize("grupo, corpo, trecho", [
    ("antigo", {"tipo": "semanal", "data": HOJE.isoformat()}, "Tipo de reunião desconhecido"),
    ("antigo", {"tipo": "anual", "data": HOJE.isoformat()}, "Tipo de reunião desconhecido"),  # saiu em 03/10/2026
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
    r = cliente.put("/api/sucesso/cadencia", headers=ADMIN, json={"cadencia": {"A": ["semestral", "trimestral"]}})
    assert r.status_code == 200, r.text
    assert r.json()["cadencia"]["A"] == ["trimestral", "semestral"] and r.json()["alterado_por"] == "Eduardo Luiz"
    assert r.json()["cadencia"]["B"] == ["trimestral"]
    assert [x["tipo"] for x in _grupo(cliente, ids["antigo"])["reunioes"]] == ["trimestral", "semestral"]


def test_intencao_da_classe_editavel_e_vazia_volta_ao_padrao(cliente, ids):
    r = cliente.put("/api/sucesso/cadencia", headers=ADMIN, json={"intencao": {"B": "  Subir para A  "}})
    assert r.status_code == 200, r.text
    assert r.json()["intencao"]["B"] == "Subir para A" and r.json()["cadencia"]["B"] == ["trimestral"]
    assert cliente.get("/api/sucesso/funil", headers=ADMIN).json()["intencao"]["B"] == "Subir para A"
    r = cliente.put("/api/sucesso/cadencia", headers=ADMIN, json={"intencao": {"B": " "}})
    assert r.json()["intencao"]["B"] == regra.INTENCAO_PADRAO["B"]


def test_tipo_antigo_gravado_na_cadencia_nao_e_cobrado(cliente, ids, engine):
    from crm.db.modelos import CadenciaDeReuniao

    with Session(engine) as s:
        s.add(CadenciaDeReuniao(classe="A", tipos=["bimestral", "anual"]))
        s.commit()
    assert [x["tipo"] for x in _grupo(cliente, ids["antigo"])["reunioes"]] == ["mensal"]  # volta ao padrão


def test_bimestral_da_carteira_registra_e_vence_de_novo(cliente, ids):
    ontem = HOJE - timedelta(days=1)
    r = cliente.post("/api/sucesso/carteira/reunioes", headers=ADMIN, json={
        "data": ontem.isoformat(), "resumo": "Carteira estável", "correcoes_de_rota": "Revisar PRA da classe B"})
    assert r.status_code == 201, r.text
    c = r.json()
    assert (c["devida"]["ultima"], c["devida"]["proxima"]) == (ontem.isoformat(), regra.mais_meses(ontem, 2).isoformat())
    (x,) = c["reunioes"]
    assert (x["participantes"], x["correcoes_de_rota"], x["registrada_por"]) == (
        "Head do BPO & CEO da Critério", "Revisar PRA da classe B", "Eduardo Luiz")
    r = cliente.post("/api/sucesso/carteira/reunioes", headers=ADMIN, json={"data": (HOJE + timedelta(days=1)).isoformat()})
    assert r.status_code == 422


@pytest.mark.parametrize("corpo, trecho", [
    ({"cadencia": {"A": []}}, "ao menos uma"),
    ({"cadencia": {"D": ["mensal"]}}, "Classe desconhecida"),
    ({"intencao": {"D": "x"}}, "Classe desconhecida"),
    ({"cadencia": {"A": ["anual"]}}, "tipo de reunião desconhecido"),
    ({"cadencia": {"B": ["semanal"]}}, "tipo de reunião desconhecido"),
])
def test_cadencia_validada(cliente, corpo, trecho):
    r = cliente.put("/api/sucesso/cadencia", headers=ADMIN, json=corpo)
    assert r.status_code == 422 and trecho in r.json()["detail"]


def test_sem_permissao_nao_ve_nem_mexe(cliente, ids):
    assert cliente.get("/api/sucesso/funil", headers=KARINE).status_code == 403
    assert cliente.post(f"/api/sucesso/grupos/{ids['antigo']}/reunioes", headers=KARINE,
                        json={"tipo": "mensal", "data": HOJE.isoformat()}).status_code == 403
    assert cliente.put("/api/sucesso/cadencia", headers=KARINE, json={"cadencia": {"A": ["mensal"]}}).status_code == 403
    assert cliente.get("/api/sucesso/carteira", headers=KARINE).status_code == 403
    assert cliente.post("/api/sucesso/carteira/reunioes", headers=KARINE, json={"data": HOJE.isoformat()}).status_code == 403
