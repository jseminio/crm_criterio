"""Mensagens do WhatsApp recebidas pelo CRM — fase 0 do SDR de IA (amostra aprovada em 14/10/2026)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm import configuracao
from crm.agente.recebimento import assinatura_valida, chave_do_telefone, eh_pedido_de_saida
from crm.api.app import criar_app
from crm.api.whatsapp_recebido import CAMINHO, LIMITE_DO_CORPO
from crm.db.modelos import ConversaDoSdr, Lead, MensagemDoSdr
from crm.domain.listas import AutorDaMensagem, CanalDeAbordagem

SEGREDO_DO_APP = "segredo-do-app-de-teste"
TOKEN = "crm-token-de-verificacao-1234"
NUMERO_ID = "1098765432"


def _payload(*, mensagens=(), entregas=(), numero=NUMERO_ID, contatos=()):
    return {"object": "whatsapp_business_account", "entry": [{"id": "conta", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"display_phone_number": "551130000000", "phone_number_id": numero},
        "contacts": list(contatos), "messages": list(mensagens), "statuses": list(entregas)}}]}]}


def _texto(id_, de, texto, ts=1760450040):
    return {"from": de, "id": id_, "timestamp": str(ts), "type": "text", "text": {"body": texto}}


def _assinar(corpo: bytes, segredo: str = SEGREDO_DO_APP) -> str:
    return "sha256=" + hmac.new(segredo.encode(), corpo, hashlib.sha256).hexdigest()


@pytest.fixture
def fabrica(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def cliente(fabrica):
    with TestClient(criar_app(fabrica)) as c:
        yield c
    configuracao.registrar_fabrica(None)


def _configurar(fabrica, **valores):
    padrao = {"whatsapp.recebimento": "true", "whatsapp.token_verificacao": TOKEN,
              "whatsapp.app_secret": SEGREDO_DO_APP, "whatsapp.numero_id": NUMERO_ID}
    with fabrica() as s:
        for chave, valor in {**padrao, **valores}.items():
            configuracao.gravar(s, chave, valor, "teste")
        s.commit()
    configuracao.invalidar()


def _enviar(cliente, payload, *, assinatura=True, segredo=SEGREDO_DO_APP):
    corpo = json.dumps(payload).encode()
    cabecalhos = {"Content-Type": "application/json"}
    if assinatura:
        cabecalhos["X-Hub-Signature-256"] = _assinar(corpo, segredo)
    return cliente.post(CAMINHO, content=corpo, headers=cabecalhos)


def _contar(fabrica, modelo):
    with fabrica() as s:
        return s.scalar(sa.select(sa.func.count()).select_from(modelo))


class TestRegras:
    def test_assinatura(self):
        corpo = b'{"a":1}'
        assert assinatura_valida(corpo, _assinar(corpo), SEGREDO_DO_APP)
        assert not assinatura_valida(corpo, _assinar(corpo, "outro"), SEGREDO_DO_APP)
        assert not assinatura_valida(corpo + b" ", _assinar(corpo), SEGREDO_DO_APP)
        assert not assinatura_valida(corpo, None, SEGREDO_DO_APP)
        assert not assinatura_valida(corpo, hmac.new(SEGREDO_DO_APP.encode(), corpo, hashlib.sha256).hexdigest(), SEGREDO_DO_APP)
        assert not assinatura_valida(corpo, _assinar(corpo, ""), "")

    @pytest.mark.parametrize("a, b", [("+55 11 98765-4321", "551187654321"), ("(11) 98765-4321", "5511987654321"),
                                      ("5511987654321", "+55 (11) 8765-4321")])
    def test_telefone_casa_com_e_sem_o_nono_digito(self, a, b):
        assert chave_do_telefone(a) == chave_do_telefone(b)

    def test_numeros_diferentes_nao_casam(self):
        assert chave_do_telefone("+55 11 98765-4321") != chave_do_telefone("+55 21 98765-4321")

    @pytest.mark.parametrize("texto", ["SAIR", "sair", " Parar. ", "pare!", "Não quero mais receber", "STOP", "descadastrar",
                                       "Parar promoções", "parar de receber mensagens", "Stop promotions"])
    def test_pedido_de_saida(self, texto):
        assert eh_pedido_de_saida(texto)

    @pytest.mark.parametrize("texto", ["quero sair do Simples", "como paro de pagar tanto imposto?", "sair agora não", ""])
    def test_frase_comum_nao_e_pedido_de_saida(self, texto):
        assert not eh_pedido_de_saida(texto)


class TestTravas:
    def test_desligado_recusa_tudo_e_nao_grava(self, cliente, fabrica):
        _configurar(fabrica, **{"whatsapp.recebimento": "false"})
        assert cliente.get(CAMINHO, params={"hub.mode": "subscribe", "hub.verify_token": TOKEN,
                                            "hub.challenge": "123"}).status_code == 404
        assert _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "oi")])).status_code == 404
        assert _contar(fabrica, MensagemDoSdr) == 0 and _contar(fabrica, Lead) == 0

    def test_verificacao_da_meta(self, cliente, fabrica):
        _configurar(fabrica)
        ok = cliente.get(CAMINHO, params={"hub.mode": "subscribe", "hub.verify_token": TOKEN, "hub.challenge": "1158201444"})
        assert ok.status_code == 200 and ok.text == "1158201444"
        assert cliente.get(CAMINHO, params={"hub.mode": "subscribe", "hub.verify_token": "errado",
                                            "hub.challenge": "1"}).status_code == 403
        assert cliente.get(CAMINHO, params={"hub.mode": "subscribe", "hub.verify_token": TOKEN,
                                            "hub.challenge": "<script>"}).status_code == 400

    def test_sem_token_salvo_nao_verifica(self, cliente, fabrica):
        _configurar(fabrica, **{"whatsapp.token_verificacao": ""})
        assert cliente.get(CAMINHO, params={"hub.mode": "subscribe", "hub.verify_token": "",
                                            "hub.challenge": "1"}).status_code == 403

    def test_sem_chave_secreta_recusa(self, cliente, fabrica):
        _configurar(fabrica, **{"whatsapp.app_secret": ""})
        assert _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "oi")])).status_code == 403
        assert _contar(fabrica, MensagemDoSdr) == 0

    @pytest.mark.parametrize("assinatura, segredo", [(False, SEGREDO_DO_APP), (True, "segredo-de-um-impostor")])
    def test_sem_assinatura_valida_nao_grava(self, cliente, fabrica, assinatura, segredo):
        _configurar(fabrica)
        r = _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "oi")]), assinatura=assinatura, segredo=segredo)
        assert r.status_code == 401 and r.content == b""
        assert _contar(fabrica, MensagemDoSdr) == 0 and _contar(fabrica, Lead) == 0

    def test_entrega_grande_demais(self, cliente, fabrica):
        _configurar(fabrica)
        corpo = b"x" * (LIMITE_DO_CORPO + 1)
        r = cliente.post(CAMINHO, content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
        assert r.status_code == 413

    def test_corpo_que_nao_e_do_whatsapp(self, cliente, fabrica):
        _configurar(fabrica)
        assert _enviar(cliente, {"object": "page", "entry": []}).status_code == 400

    def test_outro_numero_e_ignorado(self, cliente, fabrica):
        _configurar(fabrica)
        r = _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "oi")], numero="555"))
        assert r.status_code == 200 and _contar(fabrica, MensagemDoSdr) == 0


class TestGravacao:
    def test_numero_novo_vira_lead_com_a_conversa(self, cliente, fabrica):
        _configurar(fabrica)
        r = _enviar(cliente, _payload(mensagens=[_texto("wamid.A", "5511987654321", "Oi, quero saber do BPO")],
                                      contatos=[{"wa_id": "5511987654321", "profile": {"name": "Marina Teixeira"}}]))
        assert r.status_code == 200 and r.content == b""
        with fabrica() as s:
            lead = s.scalar(sa.select(Lead))
            assert (lead.nome, lead.telefone, lead.canal) == ("Marina Teixeira", "+5511987654321", "WhatsApp")
            conversa = s.scalar(sa.select(ConversaDoSdr))
            assert conversa.lead_id == lead.id and conversa.canal is CanalDeAbordagem.WHATSAPP
            assert conversa.ultima_do_lead_em.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(1760450040, timezone.utc)
            m = s.scalar(sa.select(MensagemDoSdr))
            assert (m.autor, m.texto, m.externo_id) == (AutorDaMensagem.LEAD, "Oi, quero saber do BPO", "wamid.A")

    def test_lead_existente_sem_o_nono_digito(self, cliente, fabrica):
        _configurar(fabrica)
        with fabrica() as s:
            s.add(Lead(nome="Já cadastrada", telefone="+55 11 98765-4321"))
            s.commit()
        _enviar(cliente, _payload(mensagens=[_texto("w1", "551187654321", "oi")]))
        with fabrica() as s:
            assert s.scalar(sa.select(sa.func.count()).select_from(Lead)) == 1
            assert s.scalar(sa.select(ConversaDoSdr)).lead.nome == "Já cadastrada"

    def test_entrega_repetida_grava_uma_vez(self, cliente, fabrica):
        _configurar(fabrica)
        payload = _payload(mensagens=[_texto("wamid.X", "5511987654321", "oi")])
        assert _enviar(cliente, payload).status_code == 200
        assert _enviar(cliente, payload).status_code == 200
        assert _contar(fabrica, MensagemDoSdr) == 1 and _contar(fabrica, Lead) == 1

    def test_segunda_mensagem_entra_na_mesma_conversa(self, cliente, fabrica):
        _configurar(fabrica)
        _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "oi")]))
        _enviar(cliente, _payload(mensagens=[_texto("w2", "5511987654321", "tudo bem?", ts=1760450100)]))
        assert _contar(fabrica, ConversaDoSdr) == 1 and _contar(fabrica, MensagemDoSdr) == 2

    def test_sair_marca_nao_contatar(self, cliente, fabrica):
        _configurar(fabrica)
        _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "quero sair do Simples")]))
        with fabrica() as s:
            assert s.scalar(sa.select(Lead)).nao_contatar is False
        _enviar(cliente, _payload(mensagens=[_texto("w2", "5511987654321", "SAIR", ts=1760450100)]))
        with fabrica() as s:
            lead = s.scalar(sa.select(Lead))
            assert lead.nao_contatar is True and lead.nao_contatar_em is not None
            assert [m.texto for m in s.scalars(sa.select(MensagemDoSdr).order_by(MensagemDoSdr.id))] == [
                "quero sair do Simples", "SAIR"]

    def test_midia_registra_o_tipo_sem_baixar(self, cliente, fabrica):
        _configurar(fabrica)
        _enviar(cliente, _payload(mensagens=[
            {"from": "5511987654321", "id": "w1", "timestamp": "1760450040", "type": "audio", "audio": {"id": "midia-1"}},
            {"from": "5511987654321", "id": "w2", "timestamp": "1760450041", "type": "image",
             "image": {"id": "midia-2", "caption": "o balanço"}},
        ]))
        with fabrica() as s:
            assert [m.texto for m in s.scalars(sa.select(MensagemDoSdr).order_by(MensagemDoSdr.id))] == [
                "[áudio]", "[foto] o balanço"]

    def test_situacao_de_entrega_nao_volta_atras(self, cliente, fabrica):
        _configurar(fabrica)
        with fabrica() as s:
            lead = Lead(nome="L", telefone="+5511987654321")
            s.add(lead)
            s.flush()
            c = ConversaDoSdr(lead_id=lead.id, canal=CanalDeAbordagem.WHATSAPP)
            s.add(c)
            s.flush()
            s.add(MensagemDoSdr(conversa_id=c.id, autor=AutorDaMensagem.IA, texto="Olá", externo_id="wamid.SAIU"))
            s.commit()

        def entrega(status):
            _enviar(cliente, _payload(entregas=[{"id": "wamid.SAIU", "status": status, "timestamp": "1760450040",
                                                  "recipient_id": "5511987654321"}]))
            with fabrica() as s:
                return s.scalar(sa.select(MensagemDoSdr.entrega))

        assert entrega("delivered") == "entregue"
        assert entrega("sent") == "entregue"
        assert entrega("read") == "lida"
        assert entrega("delivered") == "lida"
        assert entrega("failed") == "falhou"

    def test_log_sem_conteudo_nem_telefone(self, cliente, fabrica, caplog):
        _configurar(fabrica)
        with caplog.at_level(logging.INFO):
            _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "meu faturamento é 2 milhões")],
                                      contatos=[{"wa_id": "5511987654321", "profile": {"name": "Marina Teixeira"}}]))
            _enviar(cliente, _payload(mensagens=[_texto("w2", "5511987654321", "x")]), assinatura=False)
        texto = caplog.text
        assert "1 recebidas" in texto and "assinatura ausente ou inválida" in texto
        assert "faturamento" not in texto and "987654321" not in texto and "Marina" not in texto


class TestTela:
    def test_campos_novos_e_situacao(self, cliente, fabrica):
        _configurar(fabrica)
        grupo = next(g for g in cliente.get("/api/configuracoes/integracoes").json()["grupos"] if g["chave"] == "whatsapp")
        campos = {c["chave"]: c for c in grupo["campos"]}
        assert {"whatsapp.recebimento", "whatsapp.token_verificacao", "whatsapp.app_secret"} <= set(campos)
        assert campos["whatsapp.app_secret"]["valor"] is None and campos["whatsapp.app_secret"]["final"] == SEGREDO_DO_APP[-4:]
        assert campos["whatsapp.token_verificacao"]["valor"] is None
        assert grupo["situacao"].startswith("⚠ Nenhuma mensagem recebida ainda.")
        _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "oi")]))
        _enviar(cliente, _payload(mensagens=[_texto("w2", "5511987654321", "oi")]), assinatura=False)
        grupo = next(g for g in cliente.get("/api/configuracoes/integracoes").json()["grupos"] if g["chave"] == "whatsapp")
        assert grupo["situacao"].startswith("✓ Última mensagem recebida em ")
        assert "Última entrega recusada em" in grupo["situacao"] and "assinatura ausente ou inválida" in grupo["situacao"]

    def test_desligado_e_sem_chave_aparecem_na_situacao(self, cliente, fabrica):
        _configurar(fabrica, **{"whatsapp.recebimento": "false"})
        grupo = next(g for g in cliente.get("/api/configuracoes/integracoes").json()["grupos"] if g["chave"] == "whatsapp")
        assert grupo["situacao"].startswith("Recebimento desligado")
        _configurar(fabrica, **{"whatsapp.app_secret": ""})
        grupo = next(g for g in cliente.get("/api/configuracoes/integracoes").json()["grupos"] if g["chave"] == "whatsapp")
        assert grupo["situacao"].startswith("⚠ Recebimento ligado, mas falta a chave secreta")

    def test_conversa_aparece_no_lead(self, cliente, fabrica):
        _configurar(fabrica)
        _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "oi")]))
        with fabrica() as s:
            lead_id = s.scalar(sa.select(Lead.id))
        conversas = cliente.get(f"/api/sdr/leads/{lead_id}/conversas").json()
        assert conversas[0]["mensagens"][0]["texto"] == "oi"
        assert conversas[0]["ultima_do_lead_em"] is not None

    def test_mensagens_na_ordem_do_horario_mesmo_entregues_fora_de_ordem(self, cliente, fabrica):
        _configurar(fabrica)
        _enviar(cliente, _payload(mensagens=[_texto("w2", "5511987654321", "segunda", ts=1760450100)]))
        _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "primeira", ts=1760450000)]))
        with fabrica() as s:
            lead_id = s.scalar(sa.select(Lead.id))
        textos = [m["texto"] for m in cliente.get(f"/api/sdr/leads/{lead_id}/conversas").json()[0]["mensagens"]]
        assert textos == ["primeira", "segunda"]

    def test_falha_ao_gravar_nao_vaza_conteudo_no_log(self, cliente, fabrica, caplog, monkeypatch):
        import crm.api.whatsapp_recebido as rota

        def quebra(*_a, **_k):
            raise sa.exc.IntegrityError("INSERT ... 'meu faturamento' '5511987654321'", {}, Exception("x"))

        monkeypatch.setattr(rota, "processar", quebra)
        _configurar(fabrica)
        with caplog.at_level(logging.INFO):
            r = _enviar(cliente, _payload(mensagens=[_texto("w1", "5511987654321", "meu faturamento")]))
        assert r.status_code == 500 and r.content == b""
        assert "IntegrityError" in caplog.text and "faturamento" not in caplog.text and "987654321" not in caplog.text
        assert _contar(fabrica, MensagemDoSdr) == 0


    def test_botao_de_descadastro_do_modelo_marca_nao_contatar(self, cliente, fabrica):
        _configurar(fabrica)
        _enviar(cliente, _payload(mensagens=[{"from": "5511987654321", "id": "w1", "timestamp": "1760450040",
                                              "type": "button", "button": {"text": "Parar promoções", "payload": "x"}}]))
        with fabrica() as s:
            assert s.scalar(sa.select(Lead)).nao_contatar is True
