"""O SDR de IA que qualifica leads de tráfego pago e leads frios — 27/09/2026.

Lógica pura, sem banco nem rede: as metas aprovadas, as travas de cada
mensagem e o cálculo do painel.

**Coorte do mês.** O painel acompanha os leads que *chegaram* no mês
(`Lead.criado_em`) e tudo o que aconteceu com eles até agora. Assim o funil
fecha: cada lead está em exatamente uma etapa, e o que sai de uma etapa é a
soma dos motivos listados. O investimento em mídia também é mensal, então o
custo por lead compara coisas do mesmo mês.

**Nada vira zero por falta de dado.** Taxa sem denominador, média sem nota e
custo sem parâmetro saem como `None`, e a tela diz o que falta. Zero pareceria
medição.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Protocol, Sequence

from crm.domain.abordagem import fala_de_preco
from crm.domain.listas import AutorDaMensagem, DesfechoDaConversa, TipoCanal, Tom

__all__ = [
    "MES",
    "Meta",
    "METAS",
    "Taxa",
    "Contagem",
    "Painel",
    "intervalo_do_mes",
    "mes_anterior",
    "problema_na_mensagem",
    "calcular_painel",
    "ORIGEM_TRAFEGO_PAGO",
    "ORIGEM_FRIO",
]

MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

ORIGEM_TRAFEGO_PAGO = "trafego_pago"
ORIGEM_FRIO = "frio"

ROTULO_FRIO = "Leads frios"
ROTULO_OUTRAS = "Outras origens"
ROTULO_PAGO_TOTAL = "Tráfego pago · total"


# ------------------------------------------------------------------- metas
@dataclass(frozen=True)
class Meta:
    """Uma meta com seu alerta. Aprovadas por Eduardo em 27/09/2026 como
    ponto de partida, para rever depois de 60 dias ou 300 leads."""

    alvo: float
    alerta: float
    maior_e_melhor: bool
    texto: str
    """Como a tela descreve a meta: "meta de 70%", "alvo de 60 s"."""

    def avaliar(self, valor: float | None) -> str | None:
        if valor is None:
            return None
        if self.maior_e_melhor:
            if valor >= self.alvo:
                return "Na meta"
            return "Em alerta" if valor < self.alerta else "Entre a meta e o alerta"
        if valor <= self.alvo:
            return "Na meta"
        return "Em alerta" if valor > self.alerta else "Entre a meta e o alerta"


METAS: dict[str, Meta] = {
    "primeira_resposta": Meta(60, 300, False, "alvo de 60 s"),
    "qualificacao_concluida": Meta(70, 55, True, "meta de 70%"),
    "transbordo": Meta(20, 30, False, "limite de 20%"),
    "resposta_pago": Meta(60, 40, True, "meta de 60%"),
    "resposta_frio": Meta(8, 3, True, "meta de 8%"),
    "qualificados_pago": Meta(20, 10, True, "meta de 20%"),
    "qualificados_frio": Meta(3, 1, True, "meta de 3%"),
    "reuniao": Meta(60, 40, True, "meta de 60% com reunião"),
    "csat": Meta(4.0, 3.5, True, "alvo de 4,0"),
    "falhas": Meta(10, 15, False, "limite de 10%"),
    "espera": Meta(15, 60, False, "alvo de 15 min"),
    "custo_por_qualificado": Meta(300, 450, False, "teto de R$ 300"),
}


# ------------------------------------------------------ travas da mensagem
def problema_na_mensagem(texto: str) -> str | None:
    """Por que uma mensagem da IA não pode sair, ou `None` se pode.

    Decisão de Eduardo em 27/09/2026: o SDR de IA envia sozinho. As travas que
    antes eram conferidas na aprovação passam a valer em cada mensagem.
    """
    if not texto.strip():
        return "A mensagem está vazia"
    if fala_de_preco(texto):
        return "A mensagem fala de preço: a IA não informa preço, ela passa para a equipe"
    return None


# ------------------------------------------------------------------ período
def intervalo_do_mes(mes: str) -> tuple[datetime, datetime]:
    """Início e fim (exclusivo) do mês, no horário de Brasília, em UTC."""
    ano, numero = (int(p) for p in mes.split("-"))
    brasilia = timezone(timedelta(hours=-3))
    inicio = datetime(ano, numero, 1, tzinfo=brasilia)
    fim = datetime(ano + (numero == 12), numero % 12 + 1, 1, tzinfo=brasilia)
    return inicio.astimezone(timezone.utc), fim.astimezone(timezone.utc)


def mes_anterior(mes: str) -> str:
    ano, numero = (int(p) for p in mes.split("-"))
    anterior = date(ano, numero, 1) - timedelta(days=1)
    return f"{anterior.year:04d}-{anterior.month:02d}"


# ------------------------------------------------------------ o que entra
class MensagemLida(Protocol):
    autor: AutorDaMensagem
    enviada_em: datetime
    confianca: Decimal | None
    fallback: bool
    termo_nao_reconhecido: str | None
    custo_usd: Decimal | None
    tom: Tom | None


class ConversaLida(Protocol):
    iniciada_em: datetime
    encerrada_em: datetime | None
    desfecho: DesfechoDaConversa | None
    motivo_transbordo: object
    destino_transbordo: object
    atendida_em: datetime | None
    nota: int | None
    mensagens: Sequence[MensagemLida]


class LeadLido(Protocol):
    criado_em: datetime
    tipo_canal: TipoCanal | None
    canal: str | None
    interesse: str | None
    cnpj: str | None
    porte_estimado: str | None
    motivo_descarte: object
    reuniao_marcada_para: datetime | None
    convertido_em_id: int | None
    conversas: Sequence[ConversaLida]


# ------------------------------------------------------------ o que sai
@dataclass(frozen=True)
class Taxa:
    """Percentual com a conta à vista. `valor` é `None` sem denominador."""

    numerador: int
    denominador: int
    valor: float | None

    @classmethod
    def de(cls, numerador: int, denominador: int) -> "Taxa":
        return cls(numerador, denominador, 100 * numerador / denominador if denominador else None)


@dataclass(frozen=True)
class Contagem:
    nome: str
    quantidade: int


@dataclass(frozen=True)
class Indicador:
    """Um número do topo do painel com a avaliação contra a meta."""

    valor: float | None
    avaliacao: str | None = None
    meta: str | None = None


@dataclass(frozen=True)
class LinhaDeOrigem:
    origem: str
    leads: int
    responderam: Taxa
    qualificados: Taxa
    reunioes: int
    midia: Decimal | None
    custo_por_lead: Decimal | None
    custo_por_qualificado: Decimal | None
    avaliacao_resposta: str | None = None
    avaliacao_qualificados: str | None = None
    avaliacao_custo: str | None = None


@dataclass(frozen=True)
class EtapaDoFunil:
    nome: str
    leads: int
    saidas: list[Contagem]
    """Quem parou nesta etapa e por quê. Soma = esta etapa − a próxima."""


@dataclass(frozen=True)
class LinhaDeDestino:
    destino: str
    transbordos: int
    atendidos: int
    espera_media_min: float | None
    avaliacao: str | None


@dataclass(frozen=True)
class Confianca:
    media: float | None
    respostas: int
    faixas: list[Contagem]
    abaixo_de_0_6: Taxa


@dataclass(frozen=True)
class CustoPoupado:
    calculavel: bool
    falta: list[str]
    conversas_concluidas: int
    custo_por_conversa: Decimal | None
    bruto: Decimal | None
    custo_ia: Decimal | None
    liquido: Decimal | None
    mensagens_sem_custo: int


@dataclass(frozen=True)
class Resumo:
    """O que o topo compara com o mês anterior."""

    qualificados: int
    qualificacao_concluida: float | None
    transbordo: float | None
    tma_segundos: float | None
    csat: float | None


@dataclass(frozen=True)
class Painel:
    mes: str
    origem: str | None
    leads: int
    responderam: int
    com_desfecho: int
    em_andamento: int
    qualificados: int
    fora_do_perfil: int
    reunioes: int

    qualificados_sobre_leads: Taxa
    qualificados_sobre_responderam: Taxa
    qualificacao_concluida: Taxa
    transbordo: Taxa
    parou: Taxa
    reunioes_sobre_qualificados: Taxa

    indicador_qualificacao: Indicador
    indicador_transbordo: Indicador
    indicador_reuniao: Indicador
    tma_segundos: float | None
    primeira_resposta: Indicador
    """Mediana em segundos, só tráfego pago: no lead frio a IA fala primeiro."""
    csat: Indicador
    notas: int
    satisfeitos: Taxa

    por_origem: list[LinhaDeOrigem]
    interesses: list[Contagem]
    confianca: Confianca
    falhas_por_resposta: Taxa
    falhas_por_conversa: Taxa
    indicador_falhas: Indicador
    termos: list[Contagem]
    funil: list[EtapaDoFunil]
    gatilhos: list[Contagem]
    descartes: list[Contagem]
    tom: list[Contagem]
    portes: list[Contagem]
    destinos: list[LinhaDeDestino]
    com_dados_da_empresa: int
    oportunidades: int
    custo_poupado: CustoPoupado
    anterior: Resumo | None = field(default=None)


# ------------------------------------------------------------------ cálculo
_CENTAVO = Decimal("0.01")
_ORDEM_DOS_PORTES = ["Micro", "Pequeno", "Médio", "Grande", "Extra Grande"]
_FAIXAS = [
    ("0,9 a 1,0", Decimal("0.9"), Decimal("1.01")),
    ("0,8 a 0,9", Decimal("0.8"), Decimal("0.9")),
    ("0,7 a 0,8", Decimal("0.7"), Decimal("0.8")),
    ("0,6 a 0,7", Decimal("0.6"), Decimal("0.7")),
    ("abaixo de 0,6", Decimal("0"), Decimal("0.6")),
]


def _reais(valor: Decimal) -> Decimal:
    return valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP)


def _utc(momento: datetime) -> datetime:
    """SQLite devolve instantes sem fuso; o PostgreSQL, com. Tudo vira UTC."""
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def rotulo_da_origem(tipo_canal: TipoCanal | None, canal: str | None) -> str:
    if tipo_canal is TipoCanal.TRAFEGO_PAGO:
        return f"Tráfego pago · {canal.strip() if canal and canal.strip() else 'sem canal'}"
    if tipo_canal is TipoCanal.PROSPECCAO_ATIVA:
        return ROTULO_FRIO
    return ROTULO_OUTRAS


def _na_origem(lead: LeadLido, origem: str | None) -> bool:
    if origem == ORIGEM_TRAFEGO_PAGO:
        return lead.tipo_canal is TipoCanal.TRAFEGO_PAGO
    if origem == ORIGEM_FRIO:
        return lead.tipo_canal is TipoCanal.PROSPECCAO_ATIVA
    return True


def _mensagens(lead: LeadLido) -> list[MensagemLida]:
    return [m for c in lead.conversas for m in c.mensagens]


def _respondeu(lead: LeadLido) -> bool:
    return any(m.autor is AutorDaMensagem.LEAD for m in _mensagens(lead))


def _desfecho(lead: LeadLido) -> DesfechoDaConversa | None:
    """O desfecho da conversa mais recente. `None`: em andamento ou sem conversa."""
    return lead.conversas[-1].desfecho if lead.conversas else None


def _valor(item: object) -> str:
    return getattr(item, "value", None) or str(item)


def _contar(nomes: Iterable[str], ordem: list[str] | None = None) -> list[Contagem]:
    contagem = Counter(nomes)
    if ordem is not None:
        return [Contagem(n, contagem[n]) for n in ordem if contagem[n]]
    return [Contagem(n, q) for n, q in sorted(contagem.items(), key=lambda x: (-x[1], x[0]))]


def _topo(nomes: Iterable[str], quantos: int, outros: str) -> list[Contagem]:
    todas = _contar(nomes)
    if len(todas) <= quantos + 1:
        return todas
    resto = sum(c.quantidade for c in todas[quantos:])
    return todas[:quantos] + [Contagem(outros, resto)]


def _tom_da_conversa(conversa: ConversaLida) -> Tom | None:
    """O tom que mais aparece nas mensagens do lead. Empate vira neutro:
    não há como dizer que a conversa pendeu para um lado."""
    tons = Counter(
        m.tom for m in conversa.mensagens if m.autor is AutorDaMensagem.LEAD and m.tom
    )
    if not tons:
        return None
    maior = max(tons.values())
    vencedores = [t for t, q in tons.items() if q == maior]
    return vencedores[0] if len(vencedores) == 1 else Tom.NEUTRO


def _etapa(lead: LeadLido) -> int:
    """Até onde o lead chegou: 1 recebido, 2 respondeu, 3 deu os dados da
    empresa, 4 qualificado, 5 reunião marcada."""
    if not _respondeu(lead):
        return 1
    if _desfecho(lead) is DesfechoDaConversa.QUALIFICADO:
        return 5 if lead.reuniao_marcada_para else 4
    if lead.cnpj or lead.porte_estimado:
        return 3
    return 2


_MOTIVO_DA_SAIDA = {
    DesfechoDaConversa.PAROU: "pararam no meio",
    DesfechoDaConversa.TRANSBORDO: "passaram para a equipe",
    DesfechoDaConversa.FORA_DO_PERFIL: "fora do perfil",
    None: "em andamento",
}
_ORDEM_DAS_SAIDAS = [
    "não responderam", "em andamento", "pararam no meio", "passaram para a equipe",
    "fora do perfil", "ainda sem reunião",
]


def _funil(leads: list[LeadLido]) -> list[EtapaDoFunil]:
    nomes = [
        "Lead recebido ou contatado", "Respondeu à IA", "Informou os dados da empresa",
        "Qualificado", "Reunião marcada",
    ]
    etapas = [_etapa(l) for l in leads]
    funil = []
    for numero, nome in enumerate(nomes, start=1):
        parados = [l for l, e in zip(leads, etapas) if e == numero]
        if numero == 1:
            motivos = ["não responderam"] * len(parados)
        elif numero == 4:
            motivos = ["ainda sem reunião"] * len(parados)
        elif numero == 5:
            motivos = []
        else:
            motivos = [_MOTIVO_DA_SAIDA[_desfecho(l)] for l in parados]
        funil.append(
            EtapaDoFunil(
                nome=nome,
                leads=sum(1 for e in etapas if e >= numero),
                saidas=_contar(motivos, _ORDEM_DAS_SAIDAS),
            )
        )
    return funil


def _custo_por(midia: Decimal | None, quantidade: int) -> Decimal | None:
    return _reais(midia / quantidade) if midia is not None and quantidade else None


def _por_origem(leads: list[LeadLido], midia: dict[str, Decimal]) -> list[LinhaDeOrigem]:
    grupos: dict[str, list[LeadLido]] = {}
    for lead in leads:
        grupos.setdefault(rotulo_da_origem(lead.tipo_canal, lead.canal), []).append(lead)
    for canal in midia:
        grupos.setdefault(rotulo_da_origem(TipoCanal.TRAFEGO_PAGO, canal), [])

    def linha(nome: str, grupo: list[LeadLido], gasto: Decimal | None, tipo: str | None):
        responderam = sum(1 for l in grupo if _respondeu(l))
        qualificados = sum(1 for l in grupo if _desfecho(l) is DesfechoDaConversa.QUALIFICADO)
        taxa_resposta = Taxa.de(responderam, len(grupo))
        taxa_qualificados = Taxa.de(qualificados, len(grupo))
        custo_q = _custo_por(gasto, qualificados)
        return LinhaDeOrigem(
            origem=nome,
            leads=len(grupo),
            responderam=taxa_resposta,
            qualificados=taxa_qualificados,
            reunioes=sum(1 for l in grupo if _etapa(l) == 5),
            midia=gasto,
            custo_por_lead=_custo_por(gasto, len(grupo)),
            custo_por_qualificado=custo_q,
            avaliacao_resposta=METAS[f"resposta_{tipo}"].avaliar(taxa_resposta.valor) if tipo else None,
            avaliacao_qualificados=(
                METAS[f"qualificados_{tipo}"].avaliar(taxa_qualificados.valor) if tipo else None
            ),
            avaliacao_custo=(
                METAS["custo_por_qualificado"].avaliar(float(custo_q)) if custo_q is not None else None
            ),
        )

    linhas = []
    pagos = sorted(n for n in grupos if n.startswith("Tráfego pago · "))
    for nome in pagos:
        canal = nome.removeprefix("Tráfego pago · ")
        linhas.append(linha(nome, grupos[nome], midia.get(canal), "pago"))
    if len(pagos) > 1:
        todos = [l for n in pagos for l in grupos[n]]
        gastos = [midia[c] for c in midia]
        linhas.append(linha(ROTULO_PAGO_TOTAL, todos, sum(gastos, Decimal(0)) if gastos else None, "pago"))
    if ROTULO_FRIO in grupos:
        linhas.append(linha(ROTULO_FRIO, grupos[ROTULO_FRIO], None, "frio"))
    if ROTULO_OUTRAS in grupos:
        linhas.append(linha(ROTULO_OUTRAS, grupos[ROTULO_OUTRAS], None, None))
    return linhas


def _confianca(respostas: list[MensagemLida]) -> Confianca:
    valores = [m.confianca for m in respostas if m.confianca is not None]
    faixas = [
        Contagem(nome, sum(1 for v in valores if de <= v < ate)) for nome, de, ate in _FAIXAS
    ]
    return Confianca(
        media=float(sum(valores) / len(valores)) if valores else None,
        respostas=len(valores),
        faixas=faixas if valores else [],
        abaixo_de_0_6=Taxa.de(sum(1 for v in valores if v < Decimal("0.6")), len(valores)),
    )


def _destinos(conversas: list[ConversaLida]) -> list[LinhaDeDestino]:
    transbordos = [c for c in conversas if c.desfecho is DesfechoDaConversa.TRANSBORDO]
    por_destino: dict[str, list[ConversaLida]] = {}
    for conversa in transbordos:
        destino = _valor(conversa.destino_transbordo) if conversa.destino_transbordo else "Sem destino"
        por_destino.setdefault(destino, []).append(conversa)
    linhas = []
    for destino, grupo in sorted(por_destino.items(), key=lambda x: (-len(x[1]), x[0])):
        esperas = [
            (_utc(c.atendida_em) - _utc(c.encerrada_em)).total_seconds() / 60
            for c in grupo
            if c.atendida_em and c.encerrada_em
        ]
        media = sum(esperas) / len(esperas) if esperas else None
        linhas.append(
            LinhaDeDestino(
                destino=destino,
                transbordos=len(grupo),
                atendidos=len(esperas),
                espera_media_min=media,
                avaliacao=METAS["espera"].avaliar(media),
            )
        )
    return linhas


def _custo_poupado(
    concluidas: int,
    respostas_da_ia: list[MensagemLida],
    custo_hora_sdr: Decimal | None,
    minutos_por_conversa: int | None,
    cotacao_dolar: Decimal | None,
) -> CustoPoupado:
    falta = []
    if custo_hora_sdr is None:
        falta.append("o custo de uma hora de SDR")
    if minutos_por_conversa is None:
        falta.append("os minutos que um SDR levaria por conversa")
    if cotacao_dolar is None:
        falta.append("a cotação do dólar")
    sem_custo = sum(1 for m in respostas_da_ia if m.custo_usd is None)
    custo_usd = sum((m.custo_usd for m in respostas_da_ia if m.custo_usd is not None), Decimal(0))
    custo_ia = _reais(custo_usd * cotacao_dolar) if cotacao_dolar is not None else None
    por_conversa = (
        _reais(custo_hora_sdr * minutos_por_conversa / 60)
        if custo_hora_sdr is not None and minutos_por_conversa is not None
        else None
    )
    bruto = _reais(por_conversa * concluidas) if por_conversa is not None else None
    return CustoPoupado(
        calculavel=not falta,
        falta=falta,
        conversas_concluidas=concluidas,
        custo_por_conversa=por_conversa,
        bruto=bruto,
        custo_ia=custo_ia,
        liquido=bruto - custo_ia if bruto is not None and custo_ia is not None else None,
        mensagens_sem_custo=sem_custo,
    )


def calcular_painel(
    *,
    mes: str,
    leads: Iterable[LeadLido],
    midia: dict[str, Decimal] | None = None,
    origem: str | None = None,
    custo_hora_sdr: Decimal | None = None,
    minutos_por_conversa: int | None = None,
    cotacao_dolar: Decimal | None = None,
    anterior: Resumo | None = None,
) -> Painel:
    """O painel da coorte do mês. `leads` pode trazer leads de outros meses:
    só entram os que chegaram no mês e passam pelo filtro de origem.

    `midia` é o investimento do mês por canal de tráfego pago. Com o filtro de
    leads frios ele não entra: lead frio não tem mídia.
    """
    inicio, fim = intervalo_do_mes(mes)
    coorte = [
        l for l in leads if inicio <= _utc(l.criado_em) < fim and _na_origem(l, origem)
    ]
    midia = {} if origem == ORIGEM_FRIO else dict(midia or {})

    responderam = [l for l in coorte if _respondeu(l)]
    desfechos = [_desfecho(l) for l in responderam]
    com_desfecho = [d for d in desfechos if d is not None]
    contar = Counter(com_desfecho)
    qualificados = contar[DesfechoDaConversa.QUALIFICADO]
    fora = contar[DesfechoDaConversa.FORA_DO_PERFIL]
    veredito = qualificados + fora
    reunioes = sum(1 for l in coorte if _etapa(l) == 5)

    conversas = [c for l in coorte for c in l.conversas]
    mensagens = [m for c in conversas for m in c.mensagens]
    respostas_da_ia = [m for m in mensagens if m.autor is AutorDaMensagem.IA]

    # Tempo de qualificação: só o que a IA concluiu sozinha.
    duracoes = [
        (_utc(c.encerrada_em) - _utc(c.iniciada_em)).total_seconds()
        for c in conversas
        if c.desfecho is not None and c.desfecho.veredito_da_ia and c.encerrada_em
    ]
    tma = sum(duracoes) / len(duracoes) if duracoes else None

    # Primeira resposta: da chegada do lead de tráfego pago à primeira mensagem da IA.
    esperas = []
    for lead in coorte:
        if lead.tipo_canal is not TipoCanal.TRAFEGO_PAGO:
            continue
        da_ia = [_utc(m.enviada_em) for m in _mensagens(lead) if m.autor is AutorDaMensagem.IA]
        if da_ia:
            esperas.append(max(0.0, (min(da_ia) - _utc(lead.criado_em)).total_seconds()))
    primeira = statistics.median(esperas) if esperas else None

    notas = [c.nota for c in conversas if c.nota is not None]
    csat = sum(notas) / len(notas) if notas else None

    # Só conversa em que o lead respondeu: sem resposta não há o que entender.
    conversas_com_resposta = [
        c for c in conversas if any(m.autor is AutorDaMensagem.LEAD for m in c.mensagens)
    ]
    falhas_por_conversa = Taxa.de(
        sum(1 for c in conversas_com_resposta if any(m.fallback for m in c.mensagens)),
        len(conversas_com_resposta),
    )

    taxa_concluida = Taxa.de(veredito, len(com_desfecho))
    taxa_transbordo = Taxa.de(contar[DesfechoDaConversa.TRANSBORDO], len(com_desfecho))
    taxa_reuniao = Taxa.de(reunioes, qualificados)

    tons = [_tom_da_conversa(c) for c in conversas]
    return Painel(
        mes=mes,
        origem=origem,
        leads=len(coorte),
        responderam=len(responderam),
        com_desfecho=len(com_desfecho),
        em_andamento=len(desfechos) - len(com_desfecho),
        qualificados=qualificados,
        fora_do_perfil=fora,
        reunioes=reunioes,
        qualificados_sobre_leads=Taxa.de(qualificados, len(coorte)),
        qualificados_sobre_responderam=Taxa.de(qualificados, len(responderam)),
        qualificacao_concluida=taxa_concluida,
        transbordo=taxa_transbordo,
        parou=Taxa.de(contar[DesfechoDaConversa.PAROU], len(com_desfecho)),
        reunioes_sobre_qualificados=taxa_reuniao,
        indicador_qualificacao=Indicador(
            taxa_concluida.valor,
            METAS["qualificacao_concluida"].avaliar(taxa_concluida.valor),
            METAS["qualificacao_concluida"].texto,
        ),
        indicador_transbordo=Indicador(
            taxa_transbordo.valor,
            METAS["transbordo"].avaliar(taxa_transbordo.valor),
            METAS["transbordo"].texto,
        ),
        indicador_reuniao=Indicador(
            taxa_reuniao.valor, METAS["reuniao"].avaliar(taxa_reuniao.valor), METAS["reuniao"].texto
        ),
        tma_segundos=tma,
        primeira_resposta=Indicador(
            primeira, METAS["primeira_resposta"].avaliar(primeira), METAS["primeira_resposta"].texto
        ),
        csat=Indicador(csat, METAS["csat"].avaliar(csat), METAS["csat"].texto),
        notas=len(notas),
        satisfeitos=Taxa.de(sum(1 for n in notas if n >= 4), len(notas)),
        por_origem=_por_origem(coorte, midia),
        interesses=_topo(
            ((l.interesse or "").strip() or "Sem assunto reconhecido" for l in responderam),
            6,
            "Outros assuntos",
        ),
        confianca=_confianca(respostas_da_ia),
        falhas_por_resposta=Taxa.de(sum(1 for m in respostas_da_ia if m.fallback), len(respostas_da_ia)),
        falhas_por_conversa=falhas_por_conversa,
        indicador_falhas=Indicador(
            falhas_por_conversa.valor,
            METAS["falhas"].avaliar(falhas_por_conversa.valor),
            METAS["falhas"].texto,
        ),
        termos=_contar(
            m.termo_nao_reconhecido.strip().casefold()
            for m in respostas_da_ia
            if m.termo_nao_reconhecido and m.termo_nao_reconhecido.strip()
        )[:10],
        funil=_funil(coorte),
        gatilhos=_contar(
            _valor(c.motivo_transbordo) if c.motivo_transbordo else "Sem motivo registrado"
            for c in conversas
            if c.desfecho is DesfechoDaConversa.TRANSBORDO
        ),
        descartes=_contar(
            _valor(l.motivo_descarte) if l.motivo_descarte else "Sem motivo registrado"
            for l in responderam
            if _desfecho(l) is DesfechoDaConversa.FORA_DO_PERFIL
        ),
        tom=_contar(
            (t.value for t in tons if t is not None), [t.value for t in Tom]
        ),
        portes=_contar(
            (
                l.porte_estimado or "Sem porte"
                for l in responderam
                if _desfecho(l) is DesfechoDaConversa.QUALIFICADO
            ),
            _ORDEM_DOS_PORTES + ["Sem porte"],
        ),
        destinos=_destinos(conversas),
        com_dados_da_empresa=sum(1 for l in coorte if l.cnpj or l.porte_estimado),
        oportunidades=sum(1 for l in coorte if l.convertido_em_id is not None),
        custo_poupado=_custo_poupado(
            veredito, respostas_da_ia, custo_hora_sdr, minutos_por_conversa, cotacao_dolar
        ),
        anterior=anterior,
    )


def resumir(painel: Painel) -> Resumo:
    return Resumo(
        qualificados=painel.qualificados,
        qualificacao_concluida=painel.qualificacao_concluida.valor,
        transbordo=painel.transbordo.valor,
        tma_segundos=painel.tma_segundos,
        csat=painel.csat.valor,
    )
