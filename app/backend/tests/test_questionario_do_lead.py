"""O questionário na conversa do SDR de IA: agradecer quem respondeu, lembrar em 48 horas — 06/10/2026."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.agente.config import LINK_DO_QUESTIONARIO_PADRAO
from crm.api.app import criar_app
from crm.db.modelos import Lead, QuestionarioRecebido
from crm.domain.listas import SituacaoDoQuestionario
from crm.domain.questionario_do_lead import (
    Contato,
    PassoDoQuestionario as P,
    mesmo_contato,
    passo_do_questionario,
    tem_o_link,
)

AGORA = datetime(2026, 10, 6, 15, tzinfo=timezone.utc)


def passo(enviado=None, respondido=None, lembrado=None, agradecido=None, agora=AGORA):
    return passo_do_questionario(
        enviado_em=enviado, respondido_em=respondido, lembrado_em=lembrado, agradecido_em=agradecido, agora=agora
    )


class TestPasso:
    def test_sem_envio_nao_ha_o_que_cobrar(self):
        assert passo() is P.NAO_ENVIADO

    def test_lembra_so_depois_de_48_horas(self):
        assert passo(enviado=AGORA - timedelta(hours=47, minutes=59)) is P.AGUARDANDO
        assert passo(enviado=AGORA - timedelta(hours=48)) is P.LEMBRAR

    def test_lembra_uma_vez_so(self):
        assert passo(enviado=AGORA - timedelta(days=5), lembrado=AGORA - timedelta(days=2)) is P.LEMBRADO

    def test_respondeu_vence_o_prazo_e_o_lembrete(self):
        enviado = AGORA - timedelta(days=5)
        assert passo(enviado=enviado, respondido=AGORA) is P.AGRADECER
        assert passo(enviado=enviado, respondido=AGORA, lembrado=AGORA - timedelta(days=2)) is P.AGRADECER
        assert passo(enviado=enviado, respondido=AGORA, agradecido=AGORA) is P.AGRADECIDO

    def test_respondeu_sem_link_da_ia_nao_pede_agradecimento(self):
        assert passo(respondido=AGORA) is P.RESPONDIDO


class TestQuemEQuem:
    @pytest.mark.parametrize("questionario", [
        Contato(cnpj="12345678000190"),
        Contato(email=" Ana@Hospital.com.br "),
        Contato(celular="+55 (31) 99876-5432"),
        Contato(oportunidade_id=7),
    ])
    def test_basta_um_dado_bater(self, questionario):
        lead = Contato(cnpj="12.345.678/0001-90", email="ana@hospital.com.br", celular="31998765432", oportunidade_id=7)
        assert mesmo_contato(lead, questionario)

    def test_vazio_nunca_bate_com_vazio(self):
        assert not mesmo_contato(Contato(), Contato())
        assert not mesmo_contato(Contato(email="a@b.com"), Contato(email="c@d.com", celular="31998765432"))

    def test_link_antigo_e_novo_contam(self):
        links = ("https://questionario.criterio.com.br", LINK_DO_QUESTIONARIO_PADRAO)
        assert tem_o_link(f"Segue o link: {LINK_DO_QUESTIONARIO_PADRAO}", links)
        assert tem_o_link("Segue: https://questionario.criterio.com.br/", links)
        assert not tem_o_link("Vou te mandar o questionário.", links)


# ---------------------------------------------------------------- API
@pytest.fixture
def fabrica(engine: sa.Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


@pytest.fixture
def cliente(fabrica) -> TestClient:
    with TestClient(criar_app(fabrica)) as aberto:
        yield aberto


def conversa_com_link(cliente: TestClient, **lead) -> tuple[int, int]:
    corpo = {"nome": "Ana", "tipo_canal": "Tráfego pago", "canal": "Meta Ads"} | lead
    lead_id = cliente.post("/api/leads", json=corpo).json()["id"]
    conversa = cliente.post("/api/sdr/conversas", json={"lead_id": lead_id, "canal": "WhatsApp"}).json()["id"]
    resposta = falar(cliente, conversa, f"Segue o questionário: {LINK_DO_QUESTIONARIO_PADRAO}")
    assert resposta.status_code == 201, resposta.text
    return lead_id, conversa


def falar(cliente: TestClient, conversa: int, texto: str, autor: str = "IA", **campos):
    return cliente.post(f"/api/sdr/conversas/{conversa}/mensagens", json={"autor": autor, "texto": texto} | campos)


def recuar_envio(fabrica, lead_id: int, horas: int) -> None:
    with fabrica() as sessao:
        lead = sessao.get(Lead, lead_id)
        lead.questionario_enviado_em = lead.questionario_enviado_em - timedelta(hours=horas)
        sessao.commit()


def responder(fabrica, **contato) -> None:
    with fabrica() as sessao:
        sessao.add(QuestionarioRecebido(
            externo_id=f"q-{contato}", recebido_em=datetime.now(timezone.utc), versao="v1",
            razao_social="Hospital", cnpj=contato.pop("cnpj", "11222333000181"), contato_nome="Ana",
            contato_email=contato.pop("email", None), contato_celular=contato.pop("celular", None),
            respostas={}, situacao=SituacaoDoQuestionario.IMPORTADO, o_que_fez="teste",
        ))
        sessao.commit()


def situacao(cliente: TestClient, lead_id: int) -> dict:
    return cliente.get(f"/api/sdr/leads/{lead_id}/questionario").json()


class TestApi:
    def test_a_mensagem_com_o_link_marca_o_envio(self, cliente):
        lead_id, _ = conversa_com_link(cliente)
        atual = situacao(cliente, lead_id)
        assert atual["passo"] == "Aguardando resposta" and atual["enviado_em"] is not None
        assert atual["lembrar_a_partir_de"] is not None

    def test_lembrete_antes_de_48_horas_e_recusado(self, cliente):
        lead_id, conversa = conversa_com_link(cliente)
        resposta = falar(cliente, conversa, "Conseguiu ver o questionário?", questionario="Lembrete")
        assert resposta.status_code == 409 and "48 horas" in resposta.json()["detail"]
        assert cliente.get("/api/sdr/questionario/pendentes").json() == []

    def test_depois_de_48_horas_lembra_uma_vez(self, cliente, fabrica):
        lead_id, conversa = conversa_com_link(cliente)
        recuar_envio(fabrica, lead_id, 49)
        (pendente,) = cliente.get("/api/sdr/questionario/pendentes").json()
        assert (pendente["lead_id"], pendente["conversa_id"], pendente["passo"]) == (lead_id, conversa, "Lembrar")

        assert falar(cliente, conversa, "Conseguiu ver o questionário?", questionario="Lembrete").status_code == 201
        assert situacao(cliente, lead_id)["passo"] == "Lembrete enviado"
        de_novo = falar(cliente, conversa, "E o questionário?", questionario="Lembrete")
        assert de_novo.status_code == 409 and "já foi enviado" in de_novo.json()["detail"]
        assert cliente.get("/api/sdr/questionario/pendentes").json() == []

    def test_respondeu_agradece_uma_vez_e_nunca_lembra(self, cliente, fabrica):
        lead_id, conversa = conversa_com_link(cliente, email="ana@hospital.com.br")
        recuar_envio(fabrica, lead_id, 72)
        responder(fabrica, email="ANA@hospital.com.br")

        (pendente,) = cliente.get("/api/sdr/questionario/pendentes").json()
        assert pendente["passo"] == "Agradecer" and pendente["respondido_em"] is not None
        lembrete = falar(cliente, conversa, "Conseguiu ver?", questionario="Lembrete")
        assert lembrete.status_code == 409 and "já respondeu" in lembrete.json()["detail"]

        assert falar(cliente, conversa, "Obrigada pelas respostas!", questionario="Agradecimento").status_code == 201
        assert situacao(cliente, lead_id)["passo"] == "Agradecido"
        assert falar(cliente, conversa, "Obrigada!", questionario="Agradecimento").status_code == 409

    def test_agradecer_sem_resposta_e_recusado(self, cliente):
        _, conversa = conversa_com_link(cliente)
        assert falar(cliente, conversa, "Obrigada!", questionario="Agradecimento").status_code == 409

    def test_conversa_encerrada_so_recebe_lembrete_e_agradecimento(self, cliente, fabrica):
        lead_id, conversa = conversa_com_link(cliente, telefone="(31) 99876-5432")
        encerrada = cliente.post(f"/api/sdr/conversas/{conversa}/encerrar", json={"desfecho": "Parou no meio"})
        assert encerrada.status_code == 200, encerrada.text
        assert falar(cliente, conversa, "Oi de novo").status_code == 409
        responder(fabrica, celular="5531998765432")
        assert falar(cliente, conversa, "Obrigada!", questionario="Agradecimento").status_code == 201

    def test_lembrete_continua_sem_preco(self, cliente, fabrica):
        lead_id, conversa = conversa_com_link(cliente)
        recuar_envio(fabrica, lead_id, 49)
        assert falar(cliente, conversa, "A proposta sai por R$ 5 mil", questionario="Lembrete").status_code == 422

    def test_so_a_ia_marca_a_mensagem_do_questionario(self, cliente):
        _, conversa = conversa_com_link(cliente)
        assert falar(cliente, conversa, "Oi", autor="Equipe", questionario="Lembrete").status_code == 422

    def test_nao_contatar_some_da_lista(self, cliente, fabrica):
        lead_id, _ = conversa_com_link(cliente)
        recuar_envio(fabrica, lead_id, 49)
        with fabrica() as sessao:
            sessao.get(Lead, lead_id).nao_contatar = True
            sessao.commit()
        assert cliente.get("/api/sdr/questionario/pendentes").json() == []
