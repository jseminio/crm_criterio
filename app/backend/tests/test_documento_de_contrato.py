"""Contrato recorrente gerado em Word pela matriz com marcadores (aprovado por Eduardo em 14/10/2026)."""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.api.documento_de_contrato import data_por_extenso
from crm.contrato import matriz as regra
from crm.db.modelos import (
    Contrato, DocumentoDeContrato, Empresa, GrupoEconomico, Oportunidade, Perfil, Proposta, MatrizDeProposta, Usuario,
)
from crm.domain.listas import Situacao, SituacaoContrato, TipoDeMatriz

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}


def _p(*pedacos: str) -> str:
    return "<w:p>" + "".join(f'<w:r><w:t xml:space="preserve">{t}</w:t></w:r>' for t in pedacos) + "</w:p>"


def docx(corpo: list[str], rodape: list[str] | None = None) -> bytes:
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {W}><w:body>{"".join(corpo)}</w:body></w:document>')
        if rodape:
            z.writestr("word/footer1.xml", f'<?xml version="1.0"?><w:ftr {W}>{"".join(rodape)}</w:ftr>')
    return saida.getvalue()


def texto(conteudo: bytes, parte: str = "word/document.xml") -> str:
    import re
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", z.read(parte).decode()))


MATRIZ = docx(
    [_p("CONTRATO CCE_RJ1 ", "{{num", "ero}}"), _p("{{razao_social}}, CNPJ {{cnpj}}, com sede na {{endereco}}"),
     _p("a partir da competência {{competencia_inicial}}"), _p("Valor Líquido: {{valor_contabil}} / Bruto: {{bruto_contabil}}"),
     _p("Rio de Janeiro, {{data_extenso}}."), _p("{{signatario}} – {{cargo_signatario}}")],
    rodape=[_p("Contrato {{numero}}")],
)


# ── Matriz ─────────────────────────────────────────────────────────────────────────────────────────

def test_examina_marcadores_mesmo_partidos_e_acusa_os_que_faltam():
    exame = regra.examinar(MATRIZ)
    assert exame.encontrados[0] == "numero" and "cargo_signatario" in exame.encontrados
    assert exame.faltando == [] and exame.desconhecidos == []
    falho = regra.examinar(docx([_p("{{razao_social}} {{razao_socail}}")]))
    assert "numero" in falho.faltando and falho.desconhecidos == ["razao_socail"]
    with pytest.raises(regra.MatrizIlegivel):
        regra.examinar(b"nao e um docx")


def test_preenche_corpo_e_rodape_e_deixa_a_vista_o_que_nao_tem_valor():
    saida = regra.preencher(MATRIZ, {"numero": "102.2026", "razao_social": "Cliente A Ltda"})
    corpo = texto(saida)
    assert "CONTRATO CCE_RJ1 102.2026" in corpo and "Cliente A Ltda, CNPJ {{cnpj}}" in corpo
    assert texto(saida, "word/footer1.xml") == "Contrato 102.2026"


def test_data_por_extenso():
    assert data_por_extenso(date(2026, 10, 14)) == "14 de outubro de 2026"


# ── API ────────────────────────────────────────────────────────────────────────────────────────────

def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        leitura = Perfil(nome="Contratos", permissoes=["contratos.ver"])
        g = GrupoEconomico(nome="Cliente A")
        s.add_all([leitura, g])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=leitura.id))
        e = Empresa(grupo_id=g.id, razao_social="Cliente A Ltda", cnpj="11222333000181", logradouro="Rua Exemplo",
                    numero="100", bairro="Centro", municipio="Rio de Janeiro", uf="RJ", cep="20041004",
                    regime_tributario="Lucro Presumido")
        s.add(e)
        s.flush()
        op = Oportunidade(grupo_id=g.id, empresa_id=e.id, nome="BPO", servico="BPO Contábil, Fiscal e Dep. Pessoal",
                          situacao=Situacao.ACEITA, preco_mensal=D("4650"))
        s.add(op)
        s.flush()
        mp = MatrizDeProposta(tipo=TipoDeMatriz.CONTABIL, nome_arquivo="m.pptx", conteudo_base64="", enviada_por="EL",
                              faltando=[], desconhecidos=[])
        s.add(mp)
        s.flush()
        s.add(Proposta(oportunidade_id=op.id, numero=170, ano=2026, matriz_id=mp.id, valor_liquido=D("4650"),
                       enviada_em=date(2026, 10, 1), enviada_por="EL",
                       valores={"entrada": {"valor_contabil": "4000.00", "valor_dp": "650.00"},
                                "marcadores": {"horas_contabil": "12", "horas_dp": "5", "faturamento": "R$ 4,8 milhões",
                                               "funcionarios": "12", "movimentacao": "300", "regime": "Lucro Real"}}))
        c = Contrato(grupo_id=g.id, oportunidade_id=op.id, recorrente=True, preco_mensal=D("4650"),
                     situacao=SituacaoContrato.AGUARDANDO_ASSINATURA)
        projeto = Contrato(grupo_id=g.id, recorrente=False, preco_anual=D("40000"), situacao=SituacaoContrato.AGUARDANDO_ASSINATURA)
        s.add_all([c, projeto])
        s.commit()
        return {"contrato": c.id, "projeto": projeto.id}


@pytest.fixture
def cliente(engine, ids):
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, entrada=CONFIG, validar_token=validar, buscar_ipca=lambda de, ate: {})) as c:
        yield c


def _subir(cliente, conteudo=MATRIZ, nome="Modelo recorrente.docx"):
    return cliente.post("/api/documentos-de-contrato/matriz", params={"nome_arquivo": nome}, content=conteudo, headers=ADMIN)


def _configurar(cliente):
    return cliente.put("/api/documentos-de-contrato/configuracao", headers=ADMIN, json={
        "proximo_numero": 102, "signatario": "Sócio Exemplo", "cargo_signatario": "Sócio", "cpf_signatario": "12345678901",
        "vencimento": 25, "excedente_dp": "50.00"})


def test_sem_matriz_explica_e_nao_gera(cliente, ids):
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/documento", headers=ADMIN).json()
    assert "Ainda não há matriz" in aba["problema"]
    r = cliente.post(f"/api/contratos/{ids['contrato']}/documento", json={"valores": {}}, headers=ADMIN)
    assert r.status_code == 409


def test_sugestoes_vem_da_empresa_da_proposta_dos_parametros_e_da_configuracao(cliente, ids):
    assert _subir(cliente).status_code == 200 and _configurar(cliente).status_code == 200
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/documento", params={"hoje": "2026-10-14"}, headers=ADMIN).json()
    assert aba["problema"] is None and aba["numero"] == "102.2026"
    campos = {c["nome"]: (c["valor"], c["origem"]) for c in aba["campos"]}
    assert campos["razao_social"] == ("Cliente A Ltda", "empresa")
    assert campos["cnpj"] == ("11.222.333/0001-81", "empresa")
    assert campos["endereco"][0] == "Rua Exemplo, nº 100 – Centro – Rio de Janeiro/RJ, CEP 20.041-004"
    assert campos["valor_contabil"] == ("R$ 4.000,00", "proposta")
    assert campos["bruto_contabil"][1] == "parâmetros"
    assert campos["data_extenso"] == ("14 de outubro de 2026", "hoje")
    assert campos["signatario"] == ("Sócio Exemplo", "configurações")
    assert list(campos) == regra.examinar(MATRIZ).encontrados  # só os marcadores que a matriz tem


def test_gerar_reserva_o_numero_regrava_antes_da_assinatura_e_baixa_o_word(cliente, ids, engine):
    _subir(cliente)
    _configurar(cliente)
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/documento", params={"hoje": "2026-10-14"}, headers=ADMIN).json()
    valores = {c["nome"]: c["valor"] for c in aba["campos"]}
    r = cliente.post(f"/api/contratos/{ids['contrato']}/documento", params={"hoje": "2026-10-14"},
                     json={"valores": valores}, headers=ADMIN)
    assert r.status_code == 200, r.text
    gerado = r.json()["gerado"]
    assert gerado["numero"] == "CONT CCE RJ1 102.2026" and gerado["gerado_por"] == "Eduardo Luiz"
    valores["competencia_inicial"] = "novembro de 2026"
    de_novo = cliente.post(f"/api/contratos/{ids['contrato']}/documento", params={"hoje": "2026-10-15"},
                           json={"valores": valores}, headers=ADMIN).json()
    assert de_novo["gerado"]["numero"] == "CONT CCE RJ1 102.2026"  # mesmo número
    arquivo = cliente.get(f"/api/documentos-de-contrato/{gerado['id']}/docx", headers=ADMIN)
    assert arquivo.status_code == 200 and "CONT CCE RJ1 102.2026" in arquivo.headers["content-disposition"]
    corpo = texto(arquivo.content)
    assert "CONTRATO CCE_RJ1 102.2026" in corpo and "competência novembro de 2026" in corpo and "{{" not in corpo
    config = cliente.get("/api/documentos-de-contrato/configuracao", headers=ADMIN).json()
    assert config["proximo_numero"] == 103 and config["ultimo_usado"] == "CONT CCE RJ1 102.2026"
    with Session(engine) as s:
        s.get(Contrato, ids["contrato"]).situacao = SituacaoContrato.ATIVO
        s.commit()
    r = cliente.post(f"/api/contratos/{ids['contrato']}/documento", json={"valores": valores}, headers=ADMIN)
    assert r.status_code == 409 and "assinado" in r.json()["detail"]


def test_gerar_exige_todos_os_campos_da_matriz(cliente, ids):
    _subir(cliente)
    r = cliente.post(f"/api/contratos/{ids['contrato']}/documento", json={"valores": {"razao_social": "X"}}, headers=ADMIN)
    assert r.status_code == 422 and "CNPJ do cliente" in r.json()["detail"]


def test_matriz_com_erro_fica_gravada_mas_nao_gera(cliente, ids):
    resumo = _subir(cliente, docx([_p("{{razao_social}} {{razao_socail}}")]), "errada.docx").json()
    assert resumo["em_condicao"] is False and "numero" in resumo["faltando"]
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/documento", headers=ADMIN).json()
    assert "{{razao_socail}}" in aba["problema"]
    assert _subir(cliente, b"xx", "x.docx").status_code == 422
    assert _subir(cliente, MATRIZ, "x.pdf").status_code == 422


def test_nao_recorrente_ainda_nao_gera(cliente, ids):
    _subir(cliente)
    aba = cliente.get(f"/api/contratos/{ids['projeto']}/documento", headers=ADMIN).json()
    assert "não recorrente" in aba["problema"]


def test_numero_usado_nao_volta_e_cpf_e_validado(cliente, ids):
    _subir(cliente)
    _configurar(cliente)
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/documento", headers=ADMIN).json()
    cliente.post(f"/api/contratos/{ids['contrato']}/documento", json={"valores": {c["nome"]: c["valor"] for c in aba["campos"]}},
                 headers=ADMIN)
    base = {"signatario": "S", "cargo_signatario": "Sócio", "vencimento": 25, "excedente_dp": "50.00"}
    assert cliente.put("/api/documentos-de-contrato/configuracao", headers=ADMIN, json={**base, "proximo_numero": 102}).status_code == 422
    assert cliente.put("/api/documentos-de-contrato/configuracao", headers=ADMIN,
                       json={**base, "proximo_numero": 110, "cpf_signatario": "123"}).status_code == 422


def test_quem_so_ve_contratos_baixa_mas_nao_gera_nem_configura(cliente, ids):
    _subir(cliente)
    assert cliente.get(f"/api/contratos/{ids['contrato']}/documento", headers=KARINE).status_code == 200
    assert cliente.post(f"/api/contratos/{ids['contrato']}/documento", json={"valores": {}}, headers=KARINE).status_code == 403
    assert cliente.post("/api/documentos-de-contrato/matriz", params={"nome_arquivo": "a.docx"}, content=MATRIZ,
                        headers=KARINE).status_code == 403
