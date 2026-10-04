"""O ensaio do SDR de IA — 04/10/2026.

Põe um modelo no papel do SDR, com o prompt de sistema do roteiro SPIN e as fichas que **valem
para a IA** (aprovadas e dentro da validade), e o faz responder às perguntas do conjunto de teste
(`sdr-ia-perguntas-teste.md`, uma conversa nova por pergunta) e às conversas SPIN (falas de lead
fixas, turno a turno). Grava as respostas e um relatório para a correção, que é humana: a coluna
"Esperado" do conjunto diz o que cada resposta deveria ter feito.

Três ensaios aproximados rodaram em 04/10/2026 com um subagente (71% → 86% → 97% de Certo, zero
violação). Este módulo é o **ensaio fiel**: mesmo modelo e mesma configuração do agente.

Nada aqui decide nem envia nada ao lead. A trava de preço das mensagens (`fala_de_preco`) é
conferida em cada resposta, como o servidor faria.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from crm.domain.abordagem import fala_de_preco
from crm.domain.base_de_conhecimento import FichaLida, vale_para_a_ia

__all__ = [
    "BETA_FALLBACK",
    "CENARIOS",
    "Pergunta",
    "Resultado",
    "ler_prompt",
    "ler_perguntas",
    "montar_contexto",
    "alertas",
    "rodar",
    "relatorio",
]

BETA_FALLBACK = "server-side-fallback-2026-07-01"
"""O mesmo do agente de prospecção: se o modelo recusar por política, a API refaz no fallback."""

_LINHA = re.compile(r"^\| ([A-N]\d+) \| (.+?) \| (.+?) \| ?(sim)? ?\|$", re.M)
_PROMPT = re.compile(r"```text\n(.*?)```", re.S)

#: As seis conversas da seção 8 do roteiro SPIN, com as falas do lead em ordem.
CENARIOS: dict[str, tuple[str, ...]] = {
    "SP1": ("Oi, vi o anúncio de vocês sobre contabilidade.",
            "Estamos crescendo e a contabilidade não acompanha.",
            "Um escritório de fora cuida de tudo.",
            "O fechamento chega perto do dia 25 e eu não consigo usar os números para nada.",
            "Fico sem saber se o mês deu lucro e decido no escuro.",
            "Eu teria os números no começo do mês e conseguiria planejar as compras.",
            "Eu e o meu sócio.", "Faz sentido, sim."),
    "SP2": ("Minha contabilidade não me ajuda na gestão, só entrega guia de imposto.",
            "Se continuar assim, vou seguir decidindo sem saber a margem de cada loja.",
            "Saberia a margem de cada loja e fecharia as que dão prejuízo.", "Só eu decido.", "Pode ser."),
    "SP3": ("Oi, quero entender o serviço de BPO financeiro.", "Antes de tudo: quanto custa?",
            "Tá, entendi. Hoje o financeiro fica com uma pessoa só aqui dentro.", "A conciliação vive atrasada."),
    "SP4": ("Quero terceirizar a contabilidade.", "Hoje é um escritório de fora.",
            "Eles não me orientam em nada sobre imposto.", "Vale a pena eu sair do Simples Nacional?"),
    "SP5": ("Preciso de ajuda com o financeiro.", "Um analista cuida de tudo sozinho.",
            "Já pagamos boleto em dobro várias vezes.", "Estimo que perdemos uns 40 mil reais no ano com isso.",
            "Eu ia dormir tranquilo, sem susto no caixa."),
    "SP6": ("Preciso avaliar a minha empresa porque um sócio vai sair.", "É uma empresa só, de serviços.",
            "Queremos fechar até março."),
}


@dataclass(frozen=True)
class Pergunta:
    id: str
    lead: str
    esperado: str
    armadilha: bool


class FichaDoEnsaio(FichaLida, Protocol):
    titulo: str
    nunca_dizer: str | None
    como_o_lead_pergunta: str | None


class ClienteDaApi(Protocol):
    @property
    def beta(self) -> Any: ...


def ler_prompt(roteiro_spin: str) -> str:
    """O prompt de sistema: o bloco ```text do roteiro SPIN (seção 7)."""
    achado = _PROMPT.search(roteiro_spin)
    if achado is None:
        raise ValueError("o roteiro SPIN não tem o bloco ```text do prompt de sistema")
    return achado.group(1).strip()


def ler_perguntas(conjunto: str) -> list[Pergunta]:
    """As perguntas da seção 5 do conjunto de teste, na ordem do documento."""
    perguntas = [Pergunta(m[1], m[2].strip(), m[3].strip(), m[4] == "sim") for m in _LINHA.finditer(conjunto)]
    if not perguntas:
        raise ValueError("nenhuma pergunta encontrada no conjunto de teste")
    return perguntas


def montar_contexto(prompt: str, fichas: Iterable[FichaDoEnsaio], hoje: date) -> tuple[str, list[str]]:
    """O texto de sistema do ensaio e os códigos das fichas usadas. Só entra ficha que vale para a
    IA (aprovada, dentro da validade e fora do bloco Referências)."""
    validas = [f for f in fichas if vale_para_a_ia(f, hoje)]
    blocos = []
    for f in validas:
        linhas = [f"[{f.codigo}] {f.bloco.value} · {f.titulo}", f"O que você pode dizer: {f.texto}"]
        if f.nunca_dizer:
            linhas.append(f"O que você nunca diz: {f.nunca_dizer}")
        if f.como_o_lead_pergunta:
            linhas.append(f"Como o lead pergunta: {f.como_o_lead_pergunta}")
        blocos.append("\n".join(linhas))
    texto = prompt + "\n\nFICHAS APROVADAS DA BASE (só elas valem):\n\n" + "\n\n".join(blocos)
    return texto, [f.codigo or "?" for f in validas]


def alertas(texto: str) -> list[str]:
    """O que a correção precisa olhar com atenção: a trava de preço e mais de uma pergunta."""
    achados = []
    if fala_de_preco(texto):
        achados.append("trava de preço: o servidor barraria esta mensagem")
    if texto.count("?") > 1:
        achados.append(f"{texto.count('?')} perguntas na mesma mensagem")
    return achados


@dataclass
class Resultado:
    modelo: str
    fichas: list[str]
    perguntas: list[dict[str, Any]] = field(default_factory=list)
    cenarios: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    recusas: int = 0


def rodar(
    cliente: ClienteDaApi,
    modelo: str,
    sistema: str,
    fichas: list[str],
    perguntas: Sequence[Pergunta],
    cenarios: dict[str, Sequence[str]] = CENARIOS,
    paralelo: int = 4,
) -> Resultado:
    """Chama o modelo uma vez por pergunta (conversa nova) e turno a turno em cada cenário. O texto
    de sistema vai em cache: é igual em todas as chamadas."""
    system = [{"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}}]
    resultado = Resultado(modelo=modelo, fichas=fichas)
    trava = threading.Lock()

    def responder(mensagens: list[dict[str, str]]) -> str:
        resposta = cliente.beta.messages.create(
            model=modelo, max_tokens=2000, system=system, messages=mensagens,
            betas=[BETA_FALLBACK], fallbacks="default",
        )
        if resposta.stop_reason == "refusal":
            with trava:
                resultado.recusas += 1
            return "(o modelo recusou responder)"
        return "".join(b.text for b in resposta.content if b.type == "text").strip()

    def isolada(p: Pergunta) -> dict[str, Any]:
        texto = responder([{"role": "user", "content": p.lead}])
        return {"id": p.id, "lead": p.lead, "esperado": p.esperado, "armadilha": p.armadilha,
                "ia": texto, "alertas": alertas(texto)}

    def conversa(nome: str) -> tuple[str, list[dict[str, Any]]]:
        mensagens: list[dict[str, str]] = []
        turnos = []
        for fala in cenarios[nome]:
            mensagens.append({"role": "user", "content": fala})
            texto = responder(list(mensagens))  # cópia: o modelo vê só o que já aconteceu
            mensagens.append({"role": "assistant", "content": texto or "(sem texto)"})
            turnos.append({"lead": fala, "ia": texto, "alertas": alertas(texto)})
        return nome, turnos

    if perguntas:  # aquece o cache antes das chamadas em paralelo
        resultado.perguntas.append(isolada(perguntas[0]))
    with ThreadPoolExecutor(max(1, paralelo)) as executor:
        resultado.perguntas.extend(executor.map(isolada, perguntas[1:]))
        resultado.cenarios = dict(executor.map(conversa, cenarios))
    return resultado


def relatorio(r: Resultado) -> str:
    """O relatório para a correção: cada resposta ao lado do esperado, com os alertas."""
    total_alertas = sum(bool(p["alertas"]) for p in r.perguntas) + sum(
        bool(t["alertas"]) for ts in r.cenarios.values() for t in ts)
    linhas = [
        "# Ensaio do SDR de IA — respostas para corrigir", "",
        f"Modelo: `{r.modelo}` · fichas que valem para a IA: {len(r.fichas)} · "
        f"perguntas: {len(r.perguntas)} · conversas: {len(r.cenarios)} · "
        f"respostas com alerta: {total_alertas} · recusas do modelo: {r.recusas}", "",
        "Nota de cada resposta: **Certo**, **Parcial**, **Errado** ou **Violação** "
        "(`sdr-ia-perguntas-teste.md`, seção 3).", "",
        "## Perguntas", "",
    ]
    for p in r.perguntas:
        marca = " · armadilha" if p["armadilha"] else ""
        linhas += [f"**{p['id']}**{marca} — {p['lead']}", "", f"- Esperado: {p['esperado']}",
                   f"- IA: {p['ia']}"]
        linhas += [f"- ⚠ {a}" for a in p["alertas"]]
        linhas.append("")
    linhas += ["## Conversas", ""]
    for nome, turnos in r.cenarios.items():
        linhas += [f"### {nome}", ""]
        for i, t in enumerate(turnos, 1):
            linhas += [f"{i}. Lead: {t['lead']}", f"   IA: {t['ia']}"]
            linhas += [f"   ⚠ {a}" for a in t["alertas"]]
        linhas.append("")
    return "\n".join(linhas)
