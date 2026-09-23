"""A régua de porte por volume — **sugestão, nunca decisão automática**.

Especificada em `regua-de-porte-e-plano-de-teste.md` (raiz do projeto). Cada
direcionador vale de 0 a 4 pontos por faixa de volume; só entram os
direcionadores **aplicáveis** ao escopo contratado — um valor `None` significa
"não se aplica", e fica fora da média, não vira zero.

```
base    = média dos direcionadores aplicáveis          (0 a 4)
escopo  = +0,25 por serviço contratado além do primeiro (máx. +0,75)
grupo   = +0,50 se houver consolidação de grupo
audit   = +0,25 se a empresa for auditada
pontuação = base + escopo + grupo + audit
```

**Aferição contra um caso real só** — o próprio documento que especifica a
régua avisa: "confirma que a escala não está grosseiramente errada, não que
está calibrada". Por isso o resultado é sempre `SugestaoDePorte`: a tela
mostra a sugestão, a pessoa confirma ou sobrepõe, e é a sobreposição —
registrada com autor e data — que vira material para recalibrar a régua depois.
Este módulo nunca decide o porte sozinho.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

__all__ = ["Direcionador", "DIRECIONADORES", "Porte", "Volumetria", "SugestaoDePorte", "sugerir_porte"]


class Porte(Enum):
    MICRO = "Micro"
    PEQUENO = "Pequeno"
    MEDIO = "Médio"
    GRANDE = "Grande"
    EXTRA_GRANDE = "Extra Grande"


#: Horas-base/mês por porte — tabela da seção 2 da régua.
HORAS_BASE_POR_PORTE: dict[Porte, int] = {
    Porte.MICRO: 5,
    Porte.PEQUENO: 10,
    Porte.MEDIO: 16,
    Porte.GRANDE: 40,
    Porte.EXTRA_GRANDE: 80,
}


@dataclass(frozen=True)
class Direcionador:
    """Um direcionador da régua: o campo, o rótulo para a tela, e os cortes.

    `cortes` é uma sequência de (limite superior inclusive, pontos); o último
    corte usa `None` como limite — "sem teto, vale o máximo".
    """

    campo: str
    rotulo: str
    cortes: tuple[tuple[int | None, int], ...]

    def pontuar(self, valor: int | None) -> int | None:
        if valor is None:
            return None
        for limite, pontos in self.cortes:
            if limite is None or valor <= limite:
                return pontos
        raise AssertionError(f"{valor!r} não coube em nenhum corte de {self.campo!r}")


#: Os nove direcionadores da seção 2 da régua, na ordem do documento.
DIRECIONADORES: tuple[Direcionador, ...] = (
    Direcionador(
        "documentos_fiscais_mes", "Documentos fiscais/mês (emitidas + recebidas)",
        ((50, 0), (150, 1), (300, 2), (600, 3), (None, 4)),
    ),
    Direcionador(
        "lancamentos_contabeis_mes", "Lançamentos contábeis/mês",
        ((100, 0), (300, 1), (800, 2), (2000, 3), (None, 4)),
    ),
    Direcionador(
        "pagamentos_mes", "Pagamentos/mês",
        ((50, 0), (150, 1), (400, 2), (1000, 3), (None, 4)),
    ),
    Direcionador(
        "contas_bancarias", "Contas bancárias",
        ((1, 0), (2, 1), (4, 2), (10, 3), (None, 4)),
    ),
    Direcionador(
        "conciliacoes_cartao_mes", "Conciliações de cartão/mês",
        ((0, 0), (150, 1), (300, 2), (800, 3), (None, 4)),
    ),
    Direcionador(
        "empregados_clt", "Empregados CLT",
        ((5, 0), (20, 1), (50, 2), (150, 3), (None, 4)),
    ),
    Direcionador(
        "admissoes_desligamentos_mes", "Admissões + desligamentos/mês",
        ((1, 0), (4, 1), (10, 2), (25, 3), (None, 4)),
    ),
    Direcionador(
        "cnpjs_no_escopo", "CNPJs no escopo",
        ((1, 0), (2, 1), (4, 2), (10, 3), (None, 4)),
    ),
    Direcionador(
        "tomadores_de_servico", "Tomadores de serviço",
        ((5, 0), (30, 1), (100, 2), (300, 3), (None, 4)),
    ),
)

_MAXIMO_DE_ESCOPO = Decimal("0.75")
_PONTOS_POR_SERVICO_ADICIONAL = Decimal("0.25")
_AJUSTE_DE_GRUPO = Decimal("0.50")
_AJUSTE_DE_AUDITORIA = Decimal("0.25")


@dataclass(frozen=True)
class Volumetria:
    """O que a régua precisa. Cada direcionador ausente (`None`) é "não se
    aplica ao escopo contratado" — fica fora da média, nunca vira zero."""

    documentos_fiscais_mes: int | None = None
    lancamentos_contabeis_mes: int | None = None
    pagamentos_mes: int | None = None
    contas_bancarias: int | None = None
    conciliacoes_cartao_mes: int | None = None
    empregados_clt: int | None = None
    admissoes_desligamentos_mes: int | None = None
    cnpjs_no_escopo: int | None = None
    tomadores_de_servico: int | None = None

    servicos_contratados_alem_do_primeiro: int = 0
    tem_consolidacao_de_grupo: bool = False
    e_auditada: bool = False


@dataclass(frozen=True)
class SugestaoDePorte:
    """O resultado é sempre uma sugestão — ver o aviso no topo do módulo."""

    calculavel: bool
    pontuacao: Decimal | None
    porte: Porte | None
    horas_base: int | None
    direcionadores_aplicados: int


def _cortar(pontuacao: Decimal) -> Porte:
    if pontuacao < Decimal("0.75"):
        return Porte.MICRO
    if pontuacao < Decimal("1.50"):
        return Porte.PEQUENO
    if pontuacao < Decimal("2.25"):
        return Porte.MEDIO
    if pontuacao < Decimal("3.25"):
        return Porte.GRANDE
    return Porte.EXTRA_GRANDE


def sugerir_porte(volumetria: Volumetria) -> SugestaoDePorte:
    """Sem nenhum direcionador aplicável, não calcula — devolve
    `calculavel=False`, nunca um porte arbitrário."""
    pontos = [
        pontuado
        for direcionador in DIRECIONADORES
        if (pontuado := direcionador.pontuar(getattr(volumetria, direcionador.campo))) is not None
    ]

    if not pontos:
        return SugestaoDePorte(
            calculavel=False, pontuacao=None, porte=None, horas_base=None, direcionadores_aplicados=0
        )

    base = Decimal(sum(pontos)) / Decimal(len(pontos))
    escopo = min(
        _PONTOS_POR_SERVICO_ADICIONAL * volumetria.servicos_contratados_alem_do_primeiro,
        _MAXIMO_DE_ESCOPO,
    )
    grupo = _AJUSTE_DE_GRUPO if volumetria.tem_consolidacao_de_grupo else Decimal("0")
    audit = _AJUSTE_DE_AUDITORIA if volumetria.e_auditada else Decimal("0")

    pontuacao = (base + escopo + grupo + audit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    porte = _cortar(pontuacao)

    return SugestaoDePorte(
        calculavel=True,
        pontuacao=pontuacao,
        porte=porte,
        horas_base=HORAS_BASE_POR_PORTE[porte],
        direcionadores_aplicados=len(pontos),
    )
