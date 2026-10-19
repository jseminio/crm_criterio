"""O funil de parceiros (19/10/2026, amostra aprovada por Eduardo): a etapa da relação, os indicadores com a sua
composição e o cálculo do finder fee. Tudo aqui é conta pura, sem banco; a API (`crm.api.parceiros`) só carrega e
grava.

**Duas camadas de funil.** A relação com o parceiro (Mapeado → … → Estratégico, ou Dormente) e cada indicação, que é
uma oportunidade do Funil comercial com `parceiro_id`. A etapa da relação sai dos dados sempre que dá; só Mapeado,
Qualificado e Estratégico se marcam à mão.

**O fee é sugestão, nunca decisão.** O CRM calcula pelos recebidos do Omie e o sócio da conta confere o valor líquido
de impostos antes de aprovar. Os recebidos vêm por grupo e por competência, não por contrato: a "1ª parcela" é o
primeiro recebimento do grupo a partir do mês do aceite, limitado à parcela mensal do serviço.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Protocol

from crm.domain.indicadores import e_recorrente
from crm.domain.listas import AcordoDoParceiro, EtapaDoParceiro, RegraDoFee, Situacao, SituacaoDoFee
from crm.domain.mrr import mensalizar

__all__ = [
    "DIAS_PARA_DORMENTE",
    "INDICADORES",
    "FeeCalculado",
    "Indicacao",
    "ItemDaComposicao",
    "ResumoDoParceiro",
    "calcular_fees",
    "composicao",
    "data_da_indicacao",
    "etapa_do_parceiro",
    "indicadores",
    "mrr_da_indicacao",
    "resumir",
    "vinculo_ate",
]

DIAS_PARA_DORMENTE = 180
"""Seis meses sem indicação nova e a relação vira Dormente: pede conversa de revisão ou encerramento."""

MESES_DE_VINCULO = 12
"""Cláusula 2.3: a indicação fica ligada ao parceiro por 12 meses contados da validação."""

PERCENTUAL_NAO_RECORRENTE = Decimal("0.10")
"""Cláusula 3.4: 10% do valor recebido nos contratos não recorrentes."""

CENTAVOS = Decimal("0.01")


class Indicacao(Protocol):
    """O que o funil lê de uma oportunidade indicada."""

    id: int
    nome: str
    situacao: Situacao
    data_colocacao: date | None
    data_aceite: date | None
    data_envio_proposta: date | None
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    indicacao_recebida_em: date | None
    indicacao_validada_em: date | None
    indicacao_recusada: object | None


def data_da_indicacao(o: Indicacao) -> date | None:
    """Quando o parceiro apresentou a conta; nas oportunidades antigas, sem essa data, vale a originação."""
    return o.indicacao_recebida_em or o.data_colocacao


def _mais_meses(dia: date, meses: int) -> date:
    mes = dia.month - 1 + meses
    ano, mes = dia.year + mes // 12, mes % 12 + 1
    ultimo = (date(ano + (mes == 12), mes % 12 + 1, 1) - timedelta(days=1)).day
    return date(ano, mes, min(dia.day, ultimo))


def vinculo_ate(o: Indicacao) -> date | None:
    """Até quando a indicação gera fee (cláusula 2.3). Sem validação, o vínculo ainda não começou."""
    if o.indicacao_validada_em is None or o.indicacao_recusada is not None:
        return None
    return _mais_meses(o.indicacao_validada_em, MESES_DE_VINCULO)


def _valida(o: Indicacao) -> bool:
    return o.indicacao_recusada is None


def _chegou_a_proposta(o: Indicacao) -> bool:
    return o.data_envio_proposta is not None or o.situacao in {Situacao.EM_AVALIACAO, Situacao.ACEITA}


def mrr_da_indicacao(o: Indicacao) -> Decimal:
    """O MRR da indicação fechada: parcela × 13 ÷ 12, só no serviço recorrente (a mesma regra do ticket do funil)."""
    return mensalizar(o.preco_mensal) if e_recorrente(o) else Decimal("0")


def etapa_do_parceiro(etapa_manual: EtapaDoParceiro, acordo: AcordoDoParceiro, indicacoes: Iterable[Indicacao],
                      hoje: date) -> EtapaDoParceiro:
    """A etapa da relação. Estratégico é escolha (vale sobre tudo); depois Dormente, Produtivo, Ativado e
    Formalizado saem dos dados; sem nada disso, fica a etapa marcada à mão (Mapeado ou Qualificado)."""
    if etapa_manual is EtapaDoParceiro.ESTRATEGICO:
        return EtapaDoParceiro.ESTRATEGICO
    validas = [o for o in indicacoes if _valida(o)]
    datas = [d for o in validas if (d := data_da_indicacao(o))]
    if datas and (hoje - max(datas)).days > DIAS_PARA_DORMENTE:
        return EtapaDoParceiro.DORMENTE
    if any(_chegou_a_proposta(o) for o in validas):
        return EtapaDoParceiro.PRODUTIVO
    if validas:
        return EtapaDoParceiro.ATIVADO
    if acordo is AcordoDoParceiro.CONTRATO_ASSINADO:
        return EtapaDoParceiro.FORMALIZADO
    return etapa_manual if etapa_manual.manual else EtapaDoParceiro.MAPEADO


@dataclass(frozen=True)
class Periodo:
    """O recorte da tela: pela data da indicação ou pela data do fechamento (aceite)."""

    de: date | None = None
    ate: date | None = None
    data_tipo: str = "indicacao"

    @property
    def ativo(self) -> bool:
        return self.de is not None or self.ate is not None

    def contem(self, o: Indicacao) -> bool:
        if not self.ativo:
            return True
        dia = o.data_aceite if self.data_tipo == "fechamento" else data_da_indicacao(o)
        if dia is None:
            return False
        return (self.de is None or dia >= self.de) and (self.ate is None or dia <= self.ate)


@dataclass
class ResumoDoParceiro:
    """Um parceiro com as contas do período: o cartão do Kanban e a linha da Grade."""

    id: int
    nome: str
    tipo_pessoa: str
    nivel: str
    acordo: str
    etapa: EtapaDoParceiro
    socio_responsavel: str | None
    indicacoes: list = field(default_factory=list)
    """As indicações válidas do período."""

    @property
    def quantas(self) -> int:
        return len(self.indicacoes)

    @property
    def abertas(self) -> int:
        return sum(1 for o in self.indicacoes if not o.situacao.decidida)

    @property
    def fechadas(self) -> int:
        return sum(1 for o in self.indicacoes if o.situacao.ganha)

    @property
    def mrr(self) -> Decimal:
        return sum((mrr_da_indicacao(o) for o in self.indicacoes if o.situacao.ganha), Decimal("0"))

    @property
    def pontual(self) -> Decimal:
        """Fechado de valor único (consultoria, legalização): fora do MRR, somado à parte como no Kanban do funil."""
        return sum((o.preco_anual or Decimal("0") for o in self.indicacoes
                    if o.situacao.ganha and not e_recorrente(o)), Decimal("0"))


def resumir(parceiro, indicacoes: list[Indicacao], periodo: Periodo, hoje: date) -> ResumoDoParceiro:
    """O parceiro na tela: a etapa olha todas as indicações; os números, só as do período."""
    return ResumoDoParceiro(
        id=parceiro.id, nome=parceiro.nome, tipo_pessoa=parceiro.tipo_pessoa.value, nivel=parceiro.nivel.value,
        acordo=parceiro.acordo.value,
        etapa=etapa_do_parceiro(parceiro.etapa_manual, parceiro.acordo, indicacoes, hoje),
        socio_responsavel=parceiro.socio_responsavel,
        indicacoes=[o for o in indicacoes if _valida(o) and periodo.contem(o)],
    )


# ------------------------------------------------------------------ indicadores

INDICADORES: dict[str, str] = {
    "ativos": "Parceiros com ao menos uma indicação válida no período.",
    "indicacoes": "Indicações válidas no período, pela data escolhida em \"Data de\". Recusadas ficam fora.",
    "conversao": "Indicações fechadas (Aceita) ÷ indicações decididas (Aceita ou Perdida) do período. Em aberto não "
                 "entra, como na taxa de conversão do funil.",
    "mrr": "Parcela × 13 ÷ 12 das indicações fechadas de serviço recorrente no período. Valor único fica fora.",
    "sem_contrato": "Parceiros sem contrato assinado: informal com fee, minuta ou sem acordo. É a fila da "
                    "regularização e não depende do período.",
    "fees": "Fees calculados a partir dos recebidos do Omie que esperam o sócio da conta aprovar. Não dependem do "
            "período.",
}


@dataclass(frozen=True)
class ItemDaComposicao:
    """Uma linha do "Ver composição": o parceiro (ou a indicação), o que explica, e o valor que entra na conta."""

    parceiro: str
    detalhe: str
    valor: Decimal
    referencia: str | None = None
    """A oportunidade ou o fee, quando a linha é de um."""


def _conversao(resumos: list[ResumoDoParceiro]) -> Decimal | None:
    decididas = sum(1 for r in resumos for o in r.indicacoes if o.situacao.decidida)
    fechadas = sum(r.fechadas for r in resumos)
    if not decididas:
        return None
    return (Decimal(fechadas) * 100 / decididas).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def indicadores(resumos: list[ResumoDoParceiro], fees_a_aprovar: list) -> dict[str, Decimal | int | None]:
    """Os seis números do topo, da mesma conta da composição (`composicao`)."""
    return {
        "ativos": sum(1 for r in resumos if r.quantas),
        "indicacoes": sum(r.quantas for r in resumos),
        "conversao": _conversao(resumos),
        "mrr": sum((r.mrr for r in resumos), Decimal("0")),
        "sem_contrato": sum(1 for r in resumos if r.acordo != AcordoDoParceiro.CONTRATO_ASSINADO.value),
        "fees": sum((f.calculado for f in fees_a_aprovar), Decimal("0")),
    }


def composicao(indicador: str, resumos: list[ResumoDoParceiro], fees_a_aprovar: list) -> list[ItemDaComposicao]:
    """As linhas que somam o número do card, com o mesmo filtro. Quem entra na conta vem primeiro."""
    if indicador == "ativos":
        return [ItemDaComposicao(r.nome, r.etapa.value, Decimal(r.quantas)) for r in resumos if r.quantas]
    if indicador == "indicacoes":
        return [ItemDaComposicao(r.nome, o.nome, Decimal(1), o.situacao.value) for r in resumos for o in r.indicacoes]
    if indicador == "conversao":
        return [ItemDaComposicao(r.nome, o.nome, Decimal(1 if o.situacao.ganha else 0), o.situacao.value)
                for r in resumos for o in r.indicacoes if o.situacao.decidida]
    if indicador == "mrr":
        return [ItemDaComposicao(r.nome, o.nome, mrr_da_indicacao(o), o.situacao.value)
                for r in resumos for o in r.indicacoes if o.situacao.ganha and mrr_da_indicacao(o) > 0]
    if indicador == "sem_contrato":
        return [ItemDaComposicao(r.nome, r.acordo, Decimal(r.quantas)) for r in resumos
                if r.acordo != AcordoDoParceiro.CONTRATO_ASSINADO.value]
    if indicador == "fees":
        return [ItemDaComposicao(f.parceiro.nome, f.oportunidade.nome, f.calculado, f.situacao.value)
                for f in fees_a_aprovar]
    raise ValueError(f"indicador desconhecido: {indicador}")


# ------------------------------------------------------------------ fee

@dataclass(frozen=True)
class FeeCalculado:
    oportunidade_id: int
    regra: RegraDoFee
    competencia: date
    base: Decimal
    calculado: Decimal


def calcular_fees(o: Indicacao, recebimentos: list[tuple[date, Decimal]], ja_calculadas: set[date]) -> list[FeeCalculado]:
    """Os fees que faltam para uma indicação fechada. `recebimentos` são `(competência, valor)` do grupo; as
    competências de `ja_calculadas` não se repetem.

    - **Recorrente** (cláusula 3.2): o primeiro recebimento a partir do mês do aceite, limitado à parcela mensal.
    - **Não recorrente** (cláusula 3.4): 10% de cada recebimento a partir do mês do aceite, até somar o valor do
      contrato. O recebido do grupo pode incluir outros serviços; por isso o sócio confere antes de aprovar.
    - Fora do vínculo de 12 meses (aceite depois do fim), não há fee. Indicação recusada também não.
    """
    if not o.situacao.ganha or o.data_aceite is None or o.indicacao_recusada is not None:
        return []
    fim = vinculo_ate(o)
    if fim is not None and o.data_aceite > fim:
        return []
    inicio = o.data_aceite.replace(day=1)
    depois = sorted((c, v) for c, v in recebimentos if c >= inicio and v > 0)
    if e_recorrente(o):
        if not depois or ja_calculadas:
            return []
        competencia, valor = depois[0]
        return [FeeCalculado(o.id, RegraDoFee.PRIMEIRA_PARCELA, competencia, valor, min(valor, o.preco_mensal))]
    total = o.preco_anual or o.preco_mensal
    if not total:
        return []
    fees, coberto = [], Decimal("0")
    for competencia, valor in depois:
        if coberto >= total:
            break
        parte = min(valor, total - coberto)
        coberto += parte
        if competencia in ja_calculadas:
            continue
        fees.append(FeeCalculado(o.id, RegraDoFee.DEZ_POR_CENTO, competencia, valor,
                                 (parte * PERCENTUAL_NAO_RECORRENTE).quantize(CENTAVOS, rounding=ROUND_HALF_UP)))
    return fees


def fees_pendentes(fees: Iterable) -> list:
    return [f for f in fees if f.situacao is SituacaoDoFee.A_APROVAR]
