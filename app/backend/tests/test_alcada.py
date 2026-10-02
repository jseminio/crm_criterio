"""Alçada dos eventos de contrato (decisões de Eduardo em 02/10/2026): acima de 10% de redução, ou
aditivo que muda o escopo, o evento espera quem aprova."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal as D

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.domain.alcada import motivo_da_alcada
from crm.domain.listas import SituacaoContrato
from crm.domain.listas import TipoDeEventoDeContrato as T
from crm.db.modelos import Contrato, EventoDeContrato, GrupoEconomico, PedidoDeAprovacao, Perfil, Usuario


@dataclass
class C:
    escopo: str | None = "BPO Contábil"
    preco_mensal: D | None = D("4800.00")
    preco_anual: D | None = None


class TestRegra:
    def test_contracao_ate_10_por_cento_entra_direto(self):
        assert motivo_da_alcada(C(), T.CONTRACAO, {"preco_mensal": D("4320.00")}) is None  # exatos 10%

    def test_contracao_acima_de_10_por_cento_pede_aprovacao(self):
        assert motivo_da_alcada(C(), T.CONTRACAO, {"preco_mensal": D("3900.00")}) == "redução de 18,8% no preço mensal"

    def test_reajuste_para_baixo_conta_e_para_cima_nao(self):
        assert motivo_da_alcada(C(), T.REAJUSTE, {"preco_mensal": D("4000.00")}) == "redução de 16,7% no preço mensal"
        assert motivo_da_alcada(C(), T.REAJUSTE, {"preco_mensal": D("9000.00")}) is None

    def test_aditivo_que_muda_o_escopo_pede_aprovacao(self):
        assert motivo_da_alcada(C(), T.ADITIVO, {"escopo": "BPO Full"}) == "aditivo que muda o escopo"
        assert motivo_da_alcada(C(), T.ADITIVO, {}) is None
        assert motivo_da_alcada(C(), T.ADITIVO, {"escopo": "BPO Full", "preco_mensal": D("3000")}) == (
            "aditivo que muda o escopo; redução de 37,5% no preço mensal")

    def test_preco_anual_tambem_conta(self):
        assert motivo_da_alcada(C(preco_anual=D("12000")), T.CONTRACAO, {"preco_anual": D("10000")}) == (
            "redução de 16,7% no preço anual")

    @pytest.mark.parametrize("tipo", [T.EXPANSAO, T.RENOVACAO, T.CORRECAO, T.ENCERRAMENTO])
    def test_outros_tipos_entram_direto(self, tipo):
        assert motivo_da_alcada(C(), tipo, {"preco_mensal": D("100")}) is None

    def test_sem_preco_atual_nao_ha_reducao(self):
        assert motivo_da_alcada(C(preco_mensal=None), T.CONTRACAO, {"preco_mensal": D("100")}) is None


# ------------------------------------------------------------------ pela API

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine Nascimento"}


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


@pytest.fixture
def contrato(engine) -> int:
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        cs = Perfil(nome="Contratos", permissoes=["contratos.ver", "contratos.eventos"])
        s.add(cs)
        g = GrupoEconomico(nome="Gama Comércio")
        s.add(g)
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=cs.id))
        c = Contrato(grupo_id=g.id, escopo="BPO Contábil", preco_mensal=D("4800.00"), data_inicio=date(2026, 3, 1),
                     situacao=SituacaoContrato.ATIVO)
        s.add(c)
        s.commit()
        return c.id


@pytest.fixture
def cliente(engine, contrato):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar)) as c:
        yield c


CONTRACAO = {"tipo": "Contração", "preco_mensal_novo": "3900.00", "descricao": "reduziu o DP", "data_do_evento": "2026-10-01"}


def test_acima_da_alcada_espera_aprovacao_e_o_contrato_nao_muda(cliente, contrato, engine):
    r = cliente.post(f"/api/contratos/{contrato}/eventos", headers=KARINE, json=CONTRACAO)
    assert r.status_code == 202, r.text
    d = r.json()
    assert d["preco_mensal"] == "4800.00" and d["eventos"] == []
    p = d["aprovacao_pendente"]
    assert (p["motivo"], p["pedido_por"], p["situacao"]) == ("redução de 18,8% no preço mensal", "Karine Nascimento", "Aguardando")
    assert (p["preco_mensal_anterior"], p["preco_mensal_novo"]) == ("4800.00", "3900.00")

    # Enquanto espera, o contrato não recebe outro evento; e quem não aprova não vê a fila.
    outro = cliente.post(f"/api/contratos/{contrato}/eventos", headers=KARINE, json={"tipo": "Expansão", "preco_mensal_novo": "5000"})
    assert outro.status_code == 409 and "aguardando aprovação" in outro.json()["detail"]
    assert cliente.get("/api/aprovacoes", headers=KARINE).status_code == 403

    fila = cliente.get("/api/aprovacoes", headers=ADMIN).json()
    assert [(x["grupo_nome"], x["tipo"]) for x in fila] == [("Gama Comércio", "Contração")]
    aprovado = cliente.post(f"/api/aprovacoes/{fila[0]['id']}/aprovar", headers=ADMIN)
    assert aprovado.status_code == 200 and aprovado.json()["decidido_por"] == "Eduardo Luiz"

    d = cliente.get(f"/api/contratos/{contrato}", headers=ADMIN).json()
    assert d["preco_mensal"] == "3900.00" and d["aprovacao_pendente"] is None
    ev = d["eventos"][0]
    assert (ev["tipo"], ev["data_do_evento"], ev["preco_mensal_anterior"], ev["preco_mensal_novo"]) == (
        "Contração", "2026-10-01", "4800.00", "3900.00")
    with Session(engine) as s:
        p = s.scalar(sa.select(PedidoDeAprovacao))
        assert p.evento_id == s.scalar(sa.select(EventoDeContrato.id))
    assert cliente.post(f"/api/aprovacoes/{fila[0]['id']}/recusar", headers=ADMIN, json={"motivo": "tarde"}).status_code == 409


def test_recusar_guarda_o_porque_e_libera_o_contrato(cliente, contrato):
    cliente.post(f"/api/contratos/{contrato}/eventos", headers=KARINE,
                 json={"tipo": "Aditivo", "descricao": "inclui BPO Financeiro", "escopo_novo": "BPO Full"})
    pid = cliente.get("/api/aprovacoes", headers=ADMIN).json()[0]["id"]
    assert cliente.post(f"/api/aprovacoes/{pid}/recusar", headers=ADMIN, json={"motivo": ""}).status_code == 422
    r = cliente.post(f"/api/aprovacoes/{pid}/recusar", headers=ADMIN, json={"motivo": "escopo ainda em negociação"})
    assert r.json()["situacao"] == "Recusado" and r.json()["motivo_da_recusa"] == "escopo ainda em negociação"
    d = cliente.get(f"/api/contratos/{contrato}", headers=ADMIN).json()
    assert d["escopo"] == "BPO Contábil" and d["aprovacao_pendente"] is None and d["eventos"] == []
    assert [x["id"] for x in cliente.get("/api/aprovacoes", headers=ADMIN, params={"situacao": "Recusado"}).json()] == [pid]


def test_dentro_da_alcada_ou_para_quem_aprova_entra_direto(cliente, contrato):
    r = cliente.post(f"/api/contratos/{contrato}/eventos", headers=KARINE, json={"tipo": "Contração", "preco_mensal_novo": "4500.00"})
    assert r.status_code == 201 and r.json()["preco_mensal"] == "4500.00"
    r = cliente.post(f"/api/contratos/{contrato}/eventos", headers=ADMIN, json={"tipo": "Contração", "preco_mensal_novo": "2000.00"})
    assert r.status_code == 201 and r.json()["preco_mensal"] == "2000.00"
    assert cliente.get("/api/aprovacoes", headers=ADMIN).json() == []


def test_aprovar_revalida_contra_o_contrato_de_agora(cliente, contrato, engine):
    cliente.post(f"/api/contratos/{contrato}/eventos", headers=KARINE, json=CONTRACAO)
    with Session(engine) as s:
        s.get(Contrato, contrato).situacao = SituacaoContrato.ENCERRADO
        s.commit()
    pid = cliente.get("/api/aprovacoes", headers=ADMIN).json()[0]["id"]
    r = cliente.post(f"/api/aprovacoes/{pid}/aprovar", headers=ADMIN)
    assert r.status_code == 409 and "encerrado" in r.json()["detail"]
    assert cliente.get("/api/aprovacoes", headers=ADMIN).json()[0]["situacao"] == "Aguardando"


def test_sem_login_nao_ha_alcada(engine, contrato):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        r = c.post(f"/api/contratos/{contrato}/eventos", json=CONTRACAO)
        assert r.status_code == 201 and r.json()["preco_mensal"] == "3900.00"
