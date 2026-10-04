"""A base de conhecimento do SDR de IA — 03/10/2026."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace as NS

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.db.modelos import FichaDaBase, Perfil, Usuario
from crm.domain import base_de_conhecimento as regras
from crm.domain.abordagem import fala_de_preco
from crm.domain.base_de_conhecimento import BlocoDaBase as B, SituacaoDaFicha as S
from crm.domain.servicos import CATALOGO

HOJE = date.today()


def ficha(**campos):
    padrao = dict(codigo="P3", bloco=B.REGRAS, situacao=S.EM_REVISAO, titulo="P3", texto="Vou passar para a equipe.",
                  fonte="doc", dono="Eduardo", validade=None)
    return NS(**(padrao | campos))


# ------------------------------------------------------------------ domínio
class TestRegras:
    def test_so_aprovada_e_dentro_da_validade_vale_para_a_ia(self):
        assert not regras.vale_para_a_ia(ficha(), HOJE)
        aprovada = ficha(situacao=S.APROVADA, validade=HOJE)
        assert regras.vale_para_a_ia(aprovada, HOJE)
        assert not regras.vale_para_a_ia(aprovada, HOJE + timedelta(days=1))
        assert regras.vencida(aprovada, HOJE + timedelta(days=1))

    def test_referencias_nunca_vao_para_a_ia(self):
        ref = ficha(bloco=B.REFERENCIAS, situacao=S.APROVADA, validade=HOJE + timedelta(days=30))
        assert not regras.vale_para_a_ia(ref, HOJE)

    def test_aprovar_exige_texto_fonte_e_dono(self):
        assert regras.problemas_para_aprovar(ficha()) == []
        problemas = regras.problemas_para_aprovar(ficha(codigo=None, texto=" ", fonte=None, dono=""))
        assert problemas == ["Falta o código", "Falta o que a IA pode dizer", "Falta a fonte", "Falta o dono"]

    def test_texto_que_fala_de_preco_nao_aprova_mas_referencia_pode_citar_numero(self):
        assert any("preço" in p for p in regras.problemas_para_aprovar(ficha(texto="Custa R$ 5 mil")))
        assert regras.problemas_para_aprovar(ficha(bloco=B.REFERENCIAS, texto="Custa R$ 5 mil")) == []

    def test_validade_de_hipotese_e_mais_curta(self):
        assert regras.validade_ao_aprovar(HOJE, False) == HOJE + timedelta(days=182)
        assert regras.validade_ao_aprovar(HOJE, True) == HOJE + timedelta(days=60)

    def test_resumo_traz_todos_os_blocos_na_ordem_e_ignora_arquivadas(self):
        fichas = [
            ficha(situacao=S.APROVADA, validade=HOJE),
            ficha(situacao=S.APROVADA, validade=HOJE - timedelta(days=1)),
            ficha(situacao=S.RASCUNHO),
            ficha(situacao=S.ARQUIVADA),
        ]
        resumo = regras.resumir(fichas, HOJE)
        assert [r.bloco for r in resumo] == [b.value for b in B]
        regras_ = resumo[0]
        assert (regras_.total, regras_.valem, regras_.vencidas, regras_.rascunhos, regras_.em_revisao) == (3, 1, 1, 1, 0)
        assert resumo[-1].bloco == "Referências" and not resumo[-1].vai_para_a_ia


class TestCargaInicial:
    def test_codigos_unicos(self):
        codigos = [f.codigo for f in regras.FICHAS_INICIAIS]
        assert len(codigos) == len(set(codigos))

    def test_traz_as_regras_os_gatilhos_e_um_servico_por_item_do_catalogo(self):
        por_bloco = lambda b: [f for f in regras.FICHAS_INICIAIS if f.bloco is b]
        assert [f.codigo for f in por_bloco(B.REGRAS)] == [f"P{i}" for i in range(1, 13)]
        assert [f.codigo for f in por_bloco(B.TRANSBORDO)] == [f"T{i}" for i in range(1, 12)]
        assert [f.servico for f in por_bloco(B.SERVICOS)] == [s.nome for s in CATALOGO]
        assert por_bloco(B.OBJECOES) == []  # a Matriz fica fora do repositório

    def test_nada_nasce_aprovado(self):
        assert {f.situacao for f in regras.FICHAS_INICIAIS} <= {S.RASCUNHO, S.EM_REVISAO}

    def test_nenhum_texto_que_vai_para_a_ia_fala_de_preco(self):
        falam = [f.codigo for f in regras.FICHAS_INICIAIS if f.bloco.vai_para_a_ia and fala_de_preco(f.texto)]
        assert falam == []

    def test_fscp_usa_a_terminologia_fixa(self):
        fscp = next(f for f in regras.FICHAS_INICIAIS if f.servico == "FSCP")
        assert fscp.texto.startswith("Mapeamento dos processos e controles")


# ---------------------------------------------------------------------- API
@pytest.fixture
def cliente(engine: sa.Engine) -> TestClient:
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as aberto:
        yield aberto


def nova(cliente, **campos) -> dict:
    """Sem código pedido, usa o próximo livre do bloco, como a tela sugere."""
    corpo = {"titulo": "Prazo de implantação", "bloco": "Perguntas frequentes",
             "texto": "A implantação é combinada na proposta.", "fonte": "Comercial", "dono": "Karine"} | campos
    if "codigo" not in corpo:
        corpo["codigo"] = cliente.get("/api/sdr/base").json()["proximos_codigos"][corpo["bloco"]]
    r = cliente.post("/api/sdr/base/fichas", json=corpo)
    assert r.status_code == 201, r.text
    return r.json()


def aprovar(cliente, ficha_id: int, aprovador: str | None = "Eduardo"):
    return cliente.post(f"/api/sdr/base/fichas/{ficha_id}/aprovar", json={"aprovador": aprovador})


class TestApi:
    def test_base_vazia_mostra_todos_os_blocos(self, cliente):
        corpo = cliente.get("/api/sdr/base").json()
        assert corpo["fichas"] == []
        assert len(corpo["blocos"]) == 9 and all(b["total"] == 0 for b in corpo["blocos"])
        assert corpo["situacoes"] == ["Rascunho", "Em revisão", "Aprovada", "Arquivada"]

    def test_ficha_nova_nasce_rascunho_e_limpa_espacos(self, cliente):
        f = nova(cliente, servico="  ", dono=" Karine ")
        assert f["situacao"] == "Rascunho" and f["servico"] is None and f["dono"] == "Karine"
        assert not f["vale_para_a_ia"] and f["problemas_para_aprovar"] == []

    def test_titulo_em_branco_recusa(self, cliente):
        assert cliente.post("/api/sdr/base/fichas", json={"titulo": "  ", "bloco": "Serviços"}).status_code == 422

    def test_aprovar_carimba_quem_quando_e_validade(self, cliente):
        f = nova(cliente, depende_de_hipotese=True)
        r = aprovar(cliente, f["id"])
        assert r.status_code == 200, r.text
        a = r.json()
        assert a["situacao"] == "Aprovada" and a["aprovada_por"] == "Eduardo" and a["aprovada_em"]
        assert a["validade"] == (HOJE + timedelta(days=60)).isoformat()
        assert a["vale_para_a_ia"]
        assert aprovar(cliente, f["id"]).status_code == 409

    def test_aprovar_sem_dizer_quem_recusa(self, cliente):
        f = nova(cliente)
        assert aprovar(cliente, f["id"], None).status_code == 422

    def test_aprovar_recusa_ficha_incompleta_ou_com_preco(self, cliente):
        sem_fonte = nova(cliente, fonte=None)
        r = aprovar(cliente, sem_fonte["id"])
        assert r.status_code == 422 and "Falta a fonte" in r.json()["detail"]
        com_preco = nova(cliente, texto="A mensalidade começa em 3 mil")
        r = aprovar(cliente, com_preco["id"])
        assert r.status_code == 422 and "preço" in r.json()["detail"]

    def test_editar_aprovada_volta_para_revisao(self, cliente):
        f = nova(cliente)
        aprovar(cliente, f["id"])
        r = cliente.patch(f"/api/sdr/base/fichas/{f['id']}", json={"texto": "Outro texto."})
        e = r.json()
        assert e["situacao"] == "Em revisão" and e["aprovada_por"] is None and e["validade"] is None

    def test_trocar_so_o_dono_nao_desaprova(self, cliente):
        f = nova(cliente)
        aprovar(cliente, f["id"])
        e = cliente.patch(f"/api/sdr/base/fichas/{f['id']}", json={"dono": "Bruno"}).json()
        assert e["situacao"] == "Aprovada" and e["dono"] == "Bruno"

    def test_rascunho_vai_para_revisao_uma_vez(self, cliente):
        f = nova(cliente)
        assert cliente.post(f"/api/sdr/base/fichas/{f['id']}/revisao").json()["situacao"] == "Em revisão"
        assert cliente.post(f"/api/sdr/base/fichas/{f['id']}/revisao").status_code == 409

    def test_arquivada_nao_se_edita_e_reabre_como_rascunho(self, cliente):
        f = nova(cliente)
        aprovar(cliente, f["id"])
        a = cliente.post(f"/api/sdr/base/fichas/{f['id']}/arquivar").json()
        assert a["situacao"] == "Arquivada" and not a["vale_para_a_ia"]
        assert cliente.patch(f"/api/sdr/base/fichas/{f['id']}", json={"texto": "x"}).status_code == 409
        assert aprovar(cliente, f["id"]).status_code == 422
        r = cliente.post(f"/api/sdr/base/fichas/{f['id']}/reabrir").json()
        assert r["situacao"] == "Rascunho" and r["aprovada_por"] is None

    def test_ficha_inexistente(self, cliente):
        assert cliente.patch("/api/sdr/base/fichas/999", json={"texto": "x"}).status_code == 404

    def test_carga_inicial_so_acrescenta(self, cliente, engine):
        total = len(regras.FICHAS_INICIAIS)
        assert cliente.post("/api/sdr/base/carga-inicial").json() == {"acrescentadas": total, "ja_existiam": 0}
        p1 = next(f for f in cliente.get("/api/sdr/base").json()["fichas"] if f["codigo"] == "P1")
        cliente.patch(f"/api/sdr/base/fichas/{p1['id']}", json={"texto": "Editado pela equipe."})
        with Session(engine) as s:
            s.delete(s.scalar(sa.select(FichaDaBase).where(FichaDaBase.codigo == "R6")))
            s.commit()
        assert cliente.post("/api/sdr/base/carga-inicial").json() == {"acrescentadas": 1, "ja_existiam": total - 1}
        corpo = cliente.get("/api/sdr/base").json()
        assert len(corpo["fichas"]) == total
        assert next(f for f in corpo["fichas"] if f["codigo"] == "P1")["texto"] == "Editado pela equipe."
        blocos = {b["bloco"]: b for b in corpo["blocos"]}
        assert blocos["Regras de atuação"]["em_revisao"] == 12
        assert blocos["Objeções"]["total"] == 0

    def test_lista_na_ordem_dos_blocos(self, cliente):
        nova(cliente, bloco="Referências", titulo="Ref")
        nova(cliente, bloco="Regras de atuação", titulo="Regra")
        assert [f["titulo"] for f in cliente.get("/api/sdr/base").json()["fichas"]] == ["Regra", "Ref"]


# ---------------------------------------------------------- com login
CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))


def _cab(email: str, nome: str) -> dict:
    return {"Authorization": f"Bearer {email}|{nome}"}


def _validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


@pytest.fixture
def com_login(engine: sa.Engine) -> TestClient:
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        edita = Perfil(nome="Edita a base", permissoes=["sdr.ver", "sdr.base"])
        s.add(edita)
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=edita.id))
        s.commit()
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=_validar)) as aberto:
        yield aberto


def test_quem_edita_nao_aprova_e_com_login_quem_aprova_e_quem_entrou(com_login):
    karine = _cab("karine@grupocriterio.com.br", "Karine N")
    eduardo = _cab("eduardo@grupocriterio.com.br", "Eduardo Luiz")
    r = com_login.post("/api/sdr/base/fichas", headers=karine, json={
        "codigo": "F1", "titulo": "Prazo", "bloco": "Perguntas frequentes", "texto": "Combinado na proposta.", "fonte": "x", "dono": "Karine"})
    assert r.status_code == 201
    fid = r.json()["id"]
    assert com_login.post(f"/api/sdr/base/fichas/{fid}/aprovar", headers=karine, json={}).status_code == 403
    a = com_login.post(f"/api/sdr/base/fichas/{fid}/aprovar", headers=eduardo, json={"aprovador": "Outro"}).json()
    assert a["aprovada_por"] == "Eduardo Luiz"


# ------------------------------------------------- M1: código editável (04/10/2026)
class TestCodigo:
    def test_regras_do_codigo(self):
        assert regras.proximo_codigo(B.OBJECOES, ["O1", "O2", "P9", None]) == "O3"
        assert regras.proximo_codigo(B.SERVICOS, ["S12"]) == "S13"
        assert regras.proximo_codigo(B.PERGUNTAS, []) == "F1"
        assert regras.problema_no_codigo("F1", B.PERGUNTAS) is None
        assert "comece com F" in regras.problema_no_codigo("C2", B.PERGUNTAS)
        assert "letra do bloco" in regras.problema_no_codigo("O-1", B.OBJECOES)
        assert regras.normalizar_codigo(" o3 ") == "O3" and regras.normalizar_codigo("  ") is None
        assert regras.codigo_travado("T9") and not regras.codigo_travado("T12")

    def test_sugestao_conta_a_carga_mesmo_antes_de_trazer(self, cliente):
        proximos = cliente.get("/api/sdr/base").json()["proximos_codigos"]
        assert (proximos["Regras de atuação"], proximos["Serviços"], proximos["Objeções"]) == ("P13", "S13", "O1")

    def test_ficha_nova_com_codigo_normalizado(self, cliente):
        f = nova(cliente, bloco="Objeções", codigo=" o2 ")
        assert f["codigo"] == "O2" and not f["codigo_travado"]
        assert cliente.get("/api/sdr/base").json()["proximos_codigos"]["Objeções"] == "O3"

    def test_codigo_que_nao_combina_com_o_bloco(self, cliente):
        r = cliente.post("/api/sdr/base/fichas", json={"titulo": "Onde fica", "bloco": "Perguntas frequentes", "codigo": "C2"})
        assert r.status_code == 422 and "comece com F" in r.json()["detail"]

    def test_codigo_repetido_indica_o_proximo(self, cliente):
        nova(cliente, bloco="Objeções", codigo="O1", titulo="Preço")
        r = cliente.post("/api/sdr/base/fichas", json={"titulo": "Outra", "bloco": "Objeções", "codigo": "O1"})
        assert r.status_code == 409
        assert r.json()["detail"] == 'O código O1 já é da ficha "Preço". Use O2, o próximo livre.'

    def test_codigo_da_carga_e_reservado_e_travado(self, cliente):
        r = cliente.post("/api/sdr/base/fichas", json={"titulo": "X", "bloco": "Transbordo", "codigo": "T9"})
        assert r.status_code == 409 and "reservado" in r.json()["detail"]
        cliente.post("/api/sdr/base/carga-inicial")
        t9 = next(f for f in cliente.get("/api/sdr/base").json()["fichas"] if f["codigo"] == "T9")
        assert t9["codigo_travado"]
        for mudanca in ({"codigo": "T20"}, {"bloco": "Objeções"}):
            r = cliente.patch(f"/api/sdr/base/fichas/{t9['id']}", json=mudanca)
            assert r.status_code == 409 and "carga inicial" in r.json()["detail"]
        assert cliente.patch(f"/api/sdr/base/fichas/{t9['id']}", json={"dono": "Bruno"}).status_code == 200

    def test_trocar_de_bloco_pede_codigo_novo(self, cliente):
        f = nova(cliente, bloco="Quem é a Critério", codigo="C2", titulo="Onde fica")
        r = cliente.patch(f"/api/sdr/base/fichas/{f['id']}", json={"bloco": "Perguntas frequentes"})
        assert r.status_code == 422 and "comece com F" in r.json()["detail"]
        e = cliente.patch(f"/api/sdr/base/fichas/{f['id']}", json={"bloco": "Perguntas frequentes", "codigo": "F1"}).json()
        assert (e["bloco"], e["codigo"]) == ("Perguntas frequentes", "F1")

    def test_aprovar_exige_codigo_e_aprovada_nao_perde_o_codigo(self, cliente):
        sem = nova(cliente, codigo=None)
        r = aprovar(cliente, sem["id"])
        assert r.status_code == 422 and "Falta o código" in r.json()["detail"]
        cliente.patch(f"/api/sdr/base/fichas/{sem['id']}", json={"codigo": "F7"})
        assert aprovar(cliente, sem["id"]).json()["situacao"] == "Aprovada"
        r = cliente.patch(f"/api/sdr/base/fichas/{sem['id']}", json={"codigo": ""})
        assert r.status_code == 422 and "precisa de código" in r.json()["detail"]

    def test_trocar_so_o_codigo_nao_desaprova(self, cliente):
        f = nova(cliente)
        aprovar(cliente, f["id"])
        e = cliente.patch(f"/api/sdr/base/fichas/{f['id']}", json={"codigo": "F9"}).json()
        assert (e["situacao"], e["codigo"]) == ("Aprovada", "F9")
