"""O questionário preenche sozinho pessoa, empresa e oportunidade (Karine, 01/10/2026):
oportunidade ligada à empresa, pessoa da base reaproveitada pelo e-mail e endereço pelo CNPJ."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import Empresa, GrupoEconomico, Oportunidade, PessoaContato, QuestionarioRecebido, VinculoDeContato
from crm.domain.listas import SituacaoGrupo
from crm.questionario import endereco as modulo_endereco
from test_questionario import FonteFalsa, linha

CNPJ = "12345678000190"
ENDERECO = {"logradouro": "RUA VOLUNTARIOS DA PATRIA", "numero": "190", "complemento": "SALA 506",
            "bairro": "BOTAFOGO", "municipio": "RIO DE JANEIRO", "uf": "RJ", "cep": "22270902"}


class BuscaFalsa:
    def __init__(self, resposta=ENDERECO):
        self.resposta, self.pedidos = resposta, []

    def __call__(self, cnpj):
        self.pedidos.append(cnpj)
        return self.resposta


def _cliente(engine, fonte, busca):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return TestClient(criar_app(fabrica, fonte_de_questionarios=lambda: fonte, busca_de_endereco=busca))


def _buscar(c):
    r = c.post("/api/questionarios/buscar")
    assert r.status_code == 200, r.text
    return r.json()


def test_cliente_novo_ganha_endereco_e_oportunidade_ligada_a_empresa(engine, sessao: Session):
    busca = BuscaFalsa()
    with _cliente(engine, FonteFalsa([linha()]), busca) as c:
        novo = _buscar(c)["novos"][0]
    assert busca.pedidos == [CNPJ]
    assert "Endereço preenchido pelo CNPJ" in novo["o_que_fez"]
    e = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == CNPJ))
    assert (e.logradouro, e.numero, e.bairro, e.municipio, e.uf, e.cep) == (
        "RUA VOLUNTARIOS DA PATRIA", "190", "BOTAFOGO", "RIO DE JANEIRO", "RJ", "22270902")
    o = sessao.get(Oportunidade, novo["oportunidade_id"])
    assert o.empresa_id == e.id


def test_endereco_nao_achado_avisa_e_nao_impede(engine, sessao: Session):
    with _cliente(engine, FonteFalsa([linha()]), BuscaFalsa(resposta=None)) as c:
        novo = _buscar(c)["novos"][0]
    assert "Endereço não encontrado pelo CNPJ" in novo["o_que_fez"] and novo["oportunidade_id"]


def test_endereco_ja_preenchido_nao_e_trocado(engine, sessao: Session):
    g = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE); sessao.add(g); sessao.flush()
    sessao.add(Empresa(grupo_id=g.id, razao_social="Alfa Ltda", cnpj=CNPJ, logradouro="Rua Nossa", municipio="Niterói",
                       uf="RJ", cep="24000000"))
    sessao.commit()
    busca = BuscaFalsa()
    with _cliente(engine, FonteFalsa([linha()]), busca) as c:
        _buscar(c)
    e = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == CNPJ))
    sessao.refresh(e)
    assert busca.pedidos == [] and (e.logradouro, e.municipio) == ("Rua Nossa", "Niterói")


def test_pessoa_da_base_e_reaproveitada_pelo_email(engine, sessao: Session):
    g = GrupoEconomico(nome="Outro cliente", situacao=SituacaoGrupo.CLIENTE); sessao.add(g); sessao.flush()
    outra = Empresa(grupo_id=g.id, razao_social="Outra Ltda"); sessao.add(outra); sessao.flush()
    ana = PessoaContato(nome="Ana Souza", email="ANA@exemplo.com.br", vinculos=[VinculoDeContato(empresa_id=outra.id)])
    sessao.add(ana); sessao.commit()
    with _cliente(engine, FonteFalsa([linha()]), None) as c:
        novo = _buscar(c)["novos"][0]
    assert "vinculou o contato que já estava na base" in novo["o_que_fez"]
    pessoas = sessao.scalars(sa.select(PessoaContato).where(sa.func.lower(PessoaContato.email) == "ana@exemplo.com.br")).all()
    assert len(pessoas) == 1
    sessao.refresh(pessoas[0])
    empresas = {v.empresa.razao_social for v in pessoas[0].vinculos}
    assert empresas == {"Outra Ltda", "Exemplo Alfa Comércio Ltda"}
    assert (pessoas[0].cargo, pessoas[0].telefone) == ("Diretora Financeira", "(21) 90000-0000")  # só o vazio


def test_criar_nova_e_anexar_ligam_a_empresa(engine, sessao: Session):
    with _cliente(engine, FonteFalsa([linha()]), None) as c:
        _buscar(c)
    e = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == CNPJ))
    with _cliente(engine, FonteFalsa([linha(id_="q-2")]), None) as c:
        pendente = _buscar(c)["novos"][0]
        assert pendente["situacao"] == "Precisa de você"
        r = c.post(f"/api/questionarios/{pendente['id']}/resolver", json={"acao": "criar"})
        assert r.status_code == 200, r.text
        oid = r.json()["oportunidade_id"]
    assert sessao.get(Oportunidade, oid).empresa_id == e.id


def test_endereco_pelo_cnpj_monta_os_campos(monkeypatch):
    class Resposta:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, *a): return b'{"descricao_tipo_de_logradouro": "RUA", "logradouro": "VOLUNTARIOS  DA PATRIA", "numero": "00190", "complemento": "", "bairro": "BOTAFOGO", "municipio": "RIO DE JANEIRO", "uf": "rj", "cep": "22270-902"}'
    pedidos = []
    monkeypatch.setattr(modulo_endereco.urllib.request, "urlopen", lambda req, timeout: pedidos.append(req) or Resposta())
    e = modulo_endereco.endereco_pelo_cnpj("12.345.678/0001-90")
    assert e == {"logradouro": "RUA VOLUNTARIOS DA PATRIA", "numero": "190", "complemento": None, "bairro": "BOTAFOGO",
                 "municipio": "RIO DE JANEIRO", "uf": "RJ", "cep": "22270902"}
    assert pedidos[0].full_url.endswith("/12345678000190") and pedidos[0].get_header("User-agent") == "CRM-Criterio/1.0"
    assert modulo_endereco.endereco_pelo_cnpj("123") is None
