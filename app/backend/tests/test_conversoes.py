"""Devolução das conversões ao Meta Ads e ao Google Ads — 14/10/2026."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import httpx2 as httpx
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm.anuncios import AcessoNegado, LeituraFalhou, Recusado
from crm.anuncios import google as google_ads
from crm.anuncios import meta as meta_ads
from crm.api.app import criar_app
from crm.api.conversoes import EstadoDasConversoes, Enviador, rodar_uma_vez
from crm.db.modelos import ConversaoEnviada, Lead
from crm.domain import conversoes as c
from crm.domain.listas import Situacao, TipoCanal

AGORA = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)
sha = lambda t: hashlib.sha256(t.encode()).hexdigest()


def lead(id=1, *, qualificado=True, reuniao=False, contrato=False, email="Ana@Empresa.com.br ", telefone="(21) 99999-0000",
         gclid=None, fbclid=None, nao_contatar=False, tipo=TipoCanal.TRAFEGO_PAGO, dias=1):
    op = SimpleNamespace(situacao=Situacao.ACEITA, data_aceite=date(2026, 10, 13), preco_mensal=Decimal("7000")) if contrato else None
    return SimpleNamespace(
        id=id, tipo_canal=tipo, nao_contatar=nao_contatar, email=email, telefone=telefone, gclid=gclid, fbclid=fbclid,
        criado_em=AGORA - timedelta(days=dias), qualificado_em=AGORA - timedelta(days=dias) if qualificado else None,
        reuniao_marcada_para=AGORA + timedelta(days=2) if reuniao else None, convertido_em=op, empresa_texto=None, nome="Ana",
    )


def ja(lead_id, evento, plataforma, situacao="enviado", tentativas=1, momento=AGORA):
    return SimpleNamespace(lead_id=lead_id, evento=evento, plataforma=plataforma, situacao=situacao,
                           tentativas=tentativas, momento_do_evento=momento)


class TestNormalizacao:
    def test_email_em_minusculas_e_sem_espaco(self):
        assert c.hash_email(" Ana@Empresa.com.BR ") == sha("ana@empresa.com.br")
        assert c.hash_email("sem arroba") is None

    def test_telefone_ganha_o_55(self):
        assert c.telefone_e164("(21) 99999-0000") == "+5521999990000"
        assert c.telefone_e164("+55 21 3333-4444") == "+552133334444"
        assert c.telefone_e164("123") is None

    def test_formato_de_cada_plataforma(self):
        assert c.hash_telefone("21 99999-0000", com_mais=True) == sha("+5521999990000")
        assert c.hash_telefone("21 99999-0000", com_mais=False) == sha("5521999990000")


class TestPendentes:
    def test_eventos_e_valor_em_mrr(self):
        envios, _ = c.pendentes([lead(reuniao=True, contrato=True)], [], [c.META], AGORA)
        assert [(e.evento, e.valor) for e in envios] == [
            ("lead_qualificado", None), ("reuniao_marcada", None), ("contrato_fechado", Decimal("7583.33"))]
        reuniao = envios[1]
        assert reuniao.momento == AGORA  # reunião no futuro: vale o momento em que o CRM a viu

    def test_nao_contatar_e_outras_origens_nunca_saem(self):
        envios, sem = c.pendentes([lead(nao_contatar=True), lead(2, tipo=TipoCanal.SOCIOS)], [], [c.META, c.GOOGLE], AGORA)
        assert envios == [] and sem == {}

    def test_google_so_com_gclid(self):
        envios, sem = c.pendentes([lead(), lead(2, gclid="Cj0K")], [], [c.GOOGLE], AGORA)
        assert [e.lead_id for e in envios] == [2]
        assert sem == {("lead_qualificado", c.GOOGLE): 1}

    def test_meta_reconhece_pelo_email_ou_telefone(self):
        envios, sem = c.pendentes([lead(email=None, telefone=None), lead(2, email=None)], [], [c.META], AGORA)
        assert [e.lead_id for e in envios] == [2] and sem == {("lead_qualificado", c.META): 1}

    def test_o_que_saiu_nao_sai_de_novo_e_falha_tenta_ate_5(self):
        feitos = [ja(1, "lead_qualificado", c.META), ja(2, "lead_qualificado", c.META, "falhou", 4),
                  ja(3, "lead_qualificado", c.META, "falhou", 5), ja(4, "lead_qualificado", c.META, "recusado")]
        envios, _ = c.pendentes([lead(i) for i in (1, 2, 3, 4)], feitos, [c.META], AGORA)
        assert [(e.lead_id, e.tentativas) for e in envios] == [(2, 4)]

    def test_meta_com_mais_de_7_dias_nem_sai(self):
        envios, _ = c.pendentes([lead(dias=8)], [], [c.META, c.GOOGLE], AGORA)
        assert envios[0].recusa_previa and "7 dias" in envios[0].recusa_previa


class TestMeta:
    config = meta_ads.EnvioDoMeta("tk", "123456789012345", "v24.0")

    def _envio(self, **extra):
        return c.pendentes([lead(contrato=True, fbclid="IwAR", **extra)], [], [c.META], AGORA)[0][-1]

    def test_evento_so_com_hash(self):
        evento = meta_ads.evento_da_api(self._envio())
        assert evento["event_name"] == "ContratoFechado" and evento["action_source"] == "system_generated"
        assert evento["user_data"]["em"] == [sha("ana@empresa.com.br")]
        assert evento["user_data"]["ph"] == [sha("5521999990000")]
        assert evento["user_data"]["fbc"].startswith("fb.1.") and evento["user_data"]["fbc"].endswith(".IwAR")
        assert evento["custom_data"]["value"] == 7583.33 and evento["custom_data"]["currency"] == "BRL"
        assert "ana@empresa" not in json.dumps(evento) and "99999" not in json.dumps(evento)

    def _http(self, status, corpo):
        pedidos = []
        return httpx.Client(transport=httpx.MockTransport(
            lambda p: pedidos.append(p) or httpx.Response(status, json=corpo))), pedidos

    def test_aceite(self):
        http, pedidos = self._http(200, {"events_received": 1})
        assert "recebeu 1" in meta_ads.enviar_evento(self.config, self._envio(), http=http)
        assert "/v24.0/123456789012345/events" in str(pedidos[0].url)

    def test_token_recusado_para_a_plataforma(self):
        http, _ = self._http(400, {"error": {"code": 190, "message": "Invalid OAuth access token"}})
        with pytest.raises(AcessoNegado):
            meta_ads.enviar_evento(self.config, self._envio(), http=http)

    def test_evento_invalido_e_recusa_definitiva(self):
        http, _ = self._http(400, {"error": {"code": 100, "error_user_msg": "event_time inválido"}})
        with pytest.raises(Recusado, match="event_time"):
            meta_ads.enviar_evento(self.config, self._envio(), http=http)

    def test_instabilidade_tenta_de_novo(self):
        http, _ = self._http(503, {})
        with pytest.raises(LeituraFalhou) as falha:
            meta_ads.enviar_evento(self.config, self._envio(), http=http)
        assert not isinstance(falha.value, AcessoNegado)


class TestGoogle:
    cred = google_ads.ConfiguracaoDoGoogleAds("dev", "cli", "seg", "rt", "1234567890", None, "v25")
    config = google_ads.EnvioDoGoogle(cred, {"lead_qualificado": "111", "contrato_fechado": "333"})

    def _envio(self, **extra):
        return c.pendentes([lead(contrato=True, gclid="Cj0K", **extra)], [], [c.GOOGLE], AGORA)[0][-1]

    def test_conversao_no_formato_do_google(self):
        conv = google_ads.conversao_da_api(self.config, self._envio())
        assert conv["gclid"] == "Cj0K" and conv["conversionAction"] == "customers/1234567890/conversionActions/333"
        assert conv["conversionDateTime"] == "2026-10-13 12:00:00-03:00"
        assert conv["conversionValue"] == 7583.33 and conv["currencyCode"] == "BRL"
        assert conv["userIdentifiers"] == [{"hashedEmail": sha("ana@empresa.com.br")},
                                           {"hashedPhoneNumber": sha("+5521999990000")}]

    def _http(self, status, corpo):
        pedidos = []
        return httpx.Client(transport=httpx.MockTransport(
            lambda p: pedidos.append(p) or httpx.Response(status, json=corpo))), pedidos

    def test_aceite_com_o_token_da_rodada(self):
        http, pedidos = self._http(200, {"results": [{}]})
        assert "recebeu" in google_ads.enviar_conversao(self.config, self._envio(), http=http, acesso="ya29")
        assert ":uploadClickConversions" in str(pedidos[0].url) and pedidos[0].headers["developer-token"] == "dev"
        assert json.loads(pedidos[0].content)["partialFailure"] is True

    def test_falha_parcial_e_recusa(self):
        http, _ = self._http(200, {"partialFailureError": {"message": "The click is too old."}})
        with pytest.raises(Recusado, match="too old"):
            google_ads.enviar_conversao(self.config, self._envio(), http=http, acesso="ya29")

    def test_evento_sem_acao_configurada_para_sem_gastar_tentativa(self):
        envio = c.pendentes([lead(reuniao=True, gclid="Cj0K", qualificado=False)], [], [c.GOOGLE], AGORA)[0][0]
        with pytest.raises(AcessoNegado, match="ação de conversão"):
            google_ads.enviar_conversao(self.config, envio, acesso="ya29")


# ------------------------------------------------------------------ a rodada, com banco
@pytest.fixture
def fabrica(engine: sa.Engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


def _lead_no_banco(sessao, **campos) -> Lead:
    base = {"nome": "Ana", "tipo_canal": TipoCanal.TRAFEGO_PAGO, "canal": "Meta Ads", "email": "ana@x.com.br",
            "qualificado_em": AGORA - timedelta(hours=1)}
    lead = Lead(**(base | campos))
    sessao.add(lead)
    sessao.flush()
    return lead


class TestRodada:
    def test_grava_cada_resultado_e_nao_repete(self, fabrica, monkeypatch):
        monkeypatch.setattr("crm.api.conversoes.agora", lambda: AGORA)
        with fabrica() as s:
            a, b, d = _lead_no_banco(s), _lead_no_banco(s, email="b@x.com.br"), _lead_no_banco(s, email="d@x.com.br")
            respostas = {a.id: "ok", b.id: Recusado("dado inválido"), d.id: LeituraFalhou("rede")}

            def enviar(envio):
                r = respostas[envio.lead_id]
                if isinstance(r, Exception):
                    raise r
                return r

            enviadores = [Enviador(c.META, lambda: enviar), Enviador(c.GOOGLE, lambda: None)]
            rodada = rodar_uma_vez(s, enviadores, AGORA)
            meta = next(p for p in rodada.plataformas if p.plataforma == c.META)
            google = next(p for p in rodada.plataformas if p.plataforma == c.GOOGLE)
            assert (meta.enviados, meta.recusados, meta.falhas) == (1, 1, 1) and google.ligada is False
            linhas = {l.lead_id: l for l in s.scalars(sa.select(ConversaoEnviada))}
            assert linhas[a.id].situacao == "enviado" and linhas[b.id].resposta == "dado inválido"
            assert linhas[d.id].situacao == "falhou" and linhas[d.id].tentativas == 1

            respostas[d.id] = "ok"
            rodada = rodar_uma_vez(s, enviadores, AGORA)
            meta = next(p for p in rodada.plataformas if p.plataforma == c.META)
            assert (meta.enviados, meta.recusados, meta.falhas) == (1, 0, 0)  # só a falha voltou
            assert linhas[d.id].situacao == "enviado" and linhas[d.id].tentativas == 2

    def test_acesso_negado_para_a_plataforma_sem_registrar(self, fabrica):
        with fabrica() as s:
            _lead_no_banco(s)
            _lead_no_banco(s, email="b@x.com.br")
            chamadas = []

            def enviar(envio):
                chamadas.append(envio)
                raise AcessoNegado("A Meta recusou o token.")

            rodada = rodar_uma_vez(s, [Enviador(c.META, lambda: enviar)], AGORA)
            assert len(chamadas) == 1 and rodada.plataformas[0].aviso == "A Meta recusou o token."
            assert s.scalars(sa.select(ConversaoEnviada)).all() == []

    def test_desligada_nao_le_nem_envia(self, fabrica):
        with fabrica() as s:
            _lead_no_banco(s)
            rodada = rodar_uma_vez(s, [Enviador(c.META, lambda: None)], AGORA)
            assert rodada.plataformas[0].ligada is False and s.scalars(sa.select(ConversaoEnviada)).all() == []


def _mes():
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m")


class TestRotas:
    def _cliente(self, fabrica, enviadores):
        return TestClient(criar_app(fabrica, enviadores_de_conversoes=lambda: enviadores, conversoes_automaticas=False))

    def test_desligada_responde_409(self, fabrica):
        with self._cliente(fabrica, [Enviador(c.META, lambda: None)]) as cliente:
            r = cliente.post("/api/sdr/conversoes/enviar")
        assert r.status_code == 409 and "Integrações" in r.json()["detail"]

    def test_enviar_agora_e_o_resumo(self, fabrica):
        enviados = []
        enviadores = [Enviador(c.META, lambda: (lambda e: enviados.append(e) or "ok")),
                      Enviador(c.GOOGLE, lambda: (lambda e: "ok"))]
        with self._cliente(fabrica, enviadores) as cliente:
            for campos in ({"email": "a@x.com.br"}, {"email": "b@x.com.br", "gclid": "Cj0K"}, {"email": "c@x.com.br"}):
                r = cliente.post("/api/leads", json={"nome": "Ana", "tipo_canal": "Tráfego pago", "canal": "Meta Ads"} | campos)
                assert r.status_code == 201, r.text
                assert cliente.patch(f"/api/leads/{r.json()['id']}", json={"situacao": "Qualificado", "porte_estimado": "Médio"}).status_code == 200
            rodada = cliente.post("/api/sdr/conversoes/enviar")
            assert rodada.status_code == 200, rodada.text
            resumo = cliente.get("/api/sdr/conversoes", params={"mes": _mes()}).json()
        assert len(enviados) == 3
        linha = {(l["evento"], l["plataforma"]): l for l in resumo["linhas"]}
        assert linha[("lead_qualificado", "Meta Ads")]["enviados"] == 3
        assert linha[("lead_qualificado", "Google Ads")]["enviados"] == 1
        assert linha[("lead_qualificado", "Google Ads")]["sem_identificador"] == 2
        assert resumo["ligadas"] == {"Meta Ads": True, "Google Ads": True}
        assert resumo["ultima_rodada"] is not None


class TestPelaTela:
    @pytest.fixture
    def cliente(self, fabrica):
        with TestClient(criar_app(fabrica, conversoes_automaticas=False)) as aberto:
            yield aberto

    def test_ligar_a_devolucao_do_meta_sem_ligar_a_leitura(self, cliente):
        r = cliente.put("/api/configuracoes/integracoes/meta_ads", json={"valores": {
            "meta_ads.conversoes": "true", "meta_ads.token": "EAAsegredo", "meta_ads.conjunto": "123456789012345"}})
        assert r.status_code == 200, r.text
        assert "EAAsegredo" not in r.text
        assert meta_ads.ler_envio() == meta_ads.EnvioDoMeta("EAAsegredo", "123456789012345", "v24.0")
        assert meta_ads.ler_configuracao() is None  # a leitura do gasto continua desligada

    def test_acoes_do_google_so_com_numeros(self, cliente):
        r = cliente.put("/api/configuracoes/integracoes/google_ads", json={"valores": {"google_ads.acao_contrato": "abc"}})
        assert r.status_code == 422 and "só os números" in r.json()["detail"]

    def test_google_le_as_acoes_configuradas(self, cliente):
        r = cliente.put("/api/configuracoes/integracoes/google_ads", json={"valores": {
            "google_ads.conversoes": "true", "google_ads.token_dev": "d", "google_ads.cliente_id": "c",
            "google_ads.cliente_segredo": "s", "google_ads.refresh_token": "r", "google_ads.conta": "123-456-7890",
            "google_ads.acao_qualificado": "111", "google_ads.acao_contrato": "333"}})
        assert r.status_code == 200, r.text
        envio = google_ads.ler_envio()
        assert envio.acoes == {"lead_qualificado": "111", "contrato_fechado": "333"}
        assert envio.credenciais.conta == "1234567890"
        assert google_ads.ler_configuracao() is None  # a leitura do gasto continua desligada


def test_estado_da_rodada_tem_trava():
    estado = EstadoDasConversoes()
    assert estado.trava.acquire(blocking=False) and not estado.trava.acquire(blocking=False)
