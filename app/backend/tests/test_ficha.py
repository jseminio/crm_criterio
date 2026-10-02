"""Ficha da oportunidade e "o que falta para a proposta" (E4, 02/10/2026)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm.api.app import criar_app
from crm.proposta import ficha
from test_proposta import MATRIZ_CONTABIL, _oportunidade_do_questionario, _subir
from test_questionario import FonteFalsa, linha

HOJE = date.today()


# --------------------------------------------------------------------- regras

class TestMontar:
    def test_conta_so_o_visivel_e_o_escopo(self):
        r = {"servicos": ["Contábil", "Fiscal"], "operacao": "Interna", "auditada": "Sim", "vol": {"lancamentos": "250"}}
        f = ficha.montar(r, {}, datetime(2026, 10, 1))
        por_numero = {s.numero: s for s in f.secoes}
        # "fornecedor atual" e "valor do fornecedor" só aparecem com operação terceirizada ou mista
        assert "fornecedor_atual" not in [c.campo.chave for c in por_numero[1].campos]
        # auditada = Sim mostra o detalhe da auditoria
        assert "auditoria_det" in [c.campo.chave for c in por_numero[4].campos]
        assert not por_numero[6].no_escopo and not por_numero[7].no_escopo  # sem Folha nem Financeiro
        assert por_numero[9].no_escopo and not por_numero[9].conta_pendencia  # implantação: não conta
        assert por_numero[3].respondidas == 1 and por_numero[3].total == 13
        assert f.total == sum(s.total for s in f.secoes if s.numero in (1, 2, 3, 4, 5, 8))

    def test_correcao_vale_como_entrevista_e_decide_o_que_aparece(self):
        r = {"servicos": ["Contábil"], "plano_contas": "Não"}
        corr = {"plano_contas": {"valor": "Sim", "por": "Karine", "em": "2026-10-02T10:00:00"},
                "servicos": {"valor": ["Contábil", "Folha / DP"], "por": "Karine", "em": "2026-10-02T10:00:00"}}
        f = ficha.montar(r, corr, datetime(2026, 10, 1))
        s4 = next(s for s in f.secoes if s.numero == 4)
        plano = next(c for c in s4.campos if c.campo.chave == "plano_contas")
        assert (plano.valor, plano.origem, plano.por) == ("Sim", "Entrevista", "Karine")
        assert "plano_contas_qtd" in [c.campo.chave for c in s4.campos]
        assert next(s for s in f.secoes if s.numero == 6).no_escopo  # DP entrou na entrevista

    def test_volumes_e_sistemas_saem_de_dentro_dos_blocos(self):
        r = {"vol": {"pagamentos": 90}, "sistemas": {"erp": {"sistema": "Omie", "troca": ["Arquivo", "Manual"]}}}
        assert ficha.valor_do_questionario(r, "vol.pagamentos") == "90"
        assert ficha.valor_do_questionario(r, "sistemas.erp") == "Omie · Arquivo, Manual"
        assert ficha.valor_do_questionario(r, "sistemas.ponto") is None


# ---------------------------------------------------------------------- rotas

@pytest.fixture
def fonte():
    return FonteFalsa([linha()])


@pytest.fixture
def cliente(engine, fonte):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, fonte_de_questionarios=lambda: fonte)) as c:
        yield c


def _pendencias(cliente, oid, **params):
    r = cliente.get(f"/api/oportunidades/{oid}/pendencias", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def _item(dados, chave):
    return next(i for i in dados["itens"] if i["chave"] == chave)


class TestFicha:
    def test_ficha_do_questionario_com_origem(self, cliente):
        oid = _oportunidade_do_questionario(cliente)
        f = cliente.get(f"/api/oportunidades/{oid}/ficha").json()
        assert [s["numero"] for s in f["secoes"]] == list(range(1, 10))
        s1 = f["secoes"][0]
        razao = next(c for c in s1["campos"] if c["chave"] == "razao_social")
        assert razao["valor"] == "Exemplo Alfa Comércio Ltda" and razao["origem"] == "Questionário"
        vol = f["secoes"][2]
        assert (vol["respondidas"], vol["total"]) == (7, 13)
        assert f["revisores"] == ["Eduardo", "Karine"] and 0 < f["respondidas"] < f["total"]

    def test_corrigir_grava_como_entrevista_e_valida(self, cliente):
        oid = _oportunidade_do_questionario(cliente)
        r = cliente.put(f"/api/oportunidades/{oid}/ficha/vol.contas_bancarias", json={"valor": "3", "por": "Karine"})
        assert r.status_code == 200, r.text
        c = next(c for c in r.json()["secoes"][2]["campos"] if c["chave"] == "vol.contas_bancarias")
        assert (c["valor"], c["origem"], c["por"]) == ("3", "Entrevista", "Karine") and c["em"]
        recusas = [
            ("vol.contas_bancarias", {"valor": "3,5", "por": "Karine"}),
            ("auditada", {"valor": "Talvez", "por": "Karine"}),
            ("servicos", {"valor": ["Jurídico"], "por": "Karine"}),
            ("data_inicio", {"valor": "31/02/2026", "por": "Karine"}),
            ("auditada", {"valor": "Sim", "por": "Bruno"}),
        ]
        for chave, corpo in recusas:
            assert cliente.put(f"/api/oportunidades/{oid}/ficha/{chave}", json=corpo).status_code == 422, chave
        assert cliente.put(f"/api/oportunidades/{oid}/ficha/inventada", json={"valor": "x", "por": "Karine"}).status_code == 404

    def test_apagar_na_entrevista_fica_sem_resposta(self, cliente):
        oid = _oportunidade_do_questionario(cliente)
        r = cliente.put(f"/api/oportunidades/{oid}/ficha/nome_fantasia", json={"valor": "", "por": "Eduardo"}).json()
        c = next(c for c in r["secoes"][0]["campos"] if c["chave"] == "nome_fantasia")
        assert c["valor"] is None and c["origem"] == "Entrevista"  # a resposta do cliente continua no questionário

    def test_oportunidade_sem_questionario_tem_ficha_vazia(self, cliente, sessao):
        from crm.db.modelos import GrupoEconomico, Oportunidade
        from crm.domain.listas import Situacao
        g = GrupoEconomico(nome="Grupo Sem Questionário")
        sessao.add(g)
        sessao.flush()
        o = Oportunidade(grupo_id=g.id, nome="Op manual", situacao=Situacao.ENVIAR_PROPOSTA)
        sessao.add(o)
        sessao.commit()
        f = cliente.get(f"/api/oportunidades/{o.id}/ficha").json()
        assert f["questionario_em"] is None and f["respondidas"] == 0 and f["total"] > 0
        assert _item(_pendencias(cliente, o.id), "secao-1")["aberta"]


class TestPendencias:
    def test_automaticas_abrem_e_fecham_sozinhas(self, cliente):
        oid = _oportunidade_do_questionario(cliente)
        d = _pendencias(cliente, oid)
        assert _item(d, "volumes")["aberta"] and "6 de 13" in _item(d, "volumes")["descricao"]
        assert _item(d, "matriz")["aberta"] and _item(d, "proposta")["aberta"]
        assert not _item(d, "contato-email")["aberta"]  # o questionário trouxe o contato com e-mail
        assert all(i["automatica"] for i in d["itens"])
        _subir(cliente, conteudo=MATRIZ_CONTABIL)
        assert not _item(_pendencias(cliente, oid), "matriz")["aberta"]

    def test_responsavel_e_prazo_no_automatico_mas_nao_se_marca_feito(self, cliente):
        oid = _oportunidade_do_questionario(cliente)
        ontem = (HOJE - timedelta(days=1)).isoformat()
        r = cliente.patch(f"/api/oportunidades/{oid}/pendencias/volumes",
                          json={"responsavel": "Karine", "prazo": ontem, "por": "Eduardo"})
        assert r.status_code == 200, r.text
        v = _item(r.json(), "volumes")
        assert (v["responsavel"], v["prazo"], v["dias_de_atraso"]) == ("Karine", ontem, 1)
        assert r.json()["atrasadas"] == 1
        assert cliente.patch(f"/api/oportunidades/{oid}/pendencias/volumes", json={"feita": True, "por": "Eduardo"}).status_code == 422
        assert cliente.patch(f"/api/oportunidades/{oid}/pendencias/inventada", json={"por": "Eduardo"}).status_code == 404
        # só o que veio muda: tirar o prazo mantém o responsável
        v = _item(cliente.patch(f"/api/oportunidades/{oid}/pendencias/volumes", json={"prazo": None, "por": "Eduardo"}).json(), "volumes")
        assert (v["responsavel"], v["prazo"]) == ("Karine", None)

    def test_manual_nasce_e_se_marca_feita(self, cliente):
        oid = _oportunidade_do_questionario(cliente)
        r = cliente.post(f"/api/oportunidades/{oid}/pendencias",
                         json={"descricao": "Pedir o balancete de agosto", "responsavel": "Karine", "prazo": HOJE.isoformat(), "por": "Eduardo"})
        assert r.status_code == 200, r.text
        m = next(i for i in r.json()["itens"] if not i["automatica"])
        assert m["chave"].startswith("manual-") and m["aberta"] and m["dias_de_atraso"] == 0
        feita = next(i for i in cliente.patch(f"/api/oportunidades/{oid}/pendencias/{m['chave']}",
                                              json={"feita": True, "por": "Karine"}).json()["itens"] if i["chave"] == m["chave"])
        assert not feita["aberta"] and feita["feita_por"] == "Karine" and feita["feita_em"]
        reaberta = next(i for i in cliente.patch(f"/api/oportunidades/{oid}/pendencias/{m['chave']}",
                                                 json={"feita": False, "por": "Karine"}).json()["itens"] if i["chave"] == m["chave"])
        assert reaberta["aberta"] and reaberta["feita_por"] is None
        assert cliente.post(f"/api/oportunidades/{oid}/pendencias", json={"descricao": "x", "por": "Bruno"}).status_code == 422
        assert cliente.post(f"/api/oportunidades/{oid}/pendencias",
                            json={"descricao": "x", "responsavel": "Bruno", "por": "Karine"}).status_code == 422

    def test_pendencia_com_prazo_entra_na_agenda(self, cliente):
        oid = _oportunidade_do_questionario(cliente)
        ontem = (HOJE - timedelta(days=2)).isoformat()
        cliente.post(f"/api/oportunidades/{oid}/pendencias",
                     json={"descricao": "Pedir o contrato atual", "responsavel": "Karine", "prazo": ontem, "por": "Eduardo"})
        cliente.patch(f"/api/oportunidades/{oid}/pendencias/volumes", json={"prazo": HOJE.isoformat(), "por": "Eduardo"})
        cliente.post(f"/api/oportunidades/{oid}/pendencias", json={"descricao": "Sem prazo não entra", "por": "Eduardo"})
        agenda = cliente.get("/api/agenda", params={"hoje": HOJE.isoformat()}).json()
        p = [i for i in agenda["itens"] if i["tipo"] == "pendencia"]
        assert len(p) == 2
        atrasada = next(i for i in p if i["balde"] == "atrasada")
        assert atrasada["proxima_acao"] == "Pendência da proposta: Pedir o contrato atual"
        assert atrasada["captador"] == "Karine" and atrasada["dias_de_atraso"] == 2 and atrasada["oportunidade_id"] == oid
        assert next(i for i in p if i["balde"] == "hoje")["proxima_acao"].startswith("Pendência da proposta: Volumetria")
        # feita sai da agenda; filtro por captador também a tira (o dono é o responsável)
        assert not [i for i in cliente.get("/api/agenda", params={"captador": "EL"}).json()["itens"] if i["tipo"] == "pendencia"]
