"""Classificação da carteira: Score, classe, trava, alertas, eixo de ação e ISC.

Especificação em `modelo-classificacao-carteira.md` (fórmulas lidas das células das planilhas
auditáveis, 19/09/2026). Este módulo traduz **só o que não depende dos dois defeitos** da seção 7:

- **Entra:** Score, classe, semáforo, trava de inadimplência, alerta de churn, eixo de ação e ISC.
- **Não entra:** a *nota de rentabilidade* (margem e fator de atrito, defeito 7.2, à espera de
  conferência de Eduardo). Ela chega aqui **como dado**, já calculada pela planilha, e a
  origem é sinalizada. Quando o defeito for decidido, a margem entra como cálculo próprio.

O churn (defeito 7.1, escrito dentro da fórmula na planilha) aqui é um **campo** da nota,
com a escala 1 a 5 (≥ 4 dispara o alerta).

**Nada aqui inventa parâmetro:** pesos, cortes e réguas são os da planilha, guardados em
`Parametros` com uma `versao`, para que cada classificação diga qual versão a produziu.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

__all__ = [
    "Parametros", "PARAMETROS", "Notas", "Isc", "Unidade",
    "score", "classe", "classe_efetiva", "cobranca", "alerta_de_churn", "eixo_de_acao", "isc",
]

D = Decimal


@dataclass(frozen=True)
class Parametros:
    versao: str = "2026-07-planilha-v1"
    """Identifica a origem: pesos e cortes da planilha de 31/07/2026."""

    peso_receita: Decimal = D("0.20")
    peso_rentabilidade: Decimal = D("0.25")
    peso_cross_sell: Decimal = D("0.12")
    peso_complexidade: Decimal = D("0.12")     # entra invertido: (6 − nota)
    peso_disciplina: Decimal = D("0.09")
    peso_risco: Decimal = D("0.07")            # entra invertido: (6 − nota)
    peso_adimplencia: Decimal = D("0.15")

    corte_a: Decimal = D("3.95")
    corte_b: Decimal = D("3.35")
    trava_de_adimplencia: int = 2              # nota ≤ 2 trava e marca cobrança
    churn_alto: int = 4                        # nota ≥ 4 dispara o alerta

    # Conversões do ISC
    valor_da_classe: tuple[tuple[str, int], ...] = (("A", 100), ("B", 60), ("C", 20))
    valor_do_semaforo: tuple[tuple[int, int], ...] = ((1, 100), (2, 50), (3, 0))
    valor_do_churn: tuple[tuple[int, int], ...] = ((1, 100), (2, 80), (3, 60), (4, 20), (5, 0))
    peso_isc_classe: Decimal = D("0.33")
    peso_isc_semaforo: Decimal = D("0.33")
    peso_isc_churn: Decimal = D("0.34")
    meta_do_isc: int = 65
    zona_critica_ate: int = 35


PARAMETROS = Parametros()


@dataclass(frozen=True)
class Notas:
    """As notas 1 a 5 de um grupo, mais o semáforo (1 a 3) e o churn (1 a 5)."""

    receita: Decimal | int
    rentabilidade: Decimal | int
    complexidade: Decimal | int
    disciplina: Decimal | int
    risco: Decimal | int
    cross_sell: Decimal | int
    adimplencia: Decimal | int
    semaforo: int
    churn: int | None = None
    """`None` = ainda sem nota de churn: não dispara alerta e o grupo fica **fora do ISC**."""


def _valida(n: Notas) -> None:
    for campo in ("receita", "rentabilidade", "complexidade", "disciplina", "risco", "cross_sell", "adimplencia"):
        v = getattr(n, campo)
        if not 1 <= v <= 5:
            raise ValueError(f"nota de {campo} precisa ir de 1 a 5 (veio {v})")
    if not 1 <= n.semaforo <= 3:
        raise ValueError(f"semáforo precisa ser 1, 2 ou 3 (veio {n.semaforo})")
    if n.churn is not None and not 1 <= n.churn <= 5:
        raise ValueError(f"churn precisa ir de 1 a 5 (veio {n.churn})")


def score(n: Notas, p: Parametros = PARAMETROS) -> Decimal:
    """Todas as notas de 1 a 5. Complexidade e risco entram invertidos: `6 − nota`."""
    _valida(n)
    return (
        D(n.receita) * p.peso_receita
        + D(n.rentabilidade) * p.peso_rentabilidade
        + D(n.cross_sell) * p.peso_cross_sell
        + D(6 - n.complexidade) * p.peso_complexidade
        + D(n.disciplina) * p.peso_disciplina
        + D(6 - n.risco) * p.peso_risco
        + D(n.adimplencia) * p.peso_adimplencia
    )


def classe(pontuacao: Decimal, p: Parametros = PARAMETROS) -> str:
    """Cortes **fixos** (não percentis): A a partir de 3,95, B a partir de 3,35, senão C."""
    if pontuacao >= p.corte_a:
        return "A"
    if pontuacao >= p.corte_b:
        return "B"
    return "C"


def cobranca(n: Notas, p: Parametros = PARAMETROS) -> bool:
    """Adimplência ≤ 2: trava a classe e marca `$$$`."""
    return n.adimplencia <= p.trava_de_adimplencia


def classe_efetiva(letra: str, n: Notas, p: Parametros = PARAMETROS) -> str:
    """A letra mais o sufixo do semáforo (`A1`, `B3`); com a trava, `(TRAVADO)`.

    A trava **não rebaixa** a classe: só sinaliza."""
    texto = f"{letra}{n.semaforo}"
    return f"{texto} (TRAVADO)" if cobranca(n, p) else texto


def alerta_de_churn(letra: str, n: Notas, p: Parametros = PARAMETROS) -> str | None:
    """`⚠` se churn alto em classe A ou B (há o que salvar); `⚑` se em classe C."""
    if n.churn is None or n.churn < p.churn_alto:
        return None
    return "⚑" if letra == "C" else "⚠"


def eixo_de_acao(letra: str, n: Notas, p: Parametros = PARAMETROS) -> str:
    """Com que urgência agir, nesta ordem de precedência (seção 3 da especificação)."""
    if cobranca(n, p):
        return "Cobrança — sem tratamento preferencial"
    alerta = alerta_de_churn(letra, n, p)
    if alerta == "⚠" and letra == "A":
        return "Reter já (crítico)"
    if alerta == "⚠" and letra == "B":
        return "Reter / vigiar"
    if alerta == "⚑":
        return "Saída organizada"
    return "Sem urgência de churn"


@dataclass(frozen=True)
class Unidade:
    """O que o ISC precisa de cada grupo."""

    receita: Decimal
    classe: str
    semaforo: int
    churn: int | None


@dataclass(frozen=True)
class Isc:
    valor: Decimal
    componente_classe: Decimal
    componente_semaforo: Decimal
    componente_churn: Decimal
    receita_total: Decimal
    grupos: int
    fora_do_isc: int
    """Grupos sem nota de churn: não entram (nem no peso da receita)."""
    zona: str

    @property
    def saudavel(self) -> bool:
        return self.zona == "saudável"


def _valor(tabela: tuple[tuple, ...], chave) -> Decimal:
    return D(dict(tabela)[chave])


def isc(unidades: Iterable[Unidade], p: Parametros = PARAMETROS) -> Isc | None:
    """Índice de Saúde da Carteira, 0 a 100, ponderado pela receita de cada grupo.

    `None` sem nenhum grupo completo (nunca 0: zero seria "carteira crítica", e aqui é "não dá
    para medir")."""
    todas = list(unidades)
    completas = [u for u in todas if u.churn is not None and u.receita > 0]
    total = sum((u.receita for u in completas), D(0))
    if not completas or total <= 0:
        return None
    c_classe = c_sem = c_churn = D(0)
    for u in completas:
        peso = u.receita / total
        c_classe += _valor(p.valor_da_classe, u.classe) * peso
        c_sem += _valor(p.valor_do_semaforo, u.semaforo) * peso
        c_churn += _valor(p.valor_do_churn, u.churn) * peso
    valor = c_classe * p.peso_isc_classe + c_sem * p.peso_isc_semaforo + c_churn * p.peso_isc_churn
    zona = "crítica" if valor < p.zona_critica_ate else ("atenção" if valor < p.meta_do_isc else "saudável")
    return Isc(valor, c_classe, c_sem, c_churn, total, len(completas), len(todas) - len(completas), zona)
