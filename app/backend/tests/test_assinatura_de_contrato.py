"""Assinatura eletrônica do contrato pela Clicksign — fase 1 (amostra aprovada por Eduardo em 18/10/2026)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import date
from decimal import Decimal as D

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm import configuracao
from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.api.app import criar_app
from crm.api.assinatura_de_contrato import CAMINHO_DO_WEBHOOK
from crm.contrato import clicksign as cs
from crm.db.modelos import (
    AssinaturaDeContrato, ConfiguracaoDeContrato, Contrato, Empresa, GrupoEconomico, Perfil, PessoaContato, Usuario,
    VinculoDeContato,
)
from crm.domain.listas import PapelContato, SituacaoContrato

CONFIG = ConfiguracaoDeEntrada("t", "c", frozenset({"eduardo@grupocriterio.com.br"}))
ADMIN = {"Authorization": "Bearer eduardo@grupocriterio.com.br|Eduardo Luiz"}
KARINE = {"Authorization": "Bearer karine@grupocriterio.com.br|Karine N"}
TOKEN = "token-de-teste-da-clicksign"
SEGREDO = "segredo-do-webhook-de-teste"
PDF = b"%PDF-1.7\nconteudo do contrato\n%%EOF"
ASSINADO = b"%PDF-1.7\ncontrato assinado\n%%EOF"
URL_ASSINADO = "https://clicksign-sandbox-content.s3.amazonaws.com/assinado.pdf?X-Amz-Expires=299"


def validar(token: str) -> dict:
    email, nome = token.split("|", 1)
    return {"preferred_username": email, "name": nome}


class Clicksign:
    """Uma Clicksign falsa: guarda os pedidos e responde como a API v3."""

    def __init__(self) -> None:
        self.pedidos: list[httpx.Request] = []
        self.situacao = "running"
        self.signatarios = 0
        self.falhar_em: str | None = None

    def tratar(self, pedido: httpx.Request) -> httpx.Response:
        self.pedidos.append(pedido)
        caminho, metodo = pedido.url.path, pedido.method
        if self.falhar_em and self.falhar_em in caminho:
            return httpx.Response(422, json={"errors": [{"detail": "inválido", "source": {"pointer": "/data/attributes/email"}}]})
        if str(pedido.url) == URL_ASSINADO:
            return httpx.Response(200, content=ASSINADO)
        if metodo == "POST" and caminho == "/api/v3/envelopes":
            return httpx.Response(201, json={"data": {"id": "env-1", "type": "envelopes", "attributes": {"status": "draft"}}})
        if metodo == "POST" and caminho.endswith("/documents"):
            return httpx.Response(201, json={"data": {"id": "doc-1", "type": "documents"}})
        if metodo == "POST" and caminho.endswith("/signers"):
            self.signatarios += 1
            return httpx.Response(201, json={"data": {"id": f"sig-{self.signatarios}", "type": "signers"}})
        if metodo == "POST" and caminho.endswith("/requirements"):
            return httpx.Response(201, json={"data": {"id": "req", "type": "requirements"}})
        if metodo == "POST" and caminho.endswith("/notifications"):
            return httpx.Response(201, json={})
        if metodo == "PATCH":
            return httpx.Response(200, json={"data": {"id": "x"}})
        if metodo == "GET" and caminho == "/api/v3/envelopes/env-1/documents/doc-1":
            arquivos = {"original": "https://clicksign-sandbox-content.s3.amazonaws.com/original.pdf"}
            if self.situacao == "closed":
                arquivos["signed"] = URL_ASSINADO
            return httpx.Response(200, json={"data": {"id": "doc-1", "type": "documents", "links": {"files": arquivos},
                                                      "attributes": {"status": self.situacao,
                                                                     "modified": "2026-10-20T23:30:00-03:00"}}})
        if metodo == "GET" and caminho == "/api/v3/envelopes":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404, json={})

    def corpos(self, fim: str) -> list[dict]:
        return [json.loads(p.content) for p in self.pedidos if p.url.path.endswith(fim) and p.content]


@pytest.fixture
def falsa():
    return Clicksign()


@pytest.fixture
def ids(engine):
    with Session(engine) as s:
        s.add(Perfil(nome="Administrador", administrador=True, permissoes=[]))
        leitura = Perfil(nome="Contratos", permissoes=["contratos.ver"])
        g = GrupoEconomico(nome="Cliente A")
        s.add_all([leitura, g])
        s.flush()
        s.add(Usuario(email="karine@grupocriterio.com.br", perfil_id=leitura.id))
        e = Empresa(grupo_id=g.id, razao_social="Cliente A Ltda", cnpj="11222333000181")
        s.add(e)
        s.flush()
        decisor = PessoaContato(nome="Maria Decisora", email="maria@clientea.com.br", papel=PapelContato.DECISOR)
        outro = PessoaContato(nome="João Usuário", email="joao@clientea.com.br", papel=PapelContato.USUARIO)
        s.add_all([decisor, outro])
        s.flush()
        s.add_all([VinculoDeContato(pessoa_id=outro.id, empresa_id=e.id, principal=True),
                   VinculoDeContato(pessoa_id=decisor.id, empresa_id=e.id, principal=False)])
        s.add(ConfiguracaoDeContrato(id=1, proximo_numero=102, signatario="Sócio Exemplo", vencimento=25,
                                     excedente_dp=D("50.00")))
        c = Contrato(grupo_id=g.id, empresa_id=e.id, recorrente=True, preco_mensal=D("4650"),
                     situacao=SituacaoContrato.AGUARDANDO_ASSINATURA)
        s.add(c)
        s.commit()
        return {"contrato": c.id}


@pytest.fixture
def fabrica(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def cliente(fabrica, ids, falsa):
    app = criar_app(fabrica, entrada=CONFIG, validar_token=validar, buscar_ipca=lambda de, ate: {},
                    http_da_clicksign=lambda: httpx.Client(transport=httpx.MockTransport(falsa.tratar)))
    with TestClient(app) as c:
        yield c
    configuracao.registrar_fabrica(None)


def _configurar(fabrica, **valores):
    padrao = {"clicksign.ligado": "true", "clicksign.token": TOKEN, "clicksign.segredo_webhook": SEGREDO,
              "clicksign.email_criterio": "socio@grupocriterio.com.br"}
    with fabrica() as s:
        for chave, valor in {**padrao, **valores}.items():
            configuracao.gravar(s, chave, valor, "teste")
        s.commit()
    configuracao.invalidar()


def _pedido(**mudar):
    corpo = {
        "nome_arquivo": "CONT CCE RJ1 102.2026.pdf", "conteudo_base64": base64.b64encode(PDF).decode(),
        "prazo": "2026-11-17",
        "signatarios": [
            {"nome": "Sócio Exemplo", "email": "socio@grupocriterio.com.br", "papel": "Contratada"},
            {"nome": "Maria Decisora", "email": "Maria@ClienteA.com.br", "papel": "Contratante"},
        ],
    }
    return {**corpo, **mudar}


def _enviar(cliente, ids, **mudar):
    return cliente.post(f"/api/contratos/{ids['contrato']}/assinatura", params={"hoje": "2026-10-18"},
                        json=_pedido(**mudar), headers=ADMIN)


def _aviso(cliente, payload, *, segredo=SEGREDO, assinar=True):
    corpo = json.dumps(payload).encode()
    cabecalhos = {"Content-Type": "application/json", "Event": payload.get("event", {}).get("name", "")}
    if assinar:
        cabecalhos["Content-Hmac"] = "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()
    return cliente.post(CAMINHO_DO_WEBHOOK, content=corpo, headers=cabecalhos)


def _evento(nome, *, chave="doc-1", quando="2026-10-20T23:30:00-03:00", signer=None):
    dados = {"account": {"key": "conta"}}
    if signer:
        dados["signer"] = signer
    return {"event": {"name": nome, "data": dados, "occurred_at": quando},
            "document": {"key": chave, "status": "running"}}


def _contrato(fabrica, ids) -> Contrato:
    with fabrica() as s:
        return s.get(Contrato, ids["contrato"])


# ── Regras ───────────────────────────────────────────────────────────────────────────────────────────

def test_assinatura_do_aviso():
    corpo = b'{"a":1}'
    certo = "sha256=" + hmac.new(SEGREDO.encode(), corpo, hashlib.sha256).hexdigest()
    assert cs.assinatura_valida(corpo, certo, SEGREDO)
    assert not cs.assinatura_valida(corpo + b" ", certo, SEGREDO)
    assert not cs.assinatura_valida(corpo, None, SEGREDO)
    assert not cs.assinatura_valida(corpo, certo, "")


# ── Aba e envio ──────────────────────────────────────────────────────────────────────────────────────

def test_desligada_explica_e_sugere_os_signatarios(cliente, ids):
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/assinatura", params={"hoje": "2026-10-18"}, headers=ADMIN).json()
    assert aba["ligada"] is False and "Integrações › Clicksign" in aba["problema"]
    assert aba["prazo_sugerido"] == "2026-11-17"
    criterio, cliente_ = aba["sugeridos"]
    assert (criterio["nome"], criterio["papel"], criterio["origem"]) == ("Sócio Exemplo", "Contratada", "configurações")
    # O decisor vem antes do contato principal.
    assert (cliente_["nome"], cliente_["email"], cliente_["origem"]) == ("Maria Decisora", "maria@clientea.com.br", "contato decisor")
    assert _enviar(cliente, ids).status_code == 409


def test_envia_cria_envelope_ativa_e_registra(cliente, ids, fabrica, falsa):
    _configurar(fabrica)
    r = _enviar(cliente, ids)
    assert r.status_code == 200, r.text
    aba = r.json()
    assert aba["atual"]["situacao"] == "em_assinatura" and aba["atual"]["ambiente"] == "sandbox"
    assert aba["problema"].startswith("Já há um envio")
    assert [s["email"] for s in aba["atual"]["signatarios"]] == ["socio@grupocriterio.com.br", "maria@clientea.com.br"]

    primeiro = falsa.pedidos[0]
    assert primeiro.url.host == "sandbox.clicksign.com" and primeiro.headers["Authorization"] == TOKEN
    assert primeiro.headers["Content-Type"] == "application/vnd.api+json"
    envelope = json.loads(primeiro.content)["data"]["attributes"]
    assert envelope["deadline_at"] == "2026-11-17T23:59:00-03:00" and envelope["auto_close"] is True
    assert envelope["name"].startswith("Cliente A · CONT CCE RJ1 102.2026")
    documento = falsa.corpos("/documents")[0]["data"]["attributes"]
    assert base64.b64decode(documento["content_base64"].split(",", 1)[1]) == PDF
    requisitos = [c["data"]["attributes"] for c in falsa.corpos("/requirements")]
    assert requisitos == [{"action": "agree", "role": "sign"}, {"action": "provide_evidence", "auth": "email"}] * 2
    assert falsa.corpos("/env-1")[-1]["data"]["attributes"] == {"status": "running"}

    with fabrica() as s:
        a = s.query(AssinaturaDeContrato).one()
        assert (a.envelope_id, a.documento_id, a.enviado_por) == ("env-1", "doc-1", "Eduardo Luiz")
        assert [x["clicksign_id"] for x in a.signatarios] == ["sig-1", "sig-2"]
    assert _contrato(fabrica, ids).situacao is SituacaoContrato.AGUARDANDO_ASSINATURA
    assert _enviar(cliente, ids).status_code == 409  # um envio em andamento por vez


def test_recusa_o_que_a_clicksign_nao_aceitaria(cliente, ids, fabrica):
    _configurar(fabrica, **{"clicksign.autenticacao": "whatsapp"})
    r = _enviar(cliente, ids, conteudo_base64=base64.b64encode(b"nao e pdf").decode(), prazo="2026-10-18",
                signatarios=[{"nome": "Sócio", "email": "socio@x.com", "papel": "Contratada"},
                             {"nome": "Ana Lima", "email": "socio@x.com", "papel": "Contratada"}])
    assert r.status_code == 422
    for trecho in ("não é um PDF", "depois de hoje", "duas palavras", "e-mail repetido", "celular com DDD",
                   "Contratante"):
        assert trecho in r.json()["detail"]


def test_falha_da_clicksign_volta_como_502_e_nada_fica_gravado(cliente, ids, fabrica, falsa):
    _configurar(fabrica)
    falsa.falhar_em = "/signers"
    r = _enviar(cliente, ids)
    assert r.status_code == 502 and "inválido (email)" in r.json()["detail"]
    with fabrica() as s:
        assert s.query(AssinaturaDeContrato).count() == 0


def test_so_quem_edita_contrato_envia(cliente, ids, fabrica):
    _configurar(fabrica)
    r = cliente.post(f"/api/contratos/{ids['contrato']}/assinatura", json=_pedido(), headers=KARINE)
    assert r.status_code == 403
    assert cliente.get(f"/api/contratos/{ids['contrato']}/assinatura", headers=KARINE).status_code == 200


# ── Aviso da Clicksign ───────────────────────────────────────────────────────────────────────────────

def test_aviso_sem_assinatura_ou_desligado_e_recusado(cliente, ids, fabrica):
    assert _aviso(cliente, _evento("sign")).status_code == 404  # desligada
    _configurar(fabrica)
    assert _aviso(cliente, _evento("sign"), assinar=False).status_code == 401
    assert _aviso(cliente, _evento("sign"), segredo="outro").status_code == 401
    assert _aviso(cliente, _evento("sign", chave="de-outro-sistema")).status_code == 200  # aceito e ignorado


def test_assinou_e_fechou_ativa_o_contrato_com_a_data_de_brasilia(cliente, ids, fabrica, falsa):
    _configurar(fabrica)
    _enviar(cliente, ids)
    r = _aviso(cliente, _evento("sign", quando="2026-10-19T10:00:00-03:00",
                                signer={"email": "maria@clientea.com.br", "name": "Maria Decisora"}))
    assert r.status_code == 200
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/assinatura", headers=ADMIN).json()
    assert [s["assinou_em"] is not None for s in aba["atual"]["signatarios"]] == [False, True]

    falsa.situacao = "closed"
    assert _aviso(cliente, _evento("auto_close")).status_code == 200
    c = _contrato(fabrica, ids)
    # 23h30 em Brasília do dia 20 já é dia 21 em UTC: vale o dia de Brasília.
    assert c.situacao is SituacaoContrato.ATIVO and c.data_inicio == date(2026, 10, 20)
    assert c.signatario == "Maria Decisora" and "env-1" in c.documento_assinado
    # O PDF veio do endereço que a API informou, não do aviso.
    assert any(str(p.url) == URL_ASSINADO for p in falsa.pedidos)
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/assinatura", headers=ADMIN).json()
    assert aba["atual"]["situacao"] == "assinado" and aba["atual"]["tem_pdf"] is True
    assert "Ativo" in aba["problema"]
    pdf = cliente.get(f"/api/assinaturas-de-contrato/{aba['atual']['id']}/pdf", headers=KARINE)
    assert pdf.status_code == 200 and pdf.content == ASSINADO
    assert pdf.headers["content-type"] == "application/pdf"


def test_recusa_deixa_o_contrato_aguardando_e_permite_reenviar(cliente, ids, fabrica):
    _configurar(fabrica)
    _enviar(cliente, ids)
    _aviso(cliente, _evento("refusal", signer={"email": "maria@clientea.com.br", "name": "Maria Decisora"}))
    aba = cliente.get(f"/api/contratos/{ids['contrato']}/assinatura", headers=ADMIN).json()
    assert aba["atual"]["situacao"] == "recusado" and "Maria Decisora" in aba["atual"]["motivo"]
    assert aba["problema"] is None
    assert _contrato(fabrica, ids).situacao is SituacaoContrato.AGUARDANDO_ASSINATURA
    with fabrica() as s:  # o segundo envio ganha outro envelope
        s.query(AssinaturaDeContrato).update({"envelope_id": "env-antigo", "documento_id": "doc-antigo"})
        s.commit()
    novo = _enviar(cliente, ids).json()
    assert novo["atual"]["situacao"] == "em_assinatura" and len(novo["anteriores"]) == 1


def test_conferir_e_o_caminho_de_reserva_sem_aviso(cliente, ids, fabrica, falsa):
    _configurar(fabrica)
    _enviar(cliente, ids)
    url = f"/api/contratos/{ids['contrato']}/assinatura/conferir"
    assert cliente.post(url, headers=ADMIN).json()["atual"]["situacao"] == "em_assinatura"
    falsa.situacao = "closed"
    aba = cliente.post(url, headers=ADMIN).json()
    assert aba["atual"]["situacao"] == "assinado" and aba["atual"]["tem_pdf"] is True
    assert _contrato(fabrica, ids).data_inicio == date(2026, 10, 20)


def test_lembrete_e_cancelamento(cliente, ids, fabrica, falsa):
    _configurar(fabrica)
    _enviar(cliente, ids)
    base = f"/api/contratos/{ids['contrato']}/assinatura"
    r = cliente.post(f"{base}/lembrete", json={"email": "maria@clientea.com.br"}, headers=ADMIN)
    assert r.status_code == 200 and r.json()["atual"]["ultimo_evento"] == "lembrete para Maria Decisora"
    assert any(p.url.path == "/api/v3/envelopes/env-1/signers/sig-2/notifications" for p in falsa.pedidos)
    assert cliente.post(f"{base}/lembrete", json={"email": "ninguem@x.com"}, headers=ADMIN).status_code == 404

    r = cliente.post(f"{base}/cancelar", headers=ADMIN)
    assert r.status_code == 200 and r.json()["atual"]["situacao"] == "cancelado"
    assert falsa.corpos("/documents/doc-1")[-1]["data"]["attributes"] == {"status": "canceled"}
    assert cliente.post(f"{base}/cancelar", headers=ADMIN).status_code == 409


def test_teste_da_integracao(cliente, fabrica, falsa, monkeypatch):
    from crm.api import integracoes

    _configurar(fabrica, **{"clicksign.segredo_webhook": ""})
    monkeypatch.setattr(cs, "_cliente", lambda http: httpx.Client(transport=httpx.MockTransport(falsa.tratar)))
    r = cliente.post("/api/configuracoes/integracoes/clicksign/testar", headers=ADMIN).json()
    assert r["ok"] is True and "sandbox" in r["mensagem"] and "chave do webhook" in r["mensagem"]
    assert integracoes  # o testador real está ligado ao cartão
