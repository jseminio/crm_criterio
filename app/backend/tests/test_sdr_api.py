"""As rotas do SDR de IA e as regras novas do lead — 27/09/2026."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from crm.api.app import criar_app
from crm.db.modelos import ConversaDoSdr, Lead


@pytest.fixture
def cliente(engine: sa.Engine) -> TestClient:
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as aberto:
        yield aberto


def novo_lead(cliente: TestClient, **campos) -> int:
    corpo = {"nome": "Ana", "tipo_canal": "Tráfego pago", "canal": "Meta Ads"} | campos
    resposta = cliente.post("/api/leads", json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


def nova_conversa(cliente: TestClient, lead_id: int) -> int:
    resposta = cliente.post("/api/sdr/conversas", json={"lead_id": lead_id, "canal": "WhatsApp"})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


def falar(cliente: TestClient, conversa: int, autor: str, texto: str = "Olá", **campos):
    return cliente.post(
        f"/api/sdr/conversas/{conversa}/mensagens", json={"autor": autor, "texto": texto} | campos
    )


def encerrar(cliente: TestClient, conversa: int, **corpo):
    return cliente.post(f"/api/sdr/conversas/{conversa}/encerrar", json=corpo)


def lead_de(cliente: TestClient, lead_id: int) -> dict:
    return next(l for l in cliente.get("/api/leads").json()["itens"] if l["id"] == lead_id)


class TestSituacaoDoLead:
    def test_qualificar_exige_porte(self, cliente):
        lead = novo_lead(cliente)
        resposta = cliente.patch(f"/api/leads/{lead}", json={"situacao": "Qualificado"})
        assert resposta.status_code == 422
        assert "porte" in resposta.json()["detail"]

    def test_qualificar_carimba_a_data(self, cliente):
        lead = novo_lead(cliente)
        resposta = cliente.patch(
            f"/api/leads/{lead}", json={"situacao": "Qualificado", "porte_estimado": "Médio"}
        ).json()
        assert resposta["situacao"] == "Qualificado"
        assert resposta["qualificado_em"] is not None

    def test_porte_desconhecido(self, cliente):
        lead = novo_lead(cliente)
        resposta = cliente.patch(f"/api/leads/{lead}", json={"porte_estimado": "Gigante"})
        assert resposta.status_code == 422

    def test_descartar_exige_motivo(self, cliente):
        lead = novo_lead(cliente)
        assert cliente.patch(f"/api/leads/{lead}", json={"situacao": "Descartado"}).status_code == 422

    def test_pedir_para_nao_ser_contatado_marca_o_lead(self, cliente):
        lead = novo_lead(cliente)
        resposta = cliente.patch(
            f"/api/leads/{lead}",
            json={"situacao": "Descartado", "motivo_descarte": "Pediu para não ser contatado"},
        ).json()
        assert resposta["nao_contatar"] is True
        assert resposta["descartado_em"] is not None

    def test_reabrir_apaga_qualificacao_e_descarte(self, cliente):
        lead = novo_lead(cliente)
        cliente.patch(f"/api/leads/{lead}", json={"situacao": "Descartado", "motivo_descarte": "Outro"})
        resposta = cliente.patch(f"/api/leads/{lead}", json={"situacao": "Em contato"}).json()
        assert (resposta["motivo_descarte"], resposta["descartado_em"]) == (None, None)

    def test_motivo_sozinho_so_para_lead_descartado(self, cliente):
        lead = novo_lead(cliente)
        resposta = cliente.patch(f"/api/leads/{lead}", json={"motivo_descarte": "Outro"})
        assert resposta.status_code == 422

    def test_so_lead_qualificado_vira_oportunidade(self, cliente):
        lead = novo_lead(cliente)
        resposta = cliente.post(f"/api/leads/{lead}/converter", json={})
        assert resposta.status_code == 422
        assert "qualificado" in resposta.json()["detail"]

    def test_filtra_por_origem(self, cliente):
        novo_lead(cliente)
        novo_lead(cliente, tipo_canal="Prospecção ativa", canal=None)
        resposta = cliente.get("/api/leads", params={"tipo_canal": "Prospecção ativa"}).json()
        assert resposta["total"] == 1

    def test_listas_trazem_os_motivos_de_descarte(self, cliente):
        listas = cliente.get("/api/listas").json()
        assert "Pediu para não ser contatado" in listas["motivos_de_descarte"]
        assert "Prospecção ativa" in listas["tipos_de_canal"]


class TestConversa:
    def test_mensagem_do_lead_tira_de_novo(self, cliente):
        lead = novo_lead(cliente)
        conversa = nova_conversa(cliente, lead)
        assert falar(cliente, conversa, "Lead", tom="Positivo").status_code == 201
        assert lead_de(cliente, lead)["situacao"] == "Em contato"

    def test_uma_conversa_aberta_por_vez(self, cliente):
        lead = novo_lead(cliente)
        nova_conversa(cliente, lead)
        resposta = cliente.post("/api/sdr/conversas", json={"lead_id": lead, "canal": "E-mail"})
        assert resposta.status_code == 409

    def test_ia_nao_fala_de_preco(self, cliente):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        resposta = falar(cliente, conversa, "IA", "A mensalidade fica em R$ 2.500")
        assert resposta.status_code == 422
        assert "preço" in resposta.json()["detail"]

    def test_a_equipe_pode_falar_de_preco(self, cliente):
        """A trava é da IA. Depois do transbordo, quem fala de preço é a pessoa."""
        conversa = nova_conversa(cliente, novo_lead(cliente))
        assert falar(cliente, conversa, "Equipe", "O honorário é R$ 2.500").status_code == 201

    def test_nada_sai_para_quem_pediu_para_nao_ser_contatado(self, cliente):
        lead = novo_lead(cliente)
        conversa = nova_conversa(cliente, lead)
        cliente.patch(f"/api/leads/{lead}", json={"nao_contatar": True})
        assert falar(cliente, conversa, "IA", "Oi de novo").status_code == 409
        assert falar(cliente, conversa, "Equipe", "Oi de novo").status_code == 409
        # O lead ainda pode escrever: a trava é sobre o que a Critério envia.
        assert falar(cliente, conversa, "Lead", "Parem, por favor").status_code == 201

    def test_nao_abre_conversa_com_quem_pediu_para_nao_ser_contatado(self, cliente):
        lead = novo_lead(cliente)
        cliente.patch(f"/api/leads/{lead}", json={"nao_contatar": True})
        resposta = cliente.post("/api/sdr/conversas", json={"lead_id": lead, "canal": "WhatsApp"})
        assert resposta.status_code == 409

    def test_campos_da_ia_so_na_mensagem_da_ia(self, cliente):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        assert falar(cliente, conversa, "Lead", confianca=0.9).status_code == 422
        assert falar(cliente, conversa, "IA", tom="Positivo").status_code == 422

    def test_confianca_fora_de_0_a_1(self, cliente):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        assert falar(cliente, conversa, "IA", confianca=1.2).status_code == 422

    def test_o_horario_e_do_servidor(self, cliente):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        resposta = falar(cliente, conversa, "IA", enviada_em="2020-01-01T00:00:00Z").json()
        assert not resposta["enviada_em"].startswith("2020")


class TestEncerramento:
    def test_qualificado_qualifica_o_lead(self, cliente):
        lead = novo_lead(cliente)
        conversa = nova_conversa(cliente, lead)
        resposta = encerrar(
            cliente, conversa, desfecho="Qualificado", porte_estimado="Grande",
            cnpj="12.345.678/0001-90", interesse="Trocar de contador",
        )
        assert resposta.status_code == 200, resposta.text
        dados = lead_de(cliente, lead)
        assert (dados["situacao"], dados["porte_estimado"], dados["interesse"]) == (
            "Qualificado", "Grande", "Trocar de contador"
        )

    def test_qualificado_sem_porte_nao_encerra(self, cliente):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        assert encerrar(cliente, conversa, desfecho="Qualificado").status_code == 422

    def test_fora_do_perfil_descarta_com_o_motivo(self, cliente):
        lead = novo_lead(cliente)
        conversa = nova_conversa(cliente, lead)
        encerrar(cliente, conversa, desfecho="Fora do perfil", motivo_descarte="Porte abaixo do mínimo")
        dados = lead_de(cliente, lead)
        assert (dados["situacao"], dados["motivo_descarte"]) == ("Descartado", "Porte abaixo do mínimo")

    def test_transbordo_exige_motivo_e_destino(self, cliente):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        assert encerrar(cliente, conversa, desfecho="Passou para a equipe").status_code == 422

    def test_ia_nao_fala_depois_de_encerrar(self, cliente):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        encerrar(cliente, conversa, desfecho="Parou no meio")
        assert falar(cliente, conversa, "IA").status_code == 409
        assert encerrar(cliente, conversa, desfecho="Parou no meio").status_code == 409

    def test_primeira_mensagem_da_equipe_encerra_a_espera(self, cliente, sessao: Session):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        encerrar(
            cliente, conversa, desfecho="Passou para a equipe",
            motivo_transbordo="Perguntou o preço", destino_transbordo="Comercial · BPO (C1)",
        )
        falar(cliente, conversa, "Equipe", "Oi, aqui é da Critério")
        primeira = sessao.get(ConversaDoSdr, conversa).atendida_em
        falar(cliente, conversa, "Equipe", "Posso te ligar?")
        sessao.expire_all()
        assert primeira is not None
        assert sessao.get(ConversaDoSdr, conversa).atendida_em == primeira

    def test_nota_so_depois_de_encerrar_e_uma_vez(self, cliente):
        conversa = nova_conversa(cliente, novo_lead(cliente))
        rota = f"/api/sdr/conversas/{conversa}/nota"
        assert cliente.post(rota, json={"nota": 5}).status_code == 409
        encerrar(cliente, conversa, desfecho="Parou no meio")
        assert cliente.post(rota, json={"nota": 6}).status_code == 422
        assert cliente.post(rota, json={"nota": 5}).status_code == 200
        assert cliente.post(rota, json={"nota": 4}).status_code == 409

    def test_conversas_do_lead_trazem_as_mensagens(self, cliente):
        lead = novo_lead(cliente)
        conversa = nova_conversa(cliente, lead)
        falar(cliente, conversa, "IA", "Oi, sou da Critério", confianca=0.9, intencao="Saudação")
        falar(cliente, conversa, "Lead", "Oi")
        conversas = cliente.get(f"/api/sdr/leads/{lead}/conversas").json()
        assert [m["autor"] for m in conversas[0]["mensagens"]] == ["IA", "Lead"]


class TestCustosEMidia:
    def test_parametros_comecam_vazios_e_gravam(self, cliente):
        assert cliente.get("/api/sdr/parametros").json()["custo_hora_sdr"] is None
        cliente.put(
            "/api/sdr/parametros",
            json={"custo_hora_sdr": "45.00", "minutos_por_conversa": 25, "cotacao_dolar": "5.40"},
        )
        assert cliente.get("/api/sdr/parametros").json()["minutos_por_conversa"] == 25

    def test_midia_regrava_o_mesmo_mes_e_canal(self, cliente):
        cliente.put("/api/sdr/midia", json={"mes": "2026-09", "canal": "Meta Ads", "valor": "100"})
        cliente.put("/api/sdr/midia", json={"mes": "2026-09", "canal": " Meta Ads ", "valor": "250"})
        itens = cliente.get("/api/sdr/midia", params={"mes": "2026-09"}).json()
        assert [(i["canal"], i["valor"]) for i in itens] == [("Meta Ads", "250.00")]

    def test_midia_recusa_mes_invalido(self, cliente):
        resposta = cliente.put("/api/sdr/midia", json={"mes": "2026-13", "canal": "X", "valor": "1"})
        assert resposta.status_code == 422


class TestPainel:
    def test_painel_do_mes_com_o_que_foi_registrado(self, cliente, sessao: Session):
        qualificado = novo_lead(cliente)
        conversa = nova_conversa(cliente, qualificado)
        falar(cliente, conversa, "IA", "Oi!", confianca=0.9, custo_usd="0.05")
        falar(cliente, conversa, "Lead", "Quero trocar de contador", tom="Positivo")
        encerrar(cliente, conversa, desfecho="Qualificado", porte_estimado="Médio")
        novo_lead(cliente)  # não respondeu

        # O lead nasce agora; o painel olha o mês de agora.
        agora = datetime.now(timezone.utc)
        mes = f"{agora.year:04d}-{agora.month:02d}"
        cliente.put("/api/sdr/midia", json={"mes": mes, "canal": "Meta Ads", "valor": "200"})

        painel = cliente.get("/api/sdr/painel", params={"mes": mes}).json()
        assert (painel["leads"], painel["responderam"], painel["qualificados"]) == (2, 1, 1)
        assert painel["qualificacao_concluida"]["valor"] == 100.0
        meta = painel["por_origem"][0]
        assert (meta["origem"], meta["custo_por_qualificado"]) == ("Tráfego pago · Meta Ads", "200.00")
        assert painel["anterior"]["qualificados"] == 0
        assert painel["custo_poupado"]["calculavel"] is False

    def test_mes_invalido(self, cliente):
        assert cliente.get("/api/sdr/painel", params={"mes": "setembro"}).status_code == 422

    def test_origem_invalida(self, cliente):
        resposta = cliente.get("/api/sdr/painel", params={"mes": "2026-09", "origem": "socios"})
        assert resposta.status_code == 422
