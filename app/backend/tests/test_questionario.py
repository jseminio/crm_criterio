"""Questionário do site → cliente e oportunidade no CRM (pedido de Eduardo, 01/10/2026).

Dados fictícios. O Supabase é simulado: nenhum teste sai da máquina.
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime

import httpx2 as httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import Empresa, GrupoEconomico, Oportunidade, PessoaContato, QuestionarioRecebido
from crm.domain.listas import Origem, Situacao, SituacaoGrupo
from crm.questionario.fonte import BuscaFalhou, ConfiguracaoDoQuestionario, FonteDaFuncao, FonteSupabase, ler_configuracao
from crm.questionario.leitura import ler

CNPJ_ALFA = "12345678000190"

# A amostra aprovada: Pequeno, pontuação 1,33; complexidade 2 (auditoria); risco 2 (obrigação atrasada).
RESPOSTAS_ALFA = {
    "razao_social": "Exemplo Alfa Comércio Ltda", "cnpj": "12.345.678/0001-90", "nome_fantasia": "Exemplo Alfa",
    "servicos": ["Contábil", "Fiscal"], "regime_tributario": ["Lucro Presumido"],
    "vol": {"notas_emitidas": "40", "notas_recebidas": "80", "lancamentos": "250", "pagamentos": "90",
            "contas_bancarias": "2", "empregados_clt": "18", "cnpjs": "1"},
    "auditada": "Sim", "obrig_atraso": "Sim",
}


def linha(id_="q-1", cnpj="12.345.678/0001-90", respostas=None, **extra):
    return {
        "id": id_, "criado_em": "2026-09-30T19:40:00+00:00", "versao_questionario": "BPO Full 2026 v6",
        "razao_social": "Exemplo Alfa Comércio Ltda", "nome_fantasia": "Exemplo Alfa", "cnpj": cnpj,
        "contato_nome": "Ana Souza", "contato_cargo": "Diretora Financeira", "contato_celular": "(21) 90000-0000",
        "contato_email": "ana@exemplo.com.br", "servicos": ["Contábil", "Fiscal"],
        "respostas": respostas if respostas is not None else RESPOSTAS_ALFA,
        "avaliacao": {"porte_sugerido": "Pequeno"}, "porte_sugerido": "Pequeno",
        "pdf_base64": base64.b64encode(b"%PDF-1.4 ficticio").decode(), **extra,
    }


class FonteFalsa:
    def __init__(self, linhas=(), falhar_marca=False, falhar_busca=False):
        self.linhas = list(linhas)
        self.marcados: list[str] = []
        self.falhar_marca = falhar_marca
        self.falhar_busca = falhar_busca

    def novos(self):
        if self.falhar_busca:
            raise BuscaFalhou("O Supabase recusou a chave (HTTP 401).")
        return [l for l in self.linhas if l["id"] not in self.marcados]

    def marcar_importado(self, externo_id, quando):
        if self.falhar_marca:
            raise BuscaFalhou("o Supabase não marcou (HTTP 500).")
        self.marcados.append(externo_id)


@pytest.fixture
def fonte():
    return FonteFalsa([linha()])


@pytest.fixture
def cliente(engine, fonte):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, fonte_de_questionarios=lambda: fonte)) as c:
        yield c


def _buscar(cliente):
    r = cliente.post("/api/questionarios/buscar")
    assert r.status_code == 200, r.text
    return r.json()


class TestLeitura:
    def test_amostra_aprovada_pela_regua_do_crm(self):
        l = ler(RESPOSTAS_ALFA, recebido_em=date(2026, 9, 30))
        assert l.volumetria == {
            "documentos_fiscais_mes": 120, "lancamentos_contabeis_mes": 250, "pagamentos_mes": 90,
            "contas_bancarias": 2, "conciliacoes_cartao_mes": None, "empregados_clt": 18,
            "admissoes_desligamentos_mes": None, "cnpjs_no_escopo": 1, "tomadores_de_servico": None,
        }
        assert (l.porte, l.pontuacao, l.horas_base) == ("Pequeno", "1.33", 10)
        assert (l.fatores_complexidade, l.nota_complexidade) == (["auditoria"], 2)
        assert (l.fatores_risco, l.nota_risco) == (["obrigacao_atrasada"], 2)
        assert ("Obrigação acessória entregue com atraso nos últimos 3 meses", "Fiscal") in l.pontos_de_atencao

    def test_soma_so_o_que_veio_e_arredonda_como_o_formulario(self):
        l = ler({"vol": {"admissoes": "2.5", "desligamentos": ""}}, recebido_em=date(2026, 9, 30))
        assert l.volumetria["admissoes_desligamentos_mes"] == 3  # 2,5 sobe, como o Math.round
        assert l.volumetria["documentos_fiscais_mes"] is None
        assert l.porte is not None

    def test_sem_nenhum_volume_nao_ha_porte(self):
        assert ler({}, recebido_em=date(2026, 9, 30)).porte is None

    def test_certificado_vencendo_conta_a_partir_do_envio(self):
        r = {"certificado": "e-CNPJ A1", "certificado_validade": "2026-11-20"}
        assert "certificado_vencendo" in ler(r, recebido_em=date(2026, 9, 30)).fatores_risco  # 51 dias
        assert "certificado_vencendo" not in ler(r, recebido_em=date(2026, 9, 1)).fatores_risco  # 80 dias

    def test_fatores_de_complexidade_e_risco(self):
        r = {"relatorios": ["Consolidação", "DRE por centro/projeto"], "plano_contas": "Sim", "auditada": "Sim",
             "regime_tributario": ["Lucro Real", "Simples Nacional", "Outro"], "passivos": "Sim",
             "passivos_tipos": ["Parcelamento", "Auto de infração"], "parcelamento_situacao": "Em atraso, ou já quebrado antes"}
        l = ler(r, recebido_em=date(2026, 9, 30))
        assert l.fatores_complexidade == ["holding", "centros_de_custo", "plano_de_contas", "auditoria", "regimes",
                                          "parcelamento_complexidade"]
        assert l.nota_complexidade == 5
        assert l.fatores_risco == ["auto_de_infracao", "parcelamento_atraso"] and l.nota_risco == 3
        assert l.tem_consolidacao_de_grupo and l.e_auditada


class TestFonteSupabase:
    def _fonte(self, chave, resposta):
        pedidos = []

        def responder(pedido):
            pedidos.append(pedido)
            return resposta(pedido)

        http = httpx.Client(transport=httpx.MockTransport(responder))
        return FonteSupabase(ConfiguracaoDoQuestionario("https://exemplo.supabase.co", chave), http), pedidos

    def test_busca_so_os_nao_importados_com_a_chave_secreta(self):
        f, pedidos = self._fonte("sb_secret_abc", lambda p: httpx.Response(200, json=[{"id": "x"}]))
        assert f.novos() == [{"id": "x"}]
        p = pedidos[0]
        assert p.url.params["importado_crm_em"] == "is.null" and p.url.params["order"] == "criado_em.asc"
        assert p.headers["apikey"] == "sb_secret_abc" and "authorization" not in p.headers

    def test_chave_antiga_jwt_vai_tambem_no_authorization(self):
        f, pedidos = self._fonte("eyJabc", lambda p: httpx.Response(200, json=[]))
        f.novos()
        assert pedidos[0].headers["authorization"] == "Bearer eyJabc"

    def test_marca_importado_so_naquela_linha(self):
        f, pedidos = self._fonte("sb_secret_abc", lambda p: httpx.Response(204))
        f.marcar_importado("q-1", datetime(2026, 10, 1, 9, 0))
        assert pedidos[0].method == "PATCH" and pedidos[0].url.params["id"] == "eq.q-1"

    def test_chave_recusada_diz_o_que_fazer_sem_mostrar_a_chave(self):
        f, _ = self._fonte("sb_secret_abc", lambda p: httpx.Response(401))
        with pytest.raises(BuscaFalhou) as erro:
            f.novos()
        assert "CRM_QUESTIONARIO_CHAVE" in str(erro.value) and "sb_secret_abc" not in str(erro.value)
        assert "sb_secret" not in repr(ConfiguracaoDoQuestionario("u", "sb_secret_abc"))

    def test_sem_configuracao_nao_ha_fonte(self, monkeypatch):
        assert ler_configuracao() is None
        monkeypatch.setenv("CRM_QUESTIONARIO_URL", "https://exemplo.supabase.co/")
        monkeypatch.setenv("CRM_QUESTIONARIO_CHAVE", "sb_secret_abc")
        assert ler_configuracao().url == "https://exemplo.supabase.co"


URL_DA_FUNCAO = "https://exemplo.supabase.co/functions/v1/questionarios-crm"


class TestFonteDaFuncao:
    """O banco do site é do Lovable e a chave secreta não fica à vista: a função do site entrega os
    pendentes e marca os importados, com a senha combinada (01/10/2026)."""

    def _fonte(self, resposta, senha="senha-de-teste"):
        pedidos = []

        def responder(pedido):
            pedidos.append(pedido)
            return resposta(pedido)

        http = httpx.Client(transport=httpx.MockTransport(responder))
        return FonteDaFuncao(ConfiguracaoDoQuestionario(URL_DA_FUNCAO, senha), http), pedidos

    def test_busca_com_a_senha_no_cabecalho(self):
        f, pedidos = self._fonte(lambda p: httpx.Response(200, json=[{"id": "x"}]))
        assert f.novos() == [{"id": "x"}]
        p = pedidos[0]
        assert p.method == "GET" and str(p.url) == URL_DA_FUNCAO
        assert p.headers["x-crm-senha"] == "senha-de-teste" and "apikey" not in p.headers

    def test_marca_importado_com_post(self):
        f, pedidos = self._fonte(lambda p: httpx.Response(204))
        f.marcar_importado("q-1", datetime(2026, 10, 1, 9, 0))
        p = pedidos[0]
        assert p.method == "POST" and json.loads(p.content) == {"id": "q-1", "importado_crm_em": "2026-10-01T09:00:00"}

    def test_senha_recusada_diz_o_que_fazer_sem_mostrar_a_senha(self):
        f, _ = self._fonte(lambda p: httpx.Response(401), senha="segredo-123")
        with pytest.raises(BuscaFalhou) as erro:
            f.novos()
        assert "CRM_QUESTIONARIO_SENHA" in str(erro.value) and "segredo-123" not in str(erro.value)
        with pytest.raises(BuscaFalhou):
            f.marcar_importado("q-1", datetime(2026, 10, 1))

    @pytest.mark.parametrize("resposta, trecho", [
        (lambda p: httpx.Response(500), "HTTP 500"),
        (lambda p: httpx.Response(200, json={"erro": "x"}), "não é a lista"),
    ])
    def test_resposta_estranha(self, resposta, trecho):
        f, _ = self._fonte(resposta)
        with pytest.raises(BuscaFalhou) as erro:
            f.novos()
        assert trecho in str(erro.value)

    def test_o_endereco_escolhe_o_caminho(self, monkeypatch):
        from crm.api.questionarios import fonte_real
        monkeypatch.setenv("CRM_QUESTIONARIO_CHAVE", "senha-de-teste")
        monkeypatch.setenv("CRM_QUESTIONARIO_URL", URL_DA_FUNCAO)
        assert isinstance(fonte_real(), FonteDaFuncao)
        monkeypatch.setenv("CRM_QUESTIONARIO_URL", "https://exemplo.supabase.co")
        assert isinstance(fonte_real(), FonteSupabase)


class TestBuscar:
    def test_cliente_novo_vira_grupo_empresa_contato_e_oportunidade(self, cliente, sessao, fonte):
        r = _buscar(cliente)
        assert r["avisos"] == [] and len(r["novos"]) == 1
        q = r["novos"][0]
        assert q["situacao"] == "Importado" and q["cliente_novo"] is True and q["porte_crm"] == "Pequeno"
        assert fonte.marcados == ["q-1"]

        o = sessao.get(Oportunidade, q["oportunidade_id"])
        assert (o.nome, o.situacao, o.origem, o.data_colocacao) == ("Exemplo Alfa", Situacao.ENVIAR_PROPOSTA, Origem.QUESTIONARIO, date(2026, 9, 30))
        assert (o.documentos_fiscais_mes, o.lancamentos_contabeis_mes, o.conciliacoes_cartao_mes) == (120, 250, None)
        assert o.origem_da_volumetria["documentos_fiscais_mes"] == "Questionário"
        assert "conciliacoes_cartao_mes" not in o.origem_da_volumetria
        assert (o.complexidade, o.risco_tecnico, o.e_auditada, o.servicos_contratados_alem_do_primeiro) == (2, 2, True, 1)
        assert o.porte is None  # sugestão não é confirmação
        empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == CNPJ_ALFA))
        assert empresa.grupo_id == o.grupo_id and empresa.regime_tributario == "Lucro Presumido"
        assert sessao.get(GrupoEconomico, o.grupo_id).situacao is SituacaoGrupo.PROSPECT
        contato = sessao.scalar(sa.select(PessoaContato).where(PessoaContato.nome == "Ana Souza"))
        assert (contato.nome, contato.email) == ("Ana Souza", "ana@exemplo.com.br")
        assert [v.empresa_id for v in contato.vinculos] == [empresa.id]

    def test_buscar_de_novo_nao_duplica(self, cliente, sessao):
        _buscar(cliente)
        assert _buscar(cliente)["novos"] == []
        assert sessao.scalar(sa.select(sa.func.count()).select_from(Oportunidade)) == 1

    def test_marca_que_falhou_e_refeita_sem_importar_de_novo(self, cliente, sessao, fonte):
        fonte.falhar_marca = True
        r = _buscar(cliente)
        assert len(r["novos"]) == 1 and "só tenta marcar de novo" in r["avisos"][0]
        fonte.falhar_marca = False
        r = _buscar(cliente)
        assert r["novos"] == [] and fonte.marcados == ["q-1"]
        assert sessao.scalar(sa.select(sa.func.count()).select_from(Oportunidade)) == 1
        sessao.expire_all()
        assert sessao.scalars(sa.select(QuestionarioRecebido)).one().marcado_na_origem_em is not None

    def test_empresa_ja_no_crm_entra_no_grupo_dela(self, cliente, sessao):
        g = GrupoEconomico(nome="Grupo Exemplo Alfa", situacao=SituacaoGrupo.CLIENTE)
        sessao.add(g)
        sessao.flush()
        sessao.add(Empresa(grupo_id=g.id, razao_social="Exemplo Alfa Comércio Ltda", cnpj=CNPJ_ALFA))
        sessao.commit()
        q = _buscar(cliente)["novos"][0]
        assert q["cliente_novo"] is False and q["grupo_nome"] == "Grupo Exemplo Alfa"
        assert q["o_que_fez"] == 'Entrou no grupo "Grupo Exemplo Alfa"; criou a oportunidade e o contato.'
        assert sessao.get(Oportunidade, q["oportunidade_id"]).grupo_id == g.id

    def test_grupo_fundido_leva_ao_que_ficou(self, cliente, sessao):
        ficou = GrupoEconomico(nome="Ficou", situacao=SituacaoGrupo.CLIENTE)
        sessao.add(ficou)
        sessao.flush()
        saiu = GrupoEconomico(nome="Saiu", situacao=SituacaoGrupo.CLIENTE, fundido_em_id=ficou.id)
        sessao.add(saiu)
        sessao.flush()
        sessao.add(Empresa(grupo_id=saiu.id, razao_social="Exemplo Alfa", cnpj=CNPJ_ALFA))
        sessao.commit()
        assert _buscar(cliente)["novos"][0]["grupo_nome"] == "Ficou"

    def test_homonimo_sem_cnpj_e_avisado(self, cliente, sessao):
        sessao.add(GrupoEconomico(nome="exemplo alfa", situacao=SituacaoGrupo.PROSPECT))
        sessao.commit()
        q = _buscar(cliente)["novos"][0]
        assert q["cliente_novo"] is True and "Fundir grupos" in q["o_que_fez"]

    def test_linha_invalida_fica_de_fora_e_nao_e_marcada(self, cliente, sessao, fonte):
        fonte.linhas = [linha("q-ruim", cnpj="123"), linha("q-2")]
        r = _buscar(cliente)
        assert [q["razao_social"] for q in r["novos"]] == ["Exemplo Alfa Comércio Ltda"]
        assert "q-ruim ficou de fora" in r["avisos"][0]
        assert fonte.marcados == ["q-2"]

    def test_sem_configuracao_diz_o_que_preencher(self, engine):
        fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        with TestClient(criar_app(fabrica, fonte_de_questionarios=lambda: None)) as c:
            r = c.post("/api/questionarios/buscar")
        assert r.status_code == 409 and "CRM_QUESTIONARIO_URL" in r.json()["detail"]

    def test_falha_do_supabase_vira_mensagem_clara(self, cliente, fonte):
        fonte.falhar_busca = True
        r = cliente.post("/api/questionarios/buscar")
        assert r.status_code == 502 and "HTTP 401" in r.json()["detail"]


class TestPrecisaDeVoce:
    @pytest.fixture
    def em_aberto(self, sessao: Session) -> Oportunidade:
        g = GrupoEconomico(nome="Grupo Exemplo Alfa", situacao=SituacaoGrupo.PROSPECT)
        sessao.add(g)
        sessao.flush()
        sessao.add(Empresa(grupo_id=g.id, razao_social="Exemplo Alfa", cnpj=CNPJ_ALFA))
        o = Oportunidade(grupo_id=g.id, nome="Alfa BPO", situacao=Situacao.EM_AVALIACAO, documentos_fiscais_mes=500,
                         origem_da_volumetria={"documentos_fiscais_mes": "Entrevista"})
        sessao.add(o)
        sessao.commit()
        return o

    def test_nao_duplica_e_pergunta(self, cliente, sessao, em_aberto):
        q = _buscar(cliente)["novos"][0]
        assert q["situacao"] == "Precisa de você" and q["oportunidade_id"] is None
        assert q["oportunidade_em_aberto_id"] == em_aberto.id and "Alfa BPO" in q["o_que_fez"]
        assert sessao.scalar(sa.select(sa.func.count()).select_from(Oportunidade)) == 1
        assert cliente.get("/api/questionarios").json()[0]["situacao"] == "Precisa de você"

    def test_anexar_preenche_so_o_vazio(self, cliente, sessao, em_aberto):
        q = _buscar(cliente)["novos"][0]
        r = cliente.post(f"/api/questionarios/{q['id']}/resolver", json={"acao": "anexar"})
        assert r.status_code == 200 and r.json()["situacao"] == "Importado"
        sessao.expire_all()
        o = sessao.get(Oportunidade, em_aberto.id)
        assert o.documentos_fiscais_mes == 500 and o.origem_da_volumetria["documentos_fiscais_mes"] == "Entrevista"
        assert o.lancamentos_contabeis_mes == 250 and o.origem_da_volumetria["lancamentos_contabeis_mes"] == "Questionário"
        assert o.complexidade == 2
        assert "preencheu 7 campo(s) vazio(s)" in r.json()["o_que_fez"]  # 5 volumes + complexidade + risco
        assert cliente.post(f"/api/questionarios/{q['id']}/resolver", json={"acao": "criar"}).status_code == 409

    def test_criar_nova_ao_lado(self, cliente, sessao, em_aberto):
        q = _buscar(cliente)["novos"][0]
        r = cliente.post(f"/api/questionarios/{q['id']}/resolver", json={"acao": "criar"}).json()
        assert r["oportunidade_id"] not in (None, em_aberto.id)
        assert sessao.scalar(sa.select(sa.func.count()).select_from(Oportunidade)) == 2

    def test_oportunidade_fechada_nao_trava(self, cliente, sessao, em_aberto):
        em_aberto.situacao = Situacao.RECUSADA
        sessao.commit()
        assert _buscar(cliente)["novos"][0]["situacao"] == "Importado"


class TestPdfEDetalhe:
    def test_pdf_abre_como_pdf(self, cliente):
        q = _buscar(cliente)["novos"][0]
        r = cliente.get(f"/api/questionarios/{q['id']}/pdf")
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
        assert r.content == b"%PDF-1.4 ficticio"

    def test_sem_pdf_diz_isso(self, cliente, fonte):
        fonte.linhas = [linha(pdf_base64=None)]
        q = _buscar(cliente)["novos"][0]
        assert q["tem_pdf"] is False
        assert cliente.get(f"/api/questionarios/{q['id']}/pdf").status_code == 404

    def test_oportunidade_mostra_o_questionario(self, cliente):
        q = _buscar(cliente)["novos"][0]
        d = cliente.get(f"/api/oportunidades/{q['oportunidade_id']}/questionario").json()
        assert (d["porte_crm"], d["pontuacao"], d["horas_base"]) == ("Pequeno", "1.33", 10)
        assert (d["notas_emitidas"], d["notas_recebidas"]) == (40, 80)
        assert d["fatores_complexidade"] == [{"id": "auditoria", "rotulo": "auditoria externa"}]
        assert d["fatores_risco"][0]["rotulo"] == "obrigação acessória atrasada (3 meses)"
        assert d["contato_nome"] == "Ana Souza" and d["tem_pdf"] is True

    def test_oportunidade_sem_questionario(self, cliente, sessao):
        g = GrupoEconomico(nome="X", situacao=SituacaoGrupo.PROSPECT)
        sessao.add(g)
        sessao.flush()
        o = Oportunidade(grupo_id=g.id, nome="X", situacao=Situacao.ENVIAR_PROPOSTA)
        sessao.add(o)
        sessao.commit()
        assert cliente.get(f"/api/oportunidades/{o.id}/questionario").json() is None
