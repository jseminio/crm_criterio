"""O reajuste anual dos contratos: em julho, pelo IPCA (decisões de Eduardo em 13/10/2026).

- Todo contrato é reajustado **uma vez por ano, em julho**.
- O IPCA conta **desde a última vez que o preço foi definido**: a assinatura ou o último Reajuste. Vai do mês
  dessa base até **junho** (o IBGE publica junho por volta de 10 de julho). No ano normal são os últimos 12
  meses; no primeiro reajuste de quem foi adiado, o acumulado desde a assinatura (ex.: jan/2026 a jun/2027,
  18 meses).
- Quem não completou **12 meses** em julho fica para o julho seguinte (Lei 10.192/2001, art. 2º: reajuste com
  periodicidade menor que um ano é nulo).
- **O CRM não aplica sozinho**: monta a tabela, uma pessoa confirma ou altera cada valor, e fica registrado quem
  autorizou.
- Não recorrente, em princípio, não reajusta. O que dura mais de 12 meses (cronograma longo) entra na tabela como
  "Você decide".

Contrato da carteira anterior ao CRM, sem data de assinatura, é **presumido** com base no julho anterior (12 meses)
e a linha diz isso. Contrato em aviso de saída não entra: o cliente já está de saída.

Funções puras: não tocam no banco.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum

from crm.domain.listas import IndiceDeReajuste, SituacaoContrato

__all__ = ["ContratoParaReajuste", "LinhaDoReajuste", "SituacaoDoReajuste", "linha_do_reajuste", "acumulado", "meses_entre"]

CENTAVOS = Decimal("0.01")
MES_DO_REAJUSTE = 7
MES_FINAL_DO_IPCA = 6
MESES_MINIMOS = 12


class SituacaoDoReajuste(Enum):
    REAJUSTAR = "Reajustar"
    DECIDIR = "Você decide"
    ADIADO = "Adiado"
    REAJUSTADO = "Reajustado"
    SEM_REAJUSTE = "Sem reajuste"
    SEM_PRECO = "Sem preço"


@dataclass(frozen=True)
class ContratoParaReajuste:
    id: int
    situacao: SituacaoContrato
    recorrente: bool
    indice: IndiceDeReajuste | None
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    parcelas_no_ano: int
    data_inicio: date | None
    anterior_ao_crm: bool
    data_fim: date | None
    saida_em: date | None
    reajustes: tuple[date, ...] = ()
    """Datas dos eventos de Reajuste já registrados."""
    caso_a_caso: bool = False
    """O serviço está com reajuste "Caso a caso" na tabela de serviços (13/10/2026): a pessoa decide."""


@dataclass(frozen=True)
class LinhaDoReajuste:
    contrato_id: int
    situacao: SituacaoDoReajuste
    observacao: str | None
    base: date | None
    base_presumida: bool
    de: date | None
    ate: date | None
    meses: int | None
    ipca: Decimal | None
    """Acumulado em %, com 4 casas (6,1043 = 6,1043%). Com meses faltando, é o dos meses que já existem."""
    meses_faltando: tuple[date, ...] = field(default_factory=tuple)
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    mensal_sugerido: Decimal | None = None
    anual_sugerido: Decimal | None = None
    adiado_para: int | None = None

    @property
    def ipca_completo(self) -> bool:
        return self.ipca is not None and not self.meses_faltando

    @property
    def aprovavel(self) -> bool:
        return self.situacao in (SituacaoDoReajuste.REAJUSTAR, SituacaoDoReajuste.DECIDIR) and self.ipca_completo


def _indice(d: date) -> int:
    return d.year * 12 + d.month - 1


def meses_entre(de: date, ate: date) -> int:
    """Meses do mês de `de` ao mês de `ate`, sem contar o de `ate` (jul/2026 → jul/2027 = 12)."""
    return _indice(ate) - _indice(de)


def _meses(de: date, ate: date) -> list[date]:
    return [date(i // 12, i % 12 + 1, 1) for i in range(_indice(de), _indice(ate) + 1)]


def acumulado(variacoes: list[Decimal]) -> Decimal:
    """Fator acumulado − 1, em %: (1 + v₁/100) × (1 + v₂/100) × … − 1."""
    fator = Decimal(1)
    for v in variacoes:
        fator *= 1 + Decimal(v) / 100
    return (fator - 1) * 100


def _corrigir(valor: Decimal | None, ipca: Decimal) -> Decimal | None:
    if valor is None:
        return None
    return (valor * (1 + ipca / 100)).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def linha_do_reajuste(c: ContratoParaReajuste, ano: int, ipca: dict[date, Decimal]) -> LinhaDoReajuste | None:
    """Onde o contrato entra no reajuste de julho de `ano`; `None` se não entra (não ativo, de saída, encerrado
    antes de julho, ou assinado depois de julho — esse é do ano seguinte)."""
    if c.situacao not in (SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO) or c.saida_em is not None:
        return None
    julho = date(ano, MES_DO_REAJUSTE, 1)
    proximo = date(ano + 1, MES_DO_REAJUSTE, 1)
    if c.data_fim is not None and c.data_fim < julho:
        return None
    precos = {"preco_mensal": c.preco_mensal, "preco_anual": c.preco_anual}

    deste_ano = [d for d in c.reajustes if julho <= d < proximo]
    anteriores = [d for d in c.reajustes if d < julho]
    if deste_ano:
        return LinhaDoReajuste(c.id, SituacaoDoReajuste.REAJUSTADO, None, max(deste_ano), False, None, None, None, None, **precos)

    base, presumida = (max(anteriores), False) if anteriores else (c.data_inicio, False)
    if base is None:
        if not c.anterior_ao_crm:
            return None
        base, presumida = date(ano - 1, MES_DO_REAJUSTE, 1), True
    if base >= julho:
        return None
    base = base.replace(day=1)

    if c.indice is IndiceDeReajuste.SEM_REAJUSTE:
        return LinhaDoReajuste(c.id, SituacaoDoReajuste.SEM_REAJUSTE, "O contrato não prevê reajuste.", base, presumida,
                               None, None, None, None, **precos)
    if meses_entre(base, julho) < MESES_MINIMOS:
        return LinhaDoReajuste(c.id, SituacaoDoReajuste.ADIADO, f"Menos de 12 meses em julho/{ano}.", base, presumida,
                               None, None, meses_entre(base, julho), None, adiado_para=ano + 1, **precos)

    ate = date(ano, MES_FINAL_DO_IPCA, 1)
    janela = _meses(base, ate)
    faltando = tuple(m for m in janela if m not in ipca)
    percentual = acumulado([ipca[m] for m in janela if m in ipca]).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    observacoes = []
    situacao = SituacaoDoReajuste.REAJUSTAR
    if presumida:
        observacoes.append("Assinatura anterior ao CRM: considerados os 12 meses desde o julho anterior.")
    if not c.recorrente:
        situacao = SituacaoDoReajuste.DECIDIR
        observacoes.append("Não recorrente com mais de 12 meses: você decide se reajusta as parcelas que faltam.")
    if c.caso_a_caso and c.recorrente:
        situacao = SituacaoDoReajuste.DECIDIR
        observacoes.append("O serviço está com reajuste caso a caso.")
    if c.indice is IndiceDeReajuste.IGPM:
        situacao = SituacaoDoReajuste.DECIDIR
        observacoes.append("O contrato prevê IGP-M; a sugestão usa o IPCA.")

    if c.recorrente and c.preco_mensal is None:
        return LinhaDoReajuste(c.id, SituacaoDoReajuste.SEM_PRECO, "Contrato recorrente sem preço mensal.", base, presumida,
                               base, ate, len(janela), percentual, faltando, **precos)

    mensal = _corrigir(c.preco_mensal, percentual)
    if c.recorrente and c.preco_anual is not None and mensal is not None:
        anual = mensal * c.parcelas_no_ano
    else:
        anual = _corrigir(c.preco_anual, percentual)
    return LinhaDoReajuste(
        c.id, situacao, " ".join(observacoes) or None, base, presumida, base, ate, len(janela), percentual, faltando,
        mensal_sugerido=mensal, anual_sugerido=anual, **precos,
    )
