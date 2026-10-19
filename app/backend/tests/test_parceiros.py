"""Funil de parceiros (19/10/2026, amostra aprovada por Eduardo): a etapa da relação, os indicadores com a composição,
a conferência dos textos de canal antigos, o fee calculado pelos recebidos e aprovado pelo sócio, e o acesso."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import (
    GrupoEconomico,
    ImportacaoDeRecebimentos,
    Oportunidade,
    Perfil,
    Recebimento,
    Usuario,
)
from crm.domain import parceiros as regras
from crm.domain.listas import (
    AcordoDoParceiro,
    EtapaDoParceiro,
    LinhaServico,
    MotivoDeIndicacaoRecusada,
    RegraDoFee,
    Situacao,
    TipoCanal,
)

HOJE = date(2026, 10, 19)
CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}
SOCIO = {"Authorization": "Bearer bruno@grupocriterio.com.br|Bruno"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


def indicacao(**campos):
    base = dict(id=1, nome="x", situacao=Situacao.ENVIAR_PROPOSTA, data_colocacao=None, data_aceite=None,
                data_envio_proposta=None, preco_mensal=None, preco_anual=None, indicacao_recebida_em=None,
                indicacao_validada_em=None, indicacao_recusada=None, linha_servico=LinhaServico.C1)
    return SimpleNamespace(**{**base, **campos})


# ------------------------------------------------------------------ regras puras

def test_sem_indicacao_fica_a_etapa_marcada_ou_formalizado_com_contrato():
    assert regras.etapa_do_parceiro(EtapaDoParceiro.QUALIFICADO, AcordoDoParceiro.SEM_ACORDO, [], HOJE) \
        is EtapaDoParceiro.QUALIFICADO
    assert regras.etapa_do_parceiro(EtapaDoParceiro.MAPEADO, AcordoDoParceiro.CONTRATO_ASSINADO, [], HOJE) \
        is EtapaDoParceiro.FORMALIZADO


def test_etapa_sai_das_indicacoes_e_estrategico_vale_sobre_tudo():
    recebida = indicacao(indicacao_recebida_em=date(2026, 9, 1))
    proposta = indicacao(indicacao_recebida_em=date(2026, 9, 1), situacao=Situacao.EM_AVALIACAO)
    velha = indicacao(indicacao_recebida_em=date(2026, 3, 1), situacao=Situacao.ACEITA)
    recusada = indicacao(indicacao_recebida_em=date(2026, 9, 1), indicacao_recusada=MotivoDeIndicacaoRecusada.JA_CLIENTE)
    m, s = EtapaDoParceiro.MAPEADO, AcordoDoParceiro.SEM_ACORDO
    assert regras.etapa_do_parceiro(m, s, [recebida], HOJE) is EtapaDoParceiro.ATIVADO
    assert regras.etapa_do_parceiro(m, s, [recebida, proposta], HOJE) is EtapaDoParceiro.PRODUTIVO
    assert regras.etapa_do_parceiro(m, s, [velha], HOJE) is EtapaDoParceiro.DORMENTE
    assert regras.etapa_do_parceiro(m, s, [recusada], HOJE) is EtapaDoParceiro.MAPEADO  # recusada não conta
    assert regras.etapa_do_parceiro(EtapaDoParceiro.ESTRATEGICO, s, [velha], HOJE) is EtapaDoParceiro.ESTRATEGICO


def test_vinculo_de_12_meses_comeca_na_validacao():
    assert regras.vinculo_ate(indicacao()) is None
    assert regras.vinculo_ate(indicacao(indicacao_validada_em=date(2026, 2, 28))) == date(2027, 2, 28)
    assert regras.vinculo_ate(indicacao(indicacao_validada_em=date(2027, 2, 28))) == date(2028, 2, 28)


def test_fee_recorrente_e_o_primeiro_recebimento_desde_o_aceite_limitado_a_parcela():
    o = indicacao(situacao=Situacao.ACEITA, data_aceite=date(2026, 5, 20), preco_mensal=D("10000"))
    recebidos = [(date(2026, 4, 1), D("3000")), (date(2026, 6, 1), D("12000")), (date(2026, 7, 1), D("10000"))]
    [fee] = regras.calcular_fees(o, recebidos, set())
    assert (fee.regra, fee.competencia, fee.base, fee.calculado) == (
        RegraDoFee.PRIMEIRA_PARCELA, date(2026, 6, 1), D("12000"), D("10000"))
    assert regras.calcular_fees(o, recebidos, {date(2026, 6, 1)}) == []  # uma parcela só


def test_fee_nao_recorrente_e_10_por_cento_ate_o_valor_do_contrato():
    o = indicacao(situacao=Situacao.ACEITA, data_aceite=date(2026, 3, 10), preco_anual=D("110000"),
                  linha_servico=LinhaServico.C2)
    recebidos = [(date(2026, 3, 1), D("50000")), (date(2026, 4, 1), D("50000")), (date(2026, 5, 1), D("50000"))]
    fees = regras.calcular_fees(o, recebidos, {date(2026, 3, 1)})
    assert [(f.competencia, f.calculado) for f in fees] == [(date(2026, 4, 1), D("5000.00")), (date(2026, 5, 1), D("1000.00"))]


def test_sem_fee_fora_do_vinculo_recusada_ou_nao_fechada():
    fora = indicacao(situacao=Situacao.ACEITA, data_aceite=date(2027, 6, 1), preco_mensal=D("1000"),
                     indicacao_validada_em=date(2026, 1, 1))
    recusada = indicacao(situacao=Situacao.ACEITA, data_aceite=date(2026, 6, 1), preco_mensal=D("1000"),
                         indicacao_recusada=MotivoDeIndicacaoRecusada.EM_NEGOCIACAO)
    aberta = indicacao(preco_mensal=D("1000"))
    recebidos = [(date(2027, 6, 1), D("1000")), (date(2026, 6, 1), D("1000"))]
    for o in (fora, recusada, aberta):
        assert regras.calcular_fees(o, recebidos, set()) == []


# ------------------------------------------------------------------ API

@pytest.fixture
def base(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        comercial = Perfil(nome="Comercial", permissoes=["parceiros.ver", "parceiros.editar"])
        socio = Perfil(nome="Sócio", permissoes=["parceiros.ver", "parceiros.aprovar_fee"])
        s.add_all([comercial, socio])
        g1, g2 = GrupoEconomico(nome="Grupo Alfa"), GrupoEconomico(nome="Grupo Beta")
        s.add_all([g1, g2])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=comercial.id))
        s.add(Usuario(email="bruno@grupocriterio.com.br", perfil_id=socio.id))
        s.add(Oportunidade(grupo_id=g1.id, nome="BPO Alfa", situacao=Situacao.ACEITA, tipo_canal=TipoCanal.PARCEIROS,
                           canal="Molina", data_colocacao=date(2026, 4, 2), data_aceite=date(2026, 5, 20),
                           preco_mensal=D("12000"), linha_servico=LinhaServico.C1))
        s.add(Oportunidade(grupo_id=g2.id, nome="Contábil Beta", situacao=Situacao.PERDIDA,
                           tipo_canal=TipoCanal.PARCEIROS, canal="Molina", data_colocacao=date(2026, 7, 1)))
        s.add(Oportunidade(grupo_id=g2.id, nome="Consultoria Beta", situacao=Situacao.EM_AVALIACAO,
                           data_colocacao=date(2026, 9, 1)))
        imp = ImportacaoDeRecebimentos(arquivo="omie.xlsx", competencias=["2026-06"], linhas=1, total=D("12000"))
        s.add(imp)
        s.flush()
        s.add(Recebimento(importacao_id=imp.id, grupo_id=g1.id, competencia=date(2026, 6, 1), valor=D("12000")))
        s.commit()


@pytest.fixture
def cliente(engine, base, monkeypatch):
    monkeypatch.setattr("crm.api.parceiros._hoje", lambda: HOJE)
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


def _criar(cliente, nome="Molina", **extra):
    r = cliente.post("/api/parceiros", headers=ADMIN, json={"nome": nome, "tipo_pessoa": "PF", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_conferencia_liga_os_textos_antigos_e_o_funil_conta(cliente):
    molina = _criar(cliente, acordo="Informal, com fee", regra_combinada="1ª parcela, combinada por Eduardo",
                    documento="123.456.789-00")
    assert molina["documento"] == "12345678900"
    [texto] = cliente.get("/api/parceiros/conferencia", headers=ADMIN).json()
    assert (texto["texto"], texto["oportunidades"], texto["sugestao_id"]) == ("Molina", 2, molina["id"])

    detalhe = cliente.post("/api/parceiros/conferencia", headers=ADMIN,
                           json={"texto": "Molina", "parceiro_id": molina["id"]}).json()
    assert {i["nome"] for i in detalhe["indicacoes"]} == {"BPO Alfa", "Contábil Beta"}
    assert detalhe["etapa"] == "Produtivo"
    assert cliente.get("/api/parceiros/conferencia", headers=ADMIN).json() == []

    [linha] = cliente.get("/api/parceiros", headers=ADMIN, params={"hoje": "2026-10-19"}).json()
    assert (linha["etapa"], linha["indicacoes"], linha["fechadas"], linha["mrr"]) == ("Produtivo", 2, 1, "13000.00")

    ind = cliente.get("/api/parceiros/indicadores", headers=ADMIN, params={"hoje": "2026-10-19"}).json()
    assert (ind["ativos"], ind["indicacoes"], ind["conversao"], ind["mrr"], ind["sem_contrato"]) == (
        1, 2, "50.0", "13000.00", 1)
    comp = cliente.get("/api/parceiros/indicadores/composicao", headers=ADMIN,
                       params={"indicador": "mrr", "hoje": "2026-10-19"}).json()
    assert [(c["detalhe"], c["valor"]) for c in comp] == [("BPO Alfa", "13000.00")]


def test_periodo_pela_data_da_indicacao_ou_do_fechamento(cliente):
    molina = _criar(cliente)
    cliente.post("/api/parceiros/conferencia", headers=ADMIN, json={"texto": "Molina", "parceiro_id": molina["id"]})
    julho = {"data_de": "2026-07-01", "data_ate": "2026-07-31", "hoje": "2026-10-19"}
    assert cliente.get("/api/parceiros/indicadores", headers=ADMIN, params=julho).json()["indicacoes"] == 1
    maio = {"data_de": "2026-05-01", "data_ate": "2026-05-31", "data_tipo": "fechamento", "hoje": "2026-10-19"}
    ind = cliente.get("/api/parceiros/indicadores", headers=ADMIN, params=maio).json()
    assert (ind["indicacoes"], ind["mrr"]) == (1, "13000.00")


def test_ligar_indicacao_nova_e_nao_roubar_de_outro_parceiro(cliente):
    gaidao, guto = _criar(cliente, "Gaidão"), _criar(cliente, "Guto")
    [achada] = cliente.get("/api/parceiros/oportunidades", headers=ADMIN, params={"busca": "Consultoria"}).json()
    detalhe = cliente.post(f"/api/parceiros/{gaidao['id']}/indicacoes", headers=ADMIN,
                           json={"oportunidade_id": achada["id"], "recebida_em": "2026-09-01",
                                 "validada_em": "2026-09-03"}).json()
    [i] = detalhe["indicacoes"]
    assert (i["recebida_em"], i["vinculo_ate"], detalhe["etapa"]) == ("2026-09-01", "2027-09-03", "Produtivo")
    r = cliente.post(f"/api/parceiros/{guto['id']}/indicacoes", headers=ADMIN, json={"oportunidade_id": achada["id"]})
    assert r.status_code == 409 and "Gaidão" in r.json()["detail"]

    recusada = cliente.patch(f"/api/parceiros/indicacoes/{achada['id']}", headers=ADMIN,
                             json={"recusada": "Já é cliente"}).json()
    assert recusada["indicacoes"][0]["recusada"] == "Já é cliente" and recusada["etapa"] == "Mapeado"


def test_kanban_so_move_as_etapas_manuais(cliente):
    p = _criar(cliente, "Ficus")
    assert cliente.post(f"/api/parceiros/{p['id']}/etapa", headers=ADMIN, json={"etapa": "Qualificado"}).json()["etapa"] \
        == "Qualificado"
    r = cliente.post(f"/api/parceiros/{p['id']}/etapa", headers=ADMIN, json={"etapa": "Produtivo"})
    assert r.status_code == 422 and "muda sozinha" in r.json()["detail"]
    cliente.patch(f"/api/parceiros/{p['id']}", headers=ADMIN, json={"acordo": "Contrato assinado"})
    r = cliente.post(f"/api/parceiros/{p['id']}/etapa", headers=ADMIN, json={"etapa": "Mapeado"})
    assert r.status_code == 409 and "Formalizado" in r.json()["detail"]


def test_fee_calculado_e_so_o_socio_aprova_e_paga(cliente):
    molina = _criar(cliente)
    cliente.post("/api/parceiros/conferencia", headers=ADMIN, json={"texto": "Molina", "parceiro_id": molina["id"]})
    assert cliente.post("/api/parceiros/fees/calcular", headers=KARINE).json() == {"novos": 1}
    assert cliente.post("/api/parceiros/fees/calcular", headers=KARINE).json() == {"novos": 0}  # não repete
    [fee] = cliente.get("/api/parceiros/fees", headers=KARINE).json()
    assert (fee["regra"], fee["competencia"], fee["calculado"], fee["situacao"]) == (
        "Recorrente: 1ª parcela líquida", "2026-06-01", "12000.00", "A aprovar")
    ind = cliente.get("/api/parceiros/indicadores", headers=KARINE).json()
    assert (ind["fees"], ind["fees_quantos"]) == ("12000.00", 1)

    assert cliente.post(f"/api/parceiros/fees/{fee['id']}/aprovar", headers=KARINE, json={"valor": "10500"}).status_code == 403
    assert cliente.post(f"/api/parceiros/fees/{fee['id']}/pago", headers=SOCIO, json={"pago_em": "2026-10-20"}).status_code == 409
    aprovado = cliente.post(f"/api/parceiros/fees/{fee['id']}/aprovar", headers=SOCIO, json={"valor": "10500"}).json()
    assert (aprovado["situacao"], aprovado["valor_aprovado"], aprovado["decidido_por"]) == (
        "Aprovado, a pagar", "10500.00", "Bruno")
    pago = cliente.post(f"/api/parceiros/fees/{fee['id']}/pago", headers=SOCIO, json={"pago_em": "2026-10-20"}).json()
    assert (pago["situacao"], pago["pago_em"]) == ("Pago", "2026-10-20")
    oportunidade = fee["oportunidade_id"]
    r = cliente.post(f"/api/parceiros/indicacoes/{oportunidade}/desligar", headers=ADMIN)
    assert r.status_code == 409  # o fee guarda o vínculo


def test_acesso_e_nome_unico_e_exportacao(cliente):
    _criar(cliente)
    assert cliente.post("/api/parceiros", headers=ADMIN, json={"nome": "molina"}).status_code == 409
    assert cliente.post("/api/parceiros", headers=SOCIO, json={"nome": "Outro"}).status_code == 403
    assert cliente.get("/api/parceiros/exportar", headers=KARINE).status_code == 403
    r = cliente.get("/api/parceiros/exportar", headers=ADMIN)
    assert r.status_code == 200 and r.content[:2] == b"PK"
