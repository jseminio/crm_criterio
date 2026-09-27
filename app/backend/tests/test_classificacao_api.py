"""API da classificação da carteira: snapshot mais recente, ISC recalculado, avisos."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import ClassificacaoDoGrupo, Contrato, Empresa, GrupoEconomico
from crm.domain import classificacao as regra
from crm.domain.listas import SituacaoContrato, SituacaoGrupo


@pytest.fixture
def cliente(engine):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as c:
        yield c


def _snap(sessao: Session, grupo: GrupoEconomico, ref: date, receita: str, n: regra.Notas, revisao: int = 1) -> None:
    pontos = regra.score(n)
    letra = regra.classe(pontos)
    sessao.add(ClassificacaoDoGrupo(
        grupo_id=grupo.id, referencia=ref, revisao=revisao, fonte="teste", versao_dos_parametros=regra.PARAMETROS.versao,
        receita_mensal=Decimal(receita), nota_receita=n.receita, nota_rentabilidade=n.rentabilidade,
        complexidade=n.complexidade, disciplina=n.disciplina, risco_tecnico=n.risco, cross_sell=n.cross_sell,
        adimplencia=n.adimplencia, semaforo=n.semaforo, churn=n.churn, score=pontos, classe=letra,
        classe_efetiva=regra.classe_efetiva(letra, n), alerta_de_churn=regra.alerta_de_churn(letra, n),
        em_cobranca=regra.cobranca(n), eixo_de_acao=regra.eixo_de_acao(letra, n),
    ))


def test_sem_snapshot_devolve_vazio(cliente):
    r = cliente.get("/api/carteira/classificacao").json()
    assert r["itens"] == [] and r["isc"] is None


def test_usa_o_snapshot_mais_recente_e_calcula_o_isc(cliente, sessao: Session):
    bom = regra.Notas(receita=5, rentabilidade=5, complexidade=1, disciplina=5, risco=1, cross_sell=5, adimplencia=5, semaforo=1, churn=1)
    ruim = regra.Notas(receita=1, rentabilidade=1, complexidade=5, disciplina=1, risco=5, cross_sell=1, adimplencia=1, semaforo=3, churn=5)
    a = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    b = GrupoEconomico(nome="Beta", situacao=SituacaoGrupo.CLIENTE)
    sessao.add_all([a, b]); sessao.flush()
    sessao.add(Contrato(grupo_id=a.id, situacao=SituacaoContrato.ATIVO, preco_mensal=Decimal("1000")))
    _snap(sessao, a, date(2026, 6, 30), "500", ruim)
    _snap(sessao, a, date(2026, 7, 31), "1000", bom)
    _snap(sessao, b, date(2026, 7, 31), "1000", ruim)
    sessao.commit()

    r = cliente.get("/api/carteira/classificacao").json()
    assert r["referencia"] == "2026-07-31"
    assert len(r["itens"]) == 2
    alfa = next(i for i in r["itens"] if i["grupo_nome"] == "Alfa")
    assert alfa["classe"] == "A" and alfa["sem_contrato_ativo"] is False
    beta = next(i for i in r["itens"] if i["grupo_nome"] == "Beta")
    assert beta["classe"] == "C" and beta["sem_contrato_ativo"] is True
    assert r["por_classe"] == {"A": 1, "C": 1}
    faixa_a = next(f for f in r["distribuicao_por_classe"] if f["classe"] == "A")
    assert faixa_a == {"classe": "A", "minimo": 15, "maximo": 20, "unidades": 1, "percentual": "50.0", "dentro_da_meta": False}
    # metade da receita com tudo no máximo (100) e metade com tudo no mínimo (classe C=20, semáforo 0, churn 0)
    assert Decimal(r["isc"]["componente_classe"]) == Decimal("60")
    assert Decimal(r["isc"]["valor"]) == Decimal("53.30") and r["isc"]["zona"] == "atenção"
    assert any("rentabilidade" in a for a in r["avisos"]) and any("sem contrato ativo" in a for a in r["avisos"])


def test_grupo_fundido_nao_aparece(cliente, sessao: Session):
    n = regra.Notas(receita=3, rentabilidade=3, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=3, semaforo=1, churn=2)
    a = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    f = GrupoEconomico(nome="Fundido", situacao=SituacaoGrupo.FUNDIDO)
    sessao.add_all([a, f]); sessao.flush()
    f.fundido_em_id = a.id
    _snap(sessao, f, date(2026, 7, 31), "100", n)
    sessao.commit()
    assert cliente.get("/api/carteira/classificacao").json()["itens"] == []


def test_na_mesma_referencia_a_revisao_maior_vence(cliente, sessao: Session):
    ruim = regra.Notas(receita=1, rentabilidade=1, complexidade=5, disciplina=1, risco=5, cross_sell=1, adimplencia=1, semaforo=3, churn=5)
    bom = regra.Notas(receita=5, rentabilidade=5, complexidade=1, disciplina=5, risco=1, cross_sell=5, adimplencia=5, semaforo=1, churn=1)
    a = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    sessao.add(a); sessao.flush()
    _snap(sessao, a, date(2026, 7, 31), "1000", ruim, revisao=1)
    _snap(sessao, a, date(2026, 7, 31), "1000", bom, revisao=2)
    sessao.commit()
    itens = cliente.get("/api/carteira/classificacao").json()["itens"]
    assert len(itens) == 1 and itens[0]["classe"] == "A"


def test_traz_as_empresas_do_grupo_com_a_mensalidade(cliente, sessao: Session):
    n = regra.Notas(receita=3, rentabilidade=3, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=3, semaforo=1, churn=2)
    a = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    sessao.add(a); sessao.flush()
    e1 = Empresa(grupo_id=a.id, razao_social="Alfa Comércio Ltda", cnpj="11222333000181")
    e2 = Empresa(grupo_id=a.id, razao_social="Alfa Serviços SA")
    sessao.add_all([e1, e2]); sessao.flush()
    sessao.add(Contrato(grupo_id=a.id, empresa_id=e1.id, situacao=SituacaoContrato.ATIVO, preco_mensal=Decimal("700")))
    _snap(sessao, a, date(2026, 7, 31), "700", n)
    sessao.commit()
    emp = cliente.get("/api/carteira/classificacao").json()["itens"][0]["empresas"]
    assert [e["razao_social"] for e in emp] == ["Alfa Comércio Ltda", "Alfa Serviços SA"]
    assert Decimal(emp[0]["mensalidade"]) == Decimal("700") and emp[1]["mensalidade"] is None


def _grupo_classificado(sessao: Session, receita: str = "1000") -> GrupoEconomico:
    n = regra.Notas(receita=3, rentabilidade=3, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=5, semaforo=1, churn=1)
    g = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    sessao.add(g); sessao.flush()
    _snap(sessao, g, date(2026, 7, 31), receita, n)
    sessao.commit()
    return g


AUTOR = {"autor": "Eduardo Luiz", "motivo": "Reunião de carteira de setembro"}


def test_editar_notas_grava_leitura_nova_e_preserva_a_anterior(cliente, sessao: Session):
    g = _grupo_classificado(sessao)
    r = cliente.post(f"/api/carteira/grupos/{g.id}/notas", json={**AUTOR, "adimplencia": 1, "churn": 5})
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["item"]["em_cobranca"] is True and corpo["item"]["eixo_de_acao"].startswith("Cobrança")
    assert corpo["item"]["notas"]["atribuido_por"] == "Eduardo Luiz"
    assert corpo["item"]["notas"]["complexidade"] == "3.00"  # o que não veio, copia da leitura anterior
    hist = cliente.get(f"/api/carteira/grupos/{g.id}/historico").json()
    assert len(hist) == 2 and hist[1]["fonte"] == "teste" and hist[1]["notas"]["adimplencia"] == "5.00"
    assert cliente.get("/api/carteira/classificacao").json()["itens"][0]["notas"]["churn"] == 5


def test_editar_recalcula_o_isc(cliente, sessao: Session):
    g = _grupo_classificado(sessao)
    antes = Decimal(cliente.get("/api/carteira/classificacao").json()["isc"]["valor"])
    depois = cliente.post(f"/api/carteira/grupos/{g.id}/notas", json={**AUTOR, "semaforo": 3, "churn": 5}).json()["isc"]["valor"]
    assert Decimal(depois) < antes


def test_mudar_complexidade_avisa_que_a_rentabilidade_nao_foi_recalculada(cliente, sessao: Session):
    g = _grupo_classificado(sessao)
    corpo = cliente.post(f"/api/carteira/grupos/{g.id}/notas", json={**AUTOR, "complexidade": 5}).json()
    assert any("rentabilidade não foi recalculada" in a for a in corpo["avisos"])
    assert any("editada à mão" in a for a in cliente.get("/api/carteira/classificacao").json()["avisos"])


def test_duas_edicoes_no_mesmo_dia_viram_revisoes_1_e_2(cliente, sessao: Session):
    g = _grupo_classificado(sessao)
    cliente.post(f"/api/carteira/grupos/{g.id}/notas", json={**AUTOR, "churn": 2})
    cliente.post(f"/api/carteira/grupos/{g.id}/notas", json={**AUTOR, "churn": 3})
    hist = cliente.get(f"/api/carteira/grupos/{g.id}/historico").json()
    assert [h["revisao"] for h in hist[:2]] == [2, 1] and hist[0]["notas"]["churn"] == 3


@pytest.mark.parametrize("corpo,codigo", [
    ({"adimplencia": 6}, 422), ({"semaforo": 4}, 422), ({"churn": 0}, 422),
    ({}, 422), ({"autor": "E", "churn": 2}, 422), ({"motivo": "", "churn": 2}, 422),
])
def test_edicao_invalida_e_recusada(cliente, sessao: Session, corpo, codigo):
    g = _grupo_classificado(sessao)
    r = cliente.post(f"/api/carteira/grupos/{g.id}/notas", json={**AUTOR, **corpo})
    assert r.status_code == codigo
    assert len(cliente.get(f"/api/carteira/grupos/{g.id}/historico").json()) == 1


def test_grupo_fundido_ou_sem_classificacao_e_recusado(cliente, sessao: Session):
    a = GrupoEconomico(nome="Sem", situacao=SituacaoGrupo.CLIENTE)
    f = GrupoEconomico(nome="Fund", situacao=SituacaoGrupo.FUNDIDO)
    sessao.add_all([a, f]); sessao.flush(); f.fundido_em_id = a.id; sessao.commit()
    assert cliente.post(f"/api/carteira/grupos/{a.id}/notas", json={**AUTOR, "churn": 2}).status_code == 409
    assert cliente.post(f"/api/carteira/grupos/{f.id}/notas", json={**AUTOR, "churn": 2}).status_code == 409
    assert cliente.post("/api/carteira/grupos/99999/notas", json={**AUTOR, "churn": 2}).status_code == 404


def test_sugestao_de_porte_calcula_sem_gravar(cliente, sessao: Session):
    g = _grupo_classificado(sessao)
    r = cliente.post("/api/carteira/porte/sugestao", json={"cnpjs_no_escopo": 1})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo == {"calculavel": True, "pontuacao": "0.00", "porte": "Micro", "horas_base": 5, "direcionadores_aplicados": 1}
    # nada foi gravado: o grupo continua sem porte confirmado
    assert cliente.get("/api/carteira/classificacao").json()["itens"][0]["grupo_id"] == g.id


def test_sugestao_de_porte_sem_direcionador_algum_nao_calcula(cliente):
    r = cliente.post("/api/carteira/porte/sugestao", json={})
    assert r.json() == {"calculavel": False, "pontuacao": None, "porte": None, "horas_base": None, "direcionadores_aplicados": 0}


def test_editar_porte_grava_a_volumetria_e_o_porte_confirmado(cliente, sessao: Session):
    g = _grupo_classificado(sessao)
    r = cliente.post(f"/api/carteira/grupos/{g.id}/porte", json={
        "autor": "Eduardo Luiz", "cnpjs_no_escopo": 1, "tem_consolidacao_de_grupo": True, "porte": "Micro",
    })
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["cnpjs_no_escopo"] == 1 and corpo["tem_consolidacao_de_grupo"] is True
    assert corpo["porte"] == "Micro" and corpo["porte_definido_por"] == "Eduardo Luiz"
    assert corpo["porte_definido_em"] is not None


def test_classificacao_expoe_o_porte_ja_salvo_do_grupo(cliente, sessao: Session):
    # A tela de avaliação precisa pré-preencher com o que já foi salvo — sem isso, reavaliar um
    # único direcionador pareceria apagar os outros (mesmo o backend preservando).
    g = _grupo_classificado(sessao)
    r = cliente.get("/api/carteira/classificacao").json()
    vazio = r["itens"][0]["porte"]
    assert vazio == {
        "documentos_fiscais_mes": None, "lancamentos_contabeis_mes": None, "pagamentos_mes": None,
        "contas_bancarias": None, "conciliacoes_cartao_mes": None, "empregados_clt": None,
        "admissoes_desligamentos_mes": None, "cnpjs_no_escopo": None, "tomadores_de_servico": None,
        "servicos_contratados_alem_do_primeiro": 0, "tem_consolidacao_de_grupo": False, "e_auditada": False,
        "porte": None, "porte_definido_por": None, "porte_definido_em": None,
    }

    cliente.post(f"/api/carteira/grupos/{g.id}/porte", json={
        "autor": "Eduardo Luiz", "cnpjs_no_escopo": 4, "empregados_clt": 30, "porte": "Médio",
    })
    depois = cliente.get("/api/carteira/classificacao").json()["itens"][0]["porte"]
    assert depois["cnpjs_no_escopo"] == 4 and depois["empregados_clt"] == 30
    assert depois["porte"] == "Médio" and depois["porte_definido_por"] == "Eduardo Luiz"


def test_editar_porte_so_carimba_definido_por_quando_o_porte_muda(cliente, sessao: Session):
    g = _grupo_classificado(sessao)
    primeiro = cliente.post(f"/api/carteira/grupos/{g.id}/porte", json={
        "autor": "Eduardo Luiz", "cnpjs_no_escopo": 1, "porte": "Micro",
    }).json()
    # edita só a volumetria, sem tocar no porte: o carimbo não deve mudar
    segundo = cliente.post(f"/api/carteira/grupos/{g.id}/porte", json={
        "autor": "Outra Pessoa", "cnpjs_no_escopo": 2,
    }).json()
    assert segundo["cnpjs_no_escopo"] == 2 and segundo["porte"] == "Micro"
    assert segundo["porte_definido_por"] == "Eduardo Luiz"
    # Comparado sem fuso: o SQLite de teste não preserva tzinfo ao reler do banco (limitação do
    # dialeto, não do código) — o primeiro vem do objeto recém-atribuído, ainda com o "Z".
    sem_fuso = lambda s: datetime.fromisoformat(s).replace(tzinfo=None)  # noqa: E731
    assert sem_fuso(segundo["porte_definido_em"]) == sem_fuso(primeiro["porte_definido_em"])


def test_editar_porte_nao_exige_classificacao_carregada(cliente, sessao: Session):
    # Diferente de /notas: porte não depende de a carteira já ter sido carregada.
    g = GrupoEconomico(nome="Sem classificação", situacao=SituacaoGrupo.PROSPECT)
    sessao.add(g); sessao.commit()
    r = cliente.post(f"/api/carteira/grupos/{g.id}/porte", json={"autor": "Eduardo Luiz", "documentos_fiscais_mes": 100})
    assert r.status_code == 200, r.text
    assert r.json()["documentos_fiscais_mes"] == 100


def test_editar_porte_preserva_direcionador_nao_enviado_na_segunda_edicao(cliente, sessao: Session):
    g = _grupo_classificado(sessao)
    cliente.post(f"/api/carteira/grupos/{g.id}/porte", json={
        "autor": "Eduardo Luiz", "cnpjs_no_escopo": 4, "empregados_clt": 30,
    })
    # reavalia só um direcionador — os outros, ausentes do corpo, não podem virar None
    r = cliente.post(f"/api/carteira/grupos/{g.id}/porte", json={"autor": "Eduardo Luiz", "cnpjs_no_escopo": 5})
    corpo = r.json()
    assert corpo["cnpjs_no_escopo"] == 5
    assert corpo["empregados_clt"] == 30


def test_editar_porte_de_grupo_fundido_ou_inexistente_e_recusado(cliente, sessao: Session):
    a = GrupoEconomico(nome="Sem", situacao=SituacaoGrupo.CLIENTE)
    f = GrupoEconomico(nome="Fund", situacao=SituacaoGrupo.FUNDIDO)
    sessao.add_all([a, f]); sessao.flush(); f.fundido_em_id = a.id; sessao.commit()
    assert cliente.post(f"/api/carteira/grupos/{f.id}/porte", json={"autor": "Eduardo Luiz", "porte": "Micro"}).status_code == 409
    assert cliente.post("/api/carteira/grupos/99999/porte", json={"autor": "Eduardo Luiz", "porte": "Micro"}).status_code == 404


def test_retrato_traz_o_quadro_geral_com_travados(cliente, sessao: Session):
    bom = regra.Notas(receita=5, rentabilidade=5, complexidade=1, disciplina=5, risco=1, cross_sell=5, adimplencia=5, semaforo=1, churn=1)
    ruim = regra.Notas(receita=1, rentabilidade=1, complexidade=5, disciplina=1, risco=5, cross_sell=1, adimplencia=1, semaforo=3, churn=5)
    a = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
    b = GrupoEconomico(nome="Beta", situacao=SituacaoGrupo.CLIENTE)
    sessao.add_all([a, b]); sessao.flush()
    _snap(sessao, a, date(2026, 7, 31), "3000", bom)
    _snap(sessao, b, date(2026, 7, 31), "1000", ruim)
    sessao.commit()
    r = cliente.get("/api/carteira/classificacao").json()["retrato"]
    assert r["unidades"] == 2 and Decimal(r["receita_total"]) == Decimal("4000")
    assert r["grupos_travados"] == 1 and Decimal(r["receita_travada"]) == Decimal("1000")
    assert Decimal(r["percentual_travado"]) == Decimal("25.00")


def test_retrato_e_none_sem_classificacao(cliente):
    assert cliente.get("/api/carteira/classificacao").json()["retrato"] is None


class TestRevisaoMensal:
    def _grupo_classificado_hoje(self, sessao: Session, receita="1000") -> GrupoEconomico:
        n = regra.Notas(receita=3, rentabilidade=3, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=5, semaforo=1, churn=1)
        g = GrupoEconomico(nome="Alfa", situacao=SituacaoGrupo.CLIENTE)
        sessao.add(g); sessao.flush()
        _snap(sessao, g, date(2026, 7, 31), receita, n)
        sessao.commit()
        return g

    def test_sem_revisao_a_lista_vem_vazia(self, cliente):
        assert cliente.get("/api/carteira/revisoes").json() == []

    def test_registra_a_revisao_do_mes_atual_com_os_numeros_de_hoje(self, cliente, sessao: Session):
        self._grupo_classificado_hoje(sessao)
        hoje = date.today()
        r = cliente.post("/api/carteira/revisoes", json={"autor": "Eduardo Luiz"})
        assert r.status_code == 201, r.text
        corpo = r.json()
        assert corpo["mes_de_referencia"] == f"{hoje.year:04d}-{hoje.month:02d}-01"
        assert corpo["registrada_por"] == "Eduardo Luiz"
        assert corpo["grupos"] == 1 and Decimal(corpo["receita_total"]) == Decimal("1000")
        listado = cliente.get("/api/carteira/revisoes").json()
        assert len(listado) == 1 and listado[0]["id"] == corpo["id"] and listado[0]["registrada_por"] == "Eduardo Luiz"

    def test_uma_por_mes_recusa_a_segunda(self, cliente, sessao: Session):
        self._grupo_classificado_hoje(sessao)
        cliente.post("/api/carteira/revisoes", json={"autor": "Eduardo Luiz"})
        r = cliente.post("/api/carteira/revisoes", json={"autor": "Outra Pessoa"})
        assert r.status_code == 409
        assert "Eduardo Luiz" in r.json()["detail"]
        assert len(cliente.get("/api/carteira/revisoes").json()) == 1

    def test_editar_o_mes_corrige_so_o_rotulo(self, cliente, sessao: Session):
        self._grupo_classificado_hoje(sessao)
        criada = cliente.post("/api/carteira/revisoes", json={"autor": "Eduardo Luiz"}).json()
        r = cliente.patch(f"/api/carteira/revisoes/{criada['id']}/mes", json={"mes": "2026-07"})
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["mes_de_referencia"] == "2026-07-01"
        assert Decimal(corpo["isc_valor"]) == Decimal(criada["isc_valor"])  # números congelados não mudam

    def test_editar_para_um_mes_ja_usado_e_recusado(self, cliente, sessao: Session):
        self._grupo_classificado_hoje(sessao)
        primeira = cliente.post("/api/carteira/revisoes", json={"autor": "Eduardo Luiz"}).json()
        cliente.patch(f"/api/carteira/revisoes/{primeira['id']}/mes", json={"mes": "2026-07"})
        g2 = GrupoEconomico(nome="Beta", situacao=SituacaoGrupo.CLIENTE)
        sessao.add(g2); sessao.flush()
        n = regra.Notas(receita=3, rentabilidade=3, complexidade=3, disciplina=3, risco=3, cross_sell=3, adimplencia=5, semaforo=1, churn=1)
        _snap(sessao, g2, date(2026, 7, 31), "500", n)
        sessao.commit()
        segunda = cliente.post("/api/carteira/revisoes", json={"autor": "Eduardo Luiz"}).json()
        r = cliente.patch(f"/api/carteira/revisoes/{segunda['id']}/mes", json={"mes": "2026-07"})
        assert r.status_code == 409

    def test_mes_invalido_e_recusado(self, cliente, sessao: Session):
        self._grupo_classificado_hoje(sessao)
        criada = cliente.post("/api/carteira/revisoes", json={"autor": "Eduardo Luiz"}).json()
        assert cliente.patch(f"/api/carteira/revisoes/{criada['id']}/mes", json={"mes": "2026-13"}).status_code == 422
        assert cliente.patch(f"/api/carteira/revisoes/{criada['id']}/mes", json={"mes": "26-07"}).status_code == 422
        assert cliente.patch("/api/carteira/revisoes/99999/mes", json={"mes": "2026-07"}).status_code == 404

    def test_sem_classificacao_e_recusado(self, cliente):
        assert cliente.post("/api/carteira/revisoes", json={"autor": "Eduardo Luiz"}).status_code == 409
