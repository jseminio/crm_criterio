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
