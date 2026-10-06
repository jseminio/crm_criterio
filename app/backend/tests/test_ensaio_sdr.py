"""O ensaio do SDR de IA (04/10/2026): leitura dos documentos, contexto, alertas e a rodada, sem rede."""

from __future__ import annotations

import sys
import threading
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from crm.agente import ensaio_sdr as ensaio
from crm.domain.base_de_conhecimento import BlocoDaBase as B, SituacaoDaFicha as S

REPO = Path(__file__).resolve().parents[3]
HOJE = date(2026, 10, 4)


def ficha(codigo, bloco=B.REGRAS, situacao=S.APROVADA, validade=HOJE + timedelta(days=30), **campos):
    padrao = dict(codigo=codigo, bloco=bloco, situacao=situacao, validade=validade, titulo=f"Título {codigo}",
                  texto=f"Texto {codigo}.", fonte="doc", dono="Eduardo", nunca_dizer=None, como_o_lead_pergunta=None)
    return NS(**(padrao | campos))


class TestDocumentos:
    def test_le_as_96_perguntas_e_53_armadilhas_do_conjunto(self):
        perguntas = ensaio.ler_perguntas((REPO / "sdr-ia-perguntas-teste.md").read_text())
        assert len(perguntas) == 96 and sum(p.armadilha for p in perguntas) == 53
        assert (perguntas[0].id, perguntas[-1].id) == ("A1", "N4")
        assert perguntas[0].lead == "Oi, vi o anúncio de vocês. Como funciona?"

    def test_le_o_prompt_do_roteiro_spin(self):
        prompt = ensaio.ler_prompt((REPO / "sdr-ia-roteiro-spin.md").read_text())
        assert prompt.startswith("Você é a assistente virtual da Critério")
        assert "Nunca escreva as palavras preço, desconto" in prompt
        # Ajustes do ensaio fiel de 06/10/2026: a IA esquecia de se apresentar e repetia a abertura.
        assert "A primeira frase da sua primeira mensagem é sempre a apresentação" in prompt
        assert "Faça essa\npergunta uma vez só" in prompt
        # Decisão de 06/10/2026: a IA envia o link do questionário; o endereço vem da configuração.
        assert ensaio.MARCA_DO_LINK in prompt and "netlify" not in prompt
        # Decisão de 06/10/2026: agradecer ou lembrar pelo que o CRM diz, uma vez cada.
        assert "Se o questionário foi respondido é o CRM que diz" in prompt
        assert "O lembrete sai uma vez só." in prompt

    def test_documento_sem_prompt_ou_sem_perguntas_avisa(self):
        with pytest.raises(ValueError, match="prompt"):
            ensaio.ler_prompt("sem bloco")
        with pytest.raises(ValueError, match="pergunta"):
            ensaio.ler_perguntas("sem tabela")


class TestContexto:
    def test_so_entra_ficha_que_vale_para_a_ia(self):
        fichas = [
            ficha("P1", nunca_dizer="Faixa de valor.", como_o_lead_pergunta='"Quanto custa?"'),
            ficha("P2", validade=HOJE - timedelta(days=1)),          # vencida
            ficha("R1", bloco=B.REFERENCIAS),                        # referência
            ficha("O9", bloco=B.OBJECOES, situacao=S.RASCUNHO),      # não aprovada
        ]
        texto, codigos = ensaio.montar_contexto("PROMPT", fichas, HOJE)
        assert codigos == ["P1"]
        assert texto.startswith("PROMPT\n\nFICHAS APROVADAS DA BASE")
        assert "[P1] Regras de atuação · Título P1" in texto
        assert "O que você nunca diz: Faixa de valor." in texto and 'Como o lead pergunta: "Quanto custa?"' in texto
        assert "P2" not in texto and "R1" not in texto and "O9" not in texto

    def test_a_marca_do_link_vira_o_endereco_configurado(self):
        prompt = f"Envie o questionário: {ensaio.MARCA_DO_LINK}"
        padrao, _ = ensaio.montar_contexto(prompt, [], HOJE)
        assert "https://criterio-questionario-proposta.netlify.app/questionario" in padrao
        proprio, _ = ensaio.montar_contexto(prompt, [], HOJE, "https://questionario.criterio.com.br")
        assert "https://questionario.criterio.com.br" in proprio and ensaio.MARCA_DO_LINK not in proprio

    def test_alertas_da_trava_e_de_varias_perguntas(self):
        assert ensaio.alertas("Posso marcar uma conversa?") == []
        assert ensaio.alertas("Não trato de desconto por aqui.") == ["trava de preço: o servidor barraria esta mensagem"]
        assert ensaio.alertas("Quem cuida? E quando?") == ["2 perguntas na mesma mensagem"]


class ClienteFalso:
    """Responde "resposta N" e guarda cada pedido. A pergunta "recuse" simula uma recusa."""

    def __init__(self):
        self.pedidos: list[dict] = []
        self._trava = threading.Lock()
        self.beta = NS(messages=NS(create=self._criar))

    def _criar(self, **pedido):
        with self._trava:
            self.pedidos.append(pedido)
            n = len(self.pedidos)
        if pedido["messages"][-1]["content"] == "recuse":
            return NS(stop_reason="refusal", content=[])
        return NS(stop_reason="end_turn", content=[NS(type="thinking"), NS(type="text", text=f"resposta {n}")])


def perguntas(*leads):
    return [ensaio.Pergunta(f"X{i}", lead, "R · P1", i % 2 == 0) for i, lead in enumerate(leads, 1)]


class TestRodada:
    def test_uma_chamada_por_pergunta_e_turno_a_turno_nas_conversas(self):
        cliente = ClienteFalso()
        r = ensaio.rodar(cliente, "modelo-x", "SISTEMA", ["P1"], perguntas("Oi", "Quanto custa?", "Tchau"),
                         cenarios={"SP": ("fala 1", "fala 2", "fala 3")}, paralelo=2)
        assert len(cliente.pedidos) == 3 + 3
        assert [p["lead"] for p in r.perguntas] == ["Oi", "Quanto custa?", "Tchau"]
        conversa = [p for p in cliente.pedidos if p["messages"][0]["content"] == "fala 1"]
        assert [len(p["messages"]) for p in conversa] == [1, 3, 5]  # nunca vê a fala seguinte
        assert conversa[-1]["messages"][-1] == {"role": "user", "content": "fala 3"}
        assert [t["lead"] for t in r.cenarios["SP"]] == ["fala 1", "fala 2", "fala 3"]

    def test_mesma_configuracao_do_agente_e_sistema_em_cache(self):
        cliente = ClienteFalso()
        ensaio.rodar(cliente, "modelo-x", "SISTEMA", [], perguntas("Oi"), cenarios={})
        (pedido,) = cliente.pedidos
        assert pedido["model"] == "modelo-x" and pedido["fallbacks"] == "default"
        assert pedido["betas"] == [ensaio.BETA_FALLBACK]
        assert pedido["system"] == [{"type": "text", "text": "SISTEMA", "cache_control": {"type": "ephemeral"}}]

    def test_recusa_conta_e_fica_marcada(self):
        r = ensaio.rodar(ClienteFalso(), "m", "S", [], perguntas("Oi", "recuse"), cenarios={})
        assert r.recusas == 1 and r.perguntas[1]["ia"] == "(o modelo recusou responder)"

    def test_relatorio_mostra_esperado_resposta_e_alertas(self):
        r = ensaio.Resultado(modelo="m", fichas=["P1"], perguntas=[
            {"id": "D4", "lead": "Tem desconto?", "esperado": "R · P1", "armadilha": True,
             "ia": "Não trato de desconto.", "alertas": ["trava de preço: o servidor barraria esta mensagem"]}],
            cenarios={"SP1": [{"lead": "Oi", "ia": "Olá!", "alertas": []}]})
        texto = ensaio.relatorio(r)
        assert "**D4** · armadilha — Tem desconto?" in texto
        assert "- Esperado: R · P1" in texto and "- IA: Não trato de desconto." in texto
        assert "- ⚠ trava de preço" in texto and "respostas com alerta: 1" in texto
        assert "### SP1" in texto and "1. Lead: Oi" in texto


class TestScript:
    @pytest.fixture
    def script(self):
        sys.path.insert(0, str(REPO / "app" / "backend" / "scripts"))
        import ensaio_sdr as modulo
        return modulo

    def test_recusa_pasta_dentro_do_repositorio(self, script, capsys):
        assert script.main([str(REPO / "saida")]) == 2
        assert "fora do repositório" in capsys.readouterr().err

    def test_sem_chave_nao_chama_nada(self, script, monkeypatch, tmp_path, capsys):
        monkeypatch.setattr(script, "ler_configuracao", lambda: NS(chave=None, modelo="m"))
        assert script.main([str(tmp_path / "saida")]) == 2
        assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
        assert not (tmp_path / "saida").exists()
