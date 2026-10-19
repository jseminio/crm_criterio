"""PDF assinado no CRM, com a conferência do que a IA leu (amostra aprovada por Eduardo em 18/10/2026)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace as NS

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.agente.sdr import AgenteFalhou, Uso
from crm.api.app import criar_app
from crm.db.modelos import Contrato, DocumentoAnexado, Empresa, GrupoEconomico, Oportunidade, Perfil, Usuario
from crm.documento import leitura as regra
from crm.domain.listas import Situacao, SituacaoContrato

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}
PDF = b"%PDF-1.7\n contrato assinado de teste"


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


def _campo(valor: str, pagina: int = 1, trecho: str = "") -> dict:
    return {"valor": valor, "pagina": pagina if valor else 0, "trecho": trecho}


def lido(**campos: str) -> dict:
    base = {n: _campo("") for n in regra.CAMPOS}
    base.update({n: _campo(v, 2, f"trecho de {n}") for n, v in campos.items()})
    return {"tipo": "contrato", "razao_social": "Cliente A Ltda", "cnpjs": ["11222333000181"], "campos": base}


class Leitor:
    def __init__(self, resposta: dict | Exception) -> None:
        self.resposta, self.chamadas = resposta, 0

    def __call__(self, pdf: bytes, nome: str) -> dict:
        self.chamadas += 1
        assert pdf.startswith(b"%PDF")
        if isinstance(self.resposta, Exception):
            raise self.resposta
        return self.resposta


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        leitura = Perfil(nome="Contratos", permissoes=["contratos.ver"])
        g, outro = GrupoEconomico(nome="Cliente A"), GrupoEconomico(nome="Cliente B")
        s.add_all([leitura, g, outro])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=leitura.id))
        e = Empresa(grupo_id=g.id, razao_social="Cliente A Ltda", cnpj="11222333000181")
        s.add(e)
        s.flush()
        op = Oportunidade(grupo_id=g.id, empresa_id=e.id, nome="BPO", servico="BPO Financeiro", situacao=Situacao.ACEITA,
                          preco_mensal=D("7000"))
        s.add(op)
        s.flush()
        aguardando = Contrato(grupo_id=g.id, oportunidade_id=op.id, recorrente=True, preco_mensal=D("7000"),
                              base_do_valor="liquido", situacao=SituacaoContrato.AGUARDANDO_ASSINATURA)
        antigo = Contrato(grupo_id=g.id, recorrente=True, preco_mensal=D("5000"), anterior_ao_crm=True,
                          situacao=SituacaoContrato.ATIVO)
        s.add_all([aguardando, antigo])
        s.commit()
        return {"aguardando": aguardando.id, "antigo": antigo.id, "grupo": g.id, "outro": outro.id, "op": op.id,
                "empresa": e.id}


def _cliente(engine, leitor):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    return TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar, buscar_ipca=lambda de, ate: {},
                                leitor_de_documentos=leitor))


def _anexar(c, conteudo=PDF, **params):
    return c.post("/api/documentos", params={"nome_arquivo": "contrato assinado.pdf", **params}, content=conteudo,
                  headers=ADMIN)


def test_anexa_le_e_mostra_a_conferencia_lado_a_lado(engine, ids):
    leitor = Leitor(lido(data_assinatura="2026-10-14", preco_mensal="7000.00", base_do_valor="bruto",
                         multa_rescisoria="2 parcelas mensais", signatario="Fulano de Tal"))
    with _cliente(engine, leitor) as c:
        r = _anexar(c, contrato_id=ids["aguardando"])
        assert r.status_code == 201 and r.json()["leitura_situacao"] == "pendente"
        d = c.get(f"/api/documentos/{r.json()['id']}", headers=ADMIN).json()
    assert leitor.chamadas == 1 and d["leitura_situacao"] == "lida" and d["tipo"] == "contrato"
    linhas = {l["campo"]: l for l in d["conferencia"]}
    assert linhas["preco_mensal"]["situacao"] == "igual" and not linhas["preco_mensal"]["gravavel"]
    assert linhas["base_do_valor"]["situacao"] == "diferente" and linhas["base_do_valor"]["gravavel"]
    assert not linhas["base_do_valor"]["marcar"]  # diferente nunca vem marcado
    assert linhas["data_assinatura"]["situacao"] == "novo" and linhas["data_assinatura"]["marcar"]
    assert linhas["multa_rescisoria"]["pagina"] == 2 and linhas["multa_rescisoria"]["trecho"]
    assert linhas["aviso_previo_dias"]["situacao"] == "nao_achou"
    assert linhas["cnpj"]["situacao"] == "novo" and linhas["cnpj"]["lido"] == "11222333000181"


def test_conferir_grava_so_o_marcado_e_o_documento_guarda_numero_e_data(engine, ids):
    leitor = Leitor(lido(numero="CONT CCE RJ1 102.2026", data_assinatura="2026-10-14", base_do_valor="bruto",
                         multa_rescisoria="2 parcelas", aviso_previo_dias="30", signatario="Fulano"))
    with _cliente(engine, leitor) as c:
        doc = _anexar(c, contrato_id=ids["aguardando"]).json()["id"]
        r = c.post(f"/api/documentos/{doc}/conferir", headers=ADMIN, json={
            "campos": ["numero", "data_assinatura", "multa_rescisoria", "aviso_previo_dias", "cnpj"],
            "valores": {"multa_rescisoria": "2 parcelas mensais"}})
        assert r.status_code == 200, r.text
        assert r.json()["leitura_situacao"] == "conferida" and r.json()["conferido_por"] == "Eduardo Luiz"
        contrato = c.get(f"/api/contratos/{ids['aguardando']}", headers=ADMIN).json()
    assert contrato["data_inicio"] == "2026-10-14" and contrato["multa_rescisoria"] == "2 parcelas mensais"
    assert contrato["aviso_previo_dias"] == 30 and contrato["empresa_id"] == ids["empresa"]
    assert contrato["base_do_valor"] == "liquido" and contrato["signatario"] is None  # não marcados
    with Session(engine) as s:
        d = s.get(DocumentoAnexado, doc)
        assert d.numero_no_documento == "CONT CCE RJ1 102.2026" and d.data_do_documento == date(2026, 10, 14)


def test_contrato_assinado_nao_muda_preco_pela_conferencia(engine, ids):
    with _cliente(engine, Leitor(lido(preco_mensal="5500.00", data_assinatura="2019-05-03"))) as c:
        doc = _anexar(c, contrato_id=ids["antigo"]).json()["id"]
        linhas = {l["campo"]: l for l in c.get(f"/api/documentos/{doc}", headers=ADMIN).json()["conferencia"]}
        assert linhas["preco_mensal"]["situacao"] == "diferente" and not linhas["preco_mensal"]["gravavel"]
        assert "registre um evento" in linhas["preco_mensal"]["motivo"]
        assert c.post(f"/api/documentos/{doc}/conferir", headers=ADMIN,
                      json={"campos": ["preco_mensal"]}).status_code == 422
        # a data real da assinatura entra no contrato antigo, que até aqui não tinha nenhuma
        assert c.post(f"/api/documentos/{doc}/conferir", headers=ADMIN,
                      json={"campos": ["data_assinatura"]}).status_code == 200
        assert c.get(f"/api/contratos/{ids['antigo']}", headers=ADMIN).json()["data_inicio"] == "2019-05-03"


def test_lote_identifica_pelo_cnpj_e_espera_o_vinculo(engine, ids):
    with _cliente(engine, Leitor(lido(data_assinatura="2019-05-03"))) as c:
        r = _anexar(c)
        doc = r.json()["id"]
        d = c.get(f"/api/documentos/{doc}", headers=ADMIN).json()
        assert d["origem"] == "lote" and d["contrato_id"] is None
        assert d["sugestao"]["grupo_id"] == ids["grupo"] and d["sugestao"]["motivo"] == "pelo CNPJ"
        assert d["sugestao"]["grupo_nome"] == "Cliente A"
        assert "Vincule" in d["aviso"]
        assert c.post(f"/api/documentos/{doc}/conferir", headers=ADMIN, json={"campos": []}).status_code == 422
        v = c.patch(f"/api/documentos/{doc}", headers=ADMIN, json={"contrato_id": ids["antigo"]}).json()
        assert v["contrato_id"] == ids["antigo"] and v["grupo_id"] == ids["grupo"]
        assert [d["id"] for d in c.get("/api/documentos", params={"origem": "lote"}, headers=ADMIN).json()] == [doc]


def test_lote_cria_contrato_anterior_ao_crm_quando_nao_ha_contrato(engine, ids):
    sem_cliente = {**lido(escopo="BPO Contábil"), "cnpjs": ["99888777000166"]}
    with _cliente(engine, Leitor(sem_cliente)) as c:
        doc = _anexar(c).json()["id"]
        d = c.get(f"/api/documentos/{doc}", headers=ADMIN).json()
        assert d["sugestao"]["motivo"] == "CNPJ fora do cadastro" and d["sugestao"]["grupo_id"] is None
        assert c.patch(f"/api/documentos/{doc}", headers=ADMIN, json={"criar_contrato": True}).status_code == 422
        v = c.patch(f"/api/documentos/{doc}", headers=ADMIN, json={"criar_contrato": True, "grupo_id": ids["outro"]}).json()
    with Session(engine) as s:
        novo = s.get(Contrato, v["contrato_id"])
        assert novo.grupo_id == ids["outro"] and novo.anterior_ao_crm and novo.escopo == "BPO Contábil"


def test_proposta_aceita_na_oportunidade_grava_a_data_do_aceite(engine, ids):
    proposta = {**lido(numero="PROP CCE RJ 041.2019", data_assinatura="2019-04-20", preco_mensal="4000.00"),
                "tipo": "proposta"}
    with _cliente(engine, Leitor(proposta)) as c:
        doc = _anexar(c, oportunidade_id=ids["op"]).json()["id"]
        d = c.get(f"/api/documentos/{doc}", headers=ADMIN).json()
        linhas = {l["campo"]: l for l in d["conferencia"]}
        assert d["tipo"] == "proposta" and linhas["data_assinatura"]["destino"] == "oportunidade"
        assert linhas["preco_mensal"]["situacao"] == "informativo" and not linhas["preco_mensal"]["gravavel"]
        assert c.post(f"/api/documentos/{doc}/conferir", headers=ADMIN,
                      json={"campos": ["numero", "data_assinatura"]}).status_code == 200
    with Session(engine) as s:
        assert s.get(Oportunidade, ids["op"]).data_aceite == date(2019, 4, 20)
        assert s.get(DocumentoAnexado, doc).numero_no_documento == "PROP CCE RJ 041.2019"


def test_substituir_guarda_o_anterior_e_recusa_o_mesmo_pdf(engine, ids):
    with _cliente(engine, Leitor(lido())) as c:
        primeiro = _anexar(c, contrato_id=ids["aguardando"]).json()["id"]
        assert _anexar(c, contrato_id=ids["aguardando"]).status_code == 409
        segundo = _anexar(c, conteudo=PDF + b" v2", contrato_id=ids["aguardando"]).json()["id"]
        atuais = c.get("/api/documentos", params={"contrato_id": ids["aguardando"]}, headers=ADMIN).json()
        todos = c.get("/api/documentos", params={"contrato_id": ids["aguardando"], "historico": True}, headers=ADMIN).json()
    assert [d["id"] for d in atuais] == [segundo]
    assert {d["id"] for d in todos} == {primeiro, segundo}


def test_so_pdf_e_falha_da_leitura_fica_no_documento(engine, ids):
    with _cliente(engine, Leitor(AgenteFalhou("falta a chave da Anthropic"))) as c:
        assert c.post("/api/documentos", params={"nome_arquivo": "x.docx"}, content=PDF, headers=ADMIN).status_code == 422
        assert _anexar(c, conteudo=b"nao e pdf").status_code == 422
        doc = _anexar(c, contrato_id=ids["aguardando"]).json()["id"]
        d = c.get(f"/api/documentos/{doc}", headers=ADMIN).json()
        assert d["leitura_situacao"] == "falhou" and "falta a chave" in d["aviso"]
        # sem leitura, a pessoa preenche à mão e grava
        r = c.post(f"/api/documentos/{doc}/conferir", headers=ADMIN,
                   json={"campos": ["data_assinatura"], "valores": {"data_assinatura": "2026-10-14"}})
        assert r.status_code == 200
        assert c.post(f"/api/documentos/{doc}/conferir", headers=ADMIN,
                      json={"campos": ["data_assinatura"], "valores": {"data_assinatura": "14/10/2026"}}).status_code == 422


def test_baixar_o_pdf_pede_permissao_propria(engine, ids):
    with _cliente(engine, Leitor(lido())) as c:
        doc = _anexar(c, contrato_id=ids["aguardando"]).json()["id"]
        assert c.get(f"/api/documentos/{doc}", headers=KARINE).status_code == 200
        assert c.get(f"/api/documentos/{doc}/pdf", headers=KARINE).status_code == 403
        assert c.post(f"/api/documentos/{doc}/ler", headers=KARINE).status_code == 403
        r = c.get(f"/api/documentos/{doc}/pdf", headers=ADMIN)
        assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"


# ── A leitura pela IA ─────────────────────────────────────────────────────────────────────────────

def test_normaliza_o_que_a_ia_devolve():
    bruto = lido(data_assinatura="14/10/2026", preco_mensal="R$ 7.000,00", base_do_valor="Líquido",
                 parcelas_no_ano="13 parcelas", aviso_previo_dias="30 dias")
    bruto["cnpjs"] = ["11.222.333/0001-81", "11222333000181", "123"]
    n = regra.normalizar(bruto)
    c = n["campos"]
    assert c["data_assinatura"]["valor"] == "" and c["data_assinatura"]["pagina"] == 0  # data fora do formato: vazia
    assert c["preco_mensal"]["valor"] == "7000.00" and c["base_do_valor"]["valor"] == "liquido"
    assert c["parcelas_no_ano"]["valor"] == "13" and c["aviso_previo_dias"]["valor"] == "30"
    assert n["cnpjs"] == ["11222333000181"]


def test_manda_o_pdf_em_bloco_document_e_pede_json_com_esquema():
    pedidos = []

    def criar(**pedido):
        pedidos.append(pedido)
        import json
        return NS(stop_reason="end_turn", content=[NS(type="text", text=json.dumps(lido(escopo="BPO Financeiro")))],
                  usage=NS(input_tokens=10, output_tokens=5, cache_creation_input_tokens=0, cache_read_input_tokens=0))

    cliente = NS(beta=NS(messages=NS(create=criar)))
    saida = regra.ler_pdf(cliente, "claude-opus-5-5", pdf=PDF, nome="a.pdf", uso=Uso(modelo="claude-opus-5-5"))
    bloco = pedidos[0]["messages"][0]["content"][0]
    assert bloco["type"] == "document" and bloco["source"]["media_type"] == "application/pdf"
    assert pedidos[0]["output_config"]["format"]["type"] == "json_schema"
    assert saida["campos"]["escopo"]["valor"] == "BPO Financeiro"


def test_recusa_da_ia_vira_frase():
    cliente = NS(beta=NS(messages=NS(create=lambda **_: NS(stop_reason="refusal", content=[], usage=NS()))))
    with pytest.raises(AgenteFalhou, match="recusou"):
        regra.ler_pdf(cliente, "m", pdf=PDF, nome="a.pdf", uso=Uso(modelo="m"))


def test_reconhece_o_numero_do_contrato_e_da_proposta_do_crm():
    from crm.api.documentos import NUMERO_DO_CRM

    contrato = NUMERO_DO_CRM.search("CONT CCE RJ1 102.2026")
    assert contrato and contrato.groups() == ("CONT", "102", "2026")
    proposta = NUMERO_DO_CRM.search("PROP CCE RJ 154.2026")
    assert proposta and proposta.groups() == ("PROP", "154", "2026")
    assert NUMERO_DO_CRM.search("CONTRATO DE PRESTAÇÃO DE SERVIÇOS") is None


def test_lote_acha_o_contrato_pelo_numero_do_crm(engine, ids):
    from crm.db.modelos import DocumentoDeContrato, MatrizDeContrato

    with Session(engine) as s:
        m = MatrizDeContrato(modelo="Recorrente padrão", nome_arquivo="m.docx", conteudo_base64="", enviada_por="EL",
                             encontrados=[], faltando=[], desconhecidos=[])
        s.add(m)
        s.flush()
        s.add(DocumentoDeContrato(contrato_id=ids["aguardando"], numero=102, ano=2026, matriz_id=m.id, valores={},
                                  gerado_por="EL"))
        s.commit()
    outro_cnpj = {**lido(numero="CONT CCE RJ1 102.2026"), "cnpjs": ["99888777000166"]}
    with _cliente(engine, Leitor(outro_cnpj)) as c:
        doc = _anexar(c).json()["id"]
        sugestao = c.get(f"/api/documentos/{doc}", headers=ADMIN).json()["sugestao"]
    assert sugestao["motivo"] == "pelo número" and sugestao["contrato_id"] == ids["aguardando"]


def test_lista_do_grupo_acha_o_pdf_pelo_contrato_depois_da_juncao(engine, ids):
    """O card do grupo mostra todos os PDFs dele (19/10/2026); a junção de grupos move o contrato, não o documento."""
    from crm.db.grupos import fundir_grupos

    with _cliente(engine, Leitor(lido())) as c:
        doc = _anexar(c, contrato_id=ids["antigo"]).json()["id"]
        proposta = _anexar(c, conteudo=PDF + b" proposta", oportunidade_id=ids["op"]).json()["id"]
        assert {d["id"] for d in c.get("/api/documentos", params={"grupo_id": ids["grupo"]}, headers=ADMIN).json()} == {
            doc, proposta}
        with Session(engine) as s:
            fundir_grupos(s, s.get(GrupoEconomico, ids["outro"]), s.get(GrupoEconomico, ids["grupo"]))
            s.commit()
        assert {d["id"] for d in c.get("/api/documentos", params={"grupo_id": ids["outro"]}, headers=ADMIN).json()} == {
            doc, proposta}
