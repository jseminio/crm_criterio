"""O disparo do lembrete e do agradecimento do questionário, e o envio pelo WhatsApp — sem rede (06/10/2026)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx2 as httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.agente.config import LINK_DO_QUESTIONARIO_PADRAO, ConfiguracaoDoWhatsapp, ler_configuracao
from crm.agente.disparo_do_questionario import MODELOS, Canais, disparar
from crm.agente.envio import EnvioFalhou
from crm.agente.whatsapp import enviar_modelo
from crm.api.app import criar_app
from crm.api.disparo_do_questionario import EstadoDoDisparo, rodar_uma_vez
from crm.db.modelos import Lead, QuestionarioRecebido
from crm.domain.listas import SituacaoDoQuestionario

REPO = Path(__file__).resolve().parents[3]
BRASILIA = timezone(timedelta(hours=-3))
TERCA_MEIO_DIA = datetime(2026, 10, 6, 12, tzinfo=BRASILIA)
CONFIG = ConfiguracaoDoWhatsapp(token="token-secreto", numero_id="1234567890")


# ------------------------------------------------------------ WhatsApp
def _meta(status=200, corpo=None, pedidos=None):
    def tratar(pedido: httpx.Request) -> httpx.Response:
        if pedidos is not None:
            pedidos.append(pedido)
        return httpx.Response(status, json=corpo if corpo is not None else {"messages": [{"id": "wamid.1"}]})

    return httpx.Client(transport=httpx.MockTransport(tratar))


class TestWhatsapp:
    def test_envia_o_modelo_no_formato_da_meta(self):
        pedidos: list[httpx.Request] = []
        mid = enviar_modelo(CONFIG, para="5531998765432", modelo="criterio_lembrete_questionario",
                            parametros={"nome": "Ana", "servico": "BPO Financeiro"}, http=_meta(pedidos=pedidos))
        assert mid == "wamid.1"
        (pedido,) = pedidos
        assert str(pedido.url) == "https://graph.facebook.com/v24.0/1234567890/messages"
        assert pedido.headers["Authorization"] == "Bearer token-secreto"
        corpo = json.loads(pedido.content)
        assert (corpo["messaging_product"], corpo["to"], corpo["type"]) == ("whatsapp", "5531998765432", "template")
        assert corpo["template"]["name"] == "criterio_lembrete_questionario"
        assert corpo["template"]["language"] == {"code": "pt_BR"}
        assert corpo["template"]["components"] == [{"type": "body", "parameters": [
            {"type": "text", "parameter_name": "nome", "text": "Ana"},
            {"type": "text", "parameter_name": "servico", "text": "BPO Financeiro"},
        ]}]

    def test_token_recusado_explica_sem_mostrar_o_token(self):
        with pytest.raises(EnvioFalhou) as falha:
            enviar_modelo(CONFIG, para="55", modelo="m", parametros={}, http=_meta(401, {}))
        assert "Integrações" in str(falha.value) and "token-secreto" not in str(falha.value)
        assert "token-secreto" not in repr(CONFIG)

    def test_erro_da_meta_vem_com_o_motivo(self):
        erro = {"error": {"message": "Template name does not exist in the translation", "code": 132001}}
        with pytest.raises(EnvioFalhou, match="Template name does not exist"):
            enviar_modelo(CONFIG, para="55", modelo="m", parametros={}, http=_meta(404, erro))

    def test_configuracao_vem_do_env(self, tmp_path, monkeypatch):
        from crm.db import sessao as modulo

        arquivo = tmp_path / ".env"
        arquivo.write_text("CRM_WHATSAPP_TOKEN=t\nCRM_WHATSAPP_NUMERO_ID=99\nCRM_DISPARO_DO_QUESTIONARIO=true\n")
        monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)
        config = ler_configuracao()
        assert config.whatsapp == ConfiguracaoDoWhatsapp("t", "99", "v24.0") and config.disparo_ligado

    def test_sem_variavel_fica_desligado(self, tmp_path, monkeypatch):
        from crm.db import sessao as modulo

        arquivo = tmp_path / ".env"
        arquivo.write_text("CRM_WHATSAPP_TOKEN=t\n")
        monkeypatch.setattr(modulo, "ARQUIVO_ENV", arquivo)
        config = ler_configuracao()
        assert config.whatsapp is None and not config.disparo_ligado


class TestModelos:
    def test_os_textos_sao_os_mandados_para_a_meta(self):
        """Mudar o texto aqui sem mudar o documento (e a aprovação na Meta) derruba o teste."""
        documento = (REPO / "sdr-ia-modelos-whatsapp.md").read_text()
        for modelo in MODELOS.values():
            secao = documento.split(f"`{modelo.nome}`", 1)[1]
            corpo = re.search(r"\*\*Corpo\*\*\n\n((?:> .*\n)+)", secao).group(1)
            aprovado = " ".join(linha[2:] for linha in corpo.splitlines())
            assert modelo.corpo == re.sub(r"\{\{(\w+)\}\}", r"{\1}", aprovado)


# --------------------------------------------------------------- disparo
class Envios:
    def __init__(self, falhar: bool = False):
        self.whatsapp: list[tuple] = []
        self.email: list[tuple] = []
        self.falhar = falhar

    def canais(self, whatsapp=True, email=True) -> Canais:
        return Canais(whatsapp=self._whatsapp if whatsapp else None, email=self._email if email else None)

    def _whatsapp(self, para, modelo, parametros):
        if self.falhar:
            raise EnvioFalhou("A Meta não enviou o WhatsApp (HTTP 400): teste")
        self.whatsapp.append((para, modelo, parametros))

    def _email(self, para, assunto, corpo):
        self.email.append((para, assunto, corpo))


@pytest.fixture
def fabrica(engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def envios() -> Envios:
    return Envios()


@pytest.fixture
def cliente(fabrica, envios, monkeypatch) -> TestClient:
    import crm.api.sdr as rotas

    monkeypatch.setattr(rotas, "agora", lambda: TERCA_MEIO_DIA.astimezone(timezone.utc))
    with TestClient(criar_app(fabrica, canais_do_disparo=envios.canais)) as aberto:
        yield aberto


def lead_com_link(cliente: TestClient, fabrica, canal="WhatsApp", dias=4, **lead) -> int:
    corpo = {"nome": "Ana Souza", "tipo_canal": "Tráfego pago", "canal": "Meta Ads",
             "telefone": "(31) 99876-5432", "email": "ana@hospital.com.br", "interesse": "BPO Financeiro"} | lead
    lead_id = cliente.post("/api/leads", json=corpo).json()["id"]
    conversa = cliente.post("/api/sdr/conversas", json={"lead_id": lead_id, "canal": canal}).json()["id"]
    resposta = cliente.post(f"/api/sdr/conversas/{conversa}/mensagens",
                            json={"autor": "IA", "texto": f"Segue: {LINK_DO_QUESTIONARIO_PADRAO}"})
    assert resposta.status_code == 201, resposta.text
    with fabrica() as sessao:
        registro = sessao.get(Lead, lead_id)
        registro.questionario_enviado_em -= timedelta(days=dias)
        sessao.commit()
    return lead_id


def rodar(fabrica, canais: Canais, momento=TERCA_MEIO_DIA):
    with fabrica() as sessao:
        return disparar(sessao, canais, momento, LINK_DO_QUESTIONARIO_PADRAO)


def mensagens_da_ia(fabrica, lead_id: int) -> list[str]:
    with fabrica() as sessao:
        return [m.texto for c in sessao.get(Lead, lead_id).conversas for m in c.mensagens][1:]


class TestDisparo:
    def test_lembra_pelo_whatsapp_uma_vez_e_registra(self, cliente, fabrica, envios):
        lead_id = lead_com_link(cliente, fabrica)
        assert rodar(fabrica, envios.canais()).enviados == 1
        assert envios.whatsapp == [("5531998765432", "criterio_lembrete_questionario",
                                    {"nome": "Ana", "servico": "BPO Financeiro"})]
        (texto,) = mensagens_da_ia(fabrica, lead_id)
        assert texto.startswith("Olá, Ana! Aqui é a assistente virtual da Critério.")
        assert f"Responder o questionário: {LINK_DO_QUESTIONARIO_PADRAO}" in texto
        assert cliente.get(f"/api/sdr/leads/{lead_id}/questionario").json()["passo"] == "Lembrete enviado"

        assert rodar(fabrica, envios.canais()).enviados == 0 and len(envios.whatsapp) == 1

    def test_agradece_por_e_mail_quem_respondeu(self, cliente, fabrica, envios):
        lead_id = lead_com_link(cliente, fabrica, canal="E-mail", dias=0)
        with fabrica() as sessao:
            sessao.add(QuestionarioRecebido(
                externo_id="q1", recebido_em=datetime.now(timezone.utc), versao="v1", razao_social="Hospital",
                cnpj="11222333000181", contato_nome="Ana", contato_email="ana@hospital.com.br", respostas={},
                situacao=SituacaoDoQuestionario.IMPORTADO, o_que_fez="teste",
            ))
            sessao.commit()
        assert rodar(fabrica, envios.canais()).enviados == 1
        ((para, assunto, corpo),) = envios.email
        assert (para, assunto) == ("ana@hospital.com.br", "Recebemos o seu questionário")
        assert "obrigada pelo envio" in corpo and LINK_DO_QUESTIONARIO_PADRAO not in corpo
        assert cliente.get(f"/api/sdr/leads/{lead_id}/questionario").json()["passo"] == "Agradecido"

    def test_falha_no_envio_nao_carimba_e_tenta_de_novo(self, cliente, fabrica):
        lead_id = lead_com_link(cliente, fabrica)
        resultado = rodar(fabrica, Envios(falhar=True).canais())
        assert resultado.enviados == 0 and "HTTP 400" in resultado.erros[0]
        assert mensagens_da_ia(fabrica, lead_id) == []
        assert cliente.get(f"/api/sdr/leads/{lead_id}/questionario").json()["passo"] == "Lembrar"

    @pytest.mark.parametrize("momento", [
        datetime(2026, 10, 6, 20, tzinfo=BRASILIA), datetime(2026, 10, 10, 11, tzinfo=BRASILIA),
    ])
    def test_fora_do_horario_comercial_nada_sai(self, cliente, fabrica, envios, momento):
        lead_com_link(cliente, fabrica)
        resultado = rodar(fabrica, envios.canais(), momento)
        assert resultado.enviados == 0 and envios.whatsapp == [] and "horário comercial" in resultado.avisos[0]

    def test_canal_sem_configuracao_ou_contato_vira_aviso(self, cliente, fabrica, envios):
        lead_com_link(cliente, fabrica)
        lead_com_link(cliente, fabrica, nome="Bruno", telefone=None)
        resultado = rodar(fabrica, envios.canais(whatsapp=False))
        assert resultado.enviados == 0 and len(resultado.avisos) == 2
        assert "WhatsApp não configurado" in resultado.avisos[0]
        resultado = rodar(fabrica, envios.canais())
        assert resultado.enviados == 1 and "Bruno" in resultado.avisos[0] and "celular" in resultado.avisos[0]

    def test_desligado_nao_envia_e_diz_por_que(self, fabrica):
        estado = EstadoDoDisparo()
        rodar_uma_vez(fabrica, lambda: None, estado)
        retrato = estado.retrato()
        assert retrato["ligado"] is False and "Integrações" in retrato["avisos"][0]


class TestRotas:
    def test_disparar_agora_envia_e_mostra_o_estado(self, cliente, fabrica, envios):
        lead_com_link(cliente, fabrica)
        resposta = cliente.post("/api/sdr/questionario/disparar")
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["enviados"] == 1 and len(envios.whatsapp) == 1
        assert cliente.get("/api/sdr/questionario/disparo").json()["enviados"] == 1

    def test_desligado_recusa_o_disparo_manual(self, fabrica):
        with TestClient(criar_app(fabrica, canais_do_disparo=lambda: None)) as cliente:
            resposta = cliente.post("/api/sdr/questionario/disparar")
        assert resposta.status_code == 409 and "Integrações" in resposta.json()["detail"]
