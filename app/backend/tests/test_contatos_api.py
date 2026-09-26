"""Área de Contatos: clientes e prospects segregados, busca por empresa e por pessoa."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import Contrato, Empresa, GrupoEconomico, Oportunidade, PessoaContato
from crm.domain.listas import Situacao, SituacaoContrato, SituacaoGrupo

CNPJ_A, CNPJ_B = "11222333000181", "11444777000161"


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


@pytest.fixture
def base(sessao: Session) -> dict:
    """Um cliente com duas empresas, um prospect sem empresa e um prospect com empresa."""
    alfa = GrupoEconomico(nome="Grupo Alfa", situacao=SituacaoGrupo.CLIENTE)
    pros = GrupoEconomico(nome="Ação Consultoria", situacao=SituacaoGrupo.PROSPECT)
    pro2 = GrupoEconomico(nome="Beta Prospect", situacao=SituacaoGrupo.PROSPECT)
    fund = GrupoEconomico(nome="Grupo Fundido", situacao=SituacaoGrupo.CLIENTE)
    sessao.add_all([alfa, pros, pro2, fund]); sessao.flush()
    fund.fundido_em_id = alfa.id
    e1 = Empresa(grupo_id=alfa.id, razao_social="Alfa Comércio Ltda", cnpj=CNPJ_A, municipio="Rio de Janeiro", uf="RJ",
                 logradouro="Rua Ação", cep="20040020")
    e2 = Empresa(grupo_id=alfa.id, razao_social="Alfa Serviços SA", cnpj=CNPJ_B)
    e3 = Empresa(grupo_id=pro2.id, razao_social="Beta Ltda")
    sessao.add_all([e1, e2, e3]); sessao.flush()
    sessao.add(Contrato(grupo_id=alfa.id, empresa_id=e1.id, situacao=SituacaoContrato.ATIVO, preco_mensal=Decimal("1500.00"), anterior_ao_crm=True))
    sessao.add(Oportunidade(grupo_id=pros.id, nome="Proposta", situacao=Situacao.ENVIAR_PROPOSTA))
    sessao.add_all([
        PessoaContato(nome="Maria Silva", email="maria@alfa.com", telefone="(21) 99999-0000", empresa_id=e1.id, cargo="Sócia"),
        PessoaContato(nome="João do Grupo", email="joao@alfa.com", grupo_id=alfa.id),
        PessoaContato(nome="Bia Prospect", email="bia@acao.com", grupo_id=pros.id),
    ])
    sessao.commit()
    return {"alfa": alfa.id, "pros": pros.id, "pro2": pro2.id, "e1": e1.id, "e2": e2.id, "e3": e3.id}


class TestSegregacao:
    def test_clientes_e_prospects_nao_se_misturam(self, cliente, base):
        c = cliente.get("/api/contatos/empresas", params={"tipo": "cliente"}).json()
        p = cliente.get("/api/contatos/empresas", params={"tipo": "prospect"}).json()
        assert {i["razao_social"] for i in c["itens"]} == {"Alfa Comércio Ltda", "Alfa Serviços SA"}
        assert {i["grupo_nome"] for i in p["itens"]} == {"Ação Consultoria", "Beta Prospect"}
        assert all(i["tipo"] == "cliente" for i in c["itens"]) and all(i["tipo"] == "prospect" for i in p["itens"])

    def test_grupo_fundido_nao_aparece(self, cliente, base):
        nomes = {i["grupo_nome"] for i in cliente.get("/api/contatos/empresas", params={"tipo": "cliente"}).json()["itens"]}
        assert "Grupo Fundido" not in nomes

    def test_prospect_sem_empresa_e_uma_entidade_do_grupo(self, cliente, base):
        p = cliente.get("/api/contatos/empresas", params={"tipo": "prospect", "busca": "acao"}).json()["itens"][0]
        assert p["empresa_id"] is None and p["propostas"] == 1 and p["contatos"][0]["nome"] == "Bia Prospect"

    def test_tipo_invalido_e_422(self, cliente):
        assert cliente.get("/api/contatos/empresas", params={"tipo": "todos"}).status_code == 422


class TestBuscaPorEmpresa:
    @pytest.mark.parametrize("busca,esperado", [
        ("alfa", {"Alfa Comércio Ltda", "Alfa Serviços SA"}),
        ("COMERCIO", {"Alfa Comércio Ltda"}),      # sem acento e sem caixa
        ("11.222.333", {"Alfa Comércio Ltda"}),    # CNPJ com pontuação
        ("grupo alfa", {"Alfa Comércio Ltda", "Alfa Serviços SA"}),   # nome do grupo
        ("zzz", set()),
    ])
    def test_por_razao_social_cnpj_ou_grupo(self, cliente, base, busca, esperado):
        r = cliente.get("/api/contatos/empresas", params={"tipo": "cliente", "busca": busca}).json()
        assert {i["razao_social"] for i in r["itens"]} == esperado and r["total"] == len(esperado)

    def test_mostra_a_mensalidade_do_cliente(self, cliente, base):
        e = next(i for i in cliente.get("/api/contatos/empresas", params={"tipo": "cliente", "busca": "comercio"}).json()["itens"])
        assert e["mensalidade"] == "1500.00"

    def test_contato_do_grupo_aparece_nas_empresas_e_e_marcado(self, cliente, base):
        e = next(i for i in cliente.get("/api/contatos/empresas", params={"tipo": "cliente", "busca": "servicos"}).json()["itens"])
        assert [(c["nome"], c["do_grupo"]) for c in e["contatos"]] == [("João do Grupo", True)]

    def test_lacunas_e_filtro_so_com_lacunas(self, cliente, base):
        itens = {i["razao_social"]: i for i in cliente.get("/api/contatos/empresas", params={"tipo": "cliente"}).json()["itens"]}
        assert "Telefone" not in itens["Alfa Comércio Ltda"]["lacunas"]     # Maria tem telefone
        assert "Logradouro" in itens["Alfa Serviços SA"]["lacunas"]
        so = cliente.get("/api/contatos/empresas", params={"tipo": "cliente", "so_com_lacunas": True}).json()
        assert {i["razao_social"] for i in so["itens"]} >= {"Alfa Serviços SA"}

    def test_paginacao(self, cliente, base):
        r = cliente.get("/api/contatos/empresas", params={"tipo": "cliente", "limite": 1, "salto": 1}).json()
        assert r["total"] == 2 and len(r["itens"]) == 1


class TestBuscaPorPessoa:
    def test_acha_por_nome_email_telefone_e_cargo(self, cliente, base):
        for busca in ("maria", "MARIA@ALFA", "99999", "socia"):
            r = cliente.get("/api/contatos/pessoas", params={"tipo": "cliente", "busca": busca}).json()
            assert [i["nome"] for i in r["itens"]] == ["Maria Silva"], busca

    def test_segrega_pessoa_de_cliente_e_de_prospect(self, cliente, base):
        c = cliente.get("/api/contatos/pessoas", params={"tipo": "cliente"}).json()["itens"]
        p = cliente.get("/api/contatos/pessoas", params={"tipo": "prospect"}).json()["itens"]
        assert {i["nome"] for i in c} == {"Maria Silva", "João do Grupo"} and {i["nome"] for i in p} == {"Bia Prospect"}

    def test_devolve_a_empresa_e_o_grupo_da_pessoa(self, cliente, base):
        maria = cliente.get("/api/contatos/pessoas", params={"tipo": "cliente", "busca": "maria"}).json()["itens"][0]
        assert (maria["grupo_nome"], maria["razao_social"]) == ("Grupo Alfa", "Alfa Comércio Ltda")
        joao = cliente.get("/api/contatos/pessoas", params={"tipo": "cliente", "busca": "joao"}).json()["itens"][0]
        assert (joao["grupo_nome"], joao["razao_social"]) == ("Grupo Alfa", None)


class TestPessoas:
    def test_cria_contato_de_empresa_e_valida_email(self, cliente, base):
        r = cliente.post("/api/contatos/pessoas", json={"nome": "  Ana   Costa ", "email": "ANA@X.com", "empresa_id": base["e2"], "papel": "Decisor"})
        assert r.status_code == 201 and (r.json()["nome"], r.json()["email"], r.json()["papel"]) == ("Ana Costa", "ana@x.com", "Decisor")
        assert cliente.post("/api/contatos/pessoas", json={"nome": "X", "email": "sem-arroba", "empresa_id": base["e2"]}).status_code == 422

    def test_exige_empresa_ou_grupo_mas_nao_os_dois(self, cliente, base):
        assert cliente.post("/api/contatos/pessoas", json={"nome": "X"}).status_code == 422
        assert cliente.post("/api/contatos/pessoas", json={"nome": "X", "empresa_id": base["e1"], "grupo_id": base["alfa"]}).status_code == 422
        assert cliente.post("/api/contatos/pessoas", json={"nome": "X", "empresa_id": 9999}).status_code == 404

    def test_edita_e_marca_nao_contatar_com_a_data(self, cliente, base):
        pid = cliente.get("/api/contatos/pessoas", params={"tipo": "cliente", "busca": "maria"}).json()["itens"][0]["id"]
        r = cliente.patch(f"/api/contatos/pessoas/{pid}", json={"telefone": "21 88888-0000", "nao_contatar": True})
        assert r.status_code == 200 and r.json()["nao_contatar"] is True and r.json()["telefone"] == "21 88888-0000"
        assert cliente.patch(f"/api/contatos/pessoas/{pid}", json={"nome": "  "}).status_code == 422
        assert cliente.patch("/api/contatos/pessoas/9999", json={}).status_code == 404

    def test_o_contato_novo_tira_a_lacuna(self, cliente, base):
        antes = next(i for i in cliente.get("/api/contatos/empresas", params={"tipo": "prospect", "busca": "beta"}).json()["itens"])
        assert "Contato" in antes["lacunas"]
        cliente.post("/api/contatos/pessoas", json={"nome": "Carla", "email": "c@b.com", "telefone": "2199", "empresa_id": antes["empresa_id"]})
        depois = next(i for i in cliente.get("/api/contatos/empresas", params={"tipo": "prospect", "busca": "beta"}).json()["itens"])
        assert not {"Contato", "E-mail", "Telefone"} & set(depois["lacunas"])


class TestEmpresa:
    def test_edita_endereco_com_validacao(self, cliente, base):
        r = cliente.patch(f"/api/empresas/{base['e2']}", json={"logradouro": " Rua  Nova ", "uf": "sp", "cep": "01310-100", "municipio": "São Paulo"})
        assert r.status_code == 200 and (r.json()["logradouro"], r.json()["uf"], r.json()["cep"]) == ("Rua Nova", "SP", "01310100")

    @pytest.mark.parametrize("corpo", [{"uf": "XX"}, {"cep": "123"}, {"cnpj": "123"}, {"razao_social": " "}])
    def test_recusa_valor_invalido(self, cliente, base, corpo):
        assert cliente.patch(f"/api/empresas/{base['e2']}", json=corpo).status_code == 422

    def test_cnpj_repetido_e_409(self, cliente, base):
        assert cliente.patch(f"/api/empresas/{base['e2']}", json={"cnpj": CNPJ_A}).status_code == 409

    def test_prospect_ganha_empresa_para_guardar_o_endereco(self, cliente, base):
        r = cliente.post(f"/api/grupos/{base['pros']}/empresas", json={})
        assert r.status_code == 201 and r.json()["razao_social"] == "Ação Consultoria"
        assert cliente.post(f"/api/grupos/{base['pros']}/empresas", json={"cnpj": CNPJ_A}).status_code == 409
        assert cliente.post("/api/grupos/9999/empresas", json={}).status_code == 404
        itens = cliente.get("/api/contatos/empresas", params={"tipo": "prospect", "busca": "acao"}).json()["itens"]
        assert itens[0]["empresa_id"] == r.json()["id"]


class TestClienteNaoRecorrente:
    """Cliente sem contrato recorrente (consultoria pontual) também é cliente — decisão de 26/09/2026."""

    def test_cliente_sem_empresa_aparece_como_nao_recorrente(self, cliente, sessao, base):
        g = GrupoEconomico(nome="Consultoria Pontual SA", situacao=SituacaoGrupo.CLIENTE)
        sessao.add(g); sessao.flush()
        sessao.add(Oportunidade(grupo_id=g.id, nome="Diagnóstico", situacao=Situacao.ACEITA))
        sessao.commit()
        itens = cliente.get("/api/contatos/empresas", params={"tipo": "cliente"}).json()["itens"]
        pontual = next(i for i in itens if i["grupo_nome"] == "Consultoria Pontual SA")
        assert (pontual["empresa_id"], pontual["recorrente"], pontual["propostas"]) == (None, False, 1)

    def test_cliente_com_contrato_ativo_e_recorrente_e_prospect_nunca_e(self, cliente, base):
        c = cliente.get("/api/contatos/empresas", params={"tipo": "cliente", "busca": "comercio"}).json()["itens"][0]
        assert c["recorrente"] is True
        p = cliente.get("/api/contatos/empresas", params={"tipo": "prospect"}).json()["itens"]
        assert all(i["recorrente"] is False for i in p)

    def test_empresa_de_cliente_sem_contrato_ativo_tambem_nao_e_recorrente(self, cliente, base):
        e2 = next(i for i in cliente.get("/api/contatos/empresas", params={"tipo": "cliente", "busca": "servicos"}).json()["itens"])
        assert e2["recorrente"] is False and e2["mensalidade"] is None
