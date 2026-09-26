"""Desfazer a fusão de grupos: devolve exatamente o que foi movido, e só isso."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.grupos import FusaoInvalida, desfazer_fusao, fundir_grupos
from crm.db.modelos import Contrato, Empresa, FusaoDeGrupos, GrupoEconomico, Oportunidade, PessoaContato
from crm.domain.listas import Situacao, SituacaoContrato, SituacaoGrupo


def grupo(sessao, nome, situacao=SituacaoGrupo.PROSPECT, entrada=None):
    g = GrupoEconomico(nome=nome, situacao=situacao, data_entrada=entrada)
    sessao.add(g); sessao.flush()
    return g


def com_itens(sessao, g, sufixo):
    e = Empresa(grupo_id=g.id, razao_social=f"Emp {sufixo}", cnpj=None)
    o = Oportunidade(grupo_id=g.id, nome=f"Prop {sufixo}", situacao=Situacao.ENVIAR_PROPOSTA)
    p = PessoaContato(nome=f"Pessoa {sufixo}", grupo_id=g.id)
    c = Contrato(grupo_id=g.id, situacao=SituacaoContrato.ATIVO, preco_mensal=Decimal("100"), anterior_ao_crm=True)
    sessao.add_all([e, o, p, c]); sessao.flush()
    return {"e": e.id, "o": o.id, "p": p.id, "c": c.id}


def dono(sessao, itens):
    return {k: sessao.get(m, itens[k]).grupo_id for k, m in (("e", Empresa), ("o", Oportunidade), ("p", PessoaContato), ("c", Contrato))}


def test_a_fusao_registra_o_que_moveu_incluindo_contratos(sessao: Session):
    a, b = grupo(sessao, "A"), grupo(sessao, "B")
    it = com_itens(sessao, b, "b")
    r = fundir_grupos(sessao, a, b)
    f = sessao.get(FusaoDeGrupos, r.fusao_id)
    assert f.movidos == {"empresa": [it["e"]], "oportunidade": [it["o"]], "pessoa_contato": [it["p"]], "contrato": [it["c"]]}
    assert set(dono(sessao, it).values()) == {a.id}  # o contrato também foi (antes ficava para trás)


def test_desfazer_devolve_tudo_e_reabre_o_absorvido(sessao: Session):
    a, b = grupo(sessao, "A"), grupo(sessao, "B")
    it = com_itens(sessao, b, "b")
    f = sessao.get(FusaoDeGrupos, fundir_grupos(sessao, a, b).fusao_id)
    desfazer_fusao(sessao, f)
    assert set(dono(sessao, it).values()) == {b.id}
    assert b.fundido_em_id is None and b.situacao is SituacaoGrupo.PROSPECT and f.desfeita_em is not None


def test_o_que_foi_criado_no_principal_depois_da_fusao_fica_la(sessao: Session):
    a, b = grupo(sessao, "A"), grupo(sessao, "B")
    com_itens(sessao, b, "b")
    f = sessao.get(FusaoDeGrupos, fundir_grupos(sessao, a, b).fusao_id)
    nova = com_itens(sessao, a, "nova")   # criada depois, no principal
    desfazer_fusao(sessao, f)
    assert set(dono(sessao, nova).values()) == {a.id}


def test_fusao_nao_se_desfaz_duas_vezes(sessao: Session):
    a, b = grupo(sessao, "A"), grupo(sessao, "B")
    f = sessao.get(FusaoDeGrupos, fundir_grupos(sessao, a, b).fusao_id)
    desfazer_fusao(sessao, f)
    with pytest.raises(FusaoInvalida, match="já foi desfeita"):
        desfazer_fusao(sessao, f)


def test_prospect_que_virou_cliente_ao_absorver_volta_a_prospect(sessao: Session):
    a = grupo(sessao, "A", SituacaoGrupo.PROSPECT, entrada=date(2026, 6, 1))
    b = grupo(sessao, "B", SituacaoGrupo.CLIENTE, entrada=date(2025, 1, 1))
    f = sessao.get(FusaoDeGrupos, fundir_grupos(sessao, a, b).fusao_id)
    assert a.situacao is SituacaoGrupo.CLIENTE and a.data_entrada == date(2025, 1, 1)
    desfazer_fusao(sessao, f)
    assert a.situacao is SituacaoGrupo.PROSPECT and a.data_entrada == date(2026, 6, 1)
    assert b.situacao is SituacaoGrupo.CLIENTE


def test_se_o_principal_mudou_depois_a_mudanca_e_respeitada(sessao: Session):
    a, b = grupo(sessao, "A"), grupo(sessao, "B", SituacaoGrupo.CLIENTE)
    f = sessao.get(FusaoDeGrupos, fundir_grupos(sessao, a, b).fusao_id)
    a.data_entrada = date(2024, 2, 2)   # alguém preencheu depois
    desfazer_fusao(sessao, f)
    assert a.data_entrada == date(2024, 2, 2)


def test_fusao_em_cadeia_desfaz_a_do_meio_devolvendo_pelo_id(sessao: Session):
    a, b, c = grupo(sessao, "A"), grupo(sessao, "B"), grupo(sessao, "C")
    it = com_itens(sessao, b, "b")
    f1 = sessao.get(FusaoDeGrupos, fundir_grupos(sessao, a, b).fusao_id)   # B -> A
    fundir_grupos(sessao, c, a)                                             # A -> C (leva os itens de B junto)
    assert set(dono(sessao, it).values()) == {c.id}
    desfazer_fusao(sessao, f1)                                              # desfaz B -> A
    assert set(dono(sessao, it).values()) == {b.id} and b.fundido_em_id is None
    assert a.fundido_em_id == c.id                                          # A continua em C


def test_recusa_se_o_absorvido_ja_nao_esta_fundido_no_principal(sessao: Session):
    a, b = grupo(sessao, "A"), grupo(sessao, "B")
    f = sessao.get(FusaoDeGrupos, fundir_grupos(sessao, a, b).fusao_id)
    b.fundido_em_id = None
    with pytest.raises(FusaoInvalida, match="não está mais fundido"):
        desfazer_fusao(sessao, f)


class TestApi:
    @pytest.fixture
    def cliente(self, engine):
        fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        with TestClient(criar_app(fabrica)) as c:
            yield c

    def test_fundir_lista_e_desfazer(self, cliente, sessao):
        a, b = grupo(sessao, "Alfa"), grupo(sessao, "Beta")
        com_itens(sessao, b, "b"); sessao.commit()
        assert cliente.post(f"/api/grupos/{a.id}/fundir", json={"absorvido_id": b.id}).status_code == 200
        lista = cliente.get("/api/grupos/fusoes").json()
        assert len(lista) == 1
        f = lista[0]
        assert (f["principal_nome"], f["absorvido_nome"], f["pode_desfazer"]) == ("Alfa", "Beta", True)
        assert (f["empresas"], f["oportunidades"], f["contatos"], f["contratos"]) == (1, 1, 1, 1)
        r = cliente.post(f"/api/grupos/fusoes/{f['id']}/desfazer")
        assert r.status_code == 200 and r.json()["desfeita_em"] is not None and r.json()["pode_desfazer"] is False
        assert cliente.get("/api/grupos/fusoes").json() == []                       # some da lista padrão
        assert len(cliente.get("/api/grupos/fusoes", params={"incluir_desfeitas": True}).json()) == 1
        grupos = {g["nome"]: g for g in cliente.get("/api/grupos").json()["itens"]}
        assert grupos["Beta"]["fundido_em_id"] is None                              # reaberto

    def test_desfazer_duas_vezes_e_409_e_inexistente_e_404(self, cliente, sessao):
        a, b = grupo(sessao, "Alfa"), grupo(sessao, "Beta"); sessao.commit()
        cliente.post(f"/api/grupos/{a.id}/fundir", json={"absorvido_id": b.id})
        fid = cliente.get("/api/grupos/fusoes").json()[0]["id"]
        assert cliente.post(f"/api/grupos/fusoes/{fid}/desfazer").status_code == 200
        assert cliente.post(f"/api/grupos/fusoes/{fid}/desfazer").status_code == 409
        assert cliente.post("/api/grupos/fusoes/9999/desfazer").status_code == 404
