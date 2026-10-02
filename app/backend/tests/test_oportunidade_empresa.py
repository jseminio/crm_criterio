"""Oportunidade ligada a uma empresa já cadastrada; o grupo vem dela. Nome e empresa
editáveis depois, com trava para quem já virou contrato. Pedido de Karine em 01/10/2026."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import Empresa, GrupoEconomico, Oportunidade
from crm.domain.listas import Situacao, SituacaoGrupo

CNPJ_A, CNPJ_B = "11222333000181", "11444777000161"


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


@pytest.fixture
def base(sessao: Session) -> dict:
    delta = GrupoEconomico(nome="Grupo Delta", situacao=SituacaoGrupo.PROSPECT)
    alfa = GrupoEconomico(nome="Grupo Alfa", situacao=SituacaoGrupo.CLIENTE)
    sessao.add_all([delta, alfa]); sessao.flush()
    e1 = Empresa(grupo_id=delta.id, razao_social="Delta Engenharia Ltda", nome_fantasia="Delta", cnpj=CNPJ_A)
    e2 = Empresa(grupo_id=alfa.id, razao_social="Alfa Comércio SA", cnpj=CNPJ_B)
    sessao.add_all([e1, e2]); sessao.commit()
    return {"delta": delta.id, "alfa": alfa.id, "e1": e1.id, "e2": e2.id}


class TestBuscaDeEmpresas:
    @pytest.mark.parametrize("busca", ["delta", "DELTA ENGENHARIA", "11.222", "11222333", "grupo delta"])
    def test_por_nome_razao_social_cnpj_ou_grupo(self, cliente, base, busca):
        achadas = cliente.get("/api/empresas/busca", params={"busca": busca}).json()
        assert [a["razao_social"] for a in achadas] == ["Delta Engenharia Ltda"]
        assert achadas[0]["grupo_nome"] == "Grupo Delta" and achadas[0]["tipo"] == "prospect"

    def test_em_branco_lista_as_empresas(self, cliente, base):
        nomes = [a["razao_social"] for a in cliente.get("/api/empresas/busca").json()]
        assert nomes == ["Alfa Comércio SA", "Delta Engenharia Ltda"]


class TestCriacaoComEmpresa:
    def test_a_empresa_define_o_grupo(self, cliente, base):
        r = cliente.post("/api/oportunidades", json={
            "nome": "BPO Financeiro — Delta", "empresa_id": base["e1"], "nome_do_grupo": "Outro grupo",
        })
        assert r.status_code == 201, r.text
        o = r.json()
        assert (o["empresa_id"], o["grupo_id"], o["grupo_nome"]) == (base["e1"], base["delta"], "Grupo Delta")
        assert (o["empresa_razao_social"], o["empresa_cnpj"]) == ("Delta Engenharia Ltda", CNPJ_A)

    def test_empresa_inexistente_e_404(self, cliente, base):
        assert cliente.post("/api/oportunidades", json={"nome": "X", "empresa_id": 9999}).status_code == 404


class TestEdicaoDeNomeEEmpresa:
    def _nova(self, cliente, base) -> int:
        return cliente.post("/api/oportunidades", json={"nome": "Delta", "empresa_id": base["e1"]}).json()["id"]

    def test_edita_o_nome(self, cliente, base):
        oid = self._nova(cliente, base)
        r = cliente.patch(f"/api/oportunidades/{oid}", json={"nome": "  BPO   Contábil — Delta "})
        assert r.status_code == 200 and r.json()["nome"] == "BPO Contábil — Delta"
        assert cliente.patch(f"/api/oportunidades/{oid}", json={"nome": ""}).status_code == 422

    def test_trocar_a_empresa_leva_o_grupo(self, cliente, base):
        oid = self._nova(cliente, base)
        o = cliente.patch(f"/api/oportunidades/{oid}", json={"empresa_id": base["e2"]}).json()
        assert (o["empresa_id"], o["grupo_id"], o["grupo_nome"]) == (base["e2"], base["alfa"], "Grupo Alfa")
        assert cliente.patch(f"/api/oportunidades/{oid}", json={"empresa_id": 9999}).status_code == 404
        assert cliente.patch(f"/api/oportunidades/{oid}", json={"empresa_id": None}).status_code == 422

    def test_quem_virou_contrato_nao_troca_de_empresa(self, cliente, base):
        oid = self._nova(cliente, base)
        assert cliente.patch(f"/api/oportunidades/{oid}", json={"situacao": "Aceita", "data_aceite": "2026-09-01"}).status_code == 200
        contrato = cliente.post(f"/api/oportunidades/{oid}/converter-em-contrato", json={})
        assert contrato.status_code in (200, 201), contrato.text
        assert contrato.json().get("empresa_id", base["e1"]) == base["e1"]  # o contrato nasce com a empresa
        detalhe = cliente.get(f"/api/oportunidades/{oid}").json()
        assert detalhe["tem_contrato"] is True
        r = cliente.patch(f"/api/oportunidades/{oid}", json={"empresa_id": base["e2"]})
        assert r.status_code == 409 and "contrato" in r.json()["detail"]
        # salvar a mesma empresa (a tela manda o rascunho inteiro) não é troca
        assert cliente.patch(f"/api/oportunidades/{oid}", json={"empresa_id": base["e1"], "nome": "Delta 2"}).status_code == 200

    def test_excluir_a_empresa_deixa_a_oportunidade_sem_empresa(self, cliente, base, sessao):
        oid = self._nova(cliente, base)
        assert cliente.delete(f"/api/empresas/{base['e1']}").status_code == 204
        o = cliente.get(f"/api/oportunidades/{oid}").json()
        assert o["empresa_id"] is None and o["grupo_id"] == base["delta"]
