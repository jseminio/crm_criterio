"""As fórmulas do painel do SDR de IA — `crm.domain.sdr`, sem banco."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from crm.domain import sdr
from crm.domain.listas import (
    AutorDaMensagem as A,
    DesfechoDaConversa as D,
    DestinoDoTransbordo,
    MotivoDeDescarte,
    MotivoDeTransbordo,
    TipoCanal,
    Tom,
)

INICIO = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
PAGO, FRIO = TipoCanal.TRAFEGO_PAGO, TipoCanal.PROSPECCAO_ATIVA


def msg(autor, segundos=0, **campos):
    base = dict(
        autor=autor, enviada_em=INICIO + timedelta(seconds=segundos), confianca=None,
        fallback=False, termo_nao_reconhecido=None, custo_usd=None, tom=None,
    )
    return SimpleNamespace(**(base | campos))


def conversa(*mensagens, desfecho=None, duracao=600, **campos):
    base = dict(
        iniciada_em=INICIO, encerrada_em=INICIO + timedelta(seconds=duracao) if desfecho else None,
        desfecho=desfecho, motivo_transbordo=None, destino_transbordo=None, atendida_em=None,
        nota=None, mensagens=list(mensagens),
    )
    return SimpleNamespace(**(base | campos))


def lead(*conversas, tipo=PAGO, canal="Meta Ads", criado_em=INICIO, **campos):
    base = dict(
        criado_em=criado_em, tipo_canal=tipo, canal=canal, interesse=None, cnpj=None,
        porte_estimado=None, motivo_descarte=None, reuniao_marcada_para=None,
        convertido_em_id=None, conversas=list(conversas),
    )
    return SimpleNamespace(**(base | campos))


def respondeu(desfecho=None, **campos):
    """Um lead que respondeu à IA, com a conversa encerrada no desfecho dado."""
    return conversa(msg(A.IA, 30), msg(A.LEAD, 60), desfecho=desfecho, **campos)


def painel(leads, **opcoes):
    return sdr.calcular_painel(mes="2026-09", leads=leads, **opcoes)


class TestCoorte:
    def test_so_entram_os_leads_que_chegaram_no_mes(self):
        dentro = lead()
        fora = lead(criado_em=datetime(2026, 10, 2, tzinfo=timezone.utc))
        assert painel([dentro, fora]).leads == 1

    def test_o_mes_e_o_de_brasilia(self):
        """01/09 às 02h em UTC ainda é 31/08 em Brasília."""
        madrugada = lead(criado_em=datetime(2026, 9, 1, 2, 0, tzinfo=timezone.utc))
        assert painel([madrugada]).leads == 0
        assert sdr.calcular_painel(mes="2026-08", leads=[madrugada]).leads == 1

    def test_aceita_instante_sem_fuso_como_utc(self):
        """O SQLite devolve instantes sem fuso."""
        assert painel([lead(criado_em=datetime(2026, 9, 10, 12, 0))]).leads == 1

    def test_filtro_de_origem(self):
        leads = [lead(), lead(tipo=FRIO, canal=None), lead(tipo=TipoCanal.SOCIOS)]
        assert painel(leads, origem=sdr.ORIGEM_TRAFEGO_PAGO).leads == 1
        assert painel(leads, origem=sdr.ORIGEM_FRIO).leads == 1
        assert painel(leads).leads == 3


class TestTaxasDoTopo:
    @pytest.fixture
    def resultado(self):
        leads = [
            lead(respondeu(D.QUALIFICADO), porte_estimado="Médio"),
            lead(respondeu(D.QUALIFICADO), porte_estimado="Pequeno"),
            lead(respondeu(D.FORA_DO_PERFIL), motivo_descarte=MotivoDeDescarte.PORTE_ABAIXO),
            lead(respondeu(D.TRANSBORDO)),
            lead(respondeu(D.PAROU)),
            lead(respondeu(None)),  # em andamento
            lead(conversa(msg(A.IA, 30))),  # nunca respondeu
        ]
        return painel(leads)

    def test_contagens(self, resultado):
        assert (resultado.leads, resultado.responderam, resultado.com_desfecho) == (7, 6, 5)
        assert (resultado.qualificados, resultado.fora_do_perfil, resultado.em_andamento) == (2, 1, 1)

    def test_concluida_pela_ia_e_veredito_sobre_quem_tem_desfecho(self, resultado):
        """Em andamento fica fora do denominador: ainda pode ter qualquer desfecho."""
        taxa = resultado.qualificacao_concluida
        assert (taxa.numerador, taxa.denominador, taxa.valor) == (3, 5, 60.0)

    def test_concluida_transbordo_e_parou_somam_100(self, resultado):
        soma = (
            resultado.qualificacao_concluida.numerador
            + resultado.transbordo.numerador
            + resultado.parou.numerador
        )
        assert soma == resultado.com_desfecho

    def test_qualificados_sobre_leads_e_sobre_quem_respondeu(self, resultado):
        assert resultado.qualificados_sobre_leads.valor == pytest.approx(100 * 2 / 7)
        assert resultado.qualificados_sobre_responderam.valor == pytest.approx(100 * 2 / 6)

    def test_avaliacao_contra_a_meta(self, resultado):
        """60% está entre o alerta (55%) e a meta (70%)."""
        assert resultado.indicador_qualificacao.avaliacao == "Entre a meta e o alerta"
        assert resultado.indicador_qualificacao.meta == "meta de 70%"
        assert resultado.indicador_transbordo.avaliacao == "Na meta"  # 20% é o limite

    def test_sem_dados_nada_vira_zero(self):
        vazio = painel([])
        assert vazio.qualificacao_concluida.valor is None
        assert vazio.indicador_qualificacao.avaliacao is None
        assert vazio.tma_segundos is None
        assert vazio.csat.valor is None
        assert vazio.primeira_resposta.valor is None

    def test_o_desfecho_e_o_da_conversa_mais_recente(self):
        """Transbordou antes e a equipe devolveu para a IA, que qualificou."""
        l = lead(respondeu(D.TRANSBORDO), respondeu(D.QUALIFICADO), porte_estimado="Médio")
        assert painel([l]).qualificados == 1


class TestTempos:
    def test_tma_so_nas_conversas_que_a_ia_concluiu(self):
        leads = [
            lead(respondeu(D.QUALIFICADO, duracao=300), porte_estimado="Médio"),
            lead(respondeu(D.FORA_DO_PERFIL, duracao=500)),
            lead(respondeu(D.TRANSBORDO, duracao=9999)),
        ]
        assert painel(leads).tma_segundos == 400

    def test_primeira_resposta_e_a_mediana_do_trafego_pago(self):
        leads = [
            lead(conversa(msg(A.IA, 20))),
            lead(conversa(msg(A.IA, 40))),
            lead(conversa(msg(A.IA, 900))),
            lead(conversa(msg(A.IA, 5000)), tipo=FRIO),  # no frio a IA fala primeiro
        ]
        resultado = painel(leads)
        assert resultado.primeira_resposta.valor == 40
        assert resultado.primeira_resposta.avaliacao == "Na meta"


class TestFunil:
    @pytest.fixture
    def funil(self):
        leads = [
            lead(conversa(msg(A.IA))),  # não respondeu
            lead(respondeu(None)),  # etapa 2, em andamento
            lead(respondeu(D.PAROU)),  # etapa 2
            lead(respondeu(D.TRANSBORDO), cnpj="12.345.678/0001-90"),  # etapa 3
            lead(respondeu(D.FORA_DO_PERFIL), porte_estimado="Micro"),  # etapa 3
            lead(respondeu(D.QUALIFICADO), porte_estimado="Médio"),  # etapa 4
            lead(respondeu(D.QUALIFICADO), porte_estimado="Grande", reuniao_marcada_para=INICIO),
        ]
        return painel(leads).funil

    def test_as_etapas(self, funil):
        assert [e.leads for e in funil] == [7, 6, 4, 2, 1]

    def test_as_saidas_de_cada_etapa_fecham_com_a_diferenca(self, funil):
        for etapa, proxima in zip(funil, funil[1:]):
            assert sum(s.quantidade for s in etapa.saidas) == etapa.leads - proxima.leads

    def test_os_motivos(self, funil):
        como = lambda etapa: {s.nome: s.quantidade for s in etapa.saidas}
        assert como(funil[0]) == {"não responderam": 1}
        assert como(funil[1]) == {"em andamento": 1, "pararam no meio": 1}
        assert como(funil[2]) == {"passaram para a equipe": 1, "fora do perfil": 1}
        assert como(funil[3]) == {"ainda sem reunião": 1}
        assert funil[4].saidas == []


class TestCompreensao:
    def test_confianca_media_e_faixas(self):
        respostas = [
            msg(A.IA, confianca=Decimal(v)) for v in ("1.00", "0.95", "0.80", "0.60", "0.40")
        ]
        resultado = painel([lead(conversa(*respostas))]).confianca
        assert resultado.media == pytest.approx(0.75)
        assert [f.quantidade for f in resultado.faixas] == [2, 1, 0, 1, 1]
        assert resultado.abaixo_de_0_6.valor == 20.0

    def test_falhas_por_resposta_e_por_conversa(self):
        leads = [
            lead(conversa(msg(A.LEAD), msg(A.IA, fallback=True), msg(A.IA), msg(A.IA))),
            lead(conversa(msg(A.LEAD), msg(A.IA), msg(A.IA), msg(A.IA))),
            lead(conversa(msg(A.IA))),  # nunca respondeu: fora da conta por conversa
        ]
        resultado = painel(leads)
        assert (resultado.falhas_por_resposta.numerador, resultado.falhas_por_resposta.denominador) == (1, 7)
        assert (resultado.falhas_por_conversa.numerador, resultado.falhas_por_conversa.denominador) == (1, 2)
        assert resultado.falhas_por_conversa.valor == 50.0
        assert resultado.indicador_falhas.avaliacao == "Em alerta"

    def test_termos_juntam_maiusculas_e_espacos(self):
        respostas = [
            msg(A.IA, fallback=True, termo_nao_reconhecido=t)
            for t in ("Fator R", "fator r ", "holding")
        ]
        termos = painel([lead(conversa(*respostas))]).termos
        assert [(t.nome, t.quantidade) for t in termos] == [("fator r", 2), ("holding", 1)]

    def test_interesses_juntam_o_resto_em_outros(self):
        leads = [lead(respondeu(), interesse=f"Assunto {i}") for i in range(8)]
        interesses = painel(leads).interesses
        assert len(interesses) == 7
        assert interesses[-1] == sdr.Contagem("Outros assuntos", 2)


class TestTomEMotivos:
    def test_tom_predominante_e_empate_vira_neutro(self):
        positiva = conversa(msg(A.LEAD, tom=Tom.POSITIVO), msg(A.LEAD, tom=Tom.POSITIVO), msg(A.LEAD, tom=Tom.NEGATIVO))
        empate = conversa(msg(A.LEAD, tom=Tom.POSITIVO), msg(A.LEAD, tom=Tom.NEGATIVO))
        tom = painel([lead(positiva), lead(empate)]).tom
        assert {t.nome: t.quantidade for t in tom} == {"Positivo": 1, "Neutro": 1}

    def test_gatilhos_descartes_e_portes(self):
        leads = [
            lead(respondeu(D.TRANSBORDO, motivo_transbordo=MotivoDeTransbordo.PRECO)),
            lead(respondeu(D.FORA_DO_PERFIL), motivo_descarte=MotivoDeDescarte.NAO_CONTATAR),
            lead(respondeu(D.QUALIFICADO), porte_estimado="Médio"),
            lead(respondeu(D.QUALIFICADO), porte_estimado="Pequeno"),
        ]
        resultado = painel(leads)
        assert resultado.gatilhos == [sdr.Contagem("Perguntou o preço", 1)]
        assert resultado.descartes == [sdr.Contagem("Pediu para não ser contatado", 1)]
        # Na ordem da régua, não na da contagem.
        assert [p.nome for p in resultado.portes] == ["Pequeno", "Médio"]

    def test_espera_do_transbordo_por_destino(self):
        def transbordo(minutos):
            c = respondeu(D.TRANSBORDO, destino_transbordo=DestinoDoTransbordo.CONSULTORIA_C2)
            if minutos is not None:
                c.atendida_em = c.encerrada_em + timedelta(minutes=minutos)
            return c

        leads = [lead(transbordo(10)), lead(transbordo(30)), lead(transbordo(None))]
        destino = painel(leads).destinos[0]
        assert (destino.destino, destino.transbordos, destino.atendidos) == ("Consultoria (C2)", 3, 2)
        assert destino.espera_media_min == 20
        assert destino.avaliacao == "Entre a meta e o alerta"


class TestNota:
    def test_csat_e_satisfeitos(self):
        leads = [lead(respondeu(D.PAROU, nota=n)) for n in (5, 4, 3, 2)]
        resultado = painel(leads)
        assert resultado.csat.valor == 3.5
        assert resultado.notas == 4
        assert resultado.satisfeitos.valor == 50.0
        assert resultado.csat.avaliacao == "Entre a meta e o alerta"


class TestPorOrigem:
    @pytest.fixture
    def linhas(self):
        leads = [
            lead(respondeu(D.QUALIFICADO), porte_estimado="Médio", canal="Meta Ads"),
            lead(respondeu(D.PAROU), canal="Meta Ads"),
            lead(conversa(msg(A.IA)), canal="Google Ads"),
            lead(conversa(msg(A.IA)), tipo=FRIO, canal=None),
        ]
        midia = {"Meta Ads": Decimal("500"), "Google Ads": Decimal("300"), "TikTok": Decimal("50")}
        return {l.origem: l for l in painel(leads, midia=midia).por_origem}

    def test_custo_por_lead_e_por_qualificado(self, linhas):
        meta = linhas["Tráfego pago · Meta Ads"]
        assert (meta.leads, meta.midia, meta.custo_por_lead, meta.custo_por_qualificado) == (
            2, Decimal("500"), Decimal("250.00"), Decimal("500.00")
        )
        assert meta.avaliacao_custo == "Em alerta"  # acima de R$ 450

    def test_sem_qualificado_nao_ha_custo_por_qualificado(self, linhas):
        assert linhas["Tráfego pago · Google Ads"].custo_por_qualificado is None

    def test_midia_sem_lead_aparece(self, linhas):
        """Dinheiro gasto sem nenhum lead é justamente o que precisa aparecer."""
        tiktok = linhas["Tráfego pago · TikTok"]
        assert (tiktok.leads, tiktok.midia, tiktok.custo_por_lead) == (0, Decimal("50"), None)

    def test_total_do_trafego_pago(self, linhas):
        total = linhas["Tráfego pago · total"]
        assert (total.leads, total.midia) == (3, Decimal("850"))
        assert total.custo_por_qualificado == Decimal("850.00")

    def test_lead_frio_sem_midia_e_com_a_meta_propria(self, linhas):
        frio = linhas["Leads frios"]
        assert frio.midia is None and frio.custo_por_lead is None
        assert frio.avaliacao_resposta == "Em alerta"  # 0% de resposta

    def test_filtro_frio_ignora_a_midia(self):
        resultado = painel([lead(tipo=FRIO, canal=None)], midia={"Meta Ads": Decimal("10")}, origem="frio")
        assert [l.origem for l in resultado.por_origem] == ["Leads frios"]


class TestCustoPoupado:
    def test_sem_parametros_diz_o_que_falta(self):
        custo = painel([]).custo_poupado
        assert custo.calculavel is False
        assert len(custo.falta) == 3
        assert custo.liquido is None

    def test_a_conta(self):
        """2 conversas × (R$ 45/h × 25 min) − US$ 0,10 × 5,40."""
        leads = [
            lead(conversa(msg(A.IA, custo_usd=Decimal("0.06")), msg(A.LEAD), desfecho=D.QUALIFICADO), porte_estimado="Médio"),
            lead(conversa(msg(A.IA, custo_usd=Decimal("0.04")), msg(A.LEAD), desfecho=D.FORA_DO_PERFIL)),
            lead(conversa(msg(A.IA), msg(A.LEAD), desfecho=D.TRANSBORDO)),
        ]
        custo = painel(
            leads, custo_hora_sdr=Decimal("45"), minutos_por_conversa=25, cotacao_dolar=Decimal("5.40")
        ).custo_poupado
        assert custo.calculavel
        assert custo.conversas_concluidas == 2
        assert custo.custo_por_conversa == Decimal("18.75")
        assert custo.bruto == Decimal("37.50")
        assert custo.custo_ia == Decimal("0.54")
        assert custo.liquido == Decimal("36.96")
        assert custo.mensagens_sem_custo == 1


class TestMetasETravas:
    @pytest.mark.parametrize(
        "valor, esperado",
        [(70, "Na meta"), (69.9, "Entre a meta e o alerta"), (55, "Entre a meta e o alerta"), (54.9, "Em alerta")],
    )
    def test_meta_maior_e_melhor(self, valor, esperado):
        assert sdr.METAS["qualificacao_concluida"].avaliar(valor) == esperado

    @pytest.mark.parametrize(
        "valor, esperado", [(60, "Na meta"), (61, "Entre a meta e o alerta"), (301, "Em alerta")]
    )
    def test_meta_menor_e_melhor(self, valor, esperado):
        assert sdr.METAS["primeira_resposta"].avaliar(valor) == esperado

    def test_mensagem_com_preco_nao_sai(self):
        assert "preço" in sdr.problema_na_mensagem("O honorário fica em R$ 3.000")

    def test_mensagem_normal_sai(self):
        assert sdr.problema_na_mensagem("Quantos funcionários a empresa tem hoje?") is None

    def test_mes_anterior_vira_o_ano(self):
        assert sdr.mes_anterior("2026-01") == "2025-12"


# ------------------------------------------------------------ composição (10/10/2026)

class TestComposicaoDoPainel:
    """Cada número do painel abre a lista que o compõe, da mesma coorte e do mesmo recorte."""

    def _leads(self):
        return [
            lead(respondeu(D.QUALIFICADO, nota=5), reuniao_marcada_para=INICIO, porte_estimado="Pequeno", interesse="BPO"),
            lead(respondeu(D.QUALIFICADO, nota=3), porte_estimado="Médio"),
            lead(respondeu(D.FORA_DO_PERFIL), motivo_descarte=MotivoDeDescarte.PORTE_ABAIXO),
            lead(respondeu(D.TRANSBORDO, motivo_transbordo=MotivoDeTransbordo.PEDIU_PESSOA)),
            lead(conversa(msg(A.IA, 30))),
            lead(conversa(msg(A.IA, 30, fallback=True, confianca=Decimal("0.5"), termo_nao_reconhecido="DRE"), msg(A.LEAD, 60))),
        ]

    def _comp(self, chave):
        return sdr.composicao_do_painel(mes="2026-09", leads=self._leads(), origem=None, chave=chave)

    def test_as_listas_batem_com_os_numeros(self):
        p = painel(self._leads())
        assert len(self._comp("leads")) == p.leads
        assert sum(i.entra for i in self._comp("responderam")) == p.responderam
        assert sum(i.entra for i in self._comp("qualificados")) == p.qualificados
        conc = self._comp("qualificacao_concluida")
        assert (sum(i.entra for i in conc), len(conc)) == (p.qualificacao_concluida.numerador, p.qualificacao_concluida.denominador)
        tb = self._comp("transbordo")
        assert (sum(i.entra for i in tb), len(tb)) == (p.transbordo.numerador, p.transbordo.denominador)
        assert sum(i.entra for i in self._comp("reunioes")) == p.reunioes
        assert len(self._comp("csat")) == p.notas
        assert sum(i.entra for i in self._comp("csat")) == p.satisfeitos.numerador
        fa = self._comp("falhas")
        assert (sum(i.entra for i in fa), len(fa)) == (p.falhas_por_conversa.numerador, p.falhas_por_conversa.denominador)
        assert [i.categoria for i in self._comp("termos")] == ["dre"]
        assert {i.categoria for i in self._comp("descartes")} == {MotivoDeDescarte.PORTE_ABAIXO.value}
        assert sorted(i.categoria for i in self._comp("portes")) == ["Médio", "Pequeno"]
        assert len(self._comp("custo_poupado")) == p.custo_poupado.conversas_concluidas

    def test_numero_desconhecido_e_recusado(self):
        with pytest.raises(ValueError):
            self._comp("xyz")
