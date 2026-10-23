"""Respostas do SDR de IA no WhatsApp — fase 1 (amostra aprovada por Eduardo em 23/10/2026).

O roteador de custo (regras, modelo leve, principal, travas), a rodada que grava e envia, e o que a equipe
faz na tela. Os modelos e o WhatsApp são falsos: nada sai daqui.
"""

from __future__ import annotations

import itertools
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from crm import configuracao
from crm.agente import respostas_do_sdr as respostas
from crm.agente.envio import EnvioFalhou
from crm.agente.prompt_do_sdr import PROMPT_DO_ROTEIRO, instrucoes_do_roteador
from crm.agente.recebimento import processar
from crm.agente.roteador_do_sdr import (
    APRESENTACAO, GATILHOS, Clientes, ConfiguracaoDasRespostas, IAFora, Pedido, decidir, gatilho_por_regra,
    problema_na_resposta,
)
from crm.agente.sdr import AgenteFalhou
from crm.api.app import criar_app
from crm.db.modelos import ConversaDoSdr, Lead, MensagemDoSdr
from crm.domain.listas import AutorDaMensagem, DesfechoDaConversa, DestinoDoTransbordo, MotivoDeTransbordo

REPO = Path(__file__).resolve().parents[3]
NUMERO_ID = "1098765432"
LEAD = "5511987654321"
LINK = "https://criterio-questionario-proposta.netlify.app/questionario"
AGORA = datetime(2026, 10, 23, 13, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------ modelos falsos
class ModeloFalso:
    """Fala como o cliente de IA do CRM. `decisoes`: o que devolve em cada chamada (dict, ou exceção)."""

    def __init__(self, *decisoes, ao_chamar=None):
        self.decisoes = list(decisoes)
        self.pedidos: list[dict] = []
        self.ao_chamar = ao_chamar
        self.beta = NS(messages=NS(create=self._criar))

    def _criar(self, **pedido):
        self.pedidos.append(pedido)
        if self.ao_chamar:
            self.ao_chamar()
        decisao = self.decisoes.pop(0) if len(self.decisoes) > 1 else self.decisoes[0]
        if isinstance(decisao, Exception):
            raise decisao
        return NS(content=[NS(type="text", text=json.dumps(decisao))], stop_reason="end_turn",
                  usage=NS(modelo=pedido["model"], input_tokens=1000, output_tokens=100,
                           cache_read_input_tokens=0, cache_creation_input_tokens=0, server_tool_use=None))


def decisao(acao="responder", texto="Hoje, o que mais incomoda no que o escritório entrega?", gatilho="nenhum"):
    return {"acao": acao, "gatilho": gatilho, "texto": texto, "fichas_usadas": ["S1"], "intencao": "contar a dor"}


def clientes(leve, principal=None):
    return Clientes(leve=leve, modelo_leve="claude-haiku-4-5", principal=principal or ModeloFalso(decisao()),
                    modelo_principal="claude-opus-5")


def pedido(pendente="Estamos crescendo e a contabilidade não acompanha.", primeira=False):
    return Pedido(sistema="PROMPT", conversa=f"<conversa>{pendente}</conversa>", pendente=pendente,
                  primeira=primeira, links_permitidos=(LINK,), destino_do_servico=DestinoDoTransbordo.CONSULTORIA_C2)


# Haiku 4.5: US$ 1 e 5 por milhão; Opus 5: 5 e 25. 1000 de entrada e 100 de saída por chamada.
CUSTO_LEVE = Decimal("0.0015")
CUSTO_PRINCIPAL = Decimal("0.0075")


# ------------------------------------------------------------------ o roteador
class TestRegras:
    @pytest.mark.parametrize("texto,codigo", [
        ("Quero falar com uma pessoa", "T1"), ("posso conversar com um atendente?", "T1"),
        ("Não quero falar com robô", "T1"), ("Recebi uma intimação da Receita ontem", "T9"),
        ("Estamos sob fiscalização da Sefaz", "T9"), ("Já sou cliente de vocês", "T11"),
        ("somos clientes da Critério há 2 anos", "T11"),
    ])
    def test_reconhece_sem_ia(self, texto, codigo):
        assert gatilho_por_regra(texto).codigo == codigo

    @pytest.mark.parametrize("texto", [
        "Estamos crescendo e a contabilidade não acompanha.", "Vale a pena eu sair do Simples Nacional?",
        "Quero entender o serviço de BPO financeiro.", "Faz sentido, sim.",
    ])
    def test_na_duvida_deixa_para_o_modelo(self, texto):
        assert gatilho_por_regra(texto) is None

    def test_regra_nao_chama_modelo_e_usa_a_frase_aprovada(self):
        leve = ModeloFalso(decisao())
        r = decidir(pedido("Quero falar com uma pessoa", primeira=True), clientes(leve))
        assert leve.pedidos == [] and r.rota == "regra" and r.custo_usd is None
        assert r.texto == f"{APRESENTACAO} {GATILHOS['T1'].frase}"
        assert r.passagem.motivo is MotivoDeTransbordo.PEDIU_PESSOA
        assert r.passagem.destino is DestinoDoTransbordo.CONSULTORIA_C2  # o do serviço

    def test_urgencia_vai_para_o_tecnico_fiscal(self):
        r = decidir(pedido("Fui autuado pela Receita"), clientes(ModeloFalso(decisao())))
        assert (r.passagem.motivo, r.passagem.destino) == (MotivoDeTransbordo.URGENCIA_LEGAL,
                                                           DestinoDoTransbordo.TECNICO_FISCAL)

    def test_ja_cliente_vai_para_o_sucesso(self):
        r = decidir(pedido("Já somos clientes"), clientes(ModeloFalso(decisao())))
        assert r.passagem.destino is DestinoDoTransbordo.SUCESSO_DO_CLIENTE


class TestRoteador:
    def test_leve_responde_o_roteiro(self):
        leve, principal = ModeloFalso(decisao()), ModeloFalso(decisao())
        r = decidir(pedido(), clientes(leve, principal))
        assert (r.rota, r.modelo, r.custo_usd, r.passagem) == ("leve", "claude-haiku-4-5", CUSTO_LEVE, None)
        assert principal.pedidos == [] and leve.pedidos[0]["model"] == "claude-haiku-4-5"
        assert r.texto == "Hoje, o que mais incomoda no que o escritório entrega?"
        assert (r.intencao, r.fichas) == ("contar a dor", ["S1"])

    def test_leve_chama_o_principal_e_o_custo_soma_os_dois(self):
        leve = ModeloFalso(decisao("chamar_modelo_principal", ""))
        principal = ModeloFalso(decisao(texto="Entendo. O que pesa mais hoje?"))
        r = decidir(pedido(), clientes(leve, principal))
        assert (r.rota, r.modelo, r.texto) == ("principal", "claude-opus-5", "Entendo. O que pesa mais hoje?")
        assert r.custo_usd == CUSTO_LEVE + CUSTO_PRINCIPAL

    def test_so_o_leve_tem_a_saida_de_chamar_o_principal(self):
        leve, principal = ModeloFalso(decisao("chamar_modelo_principal", "")), ModeloFalso(decisao())
        decidir(pedido(), clientes(leve, principal))
        acoes = lambda m: m.pedidos[0]["output_config"]["format"]["schema"]["properties"]["acao"]["enum"]  # noqa: E731
        assert "chamar_modelo_principal" in acoes(leve) and "chamar_modelo_principal" not in acoes(principal)
        assert "chamar_modelo_principal" not in principal.pedidos[0]["system"][1]["text"]
        assert leve.pedidos[0]["system"][0]["cache_control"] == {"type": "ephemeral"}

    def test_principal_que_tenta_escalar_e_recusado(self):
        with pytest.raises(IAFora):
            decidir(pedido(), clientes(ModeloFalso(decisao("chamar_modelo_principal", "")),
                                       ModeloFalso(decisao("chamar_modelo_principal", ""))))

    def test_leve_fora_do_ar_passa_ao_principal(self):
        r = decidir(pedido(), clientes(ModeloFalso(AgenteFalhou("caiu")), ModeloFalso(decisao())))
        assert r.rota == "principal"

    def test_os_dois_fora_do_ar(self):
        with pytest.raises(IAFora):
            decidir(pedido(), clientes(ModeloFalso(AgenteFalhou("a")), ModeloFalso(AgenteFalhou("b"))))

    def test_duvida_tecnica_sai_com_a_frase_aprovada_nunca_com_texto_do_modelo(self):
        leve = ModeloFalso(decisao("passar_para_equipe", "No seu caso o Presumido compensa.", gatilho="T4"))
        r = decidir(pedido("Vale a pena eu sair do Simples Nacional?"), clientes(leve))
        assert r.texto == GATILHOS["T4"].frase and "Presumido" not in r.texto
        assert (r.passagem.motivo, r.passagem.destino) == (MotivoDeTransbordo.DUVIDA_TECNICA,
                                                           DestinoDoTransbordo.TECNICO_FISCAL)

    def test_passagem_sem_gatilho_vira_t5(self):
        r = decidir(pedido(), clientes(ModeloFalso(decisao("passar_para_equipe", "", gatilho="nenhum"))))
        assert r.texto == GATILHOS["T5"].frase

    def test_trava_de_preco_barra_e_passa_para_a_equipe(self):
        r = decidir(pedido(), clientes(ModeloFalso(decisao(texto="Fica em torno de R$ 900 por mês."))))
        assert r.bloqueada == "Fica em torno de R$ 900 por mês." and "preço" in r.motivo_do_bloqueio
        assert r.texto == GATILHOS["T5"].frase and r.passagem.motivo is MotivoDeTransbordo.OUTRO
        assert r.custo_usd == CUSTO_LEVE

    def test_reuniao_aceita_vai_para_a_equipe_sem_ser_transbordo(self):
        r = decidir(pedido("Faz sentido, sim."), clientes(ModeloFalso(decisao(
            "marcar_reuniao", "Ótimo. A nossa equipe vai falar com você para combinar o horário."))))
        assert r.marcou_reuniao and r.passagem.motivo is None
        assert r.passagem.destino is DestinoDoTransbordo.CONSULTORIA_C2

    def test_primeira_mensagem_se_apresenta(self):
        r = decidir(pedido(primeira=True), clientes(ModeloFalso(decisao())))
        assert r.texto.startswith(APRESENTACAO)
        ja = decidir(pedido(primeira=True), clientes(ModeloFalso(decisao(
            texto="Olá! Sou a assistente virtual da Critério. O que te trouxe?"))))
        assert ja.texto.count("assistente virtual") == 1

    def test_resposta_que_nao_e_json_conta_como_falha(self):
        class Quebrado(ModeloFalso):
            def _criar(self, **pedido):
                self.pedidos.append(pedido)
                return NS(content=[NS(type="text", text="não sei")], stop_reason="end_turn",
                          usage=NS(modelo=pedido["model"], input_tokens=10, output_tokens=10))
        r = decidir(pedido(), clientes(Quebrado(None), ModeloFalso(decisao())))
        assert r.rota == "principal"


class TestTravas:
    @pytest.mark.parametrize("texto,trecho", [
        ("Quanto ao valor, são R$ 500.", "preço"),
        ("Usamos um software próprio.", "Termo proibido"),
        ("Garantimos economia de imposto.", "Termo proibido"),
        ("Pode me mandar a senha do portal?", "dado sensível"),
        ("Me envie o extrato do banco.", "dado sensível"),
        ("Veja em https://outro-site.com/x", "Link"),
        ("x" * 1300, "caracteres"),
        ("   ", "vazia"),
    ])
    def test_barra(self, texto, trecho):
        assert trecho.casefold() in (problema_na_resposta(texto, (LINK,)) or "").casefold()

    @pytest.mark.parametrize("texto", [
        "Olá! Sou a assistente virtual da Critério Consultores. O que fez você procurar uma mudança agora?",
        f"Para a equipe montar a proposta, responda aqui: {LINK}.",
        f"O questionário está em {LINK}/ e leva uns minutos.",
    ])
    def test_deixa_passar(self, texto):
        assert problema_na_resposta(texto, (LINK,)) is None


class TestPrompt:
    def test_o_prompt_do_codigo_e_o_do_documento(self):
        doc = (REPO / "sdr-ia-roteiro-spin.md").read_text()
        bloco = re.search(r"```text\n(.*?)```", doc, re.S).group(1).strip()
        assert PROMPT_DO_ROTEIRO.strip() == bloco

    def test_o_roteador_lista_os_gatilhos_e_proibe_responder_duvida_tecnica(self):
        texto = instrucoes_do_roteador(True)
        assert all(f"- {c}:" in texto for c in GATILHOS)
        assert "Toda pergunta técnica sobre o caso do lead é T4" in texto


# ------------------------------------------------------------------ a rodada, com o banco
@pytest.fixture
def fabrica(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)


_IDS = itertools.count(1)


class Envio:
    """O WhatsApp falso. Cada envio ganha um id novo, como na Meta."""

    def __init__(self, falha: Exception | None = None):
        self.enviadas: list[tuple[str, str]] = []
        self.falha = falha

    def __call__(self, para, texto):
        if self.falha:
            raise self.falha
        self.enviadas.append((para, texto))
        return f"wamid.crm{next(_IDS)}"


def lead_escreve(fabrica, texto, quando=AGORA - timedelta(minutes=1), de=LEAD, nome="Marina", id_=None):
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "c", "changes": [{"field": "messages", "value": {
        "metadata": {"phone_number_id": NUMERO_ID}, "contacts": [{"wa_id": de, "profile": {"name": nome}}],
        "messages": [{"from": de, "id": id_ or f"wamid.lead.{quando.timestamp()}.{texto[:8]}",
                      "timestamp": str(int(quando.timestamp())), "type": "text", "text": {"body": texto}}]}}]}]}
    with fabrica() as s:
        processar(s, payload, NUMERO_ID, quando)
        s.commit()


def rodar(fabrica, leve, *, modo="Supervisionado", envio=None, principal=None, momento=AGORA, **cfg):
    config = ConfiguracaoDasRespostas(modo=modo, **cfg)
    return respostas.rodar_uma_vez(fabrica, config, lambda: clientes(leve, principal), envio, LINK, lambda: momento)


def mensagens(fabrica):
    with fabrica() as s:
        return list(s.scalars(sa.select(MensagemDoSdr).order_by(MensagemDoSdr.id)))


def conversas(fabrica):
    with fabrica() as s:
        return list(s.scalars(sa.select(ConversaDoSdr).order_by(ConversaDoSdr.id)))


def da_ia(fabrica):
    return [m for m in mensagens(fabrica) if m.autor is AutorDaMensagem.IA]


class TestRodada:
    def test_desligado_nao_faz_nada(self, fabrica):
        lead_escreve(fabrica, "Oi, vi o anúncio")
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve, modo="Desligado")
        assert leve.pedidos == [] and da_ia(fabrica) == []

    def test_supervisionado_rascunha_e_nao_envia(self, fabrica):
        lead_escreve(fabrica, "Oi, vi o anúncio")
        envio = Envio()
        rodada = rodar(fabrica, ModeloFalso(decisao()), envio=envio)
        (m,) = da_ia(fabrica)
        assert (m.entrega, m.rota, m.modelo, m.custo_usd) == ("rascunho", "leve", "claude-haiku-4-5", CUSTO_LEVE)
        assert m.texto.startswith(APRESENTACAO) and envio.enviadas == [] and rodada.rascunhos == 1

    def test_automatico_envia(self, fabrica):
        lead_escreve(fabrica, "Oi, vi o anúncio")
        envio = Envio()
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=envio)
        (m,) = da_ia(fabrica)
        assert m.entrega == "enviada" and m.externo_id.startswith("wamid.crm")
        assert envio.enviadas == [(LEAD, m.texto)]

    def test_nao_responde_duas_vezes(self, fabrica):
        lead_escreve(fabrica, "Oi")
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve)
        rodar(fabrica, leve)
        assert len(leve.pedidos) == 1 and len(da_ia(fabrica)) == 1

    def test_espera_o_lead_terminar(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(seconds=5))
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve, espera=timedelta(seconds=20))
        assert leve.pedidos == []
        rodar(fabrica, leve, espera=timedelta(seconds=20), momento=AGORA + timedelta(seconds=30))
        assert len(leve.pedidos) == 1

    def test_responde_ao_conjunto_das_mensagens(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(minutes=2))
        lead_escreve(fabrica, "quero entender o BPO", quando=AGORA - timedelta(minutes=1))
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve)
        conversa = leve.pedidos[0]["messages"][0]["content"]
        assert "Oi" in conversa and "quero entender o BPO" in conversa and len(leve.pedidos) == 1

    def test_janela_fechada_nao_responde(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(hours=25))
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve)
        assert leve.pedidos == [] and da_ia(fabrica) == []

    def test_nao_contatar_nao_responde(self, fabrica):
        lead_escreve(fabrica, "SAIR")
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve, modo="Automático", envio=Envio())
        assert leve.pedidos == [] and da_ia(fabrica) == []

    def test_lead_escreve_de_novo_e_o_rascunho_velho_e_descartado(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(minutes=3))
        rodar(fabrica, ModeloFalso(decisao()), momento=AGORA - timedelta(minutes=2))
        lead_escreve(fabrica, "Alguém aí?", quando=AGORA - timedelta(minutes=1))
        rodar(fabrica, ModeloFalso(decisao(texto="Estou aqui. O que te trouxe?")))
        velho, novo = da_ia(fabrica)
        assert (velho.entrega, novo.entrega) == ("descartada", "rascunho")

    def test_o_historico_nao_leva_rascunho_nem_dado_pessoal(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(minutes=3))
        rodar(fabrica, ModeloFalso(decisao(texto="TEXTO-DO-RASCUNHO")), momento=AGORA - timedelta(minutes=2))
        lead_escreve(fabrica, "Alguém aí?", quando=AGORA - timedelta(minutes=1))
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve)
        conversa = leve.pedidos[0]["messages"][0]["content"]
        assert "TEXTO-DO-RASCUNHO" not in conversa and "Marina" not in conversa and "98765" not in conversa
        assert "<conversa>" in conversa and "Alguém aí?" in conversa

    def test_passagem_encerra_e_a_resposta_do_lead_fica_na_mesma_conversa(self, fabrica):
        lead_escreve(fabrica, "Quero falar com uma pessoa", quando=AGORA - timedelta(minutes=2))
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=Envio(),
              momento=AGORA - timedelta(minutes=1))
        (c,) = conversas(fabrica)
        assert c.desfecho is DesfechoDaConversa.TRANSBORDO and c.equipe_desde is not None
        assert c.motivo_transbordo is MotivoDeTransbordo.PEDIU_PESSOA and c.equipe_motivo
        lead_escreve(fabrica, "Obrigado, aguardo", quando=AGORA - timedelta(seconds=30))
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve, modo="Automático", envio=Envio(), momento=AGORA + timedelta(minutes=1))
        assert len(conversas(fabrica)) == 1 and leve.pedidos == []
        assert mensagens(fabrica)[-1].texto == "Obrigado, aguardo"

    def test_maximo_de_respostas(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(minutes=3))
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=Envio(), momento=AGORA - timedelta(minutes=2))
        lead_escreve(fabrica, "E aí?", quando=AGORA - timedelta(minutes=1))
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve, modo="Automático", envio=Envio(), maximo_de_respostas=1)
        assert leve.pedidos == []
        assert da_ia(fabrica)[-1].texto == respostas.FRASE_DE_PASSAGEM
        assert conversas(fabrica)[0].equipe_motivo == "Chegou ao máximo de respostas da IA"

    def test_teto_de_custo(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(minutes=3))
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=Envio(), momento=AGORA - timedelta(minutes=2))
        lead_escreve(fabrica, "E aí?", quando=AGORA - timedelta(minutes=1))
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=Envio(), teto_por_conversa=Decimal("0.001"))
        assert conversas(fabrica)[0].equipe_motivo == "Chegou ao teto de custo da conversa"

    def test_ia_fora_do_ar_passa_em_silencio(self, fabrica):
        lead_escreve(fabrica, "Oi")
        rodada = rodar(fabrica, ModeloFalso(AgenteFalhou("a")), principal=ModeloFalso(AgenteFalhou("b")),
                       modo="Automático", envio=Envio())
        (c,) = conversas(fabrica)
        assert da_ia(fabrica) == [] and c.motivo_transbordo is MotivoDeTransbordo.SISTEMA_FORA
        assert rodada.erros

    def test_sem_chave_da_ia_passa_em_silencio(self, fabrica):
        lead_escreve(fabrica, "Oi")
        def sem_chave():
            raise AgenteFalhou("falta a chave")
        respostas.rodar_uma_vez(fabrica, ConfiguracaoDasRespostas(modo="Automático"), sem_chave, Envio(), LINK,
                                lambda: AGORA)
        assert conversas(fabrica)[0].motivo_transbordo is MotivoDeTransbordo.SISTEMA_FORA

    def test_whatsapp_falhou(self, fabrica):
        lead_escreve(fabrica, "Oi")
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=Envio(EnvioFalhou("A Meta recusou")))
        (m,) = da_ia(fabrica)
        assert (m.entrega, m.observacao) == ("falhou", "A Meta recusou")
        assert conversas(fabrica)[0].motivo_transbordo is MotivoDeTransbordo.SISTEMA_FORA

    def test_lead_que_virou_oportunidade_fica_com_a_equipe(self, fabrica, engine):
        lead_escreve(fabrica, "Oi")
        with engine.connect() as conexao:  # o vínculo com a oportunidade é só o id
            conexao.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conexao.execute(sa.update(Lead).values(convertido_em_id=999))
            conexao.commit()
            conexao.exec_driver_sql("PRAGMA foreign_keys=ON")
        leve = ModeloFalso(decisao())
        rodar(fabrica, leve, modo="Automático", envio=Envio())
        (c,) = conversas(fabrica)
        assert leve.pedidos == [] and da_ia(fabrica) == [] and c.desfecho is None and c.equipe_desde is not None

    def test_lead_escreveu_enquanto_a_ia_pensava(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(minutes=2))
        envio = Envio()
        leve = ModeloFalso(decisao(), ao_chamar=lambda: lead_escreve(fabrica, "Mais uma coisa",
                                                                        quando=AGORA - timedelta(seconds=40)))
        rodar(fabrica, leve, modo="Automático", envio=envio)
        (m,) = da_ia(fabrica)
        assert envio.enviadas == [] and m.entrega == "descartada" and m.custo_usd == CUSTO_LEVE

    def test_trava_registra_o_texto_barrado_e_envia_a_frase(self, fabrica):
        lead_escreve(fabrica, "Quanto custa?")
        envio = Envio()
        rodar(fabrica, ModeloFalso(decisao(texto="São R$ 800 por mês.")), modo="Automático", envio=envio)
        barrada, frase = da_ia(fabrica)
        assert (barrada.entrega, barrada.custo_usd, barrada.rota) == ("bloqueada", CUSTO_LEVE, "leve")
        assert (frase.entrega, frase.rota, frase.custo_usd) == ("enviada", "trava", None)
        assert envio.enviadas == [(LEAD, frase.texto)] and "R$" not in frase.texto

    def test_link_do_questionario_marca_o_envio(self, fabrica):
        lead_escreve(fabrica, "Quero uma proposta")
        rodar(fabrica, ModeloFalso(decisao(texto=f"A equipe monta a proposta pelas respostas: {LINK}")),
              modo="Automático", envio=Envio())
        with fabrica() as s:
            assert s.scalars(sa.select(Lead)).one().questionario_enviado_em is not None

    def test_log_sem_conteudo(self, fabrica, caplog):
        lead_escreve(fabrica, "Meu CNPJ é 12.345.678/0001-90")
        with caplog.at_level("INFO"):
            rodar(fabrica, ModeloFalso(decisao(texto="Obrigada! Qual o desafio hoje?")), modo="Automático",
                  envio=Envio())
        assert "12.345" not in caplog.text and "desafio" not in caplog.text and "5511" not in caplog.text


# ------------------------------------------------------------------ a equipe, pela API
@pytest.fixture
def envio():
    return Envio()


@pytest.fixture
def api(fabrica, envio):
    with TestClient(criar_app(fabrica, envio_de_texto=lambda: envio)) as c:
        yield c
    configuracao.registrar_fabrica(None)


def _com_rascunho(fabrica, texto="Hoje, o que mais incomoda?"):
    lead_escreve(fabrica, "Oi", quando=datetime.now(timezone.utc) - timedelta(minutes=1))
    rodar(fabrica, ModeloFalso(decisao(texto=texto)), momento=datetime.now(timezone.utc))
    return da_ia(fabrica)[-1]


class TestEquipe:
    def test_responder(self, fabrica, api, envio):
        rascunho = _com_rascunho(fabrica)
        r = api.post(f"/api/sdr/conversas/{rascunho.conversa_id}/responder", json={"texto": "Olá, aqui é o Eduardo."})
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["equipe_desde"] and corpo["atendida_em"] and corpo["equipe_motivo"] == "A equipe assumiu a conversa"
        equipe = corpo["mensagens"][-1]
        assert (equipe["autor"], equipe["entrega"]) == ("Equipe", "enviada")
        assert envio.enviadas == [(LEAD, "Olá, aqui é o Eduardo.")]
        assert next(m for m in corpo["mensagens"] if m["id"] == rascunho.id)["entrega"] == "descartada"

    def test_responder_com_a_janela_fechada(self, fabrica, api, envio):
        lead_escreve(fabrica, "Oi", quando=datetime.now(timezone.utc) - timedelta(hours=30))
        (c,) = conversas(fabrica)
        r = api.post(f"/api/sdr/conversas/{c.id}/responder", json={"texto": "Olá"})
        assert r.status_code == 409 and "janela" in r.json()["detail"] and envio.enviadas == []

    def test_responder_a_quem_pediu_para_sair(self, fabrica, api, envio):
        lead_escreve(fabrica, "SAIR", quando=datetime.now(timezone.utc) - timedelta(minutes=1))
        (c,) = conversas(fabrica)
        assert api.post(f"/api/sdr/conversas/{c.id}/responder", json={"texto": "Olá"}).status_code == 409
        assert envio.enviadas == []

    def test_envio_que_falha_nao_grava(self, fabrica, api, envio):
        rascunho = _com_rascunho(fabrica)
        envio.falha = EnvioFalhou("A Meta não enviou")
        r = api.post(f"/api/sdr/conversas/{rascunho.conversa_id}/responder", json={"texto": "Olá"})
        assert r.status_code == 502 and not any(m.autor is AutorDaMensagem.EQUIPE for m in mensagens(fabrica))

    def test_enviar_o_rascunho_como_esta(self, fabrica, api, envio):
        rascunho = _com_rascunho(fabrica)
        r = api.post(f"/api/sdr/mensagens/{rascunho.id}/enviar", json={})
        assert r.status_code == 200, r.text
        m = next(m for m in r.json()["mensagens"] if m["id"] == rascunho.id)
        assert (m["entrega"], m["texto"], m["autor"]) == ("enviada", rascunho.texto, "IA")
        assert envio.enviadas == [(LEAD, rascunho.texto)]
        assert api.post(f"/api/sdr/mensagens/{rascunho.id}/enviar", json={}).status_code == 409  # já foi

    def test_enviar_o_rascunho_ajustado(self, fabrica, api, envio):
        rascunho = _com_rascunho(fabrica)
        r = api.post(f"/api/sdr/mensagens/{rascunho.id}/enviar", json={"texto": "Texto ajustado."})
        m = next(m for m in r.json()["mensagens"] if m["id"] == rascunho.id)
        assert m["texto"] == "Texto ajustado." and m["observacao"].startswith("Ajustada e enviada")

    def test_descartar_passa_para_a_equipe(self, fabrica, api, envio):
        rascunho = _com_rascunho(fabrica)
        r = api.post(f"/api/sdr/mensagens/{rascunho.id}/descartar")
        corpo = r.json()
        assert corpo["equipe_motivo"] == "A equipe descartou o rascunho da IA" and corpo["desfecho"] is None
        assert envio.enviadas == []

    def test_devolver_conversa_aberta(self, fabrica, api):
        rascunho = _com_rascunho(fabrica)
        api.post(f"/api/sdr/mensagens/{rascunho.id}/descartar")
        r = api.post(f"/api/sdr/conversas/{rascunho.conversa_id}/devolver")
        assert r.status_code == 200 and r.json()["equipe_desde"] is None and r.json()["id"] == rascunho.conversa_id
        assert api.post(f"/api/sdr/conversas/{rascunho.conversa_id}/devolver").status_code == 409

    def test_devolver_depois_do_transbordo_abre_conversa_nova(self, fabrica, api):
        agora = datetime.now(timezone.utc)
        lead_escreve(fabrica, "Quero falar com uma pessoa", quando=agora - timedelta(minutes=1))
        rodar(fabrica, ModeloFalso(decisao()), momento=agora)
        (c,) = conversas(fabrica)
        r = api.post(f"/api/sdr/conversas/{c.id}/devolver")
        nova = r.json()
        assert nova["id"] != c.id and nova["equipe_desde"] is None
        lead_escreve(fabrica, "Voltei", quando=agora)
        with fabrica() as s:
            assert s.get(ConversaDoSdr, nova["id"]).mensagens[-1].texto == "Voltei"

    def test_o_modo_para_a_tela(self, api):
        assert api.get("/api/sdr/respostas").json() == {"modo": "Desligado"}


class TestIntegracoes:
    def test_aba_com_padroes(self, api):
        grupo = next(g for g in api.get("/api/configuracoes/integracoes").json()["grupos"]
                     if g["chave"] == "sdr_respostas")
        valores = {c["chave"]: c["padrao"] for c in grupo["campos"]}
        assert valores["sdr.modo"] == "Desligado" and valores["sdr.modelo_leve"] == "claude-haiku-4-5"
        assert grupo["configurado"] and not grupo["testavel"]
        assert grupo["situacao"].startswith("Respostas desligadas")

    @pytest.mark.parametrize("campo,valor", [
        ("sdr.modo", "Sempre"), ("sdr.teto_por_conversa", "abc"), ("sdr.teto_por_conversa", "0"),
        ("sdr.maximo_de_respostas", "0"), ("sdr.maximo_de_respostas", "99"), ("sdr.espera_segundos", "999"),
        ("sdr.modelo_leve", "Haiku!"),
    ])
    def test_valor_invalido(self, api, campo, valor):
        assert api.put("/api/configuracoes/integracoes/sdr_respostas", json={"valores": {campo: valor}}).status_code == 422

    def test_salvar_e_ler(self, api, fabrica):
        r = api.put("/api/configuracoes/integracoes/sdr_respostas",
                    json={"valores": {"sdr.modo": "Supervisionado", "sdr.teto_por_conversa": "0,30"}})
        assert r.status_code == 200
        from crm.agente.roteador_do_sdr import ler_configuracao_das_respostas
        cfg = ler_configuracao_das_respostas()
        assert cfg.supervisionado and cfg.teto_por_conversa == Decimal("0.30")
        assert api.get("/api/sdr/respostas").json() == {"modo": "Supervisionado"}

    def test_a_falha_vem_com_a_hora(self):
        from crm.api.respostas_do_sdr import EstadoDasRespostas

        estado = EstadoDasRespostas()
        assert estado.erro() is None
        estado.registrar(respostas.Rodada(erros=["A IA não respondeu"]))
        assert re.fullmatch(r"A IA não respondeu \(\d\d/\d\d às \d\d:\d\d\)", estado.erro())

    def test_transbordo_devolvido_continua_contando(self, fabrica):
        lead_escreve(fabrica, "Quero falar com uma pessoa")
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=Envio())
        with fabrica() as s:
            c = s.scalars(sa.select(ConversaDoSdr)).one()
            respostas.devolver_para_a_ia(s, c, AGORA)
            s.commit()
            frase = respostas.situacao_das_respostas(s, AGORA, ConfiguracaoDasRespostas(modo="Automático"))
        assert "1 passada para a equipe" in frase

    def test_situacao_com_numeros(self, fabrica):
        lead_escreve(fabrica, "Oi", quando=AGORA - timedelta(minutes=3))
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=Envio(), momento=AGORA - timedelta(minutes=2))
        lead_escreve(fabrica, "Quero falar com uma pessoa", quando=AGORA - timedelta(minutes=1))
        rodar(fabrica, ModeloFalso(decisao()), modo="Automático", envio=Envio())
        with fabrica() as s:
            frase = respostas.situacao_das_respostas(s, AGORA, ConfiguracaoDasRespostas(modo="Automático"), "caiu")
        assert frase == ("Modo automático: a IA envia sozinha. Últimos 30 dias: 1 conversa · respostas da IA: 1 no "
                         "modelo leve, 0 no principal, 1 pela regra, 0 barradas pela trava · 1 passada para a equipe · "
                         "custo US$ 0,002 (US$ 0,002 por conversa). ⚠ Última falha: caiu")


class TestPainel:
    def test_rascunho_nao_conta_como_primeira_resposta(self):
        from crm.domain.sdr import _saiu_da_ia

        ia = AutorDaMensagem.IA
        assert _saiu_da_ia(NS(autor=ia, entrega="enviada")) and _saiu_da_ia(NS(autor=ia, entrega=None))
        assert not any(_saiu_da_ia(NS(autor=ia, entrega=e)) for e in ("rascunho", "descartada", "bloqueada"))
        assert not _saiu_da_ia(NS(autor=AutorDaMensagem.LEAD, entrega=None))
