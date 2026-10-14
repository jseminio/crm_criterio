"""Tabela de serviços e o tipo do contrato (aprovado por Eduardo em 13/10/2026).

O tipo sai do serviço e é a sugestão na conversão; o modelo e o reajuste se escolhem por serviço; o reajuste do
serviço chega à tabela do reajuste de julho; os contratos de antes ganham o tipo pela tarefa de manutenção.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import Contrato, ContratoDoServico, GrupoEconomico, IpcaDoMes, Oportunidade, Perfil, Usuario
from crm.domain import contrato_do_servico as regra
from crm.domain.listas import LinhaServico, Situacao, SituacaoContrato
from crm.manutencao.tarefas import tipo_dos_contratos

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        contratos = Perfil(nome="Contratos", permissoes=["contratos.ver", "funil.ver", "funil.converter"])
        g = GrupoEconomico(nome="Cliente A")
        s.add_all([contratos, g])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=contratos.id))
        bpo = Oportunidade(grupo_id=g.id, nome="BPO", servico="BPO Financeiro", situacao=Situacao.ACEITA, preco_mensal=D("7000"))
        outro = Oportunidade(grupo_id=g.id, nome="Outro", servico="Outro", servico_descricao="Um serviço que o lead pediu",
                             situacao=Situacao.ACEITA, preco_anual=D("30000"))
        fscp = Oportunidade(grupo_id=g.id, nome="FSCP", servico="FSCP", situacao=Situacao.ACEITA, preco_anual=D("40000"))
        s.add_all([bpo, outro, fscp])
        s.commit()
        return {"bpo": bpo.id, "outro": outro.id, "fscp": fscp.id, "grupo": g.id}


@pytest.fixture
def cliente(engine, ids):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar, buscar_ipca=lambda de, ate: {})) as c:
        yield c


# ── Regra ──────────────────────────────────────────────────────────────────────────────────────────

def test_padrao_e_validacao_por_tipo():
    assert regra.padrao(LinhaServico.C1) == (regra.ModeloDeContrato.RECORRENTE_PADRAO, regra.ReajusteDoServico.IPCA_EM_JULHO)
    assert regra.padrao(LinhaServico.C2) == (regra.ModeloDeContrato.NAO_RECORRENTE_V1_1, regra.ReajusteDoServico.CASO_A_CASO)
    with pytest.raises(regra.ErroNoServico):
        regra.validar(LinhaServico.C1, regra.ModeloDeContrato.NAO_RECORRENTE_V1_1, regra.ReajusteDoServico.IPCA_EM_JULHO)
    with pytest.raises(regra.ErroNoServico):  # não recorrente nunca reajusta sozinho
        regra.validar(LinhaServico.C2, regra.ModeloDeContrato.NAO_RECORRENTE_V1_1, regra.ReajusteDoServico.IPCA_EM_JULHO)


# ── Tabela ─────────────────────────────────────────────────────────────────────────────────────────

def test_tabela_lista_o_catalogo_com_tipo_parcelas_modelo_e_reajuste(cliente):
    linhas = {l["servico"]: l for l in cliente.get("/api/servicos/contratos", headers=ADMIN).json()}
    assert len(linhas) == 12
    assert "CFO as a Service" not in linhas and "BPO Plus" not in linhas  # esperam a Descoberta do Cliente
    bpo = linhas["BPO Financeiro"]
    assert (bpo["tipo"], bpo["parcelas"], bpo["modelo"], bpo["reajuste"]) == ("Recorrente", 13, "Recorrente padrão", "IPCA em julho")
    assert bpo["situacao_do_modelo"] == "aguardando arquivo" and bpo["padrao"] is True
    assert linhas["Endereço Fiscal"]["parcelas"] == 13 and linhas["Representante Legal"]["parcelas"] == 13
    consultoria = linhas["Consultoria"]
    assert (consultoria["tipo"], consultoria["temas"], consultoria["reajuste"]) == ("Não recorrente", 6, "Caso a caso")
    assert consultoria["reajustes_possiveis"] == ["Caso a caso", "Sem reajuste"]


def test_gravar_escolha_e_voltar_ao_padrao_apaga(cliente, engine):
    escolha = {"servico": "Endereço Fiscal", "modelo": "Recorrente padrão", "reajuste": "Sem reajuste"}
    linhas = {l["servico"]: l for l in cliente.put("/api/servicos/contratos", json={"itens": [escolha]}, headers=ADMIN).json()}
    assert linhas["Endereço Fiscal"]["reajuste"] == "Sem reajuste" and linhas["Endereço Fiscal"]["padrao"] is False
    with Session(engine) as s:
        assert s.get(ContratoDoServico, "Endereço Fiscal").reajuste == "Sem reajuste"
    cliente.put("/api/servicos/contratos", json={"itens": [{**escolha, "reajuste": "IPCA em julho"}]}, headers=ADMIN)
    with Session(engine) as s:
        assert s.get(ContratoDoServico, "Endereço Fiscal") is None


def test_gravar_recusa_modelo_de_outro_tipo_e_servico_fora_do_catalogo(cliente):
    r = cliente.put("/api/servicos/contratos", headers=ADMIN, json={"itens": [
        {"servico": "BPO Financeiro", "modelo": "Não recorrente v1.1", "reajuste": "Caso a caso"}]})
    assert r.status_code == 422 and "BPO Financeiro" in r.json()["detail"]
    r = cliente.put("/api/servicos/contratos", headers=ADMIN, json={"itens": [
        {"servico": "CFO as a Service", "modelo": "Recorrente padrão", "reajuste": "IPCA em julho"}]})
    assert r.status_code == 422


def test_quem_ve_contratos_le_mas_nao_grava(cliente):
    assert cliente.get("/api/servicos/contratos", headers=KARINE).status_code == 200
    r = cliente.put("/api/servicos/contratos", headers=KARINE, json={"itens": [
        {"servico": "Endereço Fiscal", "modelo": "Recorrente padrão", "reajuste": "Sem reajuste"}]})
    assert r.status_code == 403


# ── Conversão ──────────────────────────────────────────────────────────────────────────────────────

def test_conversao_usa_o_tipo_do_servico_como_sugestao(cliente, ids):
    r = cliente.post(f"/api/oportunidades/{ids['bpo']}/converter-em-contrato", json={}, headers=ADMIN)
    assert r.status_code == 201 and r.json()["recorrente"] is True
    r = cliente.post(f"/api/oportunidades/{ids['fscp']}/converter-em-contrato", json={}, headers=ADMIN)
    assert r.status_code == 201 and r.json()["recorrente"] is False


def test_conversao_aceita_a_troca_e_exige_resposta_quando_o_servico_nao_define(cliente, ids):
    r = cliente.post(f"/api/oportunidades/{ids['outro']}/converter-em-contrato", json={}, headers=ADMIN)
    assert r.status_code == 422 and "recorrente" in r.json()["detail"]
    r = cliente.post(f"/api/oportunidades/{ids['outro']}/converter-em-contrato", json={"recorrente": False}, headers=ADMIN)
    assert r.status_code == 201 and r.json()["recorrente"] is False


# ── Reajuste ───────────────────────────────────────────────────────────────────────────────────────

def test_reajuste_do_servico_chega_a_tabela_de_julho(cliente, engine, ids):
    with Session(engine) as s:
        s.add(Contrato(grupo_id=ids["grupo"], oportunidade_id=ids["bpo"], recorrente=True, situacao=SituacaoContrato.ATIVO,
                       preco_mensal=D("7000"), data_inicio=date(2026, 7, 5)))
        s.add_all(IpcaDoMes(mes=date(2026 + (m > 12), (m - 1) % 12 + 1, 1), variacao=D("0.5")) for m in range(7, 19))
        s.commit()

    def situacao():
        tabela = cliente.get("/api/reajustes", params={"ano": 2027, "hoje": "2027-07-15"}, headers=ADMIN).json()
        return tabela["linhas"][0]["situacao"]

    assert situacao() == "Reajustar"
    cliente.put("/api/servicos/contratos", headers=ADMIN, json={"itens": [
        {"servico": "BPO Financeiro", "modelo": "Recorrente padrão", "reajuste": "Caso a caso"}]})
    assert situacao() == "Você decide"
    cliente.put("/api/servicos/contratos", headers=ADMIN, json={"itens": [
        {"servico": "BPO Financeiro", "modelo": "Recorrente padrão", "reajuste": "Sem reajuste"}]})
    assert situacao() == "Sem reajuste"


# ── Tarefa de manutenção ───────────────────────────────────────────────────────────────────────────

def test_tarefa_preenche_o_tipo_dos_contratos_de_antes(sessao: Session):
    g = GrupoEconomico(nome="Antigo")
    sessao.add(g)
    sessao.flush()
    op = Oportunidade(grupo_id=g.id, nome="x", servico="Consultoria", situacao=Situacao.ACEITA)
    sessao.add(op)
    sessao.flush()
    pelo_servico = Contrato(grupo_id=g.id, oportunidade_id=op.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("1"))
    pelo_escopo = Contrato(grupo_id=g.id, escopo="BPO Financeiro", situacao=SituacaoContrato.ATIVO)
    pelo_preco = Contrato(grupo_id=g.id, escopo="Contábil", situacao=SituacaoContrato.ATIVO, preco_mensal=D("3000"))
    so_total = Contrato(grupo_id=g.id, escopo="Projeto", situacao=SituacaoContrato.ATIVO, preco_anual=D("9000"))
    sem_nada = Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO)
    ja_tem = Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO, preco_mensal=D("1"), recorrente=False)
    sessao.add_all([pelo_servico, pelo_escopo, pelo_preco, so_total, sem_nada, ja_tem])
    sessao.flush()

    relato = tipo_dos_contratos.executar(sessao)

    assert pelo_servico.recorrente is False  # Consultoria é não recorrente, mesmo com mensal
    assert pelo_escopo.recorrente is True and pelo_preco.recorrente is True and so_total.recorrente is False
    assert sem_nada.recorrente is None and ja_tem.recorrente is False
    assert "5 contrato(s) sem tipo" in relato
    assert tipo_dos_contratos.executar(sessao).startswith("1 contrato(s) sem tipo")  # só o sem dado continua vazio
