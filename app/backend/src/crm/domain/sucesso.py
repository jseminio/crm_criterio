"""Funil do Sucesso do Cliente (aprovado por Eduardo em 02/10/2026).

O caminho de cada grupo cliente, tirado do fluxograma "Macroprocesso — Comercial & Sucesso do
Cliente": **Contrato** (Comercial & Cliente) → **Handover** (Comercial) → **Kickoff** (Gestor &
Cliente) → **Em curso**, quando as reuniões de resultado passam a ter cadência pela classe do Score.

- Cada etapa da implantação tem um checklist com os itens do fluxograma; a etapa só se conclui com
  todos marcados.
- Em curso, cada tipo de reunião do fluxograma (Mensal, Bimestral, Trimestral) e a Anual vencem
  pelo intervalo dela, contado da última realizada. A cadência por classe foi a recomendação aceita
  por Eduardo: A tem todas; B, a trimestral e a anual; C, só a anual. É editável em Configurações.
- O objetivo das reuniões (Eduardo, 02/10/2026): apresentar um dashboard com os principais números
  do cliente para ele tomar decisões mais arrojadas. Por isso a reunião guarda as decisões do cliente
  e os próximos passos; o dashboard é opcional enquanto não existir.

Funções puras: não tocam no banco.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

__all__ = [
    "CADENCIA_PADRAO", "CHECKLIST", "ETAPAS", "INICIO_DO_FUNIL", "TIPOS_DE_REUNIAO", "TipoDeReuniao", "ReuniaoDevida",
    "devidas", "mais_meses", "proxima_etapa", "tipo",
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


TIPOS_DE_REUNIAO: tuple[TipoDeReuniao, ...] = (
    TipoDeReuniao("mensal", "Mensal", 1, "Gestor & Cliente", (
        "Apresentação das demonstrações contábeis fechadas no mês (gaps, acertos, ajustes necessários)",
        "Entender os óbices do cliente na geração de informações e documentos",
    )),
    TipoDeReuniao("bimestral", "Bimestral", 2, "Gestor & CEO", (
        "Mapear as empresas com características da curva A",
        "Revisar os KPIs do fechamento contábil e as oportunidades de melhoria de processamento",
        "Avaliar a entrega de informações e documentos por parte da empresa",
        "Discutir os procedimentos de revisão analítica (PRA)",
    )),
    TipoDeReuniao("trimestral", "Trimestral", 3, "Gestor & Cliente", (
        "Discutir com o cliente os procedimentos de revisão analítica (PRA) e os KPIs das demonstrações contábeis",
        "Definir o desenho do dashboard contábil do cliente",
        "Apresentar os pontos sensíveis a serem alinhados",
    )),
    # Não está no fluxograma: pauta sugerida em 02/10/2026, a confirmar com Eduardo.
    TipoDeReuniao("anual", "Anual", 12, "Gestor & Cliente", (
        "Resultados do ano e prioridades do próximo",
        "Renovação do contrato e reajuste",
        "Pesquisa de satisfação (NPS)",
    )),
)
_POR_CHAVE = {t.chave: t for t in TIPOS_DE_REUNIAO}

INICIO_DO_FUNIL = date(2026, 10, 2)
"""Para o cliente anterior ao CRM, as reuniões contam daqui (opção A, aprovada por Eduardo em
02/10/2026): sem isto, toda a carteira antiga aparecia vencida só por não ter reunião registrada."""

CADENCIA_PADRAO: dict[str, tuple[str, ...]] = {
    "A": ("mensal", "bimestral", "trimestral", "anual"),
    "B": ("trimestral", "anual"),
    "C": ("anual",),
}
"""Quais reuniões cada classe tem, enquanto ninguém mudou em Configurações."""


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
    return _POR_CHAVE.get(chave)
