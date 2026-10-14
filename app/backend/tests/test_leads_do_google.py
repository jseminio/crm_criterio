"""Leads do formulário do Google Ads entrando sozinhos no CRM — 14/10/2026."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx2 as httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm.anuncios import google as google_ads
from crm.api.app import criar_app
from crm.api.leads_do_meta import Busca, buscador_do_google, buscar_uma_vez
from crm.db.modelos import Lead
from crm.domain import conversoes as c
from crm.domain.leads_do_google import SEM_CAMPANHA, campos_do_lead
from crm.domain.listas import TipoCanal

AGORA = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)
CRED = google_ads.ConfiguracaoDoGoogleAds("dev", "cli", "seg", "rt", "1234567890", None, "v25")


def do_google(id="7001", campanha="BPO financeiro RJ", gclid="Cj0KCQ", respostas=None,
              quando=AGORA - timedelta(minutes=5)):
    return google_ads.LeadDoGoogle(id=id, criado_em=quando, gclid=gclid, campanha=campanha, respostas=respostas if
                                   respostas is not None else {
                                       "FULL_NAME": "Carlos Pereira", "EMAIL": "carlos@pereira.com.br",
                                       "PHONE_NUMBER": "+5521977776666", "COMPANY_NAME": "Pereira Ltda",
                                       "JOB_TITLE": "Sócio", "Qual o faturamento mensal?": "R$ 800 mil"})


class TestCampos:
    def test_campos_padrao_gclid_e_perguntas_na_observacao(self):
        campos = campos_do_lead(do_google())
        assert (campos["nome"], campos["email"], campos["telefone"], campos["empresa_texto"]) == (
            "Carlos Pereira", "carlos@pereira.com.br", "+5521977776666", "Pereira Ltda")
        assert campos["canal"] == "Google Ads" and campos["tipo_canal"] is TipoCanal.TRAFEGO_PAGO
        assert campos["campanha"] == "BPO financeiro RJ" and campos["gclid"] == "Cj0KCQ"
        assert campos["observacao"].splitlines()[:2] == ["Cargo: Sócio", "Qual o faturamento mensal: R$ 800 mil"]
        assert "formulário do Google Ads, 14/10/2026 11:55" in campos["observacao"]
        assert campos["google_lead_id"] == "7001"

    def test_sem_campanha_e_nome_em_duas_partes(self):
        campos = campos_do_lead(do_google(campanha=None, respostas={"FIRST_NAME": "Ana", "LAST_NAME": "Lima"}))
        assert campos["campanha"] == SEM_CAMPANHA and campos["nome"] == "Ana Lima"
        assert campos["observacao"].startswith("(Respondido no formulário do Google Ads")


def _http(paginas):
    pedidos = []

    def tratar(p: httpx.Request) -> httpx.Response:
        pedidos.append(p)
        if "oauth2" in str(p.url):
            return httpx.Response(200, json={"access_token": "ya29"})
        corpo = paginas.pop(0) if len(paginas) > 1 else paginas[0]
        return httpx.Response(200, json=corpo)

    return httpx.Client(transport=httpx.MockTransport(tratar)), pedidos


class TestBuscaNoGoogle:
    def test_le_os_envios_e_filtra_pela_data(self):
        http, pedidos = _http([{"results": [
            {"leadFormSubmissionData": {"id": "2", "gclid": "G2", "submissionDateTime": "2026-10-14 09:40:00-03:00",
                                        "leadFormSubmissionFields": [{"fieldType": "EMAIL", "fieldValue": "b@x.com"}],
                                        "customLeadFormSubmissionFields": [{"questionText": "Faturamento?", "fieldValue": "R$ 1 mi"}]},
             "campaign": {"name": "BPO RJ"}},
            {"leadFormSubmissionData": {"id": "1", "submissionDateTime": "2026-10-10 09:00:00-03:00"}},
        ]}])
        leads = google_ads.buscar_leads(CRED, datetime(2026, 10, 12, tzinfo=timezone.utc), http=http)
        assert [(l.id, l.gclid, l.campanha) for l in leads] == [("2", "G2", "BPO RJ")]
        assert leads[0].respostas == {"EMAIL": "b@x.com", "Faturamento?": "R$ 1 mi"}
        assert leads[0].criado_em == datetime(2026, 10, 14, 12, 40, tzinfo=timezone.utc)
        busca = json.loads(pedidos[-1].content)["query"]
        assert "FROM lead_form_submission_data" in busca and "gclid" in busca and "campaign.name" in busca

    def test_conta_errada_nao_pergunta(self):
        from crm.anuncios import LeituraFalhou
        errada = google_ads.ConfiguracaoDoGoogleAds("dev", "cli", "seg", "rt", "123", None, "v25")
        with pytest.raises(LeituraFalhou):
            google_ads.buscar_leads(errada, AGORA)


@pytest.fixture
def fabrica(engine: sa.Engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _busca(lidos):
    return Busca(lambda: (lambda desde: lidos), coluna="google_lead_id",
                 converter=buscador_do_google().converter)


class TestRodada:
    def test_cria_com_gclid_e_nunca_em_dobro(self, fabrica):
        with fabrica() as s:
            assert buscar_uma_vez(s, _busca([do_google("1"), do_google("2", gclid=None)]), AGORA).novos == 2
            assert buscar_uma_vez(s, _busca([do_google("1")]), AGORA).novos == 0
            leads = {l.google_lead_id: l for l in s.scalars(sa.select(Lead))}
            assert leads["1"].gclid == "Cj0KCQ" and leads["2"].gclid is None and leads["1"].canal == "Google Ads"

    def test_lead_do_google_com_gclid_ja_sai_na_devolucao(self, fabrica):
        with fabrica() as s:
            buscar_uma_vez(s, _busca([do_google("1")]), AGORA)
            lead = s.scalar(sa.select(Lead))
            lead.qualificado_em = AGORA
            envios, sem = c.pendentes([lead], [], [c.GOOGLE], AGORA)
            assert sem == {} and envios[0].gclid == "Cj0KCQ"


class TestRotas:
    def test_rotas_proprias_e_desligada(self, fabrica):
        with TestClient(criar_app(fabrica, busca_de_leads_do_google=lambda: Busca(lambda: None),
                                  leads_do_meta_automaticos=False)) as cliente:
            assert cliente.get("/api/sdr/leads-do-google").json() == {"ligada": False, "ultima": None}
            r = cliente.post("/api/sdr/leads-do-google/buscar")
        assert r.status_code == 409 and "leads do Google" in r.json()["detail"]

    def test_buscar_agora(self, fabrica):
        busca = lambda: _busca([do_google(quando=datetime.now(timezone.utc))])
        with TestClient(criar_app(fabrica, busca_de_leads_do_google=busca, leads_do_meta_automaticos=False)) as cliente:
            r = cliente.post("/api/sdr/leads-do-google/buscar")
            itens = cliente.get("/api/leads").json()["itens"]
        assert r.status_code == 200 and r.json()["novos"] == 1
        assert [(l["nome"], l["canal"], l["campanha"]) for l in itens] == [("Carlos Pereira", "Google Ads", "BPO financeiro RJ")]


def test_ligar_pela_tela(fabrica):
    with TestClient(criar_app(fabrica, leads_do_meta_automaticos=False, conversoes_automaticas=False)) as cliente:
        r = cliente.put("/api/configuracoes/integracoes/google_ads", json={"valores": {
            "google_ads.leads": "true", "google_ads.token_dev": "d", "google_ads.cliente_id": "c",
            "google_ads.cliente_segredo": "s", "google_ads.refresh_token": "r", "google_ads.conta": "123-456-7890"}})
        assert r.status_code == 200, r.text
        assert google_ads.ler_leads().conta == "1234567890"
        assert google_ads.ler_configuracao() is None  # a leitura do gasto continua desligada
