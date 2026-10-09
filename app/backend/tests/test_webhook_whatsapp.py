"""Webhook do WhatsApp (09/10/2026): verificação, assinatura, registro sem duplicar e a conversa do lead."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm import configuracao
from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.agente.webhook_whatsapp import (
    SEM_LEAD, assinatura_confere, desafio_da_verificacao, processar, variantes_do_numero,
)
from crm.api.app import criar_app
from crm.db.modelos import ConversaDoSdr, EventoDoWhatsapp, Lead, MensagemDoSdr
from crm.domain.listas import AutorDaMensagem, CanalDeAbordagem, DesfechoDaConversa, SituacaoLead

CHAVE = "0123456789abcdef0123456789abcdef"
VERIFICACAO = "token-de-verificacao-do-teste"
AGORA = datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc)


def _aviso(*, mensagens=(), status=()) -> dict:
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{
        "field": "messages",
        "value": {"messaging_product": "whatsapp", "messages": list(mensagens), "statuses": list(status)},
    }]}]}


def _texto(id_: str, de: str, corpo: str, quando: int = 1760018400) -> dict:
    return {"id": id_, "from": de, "timestamp": str(quando), "type": "text", "text": {"body": corpo}}


def _assinar(corpo: bytes, chave: str = CHAVE) -> str:
    return "sha256=" + hmac.new(chave.encode(), corpo, hashlib.sha256).hexdigest()


# ----------------------------------------------------------------- funções
class TestConferencias:
    def test_assinatura(self):
        corpo = b'{"a":1}'
        assert assinatura_confere(corpo, _assinar(corpo), CHAVE)
        assert not assinatura_confere(corpo, _assinar(corpo, "f" * 32), CHAVE)
        assert not assinatura_confere(b'{"a":2}', _assinar(corpo), CHAVE)
        assert not assinatura_confere(corpo, None, CHAVE)
        assert not assinatura_confere(corpo, _assinar(corpo), None)  # sem chave cadastrada, nada passa

    def test_verificacao(self):
        assert desafio_da_verificacao("subscribe", VERIFICACAO, "123", VERIFICACAO) == "123"
        assert desafio_da_verificacao("subscribe", "outro", "123", VERIFICACAO) is None
        assert desafio_da_verificacao("subscribe", VERIFICACAO, "123", None) is None
        assert desafio_da_verificacao("unsubscribe", VERIFICACAO, "123", VERIFICACAO) is None

    def test_nono_digito(self):
        assert variantes_do_numero("(21) 98765-4321") == {"5521987654321", "552187654321"}
        assert variantes_do_numero("552187654321") == {"552187654321", "5521987654321"}
        assert variantes_do_numero(None) == set()


# ----------------------------------------------------------------- processar
@pytest.fixture
def lead(sessao):
    l = Lead(nome="Ana", telefone="(21) 98765-4321")
    sessao.add(l)
    sessao.commit()
    return l


class TestProcessar:
    def test_mensagem_do_lead_abre_conversa_pelo_whatsapp(self, sessao, lead):
        # A Meta manda o wa_id sem o nono dígito: o lead é achado mesmo assim.
        resumo = processar(sessao, _aviso(mensagens=[_texto("wamid.1", "552187654321", "Quero a proposta")]), AGORA)
        assert (resumo.novos, resumo.na_conversa) == (1, 1)
        conversa = sessao.scalar(sa.select(ConversaDoSdr))
        assert conversa.lead_id == lead.id and conversa.canal is CanalDeAbordagem.WHATSAPP
        mensagem = sessao.scalar(sa.select(MensagemDoSdr))
        assert mensagem.autor is AutorDaMensagem.LEAD and mensagem.texto == "Quero a proposta"
        assert mensagem.enviada_em.replace(tzinfo=timezone.utc) == datetime.fromtimestamp(1760018400, tz=timezone.utc)
        evento = sessao.scalar(sa.select(EventoDoWhatsapp))
        assert evento.situacao == "na conversa" and evento.mensagem_id == mensagem.id
        assert lead.situacao is SituacaoLead.EM_CONTATO

    def test_reenvio_da_meta_nao_duplica(self, sessao, lead):
        aviso = _aviso(mensagens=[_texto("wamid.1", "5521987654321", "Oi")])
        processar(sessao, aviso, AGORA)
        resumo = processar(sessao, aviso, AGORA)
        assert (resumo.novos, resumo.repetidos) == (0, 1)
        assert sessao.scalar(sa.select(sa.func.count()).select_from(MensagemDoSdr)) == 1

    def test_usa_a_conversa_aberta(self, sessao, lead):
        aberta = ConversaDoSdr(lead_id=lead.id, canal=CanalDeAbordagem.EMAIL, iniciada_em=AGORA)
        sessao.add(aberta)
        sessao.flush()
        processar(sessao, _aviso(mensagens=[_texto("wamid.1", "5521987654321", "Oi")]), AGORA)
        assert sessao.scalar(sa.select(sa.func.count()).select_from(ConversaDoSdr)) == 1
        assert sessao.scalar(sa.select(MensagemDoSdr.conversa_id)) == aberta.id

    def test_conversa_encerrada_abre_outra(self, sessao, lead):
        sessao.add(ConversaDoSdr(lead_id=lead.id, canal=CanalDeAbordagem.WHATSAPP, iniciada_em=AGORA,
                                 desfecho=DesfechoDaConversa.TRANSBORDO, encerrada_em=AGORA))
        sessao.flush()
        processar(sessao, _aviso(mensagens=[_texto("wamid.1", "5521987654321", "Oi de novo")]), AGORA)
        assert sessao.scalar(sa.select(sa.func.count()).select_from(ConversaDoSdr)) == 2

    def test_numero_desconhecido_nao_cria_lead(self, sessao, lead):
        resumo = processar(sessao, _aviso(mensagens=[_texto("wamid.9", "5511900000000", "Quem é?")]), AGORA)
        assert resumo.sem_lead == 1
        assert sessao.scalar(sa.select(sa.func.count()).select_from(Lead)) == 1
        assert sessao.scalar(sa.select(sa.func.count()).select_from(MensagemDoSdr)) == 0
        assert sessao.scalar(sa.select(EventoDoWhatsapp.situacao)) == SEM_LEAD

    def test_audio_entra_como_marcador(self, sessao, lead):
        audio = {"id": "wamid.2", "from": "5521987654321", "timestamp": "1760018400", "type": "audio",
                 "audio": {"id": "midia-1", "mime_type": "audio/ogg"}}
        processar(sessao, _aviso(mensagens=[audio]), AGORA)
        assert sessao.scalar(sa.select(MensagemDoSdr.texto)) == "[áudio recebido]"

    def test_status_so_registra(self, sessao, lead):
        status = {"id": "wamid.saida", "status": "read", "timestamp": "1760018400", "recipient_id": "5521987654321"}
        processar(sessao, _aviso(status=[status]), AGORA)
        processar(sessao, _aviso(status=[status]), AGORA)
        evento = sessao.scalars(sa.select(EventoDoWhatsapp)).one()
        assert (evento.tipo, evento.situacao, evento.lead_id) == ("status", "read", lead.id)
        assert sessao.scalar(sa.select(sa.func.count()).select_from(MensagemDoSdr)) == 0

    def test_aviso_que_nao_e_do_whatsapp(self, sessao):
        assert processar(sessao, {"object": "page", "entry": []}, AGORA).novos == 0


# ----------------------------------------------------------------- rota
@pytest.fixture
def fabrica(engine):
    f = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    configuracao.registrar_fabrica(f)
    yield f
    configuracao.registrar_fabrica(None)


@pytest.fixture
def cliente(fabrica):
    # Com login ligado: o webhook tem de passar sem entrada, porque quem chama é a Meta.
    entrada = ConfiguracaoDeEntrada("tenant-teste", "cliente-teste", frozenset())
    with TestClient(criar_app(fabrica, entrada=entrada, validar_token=lambda t: {})) as c:
        yield c


def _configurar(fabrica):
    with fabrica() as s:
        configuracao.gravar(s, "whatsapp.verificacao", VERIFICACAO, "Eduardo")
        configuracao.gravar(s, "whatsapp.chave_do_app", CHAVE, "Eduardo")
        s.commit()


class TestRota:
    URL = "/api/whatsapp/webhook"

    def test_sem_configurar_recusa_tudo(self, cliente):
        assert cliente.get(self.URL, params={"hub.mode": "subscribe", "hub.verify_token": "x",
                                             "hub.challenge": "1"}).status_code == 403
        corpo = json.dumps(_aviso()).encode()
        assert cliente.post(self.URL, content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)}).status_code == 403

    def test_verificacao_devolve_o_desafio(self, cliente, fabrica):
        _configurar(fabrica)
        r = cliente.get(self.URL, params={"hub.mode": "subscribe", "hub.verify_token": VERIFICACAO,
                                          "hub.challenge": "1158201444"})
        assert r.status_code == 200 and r.text == "1158201444"
        errado = cliente.get(self.URL, params={"hub.mode": "subscribe", "hub.verify_token": "outro",
                                               "hub.challenge": "1"})
        assert errado.status_code == 403

    def test_aviso_assinado_entra_e_o_falso_nao(self, cliente, fabrica):
        _configurar(fabrica)
        with fabrica() as s:
            s.add(Lead(nome="Ana", telefone="21987654321"))
            s.commit()
        corpo = json.dumps(_aviso(mensagens=[_texto("wamid.1", "5521987654321", "Oi")])).encode()
        falso = cliente.post(self.URL, content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo, "e" * 32)})
        assert falso.status_code == 403
        r = cliente.post(self.URL, content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
        assert r.status_code == 200 and r.json() == {"novos": 1, "repetidos": 0}
        with fabrica() as s:
            assert s.scalar(sa.select(MensagemDoSdr.texto)) == "Oi"

    def test_tela_mostra_o_endereco_e_o_ultimo_aviso(self, fabrica):
        _configurar(fabrica)
        with TestClient(criar_app(fabrica)) as c:  # sem login: a tela de Integrações
            corpo = json.dumps(_aviso(mensagens=[_texto("wamid.1", "5511900000000", "Oi")])).encode()
            c.post(self.URL, content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
            whatsapp = next(g for g in c.get("/api/configuracoes/integracoes").json()["grupos"] if g["chave"] == "whatsapp")
        assert whatsapp["webhook"]["caminho"] == self.URL
        assert whatsapp["webhook"]["ultimo_aviso_situacao"] == SEM_LEAD
        campos = {c["chave"]: c for c in whatsapp["campos"]}
        assert campos["whatsapp.verificacao"]["secao"] == "Receber respostas (webhook)"
        assert campos["whatsapp.chave_do_app"]["valor"] is None  # segredo nunca volta
        assert campos["whatsapp.chave_do_app"]["final"] == CHAVE[-4:]

    def test_webhook_nao_e_obrigatorio_para_configurado(self, fabrica):
        with fabrica() as s:
            configuracao.gravar(s, "whatsapp.token", "token-permanente-de-teste", "Eduardo")
            configuracao.gravar(s, "whatsapp.numero_id", "123456789012345", "Eduardo")
            s.commit()
        with TestClient(criar_app(fabrica)) as c:
            whatsapp = next(g for g in c.get("/api/configuracoes/integracoes").json()["grupos"] if g["chave"] == "whatsapp")
            assert whatsapp["configurado"] is True
            ruim = c.put("/api/configuracoes/integracoes/whatsapp", json={"valores": {"whatsapp.chave_do_app": "curta"}})
            assert ruim.status_code == 422 and "32 caracteres" in ruim.json()["detail"]
