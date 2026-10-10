"""Excluir oportunidade pela tela, com motivo (04/10/2026, amostra aprovada por Eduardo)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal as D

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.auditoria import UsuarioAtual, usuario_atual
from crm.acesso.catalogo import permissoes_da_rota, permissoes_do_comercial
from crm.api.app import criar_app
from crm.db import excluir_oportunidade as regra
from crm.db.modelos import (
    Contrato, GrupoEconomico, HistoricoDePreco, Lead, MatrizDeProposta, Oportunidade, OportunidadeDaReuniao,
    PendenciaDaProposta, Proposta, QuestionarioRecebido, RegistroDeAlteracao, ReuniaoDeResultado,
)
from crm.domain.listas import Situacao, SituacaoContrato, SituacaoDoQuestionario, TipoDeMatriz


@pytest.fixture
def cliente(engine):
    with TestClient(criar_app(sessionmaker(bind=engine, expire_on_commit=False, future=True))) as c:
        yield c


@pytest.fixture
def ids(engine) -> dict:
    with Session(engine) as s:
        g = GrupoEconomico(nome="Grupo Delta")
        s.add(g)
        s.flush()
        op = Oportunidade(grupo_id=g.id, nome="Duplicada", situacao=Situacao.ENVIAR_PROPOSTA, preco_mensal=D("4500"))
        outra = Oportunidade(grupo_id=g.id, nome="A que fica", situacao=Situacao.ENVIAR_PROPOSTA)
        matriz = MatrizDeProposta(tipo=TipoDeMatriz.CONTABIL, nome_arquivo="m.pptx", conteudo_base64="", enviada_por="t",
                                  faltando=[], desconhecidos=[])
        reuniao = ReuniaoDeResultado(grupo_id=g.id, tipo="mensal", data=date(2026, 10, 1))
        s.add_all([op, outra, matriz, reuniao])
        s.flush()
        s.add_all([
            Proposta(oportunidade_id=op.id, numero=1, ano=2026, matriz_id=matriz.id, valores={}),
            PendenciaDaProposta(oportunidade_id=op.id, descricao="Faturamento", criada_por="t"),
            PendenciaDaProposta(oportunidade_id=op.id, descricao="Folha", criada_por="t"),
            PendenciaDaProposta(oportunidade_id=outra.id, descricao="Da outra", criada_por="t"),
            HistoricoDePreco(oportunidade_id=op.id, origem="tela", preco_mensal_novo=D("4500")),
            Lead(nome="Lead de origem", convertido_em_id=op.id),
            QuestionarioRecebido(
                externo_id="q1", recebido_em=datetime(2026, 10, 1, tzinfo=timezone.utc), versao="v1",
                razao_social="Delta", cnpj="11222333000181", contato_nome="Ana", respostas={}, situacao=SituacaoDoQuestionario.IMPORTADO,
                o_que_fez="teste", grupo_id=g.id, oportunidade_id=op.id),
            OportunidadeDaReuniao(reuniao_id=reuniao.id, grupo_id=g.id, lacuna="DRE", servico="BPO", oportunidade_id=op.id),
        ])
        s.commit()
        return {"op": op.id, "outra": outra.id, "grupo": g.id}


def test_mostra_o_que_sai_e_o_que_so_se_desliga(cliente, ids):
    r = cliente.get(f"/api/oportunidades/{ids['op']}/exclusao")
    assert r.status_code == 200
    assert r.json() == {"recusa": None, "propostas": 1, "pendencias": 2, "precos": 1, "questionarios": 1,
                        "leads": 1, "vendas_da_reuniao": 1, "sai_da_conversao": False}


def test_exclui_com_motivo_e_deixa_o_resto(cliente, engine, ids):
    r = cliente.post(f"/api/oportunidades/{ids['op']}/excluir", json={"motivo": "  Cadastrada   em duplicidade "})
    assert r.status_code == 204, r.text
    with Session(engine) as s:
        assert s.get(Oportunidade, ids["op"]) is None and s.get(Oportunidade, ids["outra"]) is not None
        assert s.get(GrupoEconomico, ids["grupo"]) is not None
        assert s.scalar(sa.select(sa.func.count(Proposta.id))) == 0
        assert s.scalar(sa.select(sa.func.count(HistoricoDePreco.id))) == 0
        assert [p.descricao for p in s.scalars(sa.select(PendenciaDaProposta))] == ["Da outra"]
        assert s.scalar(sa.select(Lead)).convertido_em_id is None
        assert s.scalar(sa.select(QuestionarioRecebido)).oportunidade_id is None
        assert s.scalar(sa.select(OportunidadeDaReuniao)).oportunidade_id is None
        reg = s.scalar(sa.select(RegistroDeAlteracao).where(RegistroDeAlteracao.campo == "motivo"))
        assert (reg.acao, reg.tabela, reg.registro_id, reg.descricao, reg.depois, reg.usuario_email) == (
            "excluiu", "oportunidade", ids["op"], "Duplicada", "Cadastrada em duplicidade", "sem login")


def test_com_login_o_motivo_leva_quem_excluiu(engine, ids):
    marca = usuario_atual.set(UsuarioAtual(email="ana@x.com", nome="Ana", perfil="Administrador", administrador=True))
    try:
        with Session(engine) as s:
            regra.excluir(s, s.get(Oportunidade, ids["op"]), "teste")
            s.commit()
    finally:
        usuario_atual.reset(marca)
    with Session(engine) as s:
        reg = s.scalar(sa.select(RegistroDeAlteracao).where(RegistroDeAlteracao.campo == "motivo"))
        assert (reg.usuario_email, reg.usuario_nome) == ("ana@x.com", "Ana")


@pytest.mark.parametrize("motivo", ["", "   "])
def test_sem_motivo_nao_exclui(cliente, engine, ids, motivo):
    r = cliente.post(f"/api/oportunidades/{ids['op']}/excluir", json={"motivo": motivo})
    assert r.status_code in (409, 422)
    with Session(engine) as s:
        assert s.get(Oportunidade, ids["op"]) is not None


@pytest.mark.parametrize("situacao", [Situacao.ACEITA, Situacao.PERDIDA])
def test_recusa_aceita_e_perdida(cliente, engine, ids, situacao):
    with Session(engine) as s:
        s.get(Oportunidade, ids["op"]).situacao = situacao
        s.commit()
    assert "ela fica como Perdida, com o motivo" in cliente.get(f"/api/oportunidades/{ids['op']}/exclusao").json()["recusa"]
    r = cliente.post(f"/api/oportunidades/{ids['op']}/excluir", json={"motivo": "x"})
    assert r.status_code == 409 and situacao.value in r.json()["detail"]
    with Session(engine) as s:
        assert s.get(Oportunidade, ids["op"]) is not None


def test_recusa_a_que_virou_contrato(cliente, engine, ids):
    with Session(engine) as s:
        s.add(Contrato(grupo_id=ids["grupo"], oportunidade_id=ids["op"], situacao=SituacaoContrato.ATIVO))
        s.commit()
    r = cliente.post(f"/api/oportunidades/{ids['op']}/excluir", json={"motivo": "x"})
    assert r.status_code == 409 and "virou contrato" in r.json()["detail"]


def test_em_aberto_sai_sem_mexer_na_conversao(cliente, engine, ids):
    # Desde 10/10/2026 o que conta na conversão (Aceita, Perdida) não se exclui; o resto não mexe nela.
    corpo = cliente.get(f"/api/oportunidades/{ids['op']}/exclusao").json()
    assert corpo["recusa"] is None and corpo["sai_da_conversao"] is False


def test_inexistente_da_404(cliente):
    assert cliente.get("/api/oportunidades/999/exclusao").status_code == 404
    assert cliente.post("/api/oportunidades/999/excluir", json={"motivo": "x"}).status_code == 404


def test_permissao_propria_fora_do_perfil_comercial():
    assert permissoes_da_rota("POST", "/api/oportunidades/7/excluir") == ("funil.excluir",)
    assert permissoes_da_rota("GET", "/api/oportunidades/7/exclusao") == ("funil.excluir",)
    assert "funil.excluir" not in permissoes_do_comercial()
