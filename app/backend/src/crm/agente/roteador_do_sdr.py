"""O roteador de custo do SDR de IA no WhatsApp — fase 1 (amostra aprovada por Eduardo em 23/10/2026).

Decide a resposta a uma mensagem do lead, sem tocar no banco (quem grava e envia é
`crm.agente.respostas_do_sdr`). O ensaio usa esta mesma decisão. A ordem é sempre esta:

1. **Regras, sem IA.** Pedido de pessoa (T1), urgência com prazo legal (T9) e "já sou cliente" (T11) vão
   direto para a equipe, com a frase aprovada do gatilho.
2. **Modelo leve** (Claude Haiku 4.5 por padrão) nas perguntas do roteiro. Ele escolhe: responder, passar
   para a equipe (com o gatilho), marcar a reunião ou chamar o modelo principal.
3. **Modelo principal** (o da aba IA, com a reserva atrás) só quando o leve não basta. Ele não tem a
   saída "chamar o principal": responde ou passa para a equipe.
4. **Travas do servidor** no texto antes de sair: preço, termo proibido, dado sensível, link que não é o
   do questionário, tamanho. Barrou, a mensagem não sai: a conversa vai para a equipe com a frase do T5.

**Dúvida técnica nunca é respondida por modelo nenhum** (decisão de Eduardo): é o gatilho T4, e a frase
de passagem é sempre a aprovada, nunca texto do modelo. Confiança declarada pelo modelo não decide nada:
a escalada é por escolha do modelo entre saídas fechadas e pela conferência do servidor.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from crm.agente.prompt_do_sdr import instrucoes_do_roteador
from crm.agente.sdr import AgenteFalhou, AgenteRecusou, Uso
from crm.domain import sdr as regras
from crm.domain.listas import DestinoDoTransbordo as D
from crm.domain.listas import MotivoDeTransbordo as M

__all__ = [
    "APRESENTACAO", "BETA_FALLBACK", "Clientes", "ConfiguracaoDasRespostas", "Gatilho", "GATILHOS", "IAFora",
    "MODOS", "Passagem", "Pedido", "Resposta", "decidir", "gatilho_por_regra", "ler_configuracao_das_respostas",
    "passagem_do_servidor", "problema_na_resposta", "formatar_conversa", "cabecalho_do_lead",
]

BETA_FALLBACK = "server-side-fallback-2026-07-01"
MAX_TOKENS = 1024
LIMITE_DA_RESPOSTA = 1200
"""Mensagem de SDR é curta. Mais que isso é o modelo se perdendo, e não sai."""

APRESENTACAO = "Olá! Sou a assistente virtual da Critério Consultores."
"""A primeira mensagem da IA ao lead sempre se apresenta (`sdr-ia-limites-de-atuacao.md`, seção 2)."""

MODOS = ("Desligado", "Supervisionado", "Automático")


# ------------------------------------------------------------------ configuração
@dataclass(frozen=True)
class ConfiguracaoDasRespostas:
    modo: str = "Desligado"
    modelo_leve: str = "claude-haiku-4-5"
    modelo_leve_openai: str = "gpt-6-luna"
    teto_por_conversa: Decimal = Decimal("0.50")
    maximo_de_respostas: int = 12
    espera: timedelta = timedelta(seconds=20)

    @property
    def ligado(self) -> bool:
        return self.modo in ("Supervisionado", "Automático")

    @property
    def supervisionado(self) -> bool:
        return self.modo == "Supervisionado"


def ler_configuracao_das_respostas() -> ConfiguracaoDasRespostas:
    """A aba Respostas do SDR, em Integrações. Valor estragado volta ao padrão; modo estranho, desligado."""
    from crm import configuracao

    padrao = ConfiguracaoDasRespostas()
    modo = configuracao.valor("sdr.modo")
    try:
        teto = Decimal((configuracao.valor("sdr.teto_por_conversa") or "").replace(",", "."))
        teto = teto if teto.is_finite() and teto > 0 else padrao.teto_por_conversa
    except InvalidOperation:
        teto = padrao.teto_por_conversa

    def inteiro(chave: str, atual: int, minimo: int, maximo: int) -> int:
        texto = (configuracao.valor(chave) or "").strip()
        return int(texto) if texto.isdigit() and minimo <= int(texto) <= maximo else atual

    return ConfiguracaoDasRespostas(
        modo=modo if modo in MODOS else "Desligado",
        modelo_leve=(configuracao.valor("sdr.modelo_leve") or "").strip() or padrao.modelo_leve,
        modelo_leve_openai=(configuracao.valor("sdr.modelo_leve_openai") or "").strip() or padrao.modelo_leve_openai,
        teto_por_conversa=teto,
        maximo_de_respostas=inteiro("sdr.maximo_de_respostas", padrao.maximo_de_respostas, 1, 50),
        espera=timedelta(seconds=inteiro("sdr.espera_segundos", 20, 0, 300)),
    )


# ------------------------------------------------------------------ gatilhos
@dataclass(frozen=True)
class Gatilho:
    codigo: str
    motivo: M
    destino: D | None
    """`None`: o destino do serviço de interesse (BPO → Comercial C1; o resto → Consultoria C2)."""
    frase: str
    """A frase aprovada de `sdr-ia-limites-de-atuacao.md`, seção 4. É ela que sai, nunca texto do modelo."""
    tela: str


GATILHOS: dict[str, Gatilho] = {g.codigo: g for g in (
    Gatilho("T1", M.PEDIU_PESSOA, None, "Claro. Vou passar a conversa para a nossa equipe.",
            "Pediu para falar com uma pessoa"),
    Gatilho("T2", M.PRECO, None, "O valor depende do volume da sua operação. Quem monta a proposta é a nossa "
            "equipe, depois de entender a sua rotina. Vou passar a conversa para eles.", "Insistiu no preço"),
    Gatilho("T3", M.GRUPO_COMPLEXO, D.SOCIOS, "Pelo tamanho da operação, quem conduz é um dos nossos sócios.",
            "Grupo com vários CNPJs ou conta grande"),
    Gatilho("T4", M.DUVIDA_TECNICA, D.TECNICO_FISCAL, "Essa é uma análise que nossos especialistas fazem com os "
            "números da sua empresa. Vou passar a sua pergunta para eles.", "Dúvida técnica do caso do lead"),
    Gatilho("T5", M.DUVIDA_TECNICA, None, "Quero te responder com precisão. Vou confirmar com a equipe.",
            "Sem ficha aprovada para a pergunta"),
    Gatilho("T6", M.LEAD_IRRITADO, None, "Peço desculpas pelo transtorno. Vou passar a conversa para a nossa "
            "equipe.", "Lead irritado"),
    Gatilho("T8", M.SERVICO_SEM_ROTEIRO, D.SOCIOS, "Esse serviço é desenhado caso a caso. Vou passar para quem "
            "conduz.", "Serviço sem roteiro"),
    Gatilho("T9", M.URGENCIA_LEGAL, D.TECNICO_FISCAL, "Pelo prazo, vou passar agora para um especialista.",
            "Urgência com prazo legal"),
    Gatilho("T10", M.OUTRO, D.COMERCIAL_C1, "Vou passar a sua pergunta para a nossa equipe.",
            "Perguntou como a Critério conseguiu o contato"),
    Gatilho("T11", M.OUTRO, D.SUCESSO_DO_CLIENTE, "Vou te encaminhar para a equipe que já cuida da sua empresa.",
            "Já é cliente da Critério"),
    Gatilho("T12", M.OUTRO, D.SOCIOS, "Esse ponto é tratado pela nossa equipe na proposta. Vou passar para eles.",
            "Cláusula de contrato, dados ou tecnologia"),
)}

_REGRAS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("T1", re.compile(
        r"\b(falar|conversar|atendimento)\s+com\s+(um|uma|algum|alguma|o|a)?\s*"
        r"(pessoa|humano|atendente|consultor|consultora|especialista|algu[ée]m)\b"
        r"|\bn[ãa]o\s+quero\s+(falar\s+com\s+)?(rob[ôo]|m[áa]quina|bot|ia)\b"
        r"|\b(quero|prefiro|pode\s+me\s+passar\s+para)\s+(um|uma)\s+(atendente|pessoa|humano)\b", re.I)),
    ("T9", re.compile(
        r"\b(fiscaliza[çc][ãa]o|autua[çc][ãa]o|autuad[oa]s?|auto\s+de\s+infra[çc][ãa]o|intima[çc][ãa]o|intimad[oa]s?"
        r"|execu[çc][ãa]o\s+fiscal|malha\s+fina)\b", re.I)),
    ("T11", re.compile(
        r"\bj[áa]\s+(sou|somos)\s+clientes?\b|\b(sou|somos)\s+clientes?\s+(de\s+voc[êe]s|da\s+crit[ée]rio)\b", re.I)),
)


def gatilho_por_regra(texto: str) -> Gatilho | None:
    """Os gatilhos que o servidor reconhece sozinho, sem gastar IA. Na dúvida, não reconhece: o modelo vê."""
    for codigo, padrao in _REGRAS:
        if padrao.search(texto or ""):
            return GATILHOS[codigo]
    return None


# ------------------------------------------------------------------ travas
_PROIBIDOS = re.compile(
    r"terceiriza[çc][ãa]o\s+de\s+tarefas|\bsoftware\b|custo\s+operacional|\boverhead\b|open\s+balance"
    r"|\bgarantimos\b|\bgarantid[oa]s?\b|sem\s+risco|o\s+mais\s+barat[oa]", re.I)
_SENSIVEIS = re.compile(
    r"\bsenhas?\b|certificado\s+digital|\bextratos?\b|folha\s+nominal|documentos?\s+pessoa(l|is)|\bcpf\b|\brg\b",
    re.I)
_LINK = re.compile(r"(?:https?://|www\.)[^\s<>\"')\]]+", re.I)


def problema_na_resposta(texto: str, links_permitidos: tuple[str, ...]) -> str | None:
    """Por que a resposta da IA não pode sair, ou `None`. Vale para o texto todo, apresentação incluída."""
    problema = regras.problema_na_mensagem(texto)
    if problema:
        return problema
    if len(texto) > LIMITE_DA_RESPOSTA:
        return f"A resposta passou de {LIMITE_DA_RESPOSTA} caracteres"
    if achado := _PROIBIDOS.search(texto):
        return f"Termo proibido pelo tom de voz: “{achado.group(0)}”"
    if achado := _SENSIVEIS.search(texto):
        return f"Fala de dado sensível (P10): “{achado.group(0)}”"
    permitidos = {l.rstrip("/").casefold() for l in links_permitidos if l}
    for link in _LINK.findall(texto):
        if link.rstrip(".,;:!?").rstrip("/").casefold() not in permitidos:
            return "Link que não é o do questionário"
    return None


# ------------------------------------------------------------------ a decisão
@dataclass(frozen=True)
class Passagem:
    """A conversa vai para a equipe. Com `motivo`, é transbordo (encerra a conversa, conta no painel);
    sem ele, a equipe só assume (a reunião aceita, o lead que já é oportunidade)."""

    tela: str
    destino: D | None
    motivo: M | None = None


def passagem_do_servidor(tela: str, motivo: M | None = M.OUTRO, destino: D | None = None) -> Passagem:
    return Passagem(tela=tela, destino=destino, motivo=motivo)


@dataclass(frozen=True)
class Clientes:
    """Os dois clientes de IA do roteador (`crm.agente.ia`): o leve e o principal, cada um com a reserva."""

    leve: Any
    modelo_leve: str
    principal: Any
    modelo_principal: str


class IAFora(AgenteFalhou):
    """Nem o leve nem o principal responderam: a conversa vai para a equipe, em silêncio."""


@dataclass(frozen=True)
class Pedido:
    """O que o roteador precisa saber da conversa, já lido do banco."""

    sistema: str
    """O prompt do roteiro com as fichas aprovadas (sem as instruções do roteador)."""
    conversa: str
    """O cabeçalho do lead e as mensagens, já no formato do pedido."""
    pendente: str
    """O que o lead disse depois da última mensagem da Critério."""
    primeira: bool
    """A IA ainda não se apresentou a este lead."""
    links_permitidos: tuple[str, ...]
    destino_do_servico: D


@dataclass
class Resposta:
    rota: str
    """leve, principal ou regra. A trava aparece em `bloqueada`."""
    texto: str | None
    """O que sai para o lead. `None`: nada sai (passagem em silêncio)."""
    passagem: Passagem | None = None
    modelo: str | None = None
    custo_usd: Decimal | None = None
    intencao: str | None = None
    fichas: list[str] = field(default_factory=list)
    bloqueada: str | None = None
    """O texto do modelo que a trava barrou (fica registrado, não sai)."""
    motivo_do_bloqueio: str | None = None
    marcou_reuniao: bool = False


def formatar_conversa(cabecalho: str, falas: list[tuple[str, str, str]]) -> str:
    """O pedido ao modelo: o cabeçalho do lead e as falas (quando, quem, texto) entre <conversa>. O agente e
    o ensaio usam o mesmo formato."""
    linhas = [cabecalho, "", "<conversa>", *(f"[{quando}] {quem}: {texto[:1500]}" for quando, quem, texto in falas),
              "</conversa>"]
    return "\n".join(linhas)


def cabecalho_do_lead(servico: str | None, tema: str | None, origem: str | None, questionario: str) -> str:
    """Sem nome, telefone nem e-mail: a IA não precisa deles."""
    texto = servico or "não informado"
    if tema:
        texto += f" (tema: {tema})"
    return (f"Serviço de interesse no CRM: {texto} · origem: {origem or 'não informada'} · "
            f"questionário de volumetria: {questionario}")


def _esquema(com_principal: bool) -> dict[str, Any]:
    acoes = ["responder", "passar_para_equipe", "marcar_reuniao"] + (["chamar_modelo_principal"] if com_principal else [])
    return {
        "type": "object", "additionalProperties": False,
        "required": ["acao", "gatilho", "texto", "fichas_usadas", "intencao"],
        "properties": {
            "acao": {"type": "string", "enum": acoes},
            "gatilho": {"type": "string", "enum": ["nenhum", *GATILHOS]},
            "texto": {"type": "string"},
            "fichas_usadas": {"type": "array", "items": {"type": "string"}},
            "intencao": {"type": "string"},
        },
    }


def _chamar(cliente: Any, modelo: str, sistema: str, conversa: str, com_principal: bool, uso: Uso) -> dict[str, Any]:
    system = [
        {"type": "text", "text": sistema, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": instrucoes_do_roteador(com_principal)},
    ]
    resposta = cliente.beta.messages.create(
        model=modelo, max_tokens=MAX_TOKENS, system=system, messages=[{"role": "user", "content": conversa}],
        output_config={"format": {"type": "json_schema", "schema": _esquema(com_principal)}},
        betas=[BETA_FALLBACK], fallbacks="default",
    )
    uso.somar(resposta.usage)
    if resposta.stop_reason == "refusal":
        raise AgenteRecusou("O modelo recusou responder.")
    texto = next((b.text for b in resposta.content if getattr(b, "type", None) == "text"), "")
    try:
        dados = json.loads(texto)
    except (TypeError, ValueError) as falha:
        raise AgenteFalhou("O modelo não devolveu a decisão no formato pedido.") from falha
    if not isinstance(dados, dict) or dados.get("acao") not in _esquema(com_principal)["properties"]["acao"]["enum"]:
        raise AgenteFalhou("O modelo devolveu uma ação que não existe.")
    return dados


def _com_apresentacao(texto: str, pedido: Pedido) -> str:
    if pedido.primeira and "assistente virtual" not in texto.casefold():
        return f"{APRESENTACAO} {texto}".strip()
    return texto


def _passagem(gatilho: Gatilho, pedido: Pedido) -> Passagem:
    return Passagem(tela=gatilho.tela, destino=gatilho.destino or pedido.destino_do_servico, motivo=gatilho.motivo)


def decidir(pedido: Pedido, clientes: Clientes) -> Resposta:
    """A resposta à mensagem pendente do lead. Levanta `IAFora` se nenhum modelo respondeu."""
    regra = gatilho_por_regra(pedido.pendente)
    if regra is not None:
        return Resposta(rota="regra", texto=_com_apresentacao(regra.frase, pedido), passagem=_passagem(regra, pedido),
                        intencao=regra.tela)

    uso = Uso(clientes.modelo_leve)
    rota, modelo = "leve", clientes.modelo_leve
    try:
        dados = _chamar(clientes.leve, clientes.modelo_leve, pedido.sistema, pedido.conversa, True, uso)
    except Exception:  # noqa: BLE001 — o leve falhou ou recusou: o principal tenta
        dados = {"acao": "chamar_modelo_principal"}
    if dados["acao"] == "chamar_modelo_principal":
        rota, modelo = "principal", clientes.modelo_principal
        uso.modelo = modelo
        try:
            dados = _chamar(clientes.principal, clientes.modelo_principal, pedido.sistema, pedido.conversa, False, uso)
        except Exception as falha:  # noqa: BLE001
            raise IAFora(f"A IA não respondeu ({type(falha).__name__}).") from falha

    base = dict(rota=rota, modelo=uso.modelo, custo_usd=uso.custo_usd,
                intencao=(str(dados.get("intencao") or "").strip()[:120] or None),
                fichas=[str(f)[:20] for f in dados.get("fichas_usadas") or []][:20])

    if dados["acao"] == "passar_para_equipe":
        gatilho = GATILHOS.get(str(dados.get("gatilho"))) or GATILHOS["T5"]
        return Resposta(texto=_com_apresentacao(gatilho.frase, pedido), passagem=_passagem(gatilho, pedido), **base)

    texto = _com_apresentacao(str(dados.get("texto") or "").strip(), pedido)
    problema = problema_na_resposta(texto, pedido.links_permitidos)
    if problema:
        t5 = GATILHOS["T5"]
        return Resposta(texto=_com_apresentacao(t5.frase, pedido), bloqueada=texto, motivo_do_bloqueio=problema,
                        passagem=Passagem(tela="A trava barrou a resposta da IA",
                                          destino=pedido.destino_do_servico, motivo=M.OUTRO), **base)
    if dados["acao"] == "marcar_reuniao":
        return Resposta(texto=texto, marcou_reuniao=True,
                        passagem=Passagem(tela="Aceitou a conversa com a equipe: marcar a reunião",
                                          destino=pedido.destino_do_servico), **base)
    return Resposta(texto=texto, **base)
