"""Indicadores do funil que a Etapa 1 consegue calcular sem decisão pendente.

**Este módulo calcula pouco de propósito.** Dos doze KPIs oficiais, só entram
aqui os que os dados de 2026 sustentam sem que ninguém tenha de escolher uma
definição. Cada um dos que ficam de fora tem um motivo registrado:

- **Ticket médio da carteira** — decisão de Eduardo em 23/09/2026: receita
  média por grupo na carteira inteira. Mas a carteira inteira **não está no
  CRM** — só as propostas de 2026. É cálculo pontual, fora daqui (mesma razão
  que já tirou o MRR de escopo). Ver `../README.md`. **Não confundir** com o
  `TicketRecorrente` abaixo, que mede só as vendas recorrentes aceitas.
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
from statistics import median
from typing import Iterable, Protocol

from crm.domain.listas import LinhaServico, Situacao, TipoCanal
from crm.domain.mrr import mensalizar

__all__ = [
    "Indicadores",
    "Recorte",
    "TaxaDeConversao",
    "CicloMedioDeVendas",
    "Cobertura",
    "DependenciaDeCanal",
    "TicketRecorrente",
    "INDICADORES_COM_COMPOSICAO",
    "ItemDaComposicao",
    "calcular",
    "composicao",
    "e_recorrente",
]

ZERO = Decimal("0.00")

#: Do KPI oficial "KPI de Head de Novos Negócios": meta 50%, alerta abaixo de 30%. São o padrão:
#: os valores que valem ficam em Configurações › Metas (02/10/2026) e chegam por `calcular`.
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
    grupo_id: int
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

    meta: Decimal = META_DE_CONVERSAO
    alerta: Decimal = ALERTA_DE_CONVERSAO

    @property
    def abaixo_do_alerta(self) -> bool | None:
        """``None`` quando não calculável — não há o que alertar sobre o vazio."""
        if self.percentual is None:
            return None
        return self.percentual < self.alerta

    @property
    def atingiu_a_meta(self) -> bool | None:
        if self.percentual is None:
            return None
        return self.percentual >= self.meta


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
    dias_ate_o_envio: Decimal | None = None
    """Originação → envio da proposta, nas aceitas com as duas datas (10/10/2026): preparar e enviar."""
    amostra_ate_o_envio: int = 0
    dias_do_envio_ao_aceite: Decimal | None = None
    """Envio → aceite, nas aceitas com as duas datas: a decisão do cliente."""
    amostra_do_envio_ao_aceite: int = 0

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
class TicketRecorrente:
    """Ticket das propostas **aceitas e recorrentes** — pedido de Eduardo em
    25/09/2026.

    Recorrente = aceita com preço mensal **maior que zero**. Consultoria de
    valor único e proposta sem preço mensal ficam fora: não têm mensalidade
    para tirar a média. Segue os filtros da tela — para "contratou em 2026",
    filtre o período pela data de colocação.

    **A média engana quando um contrato pesa muito**, e foi o que aconteceu
    aqui (um contrato de R$ 40 mil = 38% do total). Por isso a mediana vem
    junto, e `participacao_do_maior` diz quanto o maior contrato pesa.

    **Não é o ticket médio oficial da carteira** (R$ 7.407,78, decisão de
    23/09/2026): aquele é receita média por grupo na carteira inteira.
    """

    quantas: int
    clientes: int
    valor_mensal: Decimal
    ticket_medio: Decimal | None
    mediana: Decimal | None
    maior_valor: Decimal | None
    participacao_do_maior: Decimal | None

    @property
    def calculavel(self) -> bool:
        return self.ticket_medio is not None


@dataclass(frozen=True)
class Indicadores:
    em_aberto: Recorte
    aceitas: Recorte
    aceitas_com_data_de_aceite: int
    ciclo_medio: CicloMedioDeVendas
    taxa_de_conversao: TaxaDeConversao
    cobertura: Cobertura
    dependencia_de_canal: DependenciaDeCanal
    ticket_recorrente: TicketRecorrente


@dataclass(frozen=True)
class _Conjuntos:
    """Os conjuntos de que saem os números do funil. `calcular` e `composicao` usam estes mesmos, e por
    isso a lista que a tela abre é sempre a conta do número (10/10/2026)."""

    em_aberto: list
    decididas: list
    aceitas: list
    recorrentes: list
    """Ticket recorrente (09/10/2026): aceitas de serviço recorrente (C1) com preço mensal — consultoria e
    legalização são trabalhos pontuais."""


def _conjuntos(todas: list[_Oportunidade]) -> _Conjuntos:
    aceitas = [o for o in todas if o.situacao.ganha]
    return _Conjuntos(
        em_aberto=[o for o in todas if not o.situacao.decidida],
        decididas=[o for o in todas if o.situacao.decidida],
        aceitas=aceitas,
        recorrentes=[o for o in aceitas if e_recorrente(o)],
    )


def e_recorrente(o) -> bool:
    """Aceita, de serviço recorrente (C1), com preço mensal (09/10/2026). A mesma regra no ticket do card,
    nos Recortes e nos cenários de ticket (`crm.domain.recortes`, alinhado em 10/10/2026)."""
    return (o.situacao.ganha and o.preco_mensal is not None and o.preco_mensal > 0
            and getattr(o, "linha_servico", LinhaServico.C1) is LinhaServico.C1)


def _media(dias: list[int]) -> Decimal | None:
    return (Decimal(sum(dias)) / Decimal(len(dias))).quantize(Decimal("0.1")) if dias else None


def _partes_do_ciclo(aceitas: list) -> dict:
    """O ciclo em duas partes (10/10/2026): originação → envio e envio → aceite, cada uma com a sua amostra."""
    ate_envio = [(o.data_envio_proposta - o.data_colocacao).days for o in aceitas
                 if getattr(o, "data_envio_proposta", None) and o.data_colocacao]
    do_envio = [(o.data_aceite - o.data_envio_proposta).days for o in aceitas
                if getattr(o, "data_envio_proposta", None) and o.data_aceite]
    return {"dias_ate_o_envio": _media(ate_envio), "amostra_ate_o_envio": len(ate_envio),
            "dias_do_envio_ao_aceite": _media(do_envio), "amostra_do_envio_ao_aceite": len(do_envio)}


def _tem_proxima_acao(o: _Oportunidade) -> bool:
    return o.proxima_acao is not None and o.proxima_acao.strip() != ""


def _falta_na_volumetria(o: _Oportunidade) -> tuple[str, ...]:
    return tuple(campo for campo in _DIRECIONADORES_DA_VOLUMETRIA if getattr(o, campo) is None)


INDICADORES_COM_COMPOSICAO = (
    "em_aberto", "aceitas", "ticket_recorrente", "ciclo_medio", "taxa_de_conversao",
    "cobertura_proxima_acao", "cobertura_volumetria", "dependencia_de_canal", "propostas",
)
"""Os números do funil que abrem "Ver composição". `propostas` é a lista inteira (a linha de um recorte)."""


@dataclass(frozen=True)
class ItemDaComposicao:
    """Uma oportunidade na lista de um número do funil.

    `entra`: se ela conta no numerador (aceita na conversão, com próxima ação na cobertura, da rede dos
    sócios na dependência); nas listas que só somam, é sempre verdadeiro. `parte` diz isso em palavra.
    `valor`: o que a linha soma — preço mensal (Em aberto, Aceitas), MRR (ticket, × 13 ÷ 12) ou dias
    (ciclo médio). `falta`: os direcionadores da volumetria que estão vazios."""

    oportunidade: _Oportunidade
    entra: bool
    parte: str
    valor: Decimal | None = None
    anual: Decimal | None = None
    falta: tuple[str, ...] = ()


def composicao(oportunidades: Iterable[_Oportunidade], indicador: str) -> list[ItemDaComposicao]:
    """A lista que compõe um número do funil, dos mesmos conjuntos de `calcular`."""
    if indicador not in INDICADORES_COM_COMPOSICAO:
        raise ValueError(f"indicador sem composição: {indicador}")
    todas = list(oportunidades)
    c = _conjuntos(todas)
    I = ItemDaComposicao
    if indicador in ("em_aberto", "aceitas"):
        return [I(o, True, o.situacao.value, o.preco_mensal, o.preco_anual) for o in getattr(c, indicador)]
    if indicador == "propostas":
        return [I(o, o.situacao.ganha, o.situacao.value, o.preco_mensal, o.preco_anual) for o in todas]
    if indicador == "ticket_recorrente":
        return [I(o, True, o.situacao.value, mensalizar(o.preco_mensal)) for o in c.recorrentes]
    if indicador == "ciclo_medio":
        itens = []
        for o in c.aceitas:
            if o.data_aceite is not None and o.data_colocacao is not None:
                itens.append(I(o, True, "na média", Decimal((o.data_aceite - o.data_colocacao).days)))
            else:
                itens.append(I(o, False, "fora: falta a data de colocação ou de aceite"))
        return itens
    if indicador == "taxa_de_conversao":
        return [I(o, o.situacao.ganha, o.situacao.value, o.preco_mensal, o.preco_anual) for o in c.decididas]
    if indicador == "cobertura_proxima_acao":
        return [I(o, _tem_proxima_acao(o), "com próxima ação" if _tem_proxima_acao(o) else "sem próxima ação")
                for o in c.em_aberto]
    if indicador == "cobertura_volumetria":
        itens = []
        for o in todas:
            falta = _falta_na_volumetria(o)
            itens.append(I(o, not falta, "completa" if not falta else f"faltam {len(falta)} de 9", falta=falta))
        return itens
    # dependencia_de_canal
    return [I(o, o.tipo_canal is CANAL_DA_REDE_DE_SOCIOS,
              o.tipo_canal.value if o.tipo_canal is not None else "(canal não informado)") for o in todas]


def _somar(oportunidades: list[_Oportunidade]) -> Recorte:
    return Recorte(
        quantas=len(oportunidades),
        valor_mensal=sum((o.preco_mensal or ZERO for o in oportunidades), ZERO),
        valor_anual=sum((o.preco_anual or ZERO for o in oportunidades), ZERO),
        sem_preco_mensal=sum(1 for o in oportunidades if o.preco_mensal is None),
    )


def calcular(
    oportunidades: Iterable[_Oportunidade],
    meta_de_conversao: Decimal = META_DE_CONVERSAO,
    alerta_de_conversao: Decimal = ALERTA_DE_CONVERSAO,
) -> Indicadores:
    """Soma o funil e diz o que ainda não dá para medir.

    **Em aberto** é tudo que ainda não foi decidido — o inverso de
    `Situacao.decidida`. Reaproveita o conceito do domínio em vez de listar as
    situações à mão: se a lista de situações mudar, esta conta muda junto.
    """
    todas = list(oportunidades)
    c = _conjuntos(todas)
    em_aberto, decididas, aceitas = c.em_aberto, c.decididas, c.aceitas
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
        **_partes_do_ciclo(aceitas),
    )

    if decididas:
        percentual = (Decimal(len(aceitas)) / Decimal(len(decididas)) * 100).quantize(
            Decimal("0.1")
        )
    else:
        percentual = None
    conversao = TaxaDeConversao(
        aceitas=len(aceitas), decididas=len(decididas), percentual=percentual,
        meta=meta_de_conversao, alerta=alerta_de_conversao,
    )

    com_proxima_acao = sum(1 for o in em_aberto if _tem_proxima_acao(o))
    com_volumetria_completa = sum(1 for o in todas if not _falta_na_volumetria(o))
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

    centavos = Decimal("0.01")
    # Ticket recorrente (09/10/2026): só serviço recorrente (C1) — consultoria e legalização são
    # trabalhos pontuais — e em MRR, a parcela × 13 ÷ 12, como todo MRR do CRM.
    recorrentes = c.recorrentes
    mensais = [mensalizar(o.preco_mensal) for o in recorrentes]
    total_mensal = sum(mensais, ZERO)
    if mensais:
        maior = max(mensais)
        ticket = TicketRecorrente(
            quantas=len(mensais),
            clientes=len({o.grupo_id for o in recorrentes}),
            valor_mensal=total_mensal,
            ticket_medio=(total_mensal / len(mensais)).quantize(centavos),
            mediana=Decimal(median(mensais)).quantize(centavos),
            maior_valor=maior,
            participacao_do_maior=(maior / total_mensal * 100).quantize(Decimal("0.1")),
        )
    else:
        ticket = TicketRecorrente(0, 0, ZERO, None, None, None, None)

    return Indicadores(
        em_aberto=_somar(em_aberto),
        aceitas=_somar(aceitas),
        aceitas_com_data_de_aceite=com_data,
        ciclo_medio=ciclo,
        taxa_de_conversao=conversao,
        cobertura=cobertura,
        dependencia_de_canal=dependencia_de_canal,
        ticket_recorrente=ticket,
    )
