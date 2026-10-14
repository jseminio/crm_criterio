"""Campanhas de tráfego pago: funil por canal e decisão por campanha — 13/10/2026.

Amostra aprovada por Eduardo em 13/10/2026 (aba Campanhas, em SDR · Abordagens e
conhecimento). Lógica pura, sem banco: quem chama entrega os leads de tráfego pago,
o investimento do mês por canal e o ICP alvo do Plano de MRR.

**Coorte do mês**, como no painel do SDR: entram os leads que *chegaram* no mês, e
cada um conta até a etapa mais funda que alcançou até hoje. O funil é cumulativo:
quem fechou contrato conta também como proposta, reunião, qualificado e ICP.

**Nada vira zero por falta de dado.** Custo sem investimento lançado, taxa sem base e
MRR sem preço saem como `None`, e a tela diz o que falta.

A régua de decisão é **hipótese em validação**: o volume mínimo é provisório, o ICP
alvo vem do Plano de MRR e a meta de qualificados é a do SDR (27/09/2026).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Protocol

from crm.domain.listas import MotivoDeDescarte, Situacao, TipoCanal
from crm.domain.mrr import mensalizar
from crm.domain.sdr import METAS, Contagem, Taxa, intervalo_do_mes

__all__ = [
    "FORA_DO_ICP",
    "VOLUME_MINIMO",
    "TETO_DE_CUSTO",
    "Investido",
    "LeituraDoMeta",
    "ETAPAS",
    "PainelDeCampanhas",
    "calcular_campanhas",
]

FORA_DO_ICP = {
    MotivoDeDescarte.PORTE_ABAIXO,
    MotivoDeDescarte.SEGMENTO,
    MotivoDeDescarte.ORCAMENTO,
    MotivoDeDescarte.SERVICO_PONTUAL,
}
"""Descartado por estes motivos = lead fora do perfil (ICP). Os demais contam como no ICP."""

VOLUME_MINIMO = 20
"""Leads de uma campanha no mês antes de decidir por ela. Hipótese de 13/10/2026, a rever com dados."""

TETO_DE_CUSTO = Decimal("1.5")
"""Custo por reunião da campanha acima de 1,5 × o do canal no mês = "Rever custo". Aprovado por
Eduardo em 13/10/2026 como hipótese, a rever com dados."""

ETAPAS = [
    ("leads", "Leads"),
    ("icp", "No ICP"),
    ("qualificados", "Qualificados"),
    ("reunioes", "Reuniões"),
    ("propostas", "Propostas"),
    ("contratos", "Contratos"),
]

SEM_CANAL = "sem canal"
SEM_CAMPANHA = "Sem campanha"
TOTAL = "Tráfego pago · total"

_PROPOSTA_ENVIADA = {Situacao.EM_AVALIACAO, Situacao.ON_HOLD, Situacao.ACEITA}
_CENTAVO = Decimal("0.01")


# ------------------------------------------------------------ o que entra
class OportunidadeLida(Protocol):
    situacao: Situacao
    data_envio_proposta: date | None
    preco_mensal: Decimal | None


class LeadLido(Protocol):
    criado_em: datetime
    tipo_canal: TipoCanal | None
    canal: str | None
    campanha: str | None
    motivo_descarte: MotivoDeDescarte | None
    qualificado_em: datetime | None
    reuniao_marcada_para: datetime | None
    convertido_em_id: int | None
    convertido_em: OportunidadeLida | None


# ------------------------------------------------------------ o que sai
@dataclass(frozen=True)
class EtapaDoCanal:
    chave: str
    rotulo: str
    quantidade: int
    passagem: Taxa | None
    """Quantos seguem para a etapa seguinte; `None` na última."""
    custo: Decimal | None
    """Investimento do canal ÷ quantidade; `None` sem investimento lançado ou sem ninguém na etapa."""


@dataclass(frozen=True)
class FunilDoCanal:
    canal: str
    investimento: Decimal | None
    etapas: list[EtapaDoCanal]
    mrr_novo: Decimal
    contratos_sem_preco: int
    cac: Decimal | None
    lead_a_contrato: Taxa


@dataclass(frozen=True)
class LinhaDaCampanha:
    canal: str
    campanha: str
    leads: int
    no_icp: Taxa
    qualificados: Taxa
    reunioes: int
    contratos: int
    mrr_novo: Decimal
    descartes: list[Contagem]
    decisao: str
    porque: str
    investimento: Decimal | None = None
    fonte: str | None = None
    """"lido" (Meta Ads), "digitado" ou `None` sem investimento por campanha."""
    custo_por_lead_icp: Decimal | None = None
    custo_por_reuniao: Decimal | None = None


@dataclass(frozen=True)
class Regua:
    volume_minimo: int
    icp_alvo_pct: Decimal | None
    qualificados_meta_pct: float
    qualificados_alerta_pct: float
    teto_de_custo: Decimal


@dataclass(frozen=True)
class Investido:
    """O investimento de uma campanha no mês, como está em `InvestimentoPorCampanha`."""

    canal: str
    campanha: str
    valor: Decimal
    fonte: str


@dataclass(frozen=True)
class LeituraDoMeta:
    configurada: bool
    lido_em: datetime | None


@dataclass(frozen=True)
class Pendencia:
    ok: bool
    texto: str


@dataclass(frozen=True)
class PainelDeCampanhas:
    mes: str
    leads: int
    total: FunilDoCanal | None
    canais: list[FunilDoCanal]
    campanhas: list[LinhaDaCampanha]
    regua: Regua
    prontidao: list[Pendencia]
    meta_ads: LeituraDoMeta


# ------------------------------------------------------------------ cálculo
def _utc(momento: datetime) -> datetime:
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _reais(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def _nome_do_canal(lead: LeadLido) -> str:
    return (lead.canal or "").strip() or SEM_CANAL


def _chave(canal: str, campanha: str) -> tuple[str, str]:
    """Campanha do lead e do anúncio se ligam pelo nome, sem diferença de maiúsculas e espaços."""
    junta = lambda t: " ".join(t.split()).casefold()
    return junta(canal), junta(campanha)


def _no_icp(lead: LeadLido) -> bool:
    return lead.motivo_descarte not in FORA_DO_ICP


def nivel(lead: LeadLido) -> int:
    """A etapa mais funda que o lead alcançou, pelo índice de `ETAPAS`."""
    op = lead.convertido_em
    if op is not None and op.situacao is Situacao.ACEITA:
        return 5
    if op is not None and (op.data_envio_proposta is not None or op.situacao in _PROPOSTA_ENVIADA):
        return 4
    if lead.reuniao_marcada_para is not None:
        return 3
    if lead.qualificado_em is not None or lead.convertido_em_id is not None:
        return 2
    return 1 if _no_icp(lead) else 0


def _mrr(leads: list[LeadLido]) -> tuple[Decimal, int]:
    """MRR (parcela × 13 ÷ 12) das oportunidades ganhas, e quantas ganharam sem preço mensal."""
    total, sem_preco = Decimal("0.00"), 0
    for l in leads:
        if nivel(l) == 5:
            valor = mensalizar(l.convertido_em.preco_mensal)
            if valor is None:
                sem_preco += 1
            else:
                total += valor
    return total, sem_preco


def _funil(canal: str, leads: list[LeadLido], investimento: Decimal | None) -> FunilDoCanal:
    niveis = [nivel(l) for l in leads]
    quantidades = [sum(1 for n in niveis if n >= i) for i in range(len(ETAPAS))]
    etapas = []
    for i, (chave, rotulo) in enumerate(ETAPAS):
        q = quantidades[i]
        etapas.append(EtapaDoCanal(
            chave=chave, rotulo=rotulo, quantidade=q,
            passagem=Taxa.de(quantidades[i + 1], q) if i + 1 < len(ETAPAS) else None,
            custo=_reais(investimento / q) if investimento is not None and q else None,
        ))
    mrr, sem_preco = _mrr(leads)
    contratos = quantidades[-1]
    return FunilDoCanal(
        canal=canal, investimento=investimento, etapas=etapas, mrr_novo=mrr, contratos_sem_preco=sem_preco,
        cac=_reais(investimento / contratos) if investimento is not None and contratos else None,
        lead_a_contrato=Taxa.de(contratos, quantidades[0]),
    )


def _decidir(leads: int, no_icp: Taxa, qualificados: Taxa, descartes: list[Contagem], icp_alvo: Decimal | None,
             custo_reuniao: Decimal | None, investimento: Decimal | None, reunioes: int,
             custo_do_canal: Decimal | None) -> tuple[str, str]:
    """A régua provisória (hipótese de 13/10/2026). Devolve a decisão e o porquê, em palavras."""
    if leads < VOLUME_MINIMO:
        if leads == 0 and investimento:
            return "Aguardar volume", "Nenhum lead com este nome de campanha: confira se o nome no anúncio e no lead é o mesmo."
        return "Aguardar volume", f"{leads} lead{'s' if leads != 1 else ''} no mês; a régua pede {VOLUME_MINIMO} para decidir."
    principal = descartes[0].nome if descartes else None
    icp = no_icp.valor or 0.0
    texto_icp = f"{icp:.0f}% no ICP".replace(".", ",")
    if icp_alvo is not None and icp < float(icp_alvo) and principal in {m.value for m in FORA_DO_ICP}:
        return "Refazer público", f"{texto_icp}, abaixo do alvo de {float(icp_alvo):.0f}%; o que mais tira é “{principal}”."
    if principal == MotivoDeDescarte.EXPECTATIVA.value:
        return "Ajustar criativo", "O descarte que mais aparece é “esperava outra coisa”: a promessa do anúncio não bate."
    if custo_do_canal:
        teto = custo_do_canal * TETO_DE_CUSTO
        if custo_reuniao is not None and custo_reuniao > teto:
            return "Rever custo", (f"R$ {_br(custo_reuniao)} por reunião, acima de 1,5 × a média do canal "
                                   f"(R$ {_br(custo_do_canal)}).")
        if investimento and reunioes == 0:
            return "Rever custo", f"R$ {_br(investimento)} investidos sem nenhuma reunião; o canal tem."
    meta = METAS["qualificados_pago"]
    qual = qualificados.valor or 0.0
    icp_ok = icp_alvo is None or icp >= float(icp_alvo)
    if qual >= meta.alvo and icp_ok:
        ressalva = "" if icp_alvo is not None else " Sem ICP alvo no Plano de MRR."
        return "Escalar", f"Qualifica {qual:.0f}% dos leads, na meta de {meta.alvo:.0f}%.{ressalva}"
    if qual < meta.alerta:
        return "Rever campanha", f"Qualifica {qual:.0f}% dos leads, abaixo do alerta de {meta.alerta:.0f}%."
    return "Manter e observar", f"Qualifica {qual:.0f}% dos leads, entre o alerta e a meta."


def _br(valor: Decimal) -> str:
    """R$ no formato do PAD-002, sem o símbolo: 1.248,30."""
    return f"{_reais(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _campanha(canal: str, campanha: str, leads: list[LeadLido], icp_alvo: Decimal | None,
              investido: Investido | None, custo_do_canal: Decimal | None) -> LinhaDaCampanha:
    n = len(leads)
    niveis = [nivel(l) for l in leads]
    no_icp_n = sum(1 for x in niveis if x >= 1)
    reunioes = sum(1 for x in niveis if x >= 3)
    no_icp = Taxa.de(no_icp_n, n)
    qualificados = Taxa.de(sum(1 for x in niveis if x >= 2), n)
    contagem = Counter(l.motivo_descarte.value for l in leads if l.motivo_descarte is not None)
    descartes = [Contagem(nome, q) for nome, q in sorted(contagem.items(), key=lambda kv: (-kv[1], kv[0]))]
    valor = investido.valor if investido else None
    custo_icp = _reais(valor / no_icp_n) if valor is not None and no_icp_n else None
    custo_reuniao = _reais(valor / reunioes) if valor is not None and reunioes else None
    decisao, porque = _decidir(n, no_icp, qualificados, descartes, icp_alvo, custo_reuniao, valor, reunioes,
                               custo_do_canal if valor is not None else None)
    return LinhaDaCampanha(
        canal=canal, campanha=campanha, leads=n, no_icp=no_icp, qualificados=qualificados,
        reunioes=reunioes, contratos=sum(1 for x in niveis if x >= 5),
        mrr_novo=_mrr(leads)[0], descartes=descartes, decisao=decisao, porque=porque,
        investimento=valor, fonte=investido.fonte if investido else None,
        custo_por_lead_icp=custo_icp, custo_por_reuniao=custo_reuniao,
    )


def calcular_campanhas(
    *,
    mes: str,
    leads: Iterable[LeadLido],
    midia: dict[str, Decimal] | None = None,
    icp_alvo_pct: Decimal | None = None,
    por_campanha: Iterable[Investido] = (),
    meta_ads: LeituraDoMeta | None = None,
) -> PainelDeCampanhas:
    """O painel de campanhas da coorte do mês. `leads` pode trazer outros meses e outras
    origens: só entram os de tráfego pago que chegaram no mês.

    `midia` é o investimento digitado por canal; `por_campanha`, o de cada campanha (lido ou digitado).
    Canal com campanhas investidas usa a soma delas; sem campanhas, vale o valor do canal.
    """
    meta_ads = meta_ads or LeituraDoMeta(False, None)
    inicio, fim = intervalo_do_mes(mes)
    coorte = [
        l for l in leads
        if l.tipo_canal is TipoCanal.TRAFEGO_PAGO and inicio <= _utc(l.criado_em) < fim
    ]
    investidos = {_chave(i.canal, i.campanha): i for i in por_campanha}
    midia = {k.strip(): Decimal(v) for k, v in (midia or {}).items()}
    for i in investidos.values():
        midia[i.canal.strip()] = Decimal("0")
    for i in investidos.values():
        midia[i.canal.strip()] += Decimal(i.valor)

    por_canal: dict[str, list[LeadLido]] = {}
    for l in coorte:
        por_canal.setdefault(_nome_do_canal(l), []).append(l)
    for canal in midia:
        por_canal.setdefault(canal, [])
    canais = [
        _funil(c, por_canal[c], midia.get(c))
        for c in sorted(por_canal, key=lambda c: (-len(por_canal[c]), c))
    ]
    custo_reuniao_do_canal = {_chave(f.canal, "")[0]: f.etapas[3].custo for f in canais}
    investimento_total = sum(midia.values(), Decimal("0")) if midia else None
    total = _funil(TOTAL, coorte, investimento_total) if coorte or midia else None

    grupos: dict[tuple[str, str], tuple[str, str, list[LeadLido]]] = {}
    for l in coorte:
        canal, nome = _nome_do_canal(l), (l.campanha or "").strip() or SEM_CAMPANHA
        grupos.setdefault(_chave(canal, nome), (canal, nome, []))[2].append(l)
    for chave, i in investidos.items():
        grupos.setdefault(chave, (i.canal.strip(), i.campanha.strip(), []))
    campanhas = sorted(
        (_campanha(c, n, ls, icp_alvo_pct, investidos.get(k) if n != SEM_CAMPANHA else None,
                   custo_reuniao_do_canal.get(k[0]))
         for k, (c, n, ls) in grupos.items()),
        key=lambda x: (-x.leads, -(x.investimento or 0), x.canal, x.campanha),
    )

    sem_campanha = sum(1 for l in coorte if not (l.campanha or "").strip())
    sem_investimento = [c.canal for c in canais if c.investimento is None and c.canal != SEM_CANAL]
    prontidao = [
        Pendencia(not sem_investimento,
                  "Investimento do mês lançado em todos os canais" if not sem_investimento
                  else f"Sem investimento lançado em Custos e mídia: {', '.join(sem_investimento)}"),
        Pendencia(sem_campanha == 0,
                  "Todo lead de tráfego pago tem campanha" if sem_campanha == 0
                  else f"{sem_campanha} lead(s) de tráfego pago sem campanha no cadastro"),
        Pendencia(icp_alvo_pct is not None,
                  "ICP alvo definido no Plano de MRR" if icp_alvo_pct is not None
                  else "Sem ICP alvo no Plano de MRR: a régua não julga o % no ICP"),
        Pendencia(meta_ads.configurada,
                  "Leitura do Meta Ads ligada em Configurações › Integrações" if meta_ads.configurada
                  else "Leitura do Meta Ads desligada: ligue em Configurações › Integrações"),
        Pendencia(False, "Google Ads sem leitura automática (falta o token de desenvolvedor): "
                         "digite o investimento por campanha em Custos e mídia"),
    ]
    return PainelDeCampanhas(
        mes=mes, leads=len(coorte), total=total, canais=canais, campanhas=campanhas,
        regua=Regua(VOLUME_MINIMO, icp_alvo_pct, METAS["qualificados_pago"].alvo, METAS["qualificados_pago"].alerta,
                    TETO_DE_CUSTO),
        prontidao=prontidao, meta_ads=meta_ads,
    )
