"""Leads do formulário do Meta entrando sozinhos no CRM — 14/10/2026."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx2 as httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm.anuncios import AcessoNegado, LeituraFalhou
from crm.anuncios import leads_do_meta as meta_leads
from crm.anuncios import meta as meta_ads
from crm.api.app import criar_app
from crm.api.leads_do_meta import Busca, buscar_uma_vez
from crm.db.modelos import Lead
from crm.domain import conversoes as c
from crm.domain.leads_do_meta import ORGANICO, campos_do_lead
from crm.domain.listas import TipoCanal

AGORA = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)


def do_meta(id="900001", respostas=None, campanha="Vale da Morte da Gestão", anuncio="Vídeo CFO 30s",
            organico=False, quando=AGORA - timedelta(minutes=5)):
    return meta_leads.LeadDoMeta(
        id=id, criado_em=quando, campanha=campanha, anuncio=anuncio, formulario="BPO Financeiro", organico=organico,
        respostas=respostas if respostas is not None else {
            "full_name": "Mariana Souza", "email": "mariana@souza.com.br", "phone_number": "+5521988881111",
            "company_name": "Souza Distribuidora", "faixa_de_faturamento_mensal?": "R$ 500 mil a R$ 1 milhão"},
    )


class TestCampos:
    def test_respostas_viram_campos_e_o_resto_vai_para_a_observacao(self):
        campos = campos_do_lead(do_meta())
        assert (campos["nome"], campos["email"], campos["telefone"], campos["empresa_texto"]) == (
            "Mariana Souza", "mariana@souza.com.br", "+5521988881111", "Souza Distribuidora")
        assert campos["tipo_canal"] is TipoCanal.TRAFEGO_PAGO and campos["canal"] == "Meta Ads"
        assert campos["campanha"] == "Vale da Morte da Gestão" and campos["campanha_midia"] == "Vídeo CFO 30s"
        assert campos["observacao"].startswith("Faixa de faturamento mensal: R$ 500 mil a R$ 1 milhão")
        assert "“BPO Financeiro”, 14/10/2026 11:55" in campos["observacao"]
        assert campos["meta_lead_id"] == "900001" and campos["criado_em"] == AGORA - timedelta(minutes=5)

    def test_nome_em_duas_partes(self):
        campos = campos_do_lead(do_meta(respostas={"first_name": "Ana", "last_name": "Lima"}))
        assert campos["nome"] == "Ana Lima" and campos["email"] is None
        assert campos["observacao"].startswith("(Respondido no formulário do Meta")

    def test_organico_e_sem_campanha(self):
        assert campos_do_lead(do_meta(organico=True))["campanha"] == ORGANICO
        assert campos_do_lead(do_meta(campanha=None))["campanha"] == ORGANICO


def _http(rotas: dict[str, list[dict]]):
    """Responde pelo trecho do endereço, em fila."""
    pedidos = []

    def tratar(pedido: httpx.Request) -> httpx.Response:
        pedidos.append(pedido)
        caminho = pedido.url.path
        for trecho, fila in rotas.items():
            if caminho.endswith(trecho):
                return httpx.Response(200, json=fila.pop(0) if len(fila) > 1 else fila[0])
        return httpx.Response(404, json={"error": {"message": f"sem rota {caminho}"}})

    return httpx.Client(transport=httpx.MockTransport(tratar)), pedidos


class TestBuscaNoMeta:
    config = meta_leads.ConfiguracaoDosLeads("102938475610293", "tkpag", "v24.0")

    def test_busca_todos_os_formularios_com_paginas(self):
        http, pedidos = _http({
            "/102938475610293/leadgen_forms": [{"data": [{"id": "F1", "name": "BPO"}, {"id": "F2", "name": "CFO"}]}],
            "/F1/leads": [{"data": [{"id": "L1", "created_time": "2026-10-14T12:32:05+0000", "campaign_name": "Vale",
                                     "ad_name": "Vídeo", "field_data": [{"name": "email", "values": ["a@b.com"]}]}],
                           "paging": {"next": "https://graph.facebook.com/v24.0/F1/leads/p2"}}],
            "/F1/leads/p2": [{"data": [{"id": "L2", "created_time": "2026-10-14T12:40:00+0000", "is_organic": True,
                                        "field_data": []}]}],
            "/F2/leads": [{"data": []}],
        })
        leads = meta_leads.buscar_leads(self.config, AGORA - timedelta(days=1), http=http)
        assert [(l.id, l.campanha, l.organico, l.formulario) for l in leads] == [
            ("L1", "Vale", False, "BPO"), ("L2", None, True, "BPO")]
        assert leads[0].respostas == {"email": "a@b.com"}
        assert leads[0].criado_em == datetime(2026, 10, 14, 12, 32, 5, tzinfo=timezone.utc)
        primeiro = next(p for p in pedidos if p.url.path.endswith("/F1/leads"))
        filtro = json.loads(primeiro.url.params["filtering"])
        assert filtro == [{"field": "time_created", "operator": "GREATER_THAN",
                           "value": int((AGORA - timedelta(days=1)).timestamp())}]
        assert primeiro.headers["Authorization"] == "Bearer tkpag"

    def test_conferir_pagina(self):
        http, _ = _http({"/102938475610293": [{"name": "Critério Consultores"}],
                         "/leadgen_forms": [{"data": [{"id": "F1"}, {"id": "F2"}]}]})
        assert meta_leads.conferir_pagina(self.config, http=http) == "Página Critério Consultores · 2 formulário(s) de lead."

    def test_token_recusado_sem_mostrar_o_token(self):
        http = httpx.Client(transport=httpx.MockTransport(
            lambda p: httpx.Response(400, json={"error": {"code": 190, "message": "Invalid token"}})))
        with pytest.raises(AcessoNegado) as falha:
            meta_leads.conferir_pagina(self.config, http=http)
        assert "tkpag" not in str(falha.value)

    def test_pagina_com_letras(self):
        with pytest.raises(AcessoNegado):
            meta_leads.conferir_pagina(meta_leads.ConfiguracaoDosLeads("minha", "tk", "v24.0"))


@pytest.fixture
def fabrica(engine: sa.Engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


class TestRodada:
    def test_cria_os_novos_e_nunca_em_dobro(self, fabrica):
        pedidos = []
        lidos = [do_meta("1"), do_meta("2", respostas={"full_name": "Bruno"})]

        def buscar(desde):
            pedidos.append(desde)
            return lidos

        with fabrica() as s:
            r = buscar_uma_vez(s, Busca(lambda: buscar), AGORA)
            assert (r.lidos, r.novos) == (2, 2)
            assert pedidos[0] == AGORA - timedelta(days=30)  # primeira vez: 30 dias
            r = buscar_uma_vez(s, Busca(lambda: buscar), AGORA)
            assert (r.lidos, r.novos) == (2, 0)
            assert pedidos[1] == AGORA - timedelta(minutes=5) - timedelta(hours=1)  # desde o último, com folga
            leads = s.scalars(sa.select(Lead).order_by(Lead.meta_lead_id)).all()
            assert [(l.meta_lead_id, l.nome, l.canal) for l in leads] == [
                ("1", "Mariana Souza", "Meta Ads"), ("2", "Bruno", "Meta Ads")]

    def test_mesmo_email_entra_assim_mesmo(self, fabrica):
        with fabrica() as s:
            s.add(Lead(nome="Mariana", email="mariana@souza.com.br"))
            s.flush()
            r = buscar_uma_vez(s, Busca(lambda: (lambda desde: [do_meta()])), AGORA)
            assert r.novos == 1
            assert s.scalar(sa.select(sa.func.count()).select_from(Lead)) == 2

    def test_falha_vira_frase_e_desligada_nao_pede(self, fabrica):
        def falhar(desde):
            raise LeituraFalhou("A Meta não respondeu.")
        with fabrica() as s:
            assert buscar_uma_vez(s, Busca(lambda: falhar), AGORA).erro == "A Meta não respondeu."
            assert buscar_uma_vez(s, Busca(lambda: None), AGORA).ligada is False


class TestRotas:
    def _cliente(self, fabrica, preparar):
        return TestClient(criar_app(fabrica, busca_de_leads_do_meta=lambda: Busca(preparar),
                                    leads_do_meta_automaticos=False))

    def test_desligada_responde_409(self, fabrica):
        with self._cliente(fabrica, lambda: None) as cliente:
            assert cliente.get("/api/sdr/leads-do-meta").json() == {"ligada": False, "ultima": None}
            r = cliente.post("/api/sdr/leads-do-meta/buscar")
        assert r.status_code == 409 and "Integrações" in r.json()["detail"]

    def test_buscar_agora_e_o_lead_aparece_na_lista(self, fabrica):
        with self._cliente(fabrica, lambda: (lambda desde: [do_meta(quando=datetime.now(timezone.utc))])) as cliente:
            r = cliente.post("/api/sdr/leads-do-meta/buscar")
            assert r.status_code == 200 and r.json()["novos"] == 1
            assert cliente.get("/api/sdr/leads-do-meta").json()["ultima"]["novos"] == 1
            itens = cliente.get("/api/leads").json()["itens"]
        assert [(l["nome"], l["campanha"]) for l in itens] == [("Mariana Souza", "Vale da Morte da Gestão")]


class TestPelaTela:
    def test_ligar_a_entrada_e_testar_a_pagina(self, fabrica, monkeypatch):
        vistos = []
        monkeypatch.setattr(meta_leads, "conferir_pagina",
                            lambda config, http=None: vistos.append(config) or "Página Critério · 2 formulário(s) de lead.")
        with TestClient(criar_app(fabrica, leads_do_meta_automaticos=False, conversoes_automaticas=False)) as cliente:
            r = cliente.put("/api/configuracoes/integracoes/meta_ads", json={"valores": {
                "meta_ads.leads": "true", "meta_ads.pagina": "102938475610293", "meta_ads.token_pagina": "PAGsegredo"}})
            assert r.status_code == 200, r.text
            assert "PAGsegredo" not in r.text
            t = cliente.post("/api/configuracoes/integracoes/meta_ads/testar").json()
            ruim = cliente.put("/api/configuracoes/integracoes/meta_ads", json={"valores": {"meta_ads.pagina": "abc"}})
        assert t["ok"] is True and "Página Critério" in t["mensagem"]
        assert vistos[0] == meta_leads.ConfiguracaoDosLeads("102938475610293", "PAGsegredo", "v24.0")
        assert ruim.status_code == 422


def test_conversao_do_meta_vai_com_o_id_do_lead():
    lead = SimpleNamespace(
        id=1, tipo_canal=TipoCanal.TRAFEGO_PAGO, nao_contatar=False, email=None, telefone=None, gclid=None, fbclid=None,
        meta_lead_id="900001", criado_em=AGORA, qualificado_em=AGORA, reuniao_marcada_para=None, convertido_em=None)
    envios, sem = c.pendentes([lead], [], [c.META], AGORA)
    assert sem == {} and envios[0].meta_lead_id == "900001"
    assert meta_ads.evento_da_api(envios[0])["user_data"] == {"lead_id": 900001}
