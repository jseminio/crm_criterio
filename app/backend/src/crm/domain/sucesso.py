"""Funil do Sucesso do Cliente (aprovado por Eduardo em 02/10/2026).

O caminho de cada grupo cliente, tirado do fluxograma "Macroprocesso — Comercial & Sucesso do
Cliente": **Contrato** (Comercial & Cliente) → **Handover** (Comercial) → **Kickoff** (Gestor &
Cliente) → **Em curso**, quando as reuniões de resultado passam a ter cadência pela classe do Score.

- Cada etapa da implantação tem um checklist com os itens do fluxograma; a etapa só se conclui com
  todos marcados.
- Em curso, uma reunião de resultado por classe (Eduardo, 03/10/2026): A mensal, B trimestral, C
  semestral. Vence pelo intervalo, contado da última realizada. Editável em Configurações › Metas, com
  a intenção de cada classe.
- O objetivo das reuniões (Eduardo, 02 e 03/10/2026): apresentar um dashboard com análise vertical e
  horizontal e indicadores de performance financeira, para o cliente tomar decisões mais arrojadas; e,
  entendendo a estratégia e os desafios dele, vender o serviço que cobre as lacunas técnicas da equipe
  dele (consultoria, plano maior, valuation). A ata guarda as decisões, os ajustes para a área técnica
  e as oportunidades de novos negócios.
- A bimestral é interna, da carteira (Head do BPO e CEO da Critério), e não de um cliente.

Funções puras: não tocam no banco.
"""

from __future__ import annotations

import calendar
import unicodedata
from dataclasses import dataclass
from datetime import date

__all__ = [
    "CADENCIA_PADRAO", "CHECKLIST", "ETAPAS", "INICIO_DO_FUNIL", "INTENCAO_PADRAO", "REUNIAO_DA_CARTEIRA",
    "TIPOS_ANTIGOS", "TIPOS_DE_REUNIAO", "TipoDeReuniao", "ReuniaoDevida",
    "achar_responsavel", "devida_da_carteira", "devidas", "mais_meses", "nome_do_tipo", "proxima_etapa", "tipo",
]

ETAPAS: tuple[tuple[str, str, str | None], ...] = (
    ("contrato", "Contrato", "Comercial & Cliente"),
    ("handover", "Handover", "Comercial"),
    ("kickoff", "Kickoff", "Gestor & Cliente"),
    ("em_curso", "Em curso", None),
)
"""(chave, nome, quem participa), na ordem do fluxograma."""

CHECKLIST: dict[str, tuple[tuple[str, str], ...]] = {
    "contrato": (
        ("proposta", "Emitir a proposta comercial"),
        ("contrato", "Emitir o contrato com o detalhe das entregas e do que não entregamos"),
        ("assinatura", "Assinar o contrato comercial"),
    ),
    # O fluxograma junta Handover e Kickoff numa caixa só; os itens vão para a etapa de quem participa:
    # o que o comercial passa adiante é Handover, o que se faz com o cliente é Kickoff.
    "handover": (
        ("pontos_sensiveis", "Apresentar os pontos sensíveis a alinhar, captados na abordagem comercial"),
    ),
    "kickoff": (
        ("apresentacao", "Apresentar a Critério (ferramentas, comunicação, equipe e SLAs)"),
        ("rescisao", "Entregar o modelo de carta de rescisão do contador anterior e o termo de transferência"),
        ("documentos", "Entregar a lista de documentos e informações iniciais e mensais"),
        ("fluxo_financeiro", "Entender a situação do fluxo de informações financeiras do cliente"),
        ("kyc", "Preencher o formulário Know Your Client (KYC)"),
    ),
}


@dataclass(frozen=True)
class TipoDeReuniao:
    chave: str
    nome: str
    meses: int
    """Intervalo até a próxima, contado da última realizada."""
    participantes: str
    pauta: tuple[str, ...]


_LACUNAS = "Lacunas técnicas do cliente e os serviços da Critério que as cobrem (consultoria, plano maior, valuation…)"

TIPOS_DE_REUNIAO: tuple[TipoDeReuniao, ...] = (
    TipoDeReuniao("mensal", "Mensal", 1, "Gestor & Cliente", (
        "Apresentar o dashboard do fechamento do mês: análise vertical e horizontal e indicadores de performance financeira",
        "Gaps, acertos e ajustes necessários no fechamento",
        "Entender os óbices do cliente na geração de informações e documentos",
        _LACUNAS,
    )),
    TipoDeReuniao("trimestral", "Trimestral", 3, "Gestor & Cliente", (
        "Apresentar o dashboard do trimestre: análise vertical e horizontal e indicadores de performance financeira",
        "Discutir os procedimentos de revisão analítica (PRA) e os KPIs das demonstrações contábeis",
        "Apresentar os pontos sensíveis a serem alinhados",
        _LACUNAS,
    )),
    TipoDeReuniao("semestral", "Semestral", 6, "Gestor & Cliente", (
        "Entender a estratégia e os desafios da empresa",
        "Resultados do semestre: análise vertical e horizontal e indicadores de performance financeira",
        "Contrato e escopo: revisão e satisfação (NPS)",
        "Prioridades do próximo semestre",
        _LACUNAS,
    )),
)
"""As reuniões com o cliente (03/10/2026, Eduardo): uma por classe. A anual saiu ("se teremos reuniões
semestrais não há necessidade de anuais") e a bimestral virou interna, da carteira (abaixo)."""

TIPOS_ANTIGOS: dict[str, str] = {"bimestral": "Bimestral", "anual": "Anual"}
"""Tipos que já foram registrados antes de 03/10/2026: ficam no histórico com o nome, mas não se
registram mais nem são cobrados."""

_POR_CHAVE = {t.chave: t for t in TIPOS_DE_REUNIAO}

REUNIAO_DA_CARTEIRA = TipoDeReuniao("carteira", "Bimestral da carteira", 2, "Head do BPO & CEO da Critério", (
    "Overview da carteira: classes, reuniões vencidas e ajustes atrasados",
    "Corrigir rotas de análise",
    "Vendas abertas nas reuniões com os clientes",
))
"""Interna, entre o Head do BPO e o CEO da Critério (Eduardo, 03/10/2026): um overview da carteira
para corrigir rotas de análise. Não é de um cliente: vence a cada 2 meses, da última registrada."""

INICIO_DO_FUNIL = date(2026, 10, 2)
"""Para o cliente anterior ao CRM, as reuniões contam daqui (opção A, aprovada por Eduardo em
02/10/2026): sem isto, toda a carteira antiga aparecia vencida só por não ter reunião registrada."""

CADENCIA_PADRAO: dict[str, tuple[str, ...]] = {
    "A": ("mensal",),
    "B": ("trimestral",),
    "C": ("semestral",),
}
"""Uma reunião por classe (Eduardo, 03/10/2026), enquanto ninguém mudou em Configurações › Metas."""

INTENCAO_PADRAO: dict[str, str] = {
    "A": "Reter e expandir: todo mês, apresentar o dashboard do fechamento (análise vertical e horizontal e "
         "indicadores de performance financeira) e levar o cliente a decisões mais arrojadas; das lacunas, "
         "oferecer consultoria ou ampliar o plano.",
    "B": "Aprofundar a relação: revisar PRA e KPIs, oferecer o que fecha as lacunas (BPO Financeiro, "
         "consultoria) e preparar a subida para a classe A.",
    "C": "Entender a estratégia e os desafios da empresa e achar onde a Critério complementa a equipe dele "
         "(valuation, consultoria, plano maior).",
}
"""O que a Critério quer com cada classe; aparece no topo do funil da classe. Editável em Metas."""


def proxima_etapa(etapa: str) -> str | None:
    chaves = [e for e, _, _ in ETAPAS]
    i = chaves.index(etapa)
    return chaves[i + 1] if i + 1 < len(chaves) else None


def mais_meses(dia: date, meses: int) -> date:
    """O mesmo dia `meses` depois; no mês mais curto, o último dia dele (31/01 + 1 = 28 ou 29/02)."""
    total = dia.month - 1 + meses
    ano, mes = dia.year + total // 12, total % 12 + 1
    return date(ano, mes, min(dia.day, calendar.monthrange(ano, mes)[1]))


@dataclass(frozen=True)
class ReuniaoDevida:
    tipo: str
    ultima: date | None
    proxima: date | None
    """`None`: nenhuma registrada e sem data de entrada em curso para contar — conta como atrasada."""
    atrasada: bool
    dias_de_atraso: int | None


def devidas(
    tipos: tuple[str, ...] | list[str], ultimas: dict[str, date], em_curso_desde: date | None, hoje: date,
) -> list[ReuniaoDevida]:
    """Uma linha por tipo da cadência da classe, na ordem do fluxograma.

    A próxima vence `meses` depois da última realizada daquele tipo. Sem nenhuma realizada, conta da
    entrada em curso; sem essa data (cliente anterior ao CRM), não há como saber se está em dia: entra
    como atrasada, com a próxima vazia, até a primeira ser registrada."""
    linhas = []
    for tipo in TIPOS_DE_REUNIAO:
        if tipo.chave not in tipos:
            continue
        ultima = ultimas.get(tipo.chave)
        base = ultima or em_curso_desde
        proxima = mais_meses(base, tipo.meses) if base else None
        atrasada = proxima is None or proxima < hoje
        dias = (hoje - proxima).days if proxima is not None and atrasada else None
        linhas.append(ReuniaoDevida(tipo.chave, ultima, proxima, atrasada, dias))
    return linhas


def tipo(chave: str) -> TipoDeReuniao | None:
    """Só os tipos que se registram hoje."""
    return _POR_CHAVE.get(chave)


def nome_do_tipo(chave: str) -> str:
    """O nome para o histórico, também dos tipos antigos."""
    t = _POR_CHAVE.get(chave)
    return t.nome if t else TIPOS_ANTIGOS.get(chave, chave)


def devida_da_carteira(ultima: date | None, hoje: date) -> ReuniaoDevida:
    """A bimestral da carteira: 2 meses depois da última; sem nenhuma, do início do funil."""
    proxima = mais_meses(ultima or INICIO_DO_FUNIL, REUNIAO_DA_CARTEIRA.meses)
    atrasada = proxima < hoje
    return ReuniaoDevida(REUNIAO_DA_CARTEIRA.chave, ultima, proxima, atrasada, (hoje - proxima).days if atrasada else None)


def _sem_acento(texto: str) -> list[str]:
    limpo = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().casefold()
    return [p for p in "".join(c if c.isalnum() else " " for c in limpo).split() if p]


def achar_responsavel(citado: str | None, pessoas: list[tuple[str, str | None]]) -> str | None:
    """O e-mail de quem a ata cita como responsável, entre as pessoas que podem receber ajustes
    (`(email, nome)`). Sem acento e sem caixa: "jefferson" acha "Jefferson Souza"; "Jefferson Souza",
    também. Mais de uma pessoa possível, ou nenhuma, devolve `None`: a pessoa escolhe na tela."""
    partes = _sem_acento(citado or "")
    if not partes:
        return None
    achados = []
    for email, nome in pessoas:
        do_nome = _sem_acento(nome or "") or _sem_acento(email.split("@")[0])
        if all(p in do_nome for p in partes) and do_nome[0] == partes[0]:
            achados.append(email)
    return achados[0] if len(achados) == 1 else None
