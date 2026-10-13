"""Campanhas de tráfego pago: funil por canal e decisão por campanha — 13/10/2026."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm.api.app import criar_app
from crm.domain import campanhas as c
from crm.domain.listas import MotivoDeDescarte as M
from crm.domain.listas import Situacao, TipoCanal

OUTUBRO = datetime(2026, 10, 10, 15, tzinfo=timezone.utc)
UM_DIA = datetime(2026, 10, 12, 15, tzinfo=timezone.utc)


def lead(canal="Meta Ads", campanha="Vale", *, descarte=None, qualificado=False, reuniao=False,
         op=None, tipo=TipoCanal.TRAFEGO_PAGO, criado=OUTUBRO):
    return SimpleNamespace(
        criado_em=criado, tipo_canal=tipo, canal=canal, campanha=campanha, motivo_descarte=descarte,
        qualificado_em=UM_DIA if qualificado else None, reuniao_marcada_para=UM_DIA if reuniao else None,
        convertido_em_id=1 if op else None, convertido_em=op,
    )


def op(situacao=Situacao.ENVIAR_PROPOSTA, envio=None, preco=None):
    return SimpleNamespace(situacao=situacao, data_envio_proposta=envio, preco_mensal=preco)


def etapas(funil):
    return [e.quantidade for e in funil.etapas]


class TestNivel:
    def test_lead_fora_do_icp_fica_no_topo(self):
        assert c.nivel(lead(descarte=M.PORTE_ABAIXO)) == 0

    def test_esperava_outra_coisa_conta_no_icp(self):
        assert c.nivel(lead(descarte=M.EXPECTATIVA)) == 1

    def test_oportunidade_aberta_e_qualificado(self):
        assert c.nivel(lead(op=op())) == 2

    def test_proposta_enviada(self):
        assert c.nivel(lead(op=op(envio=date(2026, 10, 11)))) == 4
        assert c.nivel(lead(op=op(Situacao.EM_AVALIACAO))) == 4

    def test_perdida_sem_envio_nao_conta_como_proposta(self):
        assert c.nivel(lead(reuniao=True, op=op(Situacao.PERDIDA))) == 3

    def test_contrato_e_a_oportunidade_aceita(self):
        assert c.nivel(lead(op=op(Situacao.ACEITA))) == 5


class TestFunil:
    def leads(self):
        return [
            lead(),
            lead(descarte=M.PORTE_ABAIXO),
            lead(qualificado=True),
            lead(qualificado=True, reuniao=True),
            lead(op=op(Situacao.ACEITA, preco=Decimal("7000"))),
            lead("Google Ads", "BPO RJ", qualificado=True),
        ]

    def test_cumulativo_e_por_canal(self):
        p = c.calcular_campanhas(mes="2026-10", leads=self.leads(), midia={"Meta Ads": Decimal("1000")})
        meta = next(f for f in p.canais if f.canal == "Meta Ads")
        assert etapas(meta) == [5, 4, 3, 2, 1, 1]
        assert meta.etapas[0].passagem.valor == 80
        assert meta.etapas[-1].passagem is None
        assert etapas(p.total) == [6, 5, 4, 2, 1, 1]

    def test_custo_por_etapa_cac_e_mrr(self):
        p = c.calcular_campanhas(mes="2026-10", leads=self.leads(), midia={"Meta Ads": Decimal("1000")})
        meta = next(f for f in p.canais if f.canal == "Meta Ads")
        assert [e.custo for e in meta.etapas[:2]] == [Decimal("200.00"), Decimal("250.00")]
        assert meta.cac == Decimal("1000.00")
        assert meta.mrr_novo == Decimal("7583.33")

    def test_sem_investimento_o_custo_fica_vazio(self):
        p = c.calcular_campanhas(mes="2026-10", leads=self.leads(), midia={"Meta Ads": Decimal("1000")})
        google = next(f for f in p.canais if f.canal == "Google Ads")
        assert google.investimento is None and google.cac is None
        assert all(e.custo is None for e in google.etapas)
        assert p.prontidao[0].ok is False and "Google Ads" in p.prontidao[0].texto

    def test_so_trafego_pago_do_mes(self):
        outros = [lead(tipo=TipoCanal.SOCIOS), lead(criado=datetime(2026, 9, 30, 12, tzinfo=timezone.utc))]
        p = c.calcular_campanhas(mes="2026-10", leads=outros)
        assert p.leads == 0 and p.total is None and p.canais == []

    def test_contrato_sem_preco_e_contado(self):
        p = c.calcular_campanhas(mes="2026-10", leads=[lead(op=op(Situacao.ACEITA))])
        assert p.total.mrr_novo == Decimal("0.00") and p.total.contratos_sem_preco == 1

    def test_lead_sem_campanha_aparece_na_prontidao(self):
        p = c.calcular_campanhas(mes="2026-10", leads=[lead(campanha=None), lead(campanha="  ")])
        assert p.campanhas[0].campanha == c.SEM_CAMPANHA and p.campanhas[0].leads == 2
        assert "2 lead(s)" in p.prontidao[1].texto


class TestDecisao:
    def decidir(self, leads, icp_alvo=None):
        return c.calcular_campanhas(mes="2026-10", leads=leads, icp_alvo_pct=icp_alvo).campanhas[0]

    def test_pouco_volume_nao_decide(self):
        linha = self.decidir([lead(qualificado=True)] * 5)
        assert linha.decisao == "Aguardar volume"

    def test_refazer_publico_quando_o_icp_fica_abaixo_do_alvo(self):
        leads = [lead(descarte=M.PORTE_ABAIXO)] * 14 + [lead(qualificado=True)] * 6
        linha = self.decidir(leads, Decimal("40"))
        assert linha.decisao == "Refazer público"
        assert "30% no ICP" in linha.porque and "Porte abaixo do mínimo" in linha.porque

    def test_ajustar_criativo_quando_a_promessa_nao_bate(self):
        leads = [lead(descarte=M.EXPECTATIVA)] * 10 + [lead(qualificado=True)] * 10
        assert self.decidir(leads, Decimal("40")).decisao == "Ajustar criativo"

    def test_escalar_na_meta_de_qualificados(self):
        leads = [lead()] * 15 + [lead(qualificado=True)] * 5
        linha = self.decidir(leads, Decimal("40"))
        assert linha.decisao == "Escalar" and "25%" in linha.porque

    def test_escalar_sem_icp_alvo_avisa(self):
        leads = [lead()] * 15 + [lead(qualificado=True)] * 5
        assert "Sem ICP alvo" in self.decidir(leads).porque

    def test_rever_abaixo_do_alerta(self):
        leads = [lead()] * 19 + [lead(qualificado=True)]
        assert self.decidir(leads).decisao == "Rever campanha"

    def test_manter_entre_alerta_e_meta(self):
        leads = [lead()] * 17 + [lead(qualificado=True)] * 3
        assert self.decidir(leads).decisao == "Manter e observar"


# ------------------------------------------------------------------ pela API
@pytest.fixture
def cliente(engine: sa.Engine) -> TestClient:
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica)) as aberto:
        yield aberto


def test_rota_das_campanhas(cliente):
    for campanha in ("Vale", "Vale", "Tempo"):
        r = cliente.post("/api/leads", json={"nome": "Ana", "tipo_canal": "Tráfego pago", "canal": "Meta Ads",
                                             "campanha": campanha})
        assert r.status_code == 201, r.text
    cliente.post("/api/leads", json={"nome": "Bia", "tipo_canal": "Sócios"})
    mes = datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m")
    assert cliente.put("/api/sdr/midia", json={"mes": mes, "canal": "Meta Ads", "valor": "300"}).status_code == 200

    p = cliente.get("/api/sdr/campanhas", params={"mes": mes}).json()
    assert p["leads"] == 3
    assert p["canais"][0]["canal"] == "Meta Ads"
    assert p["canais"][0]["etapas"][0]["custo"] == "100.00"
    assert [x["campanha"] for x in p["campanhas"]] == ["Vale", "Tempo"]
    assert p["regua"]["volume_minimo"] == c.VOLUME_MINIMO


def test_mes_invalido(cliente):
    assert cliente.get("/api/sdr/campanhas", params={"mes": "2026-13"}).status_code == 422


# ------------------------------------------------- custo por campanha (13/10/2026)
from crm.anuncios import meta as meta_ads  # noqa: E402

import httpx2 as httpx  # noqa: E402


def investido(campanha, valor, canal="Meta Ads", fonte="lido"):
    return c.Investido(canal, campanha, Decimal(valor), fonte)


class TestCustoPorCampanha:
    def test_canal_vira_a_soma_das_campanhas(self):
        p = c.calcular_campanhas(mes="2026-10", leads=[lead()], midia={"Meta Ads": Decimal("999")},
                                 por_campanha=[investido("Vale", "300"), investido("Tempo", "200")])
        assert next(f for f in p.canais if f.canal == "Meta Ads").investimento == Decimal("500")

    def test_liga_pelo_nome_sem_maiusculas_e_espacos(self):
        p = c.calcular_campanhas(mes="2026-10", leads=[lead(campanha="vale  da morte", qualificado=True, reuniao=True)],
                                 por_campanha=[investido("Vale da Morte", "300")])
        linha = p.campanhas[0]
        assert linha.investimento == Decimal("300") and linha.fonte == "lido"
        assert linha.custo_por_reuniao == Decimal("300.00") and linha.custo_por_lead_icp == Decimal("300.00")

    def test_campanha_com_gasto_e_sem_lead_aparece(self):
        p = c.calcular_campanhas(mes="2026-10", leads=[], por_campanha=[investido("Fantasma", "100")])
        linha = p.campanhas[0]
        assert linha.leads == 0 and linha.investimento == Decimal("100")
        assert "nome no anúncio" in linha.porque

    def test_rever_custo_acima_de_1_5_vez_o_canal(self):
        barata = [lead("Meta Ads", "Barata", qualificado=True, reuniao=True)] * 10 + [lead("Meta Ads", "Barata")] * 10
        cara = [lead("Meta Ads", "Cara", qualificado=True, reuniao=True)] + [lead("Meta Ads", "Cara", qualificado=True)] * 19
        p = c.calcular_campanhas(mes="2026-10", leads=barata + cara,
                                 por_campanha=[investido("Barata", "1000"), investido("Cara", "1000")])
        por_nome = {x.campanha: x for x in p.campanhas}
        # canal: 2000 ÷ 11 reuniões = 181,82; Cara: 1000 por reunião
        assert por_nome["Cara"].decisao == "Rever custo"
        assert "1.000,00" in por_nome["Cara"].porque and "181,82" in por_nome["Cara"].porque
        assert por_nome["Barata"].decisao == "Escalar"

    def test_rever_custo_quando_gasta_sem_reuniao(self):
        com = [lead("Meta Ads", "A", qualificado=True, reuniao=True)] * 20
        sem = [lead("Meta Ads", "B", qualificado=True)] * 20
        p = c.calcular_campanhas(mes="2026-10", leads=com + sem,
                                 por_campanha=[investido("A", "500"), investido("B", "500")])
        b = next(x for x in p.campanhas if x.campanha == "B")
        assert b.decisao == "Rever custo" and "sem nenhuma reunião" in b.porque

    def test_sem_custo_por_campanha_a_regua_de_custo_nao_vale(self):
        leads = [lead(qualificado=True)] * 20
        p = c.calcular_campanhas(mes="2026-10", leads=leads, midia={"Meta Ads": Decimal("500")})
        assert p.campanhas[0].decisao == "Escalar" and p.campanhas[0].investimento is None


def _meta(paginas: list[dict], status: int = 200):
    chamadas = []

    def tratar(pedido: httpx.Request) -> httpx.Response:
        chamadas.append(pedido)
        corpo = paginas[min(len(chamadas), len(paginas)) - 1]
        return httpx.Response(status, json=corpo)

    return httpx.Client(transport=httpx.MockTransport(tratar)), chamadas


class TestLeituraDoMeta:
    config = meta_ads.ConfiguracaoDoMetaAds("tk", "1708029123631617", "v24.0")

    def test_le_o_gasto_com_paginas(self):
        http, chamadas = _meta([
            {"data": [{"campaign_id": "1", "campaign_name": "Vale", "spend": "123.45"}],
             "paging": {"next": "https://graph.facebook.com/v24.0/next"}},
            {"data": [{"campaign_id": "2", "campaign_name": "Tempo", "spend": "10"}]},
        ])
        gastos = meta_ads.gasto_por_campanha(self.config, "2026-10", date(2026, 10, 13), http=http)
        assert [(g.nome, g.valor) for g in gastos] == [("Vale", Decimal("123.45")), ("Tempo", Decimal("10"))]
        primeira = chamadas[0]
        assert "act_1708029123631617/insights" in str(primeira.url)
        assert "2026-10-13" in primeira.url.params["time_range"]
        assert primeira.headers["Authorization"] == "Bearer tk"

    def test_mes_futuro_nao_pergunta(self):
        http, chamadas = _meta([{}])
        assert meta_ads.gasto_por_campanha(self.config, "2026-11", date(2026, 10, 13), http=http) == []
        assert chamadas == []

    def test_token_recusado_vira_frase_sem_token(self):
        http, _ = _meta([{"error": {"message": "x"}}], status=401)
        with pytest.raises(meta_ads.LeituraFalhou) as falha:
            meta_ads.gasto_por_campanha(self.config, "2026-10", date(2026, 10, 13), http=http)
        assert "ads_read" in str(falha.value) and "tk" not in str(falha.value)

    def test_conferir_conta(self):
        http, _ = _meta([{"name": "Critério", "account_status": 1, "currency": "BRL"}])
        assert "Critério: ativa, moeda BRL" in meta_ads.conferir_conta(self.config, http=http)

    def test_conta_com_letras_e_recusada(self):
        with pytest.raises(meta_ads.LeituraFalhou):
            meta_ads.conferir_conta(meta_ads.ConfiguracaoDoMetaAds("tk", "abc", "v24.0"))


@pytest.fixture
def cliente_com_meta(engine: sa.Engine):
    gastos: dict = {"valor": [meta_ads.GastoDaCampanha("1", "Vale", Decimal("300")),
                              meta_ads.GastoDaCampanha("2", "Google digitado", Decimal("1"))]}
    fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with TestClient(criar_app(fabrica, gastos_do_meta=lambda mes: gastos["valor"])) as aberto:
        yield aberto, gastos


def _mes():
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m")


class TestRotasDeCustoPorCampanha:
    def test_atualizar_grava_lido_e_mantem_o_digitado(self, cliente_com_meta):
        cliente, _ = cliente_com_meta
        mes = _mes()
        r = cliente.put("/api/sdr/midia/campanha", json={"mes": mes, "canal": "Meta Ads", "campanha": "google  DIGITADO",
                                                         "valor": "50"})
        assert r.status_code == 200 and r.json()["fonte"] == "digitado" and r.json()["campanha"] == "google DIGITADO"
        r = cliente.post("/api/sdr/campanhas/atualizar", params={"mes": mes})
        assert r.status_code == 200, r.text
        assert r.json()["gravadas"] == 1 and r.json()["digitadas_mantidas"] == ["google DIGITADO"]
        linhas = {l["campanha"]: l for l in cliente.get("/api/sdr/midia/campanhas", params={"mes": mes}).json()}
        assert linhas["Vale"]["fonte"] == "lido" and linhas["Vale"]["valor"] == "300.00"
        assert linhas["google DIGITADO"]["valor"] == "50.00"

    def test_atualizar_de_novo_atualiza_o_valor(self, cliente_com_meta):
        cliente, gastos = cliente_com_meta
        mes = _mes()
        cliente.post("/api/sdr/campanhas/atualizar", params={"mes": mes})
        gastos["valor"] = [meta_ads.GastoDaCampanha("1", "Vale", Decimal("450"))]
        cliente.post("/api/sdr/campanhas/atualizar", params={"mes": mes})
        linhas = cliente.get("/api/sdr/midia/campanhas", params={"mes": mes}).json()
        assert ("Vale", "450.00") in [(l["campanha"], l["valor"]) for l in linhas]
        assert sum(1 for l in linhas if l["campanha"] == "Vale") == 1

    def test_painel_traz_o_custo_e_a_leitura(self, cliente_com_meta):
        cliente, _ = cliente_com_meta
        mes = _mes()
        cliente.post("/api/leads", json={"nome": "Ana", "tipo_canal": "Tráfego pago", "canal": "Meta Ads",
                                         "utm_campaign": "Vale", "fbclid": "abc"})
        cliente.post("/api/sdr/campanhas/atualizar", params={"mes": mes})
        p = cliente.get("/api/sdr/campanhas", params={"mes": mes}).json()
        vale = next(x for x in p["campanhas"] if x["campanha"] == "Vale")
        assert vale["leads"] == 1 and vale["investimento"] == "300.00" and vale["fonte"] == "lido"
        assert p["meta_ads"]["lido_em"] is not None

    def test_desligado_responde_409(self, engine):
        fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        with TestClient(criar_app(fabrica, gastos_do_meta=lambda mes: None)) as cliente:
            r = cliente.post("/api/sdr/campanhas/atualizar", params={"mes": _mes()})
        assert r.status_code == 409 and "Integrações" in r.json()["detail"]

    def test_falha_da_meta_responde_502_com_a_frase(self, engine):
        def falhar(mes):
            raise meta_ads.LeituraFalhou("A Meta recusou o token do Meta Ads (HTTP 401).")
        fabrica = sessionmaker(bind=engine, expire_on_commit=False, future=True)
        with TestClient(criar_app(fabrica, gastos_do_meta=falhar)) as cliente:
            r = cliente.post("/api/sdr/campanhas/atualizar", params={"mes": _mes()})
        assert r.status_code == 502 and "recusou o token" in r.json()["detail"]

    def test_apagar(self, cliente_com_meta):
        cliente, _ = cliente_com_meta
        r = cliente.put("/api/sdr/midia/campanha", json={"mes": _mes(), "canal": "Google Ads", "campanha": "BPO",
                                                         "valor": "10"})
        assert cliente.delete(f"/api/sdr/midia/campanha/{r.json()['id']}").status_code == 204
        assert cliente.get("/api/sdr/midia/campanhas", params={"mes": _mes()}).json() == []
        assert cliente.delete("/api/sdr/midia/campanha/999").status_code == 404


def test_lead_guarda_a_origem_do_clique_e_a_campanha_do_utm(cliente):
    r = cliente.post("/api/leads", json={"nome": "Ana", "tipo_canal": "Tráfego pago", "canal": "Google Ads",
                                         "utm_source": "google", "utm_campaign": "BPO RJ", "gclid": "Cj0K"})
    assert r.status_code == 201, r.text
    lead = next(l for l in cliente.get("/api/leads").json()["itens"] if l["id"] == r.json()["id"])
    assert lead["campanha"] == "BPO RJ"


def test_campanha_digitada_vale_mais_que_o_utm(cliente):
    r = cliente.post("/api/leads", json={"nome": "Ana", "campanha": "Minha", "utm_campaign": "Outra"})
    assert r.json()["campanha"] == "Minha"


class TestMetaAdsPelaTela:
    def test_salva_testa_e_nunca_devolve_o_token(self, cliente, monkeypatch):
        vistos = []

        def conferir(config, http=None):
            vistos.append(config)
            return "A Meta reconheceu a conta Critério: ativa, moeda BRL."

        monkeypatch.setattr(meta_ads, "conferir_conta", conferir)
        r = cliente.post("/api/configuracoes/integracoes/meta_ads/testar")
        assert r.json()["ok"] is False and "Ligue a leitura" in r.json()["mensagem"]

        r = cliente.put("/api/configuracoes/integracoes/meta_ads", json={"valores": {
            "meta_ads.ligado": "true", "meta_ads.token": "EAAsegredo1234", "meta_ads.conta": "act_1708029123631617"}})
        assert r.status_code == 200, r.text
        assert "EAAsegredo1234" not in r.text
        r = cliente.post("/api/configuracoes/integracoes/meta_ads/testar")
        assert r.json()["ok"] is True and "Critério" in r.json()["mensagem"]
        assert vistos[0].conta == "1708029123631617" and vistos[0].versao == "v24.0"

    def test_conta_com_letras_nao_salva(self, cliente):
        r = cliente.put("/api/configuracoes/integracoes/meta_ads", json={"valores": {"meta_ads.conta": "minha conta"}})
        assert r.status_code == 422 and "só os números" in r.json()["detail"]
