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

from crm.agente.config import LINK_DO_QUESTIONARIO_PADRAO
from crm.domain.abordagem import fala_de_preco
from crm.domain.base_de_conhecimento import FichaLida, vale_para_a_ia

__all__ = [
    "BETA_FALLBACK",
    "MARCA_DO_LINK",
    "CENARIOS",
    "Pergunta",
    "Resultado",
    "ler_prompt",
    "ler_perguntas",
    "montar_contexto",
    "alertas",
    "rodar",
    "rodar_roteador",
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


MARCA_DO_LINK = "{link_do_questionario}"
"""Onde o prompt do roteiro SPIN põe o link do questionário; o endereço vem da configuração."""


def montar_contexto(
    prompt: str, fichas: Iterable[FichaDoEnsaio], hoje: date, link_do_questionario: str = LINK_DO_QUESTIONARIO_PADRAO,
) -> tuple[str, list[str]]:
    """O texto de sistema do ensaio e os códigos das fichas usadas. Só entra ficha que vale para a
    IA (aprovada, dentro da validade e fora do bloco Referências). A marca do link do questionário
    vira o endereço configurado."""
    prompt = prompt.replace(MARCA_DO_LINK, link_do_questionario)
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
    roteador: bool = False
    """Ensaio pelo roteador de custo (fase 1, 23/10/2026): cada resposta traz a rota e o custo."""


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


def rodar_roteador(
    clientes: Any,
    sistema: str,
    fichas: list[str],
    perguntas: Sequence[Pergunta],
    link_do_questionario: str = LINK_DO_QUESTIONARIO_PADRAO,
    cenarios: dict[str, Sequence[str]] = CENARIOS,
    paralelo: int = 4,
) -> Resultado:
    """O ensaio pelo mesmo roteador do agente (`crm.agente.roteador_do_sdr.decidir`): regras, modelo leve,
    principal e travas. Como no WhatsApp, a conversa para quando passa para a equipe."""
    from crm.agente.roteador_do_sdr import IAFora, Pedido, cabecalho_do_lead, decidir, formatar_conversa
    from crm.domain.listas import DestinoDoTransbordo

    cabecalho = cabecalho_do_lead(None, None, "Tráfego pago", "Não enviado")
    resultado = Resultado(modelo=f"{clientes.modelo_leve} → {clientes.modelo_principal}", fichas=fichas, roteador=True)

    def turno(falas: list[tuple[str, str, str]], pendente: str, primeira: bool) -> dict[str, Any]:
        pedido = Pedido(sistema=sistema, conversa=formatar_conversa(cabecalho, falas), pendente=pendente,
                        primeira=primeira, links_permitidos=(link_do_questionario,),
                        destino_do_servico=DestinoDoTransbordo.COMERCIAL_C1)
        try:
            r = decidir(pedido, clientes)
        except IAFora as falha:
            return {"ia": f"(a IA não respondeu: {falha})", "rota": "falha", "custo_usd": None, "passagem": None,
                    "alertas": ["a IA não respondeu"]}
        achados = alertas(r.texto or "")
        if r.bloqueada:
            achados.append(f"trava barrou: {r.motivo_do_bloqueio} — texto do modelo: {r.bloqueada}")
        return {"ia": r.texto or "(nada sai)", "rota": r.rota, "modelo": r.modelo,
                "custo_usd": str(r.custo_usd) if r.custo_usd is not None else None,
                "passagem": r.passagem.tela if r.passagem else None, "alertas": achados}

    def isolada(p: Pergunta) -> dict[str, Any]:
        return {"id": p.id, "lead": p.lead, "esperado": p.esperado, "armadilha": p.armadilha,
                **turno([("—", "Lead", p.lead)], p.lead, True)}

    def conversa(nome: str) -> tuple[str, list[dict[str, Any]]]:
        falas: list[tuple[str, str, str]] = []
        turnos, primeira = [], True
        for fala in cenarios[nome]:
            falas.append(("—", "Lead", fala))
            t = turno(list(falas), fala, primeira)
            turnos.append({"lead": fala, **t})
            if t["passagem"] or t["rota"] == "falha":
                break  # com a equipe, a IA não responde mais
            falas.append(("—", "Critério (IA)", t["ia"]))
            primeira = primeira and "assistente virtual" not in t["ia"].casefold()
        return nome, turnos

    if perguntas:  # aquece o cache antes das chamadas em paralelo
        resultado.perguntas.append(isolada(perguntas[0]))
    with ThreadPoolExecutor(max(1, paralelo)) as executor:
        resultado.perguntas.extend(executor.map(isolada, perguntas[1:]))
        resultado.cenarios = dict(executor.map(conversa, cenarios))
    return resultado


def _resumo_do_roteador(r: Resultado) -> list[str]:
    from decimal import Decimal

    respostas = [*r.perguntas, *(t for ts in r.cenarios.values() for t in ts)]
    rotas: dict[str, int] = {}
    for t in respostas:
        rotas[t["rota"]] = rotas.get(t["rota"], 0) + 1
    custos = [Decimal(t["custo_usd"]) for t in respostas if t.get("custo_usd")]
    sem_preco = sum(1 for t in respostas if t["rota"] in ("leve", "principal") and not t.get("custo_usd"))
    por_conversa = [sum((Decimal(t["custo_usd"]) for t in ts if t.get("custo_usd")), Decimal(0))
                    for ts in r.cenarios.values()]
    linhas = [
        "Rotas: " + " · ".join(f"{k} {v}" for k, v in sorted(rotas.items())) +
        f" · passadas para a equipe: {sum(1 for t in respostas if t['passagem'])}"
        f" · barradas pela trava: {sum(1 for t in respostas if any(a.startswith('trava barrou') for a in t['alertas']))}",
        f"Custo estimado: US$ {sum(custos, Decimal(0)):.4f} em {len(respostas)} respostas"
        + (f" · média por conversa SPIN: US$ {sum(por_conversa, Decimal(0)) / len(por_conversa):.4f}" if por_conversa else "")
        + (f" · {sem_preco} respostas sem preço na tabela (custo incompleto)" if sem_preco else ""),
        "",
    ]
    return linhas


def _rota(t: dict[str, Any]) -> str:
    if "rota" not in t:
        return ""
    partes = [t["rota"]] + ([f"US$ {t['custo_usd']}"] if t.get("custo_usd") else []) + (
        [f"para a equipe: {t['passagem']}"] if t.get("passagem") else [])
    return f" _({' · '.join(partes)})_"


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
        *(_resumo_do_roteador(r) if r.roteador else []),
        "## Perguntas", "",
    ]
    for p in r.perguntas:
        marca = " · armadilha" if p["armadilha"] else ""
        linhas += [f"**{p['id']}**{marca} — {p['lead']}", "", f"- Esperado: {p['esperado']}",
                   f"- IA: {p['ia']}{_rota(p)}"]
        linhas += [f"- ⚠ {a}" for a in p["alertas"]]
        linhas.append("")
    linhas += ["## Conversas", ""]
    for nome, turnos in r.cenarios.items():
        linhas += [f"### {nome}", ""]
        for i, t in enumerate(turnos, 1):
            linhas += [f"{i}. Lead: {t['lead']}", f"   IA: {t['ia']}{_rota(t)}"]
            linhas += [f"   ⚠ {a}" for a in t["alertas"]]
        linhas.append("")
    return "\n".join(linhas)
