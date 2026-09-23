"""Indicadores do funil que a Etapa 1 consegue calcular sem decisão pendente.

**Este módulo calcula pouco de propósito.** Dos doze KPIs oficiais, só entram
aqui os que os dados de 2026 sustentam sem que ninguém tenha de escolher uma
definição. Cada um dos que ficam de fora tem um motivo registrado:

- **Ticket médio** — decisão de Eduardo em 23/09/2026: receita média por
  grupo na carteira inteira, não venda nova. Mas a carteira inteira **não
  está no CRM** — só as propostas de 2026. É cálculo pontual, fora daqui
  (mesma razão que já tirou o MRR de escopo). Ver `../README.md`.
- **MRR** — o oficial é a receita contratada da *carteira inteira*. Aqui só há o
  preço mensal das propostas de 2026, que é outra grandeza. Dar o nome de MRR a
  esse número seria um valor certo com o rótulo errado.

Quando um indicador não é calculável, o resultado diz **por quê** e **o que
falta** — não devolve zero nem esconde o campo.

**Ciclo médio de vendas** entrou em 23/09/2026: originação → aceite, decisão
de Eduardo sobre a base do cálculo. **Cobertura do processo** também: dos oito
indicadores do `documento-de-negocio.md` (seção 12.5), só dois não exigem
entidade que a Etapa 1 não modela (reunião, classe, entrevista, implantação,
contrato) — % com próxima ação definida e % com ficha de volumetria completa.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Protocol

from crm.domain.listas import Situacao, TipoCanal

__all__ = [
    "Indicadores",
    "Recorte",
    "TaxaDeConversao",
    "CicloMedioDeVendas",
    "Cobertura",
    "DependenciaDeCanal",
    "calcular",
]

ZERO = Decimal("0.00")

#: Do KPI oficial "KPI de Head de Novos Negócios": meta 50%, alerta abaixo de 30%.
META_DE_CONVERSAO = Decimal("50")
ALERTA_DE_CONVERSAO = Decimal("30")

#: Origem que o documento de negócio mede como "dependência de canal".
CANAL_DA_REDE_DE_SOCIOS = TipoCanal.SOCIOS

#: Os nove direcionadores que definem "ficha de volumetria completa".
_DIRECIONADORES_DA_VOLUMETRIA = (
    "documentos_fiscais_mes", "lancamentos_contabeis_mes", "pagamentos_mes",
    "contas_bancarias", "conciliacoes_cartao_mes", "empregados_clt",
    "admissoes_desligamentos_mes", "cnpjs_no_escopo", "tomadores_de_servico",
)


class _Oportunidade(Protocol):
    situacao: Situacao
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    data_colocacao: date | None
    data_aceite: date | None
    proxima_acao: str | None
    tipo_canal: TipoCanal | None
    documentos_fiscais_mes: int | None
    lancamentos_contabeis_mes: int | None
    pagamentos_mes: int | None
    contas_bancarias: int | None
    conciliacoes_cartao_mes: int | None
    empregados_clt: int | None
    admissoes_desligamentos_mes: int | None
    cnpjs_no_escopo: int | None
    tomadores_de_servico: int | None


@dataclass(frozen=True)
class Recorte:
    """Um conjunto de oportunidades somado."""

    quantas: int
    valor_mensal: Decimal
    valor_anual: Decimal
    sem_preco_mensal: int
    """Quantas do conjunto **não têm** preço mensal.

    Consultoria de valor único não tem mensalidade, e a planilha de 2026 deixa o
    campo vazio de propósito. Sem este número, o total mensal parece cobrir o
    conjunto inteiro quando cobre só parte dele.
    """

    @property
    def com_preco_mensal(self) -> int:
        return self.quantas - self.sem_preco_mensal


@dataclass(frozen=True)
class TaxaDeConversao:
    """Aceitas ÷ decididas — decisão de Eduardo em 22/09/2026.

    O denominador conta só o que já tem desfecho: Aceita, Recusada ou Perdido
    (`Situacao.decidida`). Oportunidade em aberto não entra — ela ainda pode
    fechar, e contá-la já penalizaria o time por um resultado que não
    aconteceu ainda. É a leitura padrão de funil de vendas: não se julga a
    conversão do período por proposta que ainda não venceu.

    Sobre o mesmo dado, a outra definição possível — todas as trabalhadas,
    incluindo o que está em aberto — dava um número bem diferente: 26% contra
    38%, diagnósticos opostos do mesmo trimestre. Só uma pessoa podia decidir
    qual conta, e a decisão está registrada no anexo técnico.
    """

    aceitas: int
    decididas: int
    percentual: Decimal | None
    """``None`` só quando não há nenhuma decidida ainda.

    Sem este caso à parte, dividir por zero viraria 0% — que parece "nada
    fechou" quando na verdade é "não dá para medir ainda".
    """

    @property
    def calculavel(self) -> bool:
        return self.percentual is not None

    @property
    def abaixo_do_alerta(self) -> bool | None:
        """``None`` quando não calculável — não há o que alertar sobre o vazio."""
        if self.percentual is None:
            return None
        return self.percentual < ALERTA_DE_CONVERSAO

    @property
    def atingiu_a_meta(self) -> bool | None:
        if self.percentual is None:
            return None
        return self.percentual >= META_DE_CONVERSAO


@dataclass(frozen=True)
class CicloMedioDeVendas:
    """Dias entre originação e aceite — decisão de Eduardo em 23/09/2026 sobre
    a base do cálculo (a partir de quando se conta).

    Só entra proposta **aceita com as duas datas presentes**. Aceita sem data
    de originação ou sem data de aceite fica de fora da média — não vira
    zero dias, que pareceria "fechou na hora".
    """

    dias: Decimal | None
    amostra: int
    aceitas_sem_as_duas_datas: int

    @property
    def calculavel(self) -> bool:
        return self.dias is not None


@dataclass(frozen=True)
class Cobertura:
    """"Aumentar os pontos de contato" virando número — `documento-de-negocio.md`,
    seção 12.5. Dos oito indicadores de cobertura ali listados, só estes dois
    não exigem entidade que a Etapa 1 não modela (reunião, classe da
    carteira, entrevista, implantação, contrato).
    """

    em_aberto_com_proxima_acao: int
    em_aberto_total: int
    com_volumetria_completa: int
    total: int

    @property
    def percentual_com_proxima_acao(self) -> Decimal | None:
        if self.em_aberto_total == 0:
            return None
        return (
            Decimal(self.em_aberto_com_proxima_acao) / Decimal(self.em_aberto_total) * 100
        ).quantize(Decimal("0.1"))

    @property
    def percentual_com_volumetria_completa(self) -> Decimal | None:
        if self.total == 0:
            return None
        return (
            Decimal(self.com_volumetria_completa) / Decimal(self.total) * 100
        ).quantize(Decimal("0.1"))


@dataclass(frozen=True)
class DependenciaDeCanal:
    """Quanto do funil nasce da rede dos sócios — insight já identificado em
    `documento-de-negocio.md` (56% em 19/09/2026). É o que tráfego pago e
    afiliados tentariam reduzir, se entrarem em operação."""

    da_rede_de_socios: int
    total: int

    @property
    def percentual(self) -> Decimal | None:
        if self.total == 0:
            return None
        return (Decimal(self.da_rede_de_socios) / Decimal(self.total) * 100).quantize(
            Decimal("0.1")
        )


@dataclass(frozen=True)
class Indicadores:
    em_aberto: Recorte
    aceitas: Recorte
    aceitas_com_data_de_aceite: int
    ciclo_medio: CicloMedioDeVendas
    taxa_de_conversao: TaxaDeConversao
    cobertura: Cobertura
    dependencia_de_canal: DependenciaDeCanal


def _somar(oportunidades: list[_Oportunidade]) -> Recorte:
    return Recorte(
        quantas=len(oportunidades),
        valor_mensal=sum((o.preco_mensal or ZERO for o in oportunidades), ZERO),
        valor_anual=sum((o.preco_anual or ZERO for o in oportunidades), ZERO),
        sem_preco_mensal=sum(1 for o in oportunidades if o.preco_mensal is None),
    )


def calcular(oportunidades: Iterable[_Oportunidade]) -> Indicadores:
    """Soma o funil e diz o que ainda não dá para medir.

    **Em aberto** é tudo que ainda não foi decidido — o inverso de
    `Situacao.decidida`. Reaproveita o conceito do domínio em vez de listar as
    situações à mão: se a lista de situações mudar, esta conta muda junto.
    """
    todas = list(oportunidades)
    em_aberto = [o for o in todas if not o.situacao.decidida]
    decididas = [o for o in todas if o.situacao.decidida]
    aceitas = [o for o in todas if o.situacao.ganha]
    com_data = sum(1 for o in aceitas if o.data_aceite is not None)

    dias_por_aceita = [
        (o.data_aceite - o.data_colocacao).days
        for o in aceitas
        if o.data_aceite is not None and o.data_colocacao is not None
    ]
    ciclo = CicloMedioDeVendas(
        dias=(
            (Decimal(sum(dias_por_aceita)) / Decimal(len(dias_por_aceita))).quantize(
                Decimal("0.1")
            )
            if dias_por_aceita
            else None
        ),
        amostra=len(dias_por_aceita),
        aceitas_sem_as_duas_datas=len(aceitas) - len(dias_por_aceita),
    )

    if decididas:
        percentual = (Decimal(len(aceitas)) / Decimal(len(decididas)) * 100).quantize(
            Decimal("0.1")
        )
    else:
        percentual = None
    conversao = TaxaDeConversao(
        aceitas=len(aceitas), decididas=len(decididas), percentual=percentual
    )

    com_proxima_acao = sum(
        1 for o in em_aberto if o.proxima_acao is not None and o.proxima_acao.strip() != ""
    )
    com_volumetria_completa = sum(
        1
        for o in todas
        if all(getattr(o, campo) is not None for campo in _DIRECIONADORES_DA_VOLUMETRIA)
    )
    cobertura = Cobertura(
        em_aberto_com_proxima_acao=com_proxima_acao,
        em_aberto_total=len(em_aberto),
        com_volumetria_completa=com_volumetria_completa,
        total=len(todas),
    )

    da_rede_de_socios = sum(1 for o in todas if o.tipo_canal is CANAL_DA_REDE_DE_SOCIOS)
    dependencia_de_canal = DependenciaDeCanal(
        da_rede_de_socios=da_rede_de_socios, total=len(todas)
    )

    return Indicadores(
        em_aberto=_somar(em_aberto),
        aceitas=_somar(aceitas),
        aceitas_com_data_de_aceite=com_data,
        ciclo_medio=ciclo,
        taxa_de_conversao=conversao,
        cobertura=cobertura,
        dependencia_de_canal=dependencia_de_canal,
    )
