"""KPIs da liderança (amostra aprovada por Eduardo em 09/10/2026): os cinco indicadores da planilha
"CRITÉRIO — KPIs de mercado" (linhas 17 a 21), calculados no CRM, mês a mês. **Só o Administrador.**

Todo valor é MRR: a parcela × 13 ÷ 12, em bruto (`crm.domain.mrr.em_bruto`). Cada KPI diz o que
entrou na conta e, quando falta registro para ele valer, o que falta — nunca um zero inventado.

- **20 · MRR novo no mês:** soma do MRR dos contratos recorrentes que começaram no mês, da carteira
  inteira (inclusive os carregados da carteira anterior). É o "novo" do movimento de MRR.
- **19 · Ticket:** o MRR novo do mês dividido por **grupo** e por **CNPJ**; o acumulado do ano vai junto.
  As propostas recorrentes aceitas no mês sem contrato aparecem como pendência, fora da conta.
- **18 · Upsell sobre o MRR:** recorrente (expansão e aditivo + contrato novo de quem já era cliente) e
  não recorrente (consultoria e legalização aceitas por quem já era cliente), cada um sobre o MRR do
  fim do mês anterior. Meta: 10% (09/10/2026).
- **17 · Churn da base no ano** (coorte, decisão de Eduardo em 13/10/2026): clientes (grupos) da base de
  31/12 do ano anterior que pediram para encerrar o último contrato no ano, até o fim do mês, sobre a
  base; ao lado, o MRR que eles tinham sobre o MRR da base. O baseline é o churn do ano anterior — sem
  encerramentos daquele ano no CRM, fica "sem dado".
- **17b · Churn de novos no ano:** quem entrou no ano (fora da base) e já pediu para sair. À parte, para
  não distorcer a coorte, e sem sumir: é sinal de venda ou implantação.
- **21 · Cobertura de relacionamento:** clientes com classe que tiveram a reunião **realizada** dentro da
  janela da cadência da classe (A: 1 mês, B: 3 meses, C: 6 meses) até o fim do mês. Diferente do "em dia"
  do Funil do Sucesso, que dá carência a quem entrou no funil: aqui só conta reunião registrada.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from decimal import Decimal
from statistics import median

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from crm.acesso.auditoria import usuario_atual
from crm.api import sucesso
from crm.api.classificacao import parametros_vigentes
from crm.db.modelos import Contrato, GrupoEconomico, Oportunidade
from crm.domain import mrr as regras_de_mrr
from crm.domain.eventos_de_contrato import encerramento_vigente, saida_vigente
from crm.domain import sucesso as regras_do_sucesso
from crm.domain.listas import LinhaServico, Situacao, SituacaoContrato, TipoDeEventoDeContrato

__all__ = ["roteador_de_kpis", "calcular"]

ZERO = Decimal("0.00")
CENTAVOS = Decimal("0.01")
META_DE_UPSELL = Decimal("10")
"""% do MRR do mês anterior (decisão de Eduardo, 09/10/2026)."""


class Item(BaseModel):
    grupo: str
    detalhe: str
    valor: Decimal
    entra: bool = True
    """Conta no numerador do KPI (10/10/2026). Fora: a base do churn, quem ficou sem reunião na cobertura."""
    secao: str | None = None
    """O bloco da composição em que o item aparece (13/10/2026): no churn, "saiu no ano" e "os demais da base"."""


class Kpi(BaseModel):
    chave: str
    titulo: str
    valor: Decimal | None
    """`None` = sem dado: não há como calcular com o que está registrado."""
    unidade: str
    """"R$" ou "%" ou "clientes"."""
    resumo: str
    falta: list[str]
    """O que falta registrar para o KPI valer por inteiro. Vazio = completo."""
    meta: str | None = None
    extras: dict[str, Decimal | int | str | None] = {}
    itens: list[Item] = []
    """A composição do número ("Ver composição", 10/10/2026): o que entrou na conta, e o que ficou fora."""
    explicacao: str = ""
    """Como o número é calculado: aparece ao passar o mouse."""


class KpisResposta(BaseModel):
    mes: str
    de: date
    ate: date
    kpis: list[Kpi]


def _intervalo(mes: str) -> tuple[date, date]:
    ano, numero = (int(p) for p in mes.split("-"))
    return date(ano, numero, 1), date(ano, numero, calendar.monthrange(ano, numero)[1])


def _pct(parte: Decimal, todo: Decimal) -> Decimal | None:
    return (parte / todo * 100).quantize(Decimal("0.1")) if todo > 0 else None


def _reais(v: Decimal) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _encerramento(c, pelo_anuncio: bool = False) -> date | None:
    """A data do encerramento que vale: a saída efetiva (o MRR cai nela) ou, com `pelo_anuncio`, o dia em que o
    cliente pediu para sair — o indicador de churn conta no anúncio (decisão de Eduardo em 11/10/2026)."""
    if pelo_anuncio:
        ev = encerramento_vigente(c)
        return ev.data_do_evento if ev is not None else None
    return saida_vigente(c)


def _valendo_em(c, dia: date, pelo_anuncio: bool = False) -> bool:
    """O contrato estava valendo ao fim de `dia`: começou até ali (ou é da carteira anterior, sem data) e
    não tinha sido encerrado. Aguardando assinatura não vale. Com `pelo_anuncio`, o contrato em aviso de saída já
    não vale: é o que o churn de clientes usa."""
    if c.situacao is SituacaoContrato.AGUARDANDO_ASSINATURA:
        return False
    if c.data_inicio is not None and c.data_inicio > dia:
        return False
    fim = _encerramento(c, pelo_anuncio)
    if fim is not None:
        return fim > dia
    return c.situacao is not SituacaoContrato.ENCERRADO


def _cnpj_do(c) -> str:
    if c.empresa is not None:
        return c.empresa.nome_fantasia or c.empresa.razao_social
    return "sem CNPJ"


def calcular(sessao: Session, mes: str, hoje: date) -> KpisResposta:
    de, ate_do_mes = _intervalo(mes)
    if de > hoje:
        raise HTTPException(422, "o mês ainda não começou")
    ate = min(ate_do_mes, hoje)
    imposto = parametros_vigentes(sessao)[1].imposto
    originais = list(sessao.scalars(sa.select(Contrato).options(selectinload(Contrato.eventos), selectinload(Contrato.empresa))))
    bruto = {c.id: c for c in regras_de_mrr.em_bruto(originais, imposto)}
    nomes = dict(sessao.execute(sa.select(GrupoEconomico.id, GrupoEconomico.nome)).all())
    mov = regras_de_mrr.movimento(list(bruto.values()), de, ate, hoje)
    mrr_anterior = mov.mrr_inicio

    # ------------------------------------------------ 20 e 19: MRR novo e ticket
    def novos_entre(a: date, b: date) -> list[tuple[Contrato, Decimal]]:
        lista = []
        for c in originais:
            if c.data_inicio is None or not (a <= c.data_inicio <= b):
                continue
            if c.situacao is SituacaoContrato.AGUARDANDO_ASSINATURA:
                continue
            valor = regras_de_mrr._preco_inicial(bruto[c.id])
            if valor and valor > 0:
                lista.append((c, valor))
        return lista

    novos = novos_entre(de, ate)
    total_novo = sum((v for _, v in novos), ZERO)
    itens_novos = [Item(grupo=nomes.get(c.grupo_id, "?"), detalhe=(c.escopo or "contrato"), valor=v) for c, v in novos]
    aceitas_sem_contrato = list(sessao.scalars(
        sa.select(Oportunidade).where(
            Oportunidade.situacao == Situacao.ACEITA, Oportunidade.data_aceite.between(de, ate),
            Oportunidade.linha_servico == LinhaServico.C1, Oportunidade.preco_mensal > 0,
            ~sa.exists().where(Contrato.oportunidade_id == Oportunidade.id),
        )
    ))
    pendente = sum((regras_de_mrr.mensalizar(o.preco_mensal) for o in aceitas_sem_contrato), ZERO)
    falta_contrato = (
        [f"{len(aceitas_sem_contrato)} proposta(s) recorrente(s) aceita(s) no mês sem contrato "
         f"({_reais(pendente)}/mês): cadastre o contrato para entrar"] if aceitas_sem_contrato else []
    )

    kpi20 = Kpi(
        chave="mrr_novo", titulo="20 · MRR novo no mês", valor=total_novo, unidade="R$",
        resumo=f"{len(novos)} contrato(s) recorrente(s) começaram no mês, já com a 13ª parcela",
        falta=falta_contrato, meta="Fixar após o baseline", itens=itens_novos,
        explicacao="Soma do MRR (parcela × 13 ÷ 12, em bruto) dos contratos recorrentes com início no mês, da carteira "
                   "inteira. Proposta aceita sem contrato não entra: aparece em Falta.",
    )

    def ticket(lista: list[tuple[Contrato, Decimal]]) -> dict[str, Decimal | int | None]:
        por_grupo: dict[int, Decimal] = {}
        por_cnpj: dict[str, Decimal] = {}
        for c, v in lista:
            por_grupo[c.grupo_id] = por_grupo.get(c.grupo_id, ZERO) + v
            cnpj = f"e{c.empresa_id}" if c.empresa_id else f"c{c.id}"  # sem CNPJ: o contrato conta sozinho
            por_cnpj[cnpj] = por_cnpj.get(cnpj, ZERO) + v
        total = sum(por_grupo.values(), ZERO)
        return {
            "grupos": len(por_grupo), "cnpjs": len(por_cnpj),
            "por_grupo": (total / len(por_grupo)).quantize(CENTAVOS) if por_grupo else None,
            "mediana_por_grupo": Decimal(median(por_grupo.values())).quantize(CENTAVOS) if por_grupo else None,
            "por_cnpj": (total / len(por_cnpj)).quantize(CENTAVOS) if por_cnpj else None,
            "mediana_por_cnpj": Decimal(median(por_cnpj.values())).quantize(CENTAVOS) if por_cnpj else None,
        }

    do_mes = ticket(novos)
    do_ano = ticket(novos_entre(date(de.year, 1, 1), ate))
    sem_cnpj = sum(1 for c, _ in novos if not c.empresa_id)
    kpi19 = Kpi(
        chave="ticket", titulo="19 · Ticket médio mensal", valor=do_mes["por_grupo"], unidade="R$",
        resumo=f"Por grupo, no mês ({do_mes['grupos']} grupo(s), {do_mes['cnpjs']} CNPJ(s))",
        falta=falta_contrato + ([f"{sem_cnpj} contrato(s) sem CNPJ: contam como um CNPJ cada"] if sem_cnpj else []),
        meta="Crescendo sem elevar a concentração",
        extras={**{f"mes_{k}": v for k, v in do_mes.items()}, **{f"ano_{k}": v for k, v in do_ano.items()}},
        itens=[Item(grupo=nomes.get(c.grupo_id, "?"),
                    detalhe=f"{c.escopo or 'contrato'} · {_cnpj_do(c)}", valor=v) for c, v in novos],
        explicacao="MRR novo do mês ÷ número de grupos (e ÷ número de CNPJs) que o geraram. Empresas do mesmo grupo "
                   "contam como um grupo; contrato sem CNPJ conta como um CNPJ. O acumulado do ano vai na linha de baixo.",
    )

    # ------------------------------------------------ 18: upsell
    def era_cliente(grupo_id: int, dia: date, exceto: int | None = None) -> bool:
        return any(c.grupo_id == grupo_id and c.id != exceto and _valendo_em(c, dia) for c in originais)

    expansao = mov.expansao
    itens_de_expansao = [i for i in regras_de_mrr.itens_do_movimento(list(bruto.values()), de, ate) if i.categoria == "expansao"]
    cross_rec = [(c, v) for c, v in novos if era_cliente(c.grupo_id, de - timedelta(days=1), exceto=c.id)]
    recorrente = expansao + sum((v for _, v in cross_rec), ZERO)
    pontuais = [
        o for o in sessao.scalars(sa.select(Oportunidade).where(
            Oportunidade.situacao == Situacao.ACEITA, Oportunidade.data_aceite.between(de, ate),
            Oportunidade.linha_servico == LinhaServico.C2,
        ))
        if era_cliente(o.grupo_id, o.data_aceite)
    ]
    nao_recorrente = sum(((o.preco_anual or o.preco_mensal or ZERO) for o in pontuais), ZERO)
    total_upsell = recorrente + nao_recorrente
    eventos_no_mes = sum(1 for c in originais for e in c.eventos
                         if de <= e.data_do_evento <= ate and e.tipo is not TipoDeEventoDeContrato.CORRECAO)
    kpi18 = Kpi(
        chave="upsell", titulo="18 · Upsell sobre o MRR", valor=_pct(total_upsell, mrr_anterior), unidade="%",
        resumo=f"Sobre o MRR do fim do mês anterior ({_reais(mrr_anterior)})",
        falta=([] if eventos_no_mes else ["Nenhum aditivo ou expansão registrado no mês (Contratos › eventos)"]),
        meta=f"{META_DE_UPSELL}% do MRR do mês anterior",
        extras={"recorrente": recorrente, "recorrente_pct": _pct(recorrente, mrr_anterior),
                "nao_recorrente": nao_recorrente, "nao_recorrente_pct": _pct(nao_recorrente, mrr_anterior),
                "expansao": expansao, "contratos_de_clientes": len(cross_rec), "pontuais": len(pontuais)},
        itens=[Item(grupo=nomes.get(i.grupo_id, "?"), detalhe=f"expansão ou aditivo em {i.data:%d/%m}", valor=i.valor)
               for i in itens_de_expansao]
        + [Item(grupo=nomes.get(c.grupo_id, "?"), detalhe="novo contrato recorrente", valor=v) for c, v in cross_rec]
        + [Item(grupo=nomes.get(o.grupo_id, "?"), detalhe=f"{o.servico} (pontual)", valor=o.preco_anual or o.preco_mensal or ZERO)
           for o in pontuais],
        explicacao="Recorrente: expansões e aditivos do mês + contratos recorrentes novos de quem já era cliente (MRR). "
                   "Não recorrente: consultoria e legalização aceitas no mês por quem já era cliente (valor do serviço). "
                   "Cada um sobre o MRR do fim do mês anterior.",
    )

    # ------------------------------------------------ 17 e 17b: churn no ano
    # Por coorte (decisão de Eduardo em 13/10/2026): a base é a carteira de 31/12 do ano anterior e o churn é o que
    # dela saiu no ano, até o fim do mês. Quem entrou e saiu no mesmo ano não some: vai para o 17b, à parte.
    # Conta no **anúncio** (11/10/2026): o cliente pediu para sair, apesar de o MRR seguir até a saída efetiva. O MRR,
    # o movimento e o NRR/GRR seguem pela saída. Encerrar um contrato de quem tem outro não é churn de cliente: é
    # contração, que fica no GRR e no Plano de MRR.
    churn_valendo = lambda c, dia: _valendo_em(c, dia, pelo_anuncio=True)
    base_dia = date(de.year - 1, 12, 31)
    inicio_do_ano = date(de.year, 1, 1)
    por_grupo: dict[int, list[Contrato]] = {}
    for c in originais:
        por_grupo.setdefault(c.grupo_id, []).append(c)

    def cliente_em(g: int, dia: date) -> bool:
        return any(churn_valendo(c, dia) for c in por_grupo[g])

    def mrr_do_grupo(g: int, dia: date) -> Decimal:
        return sum(((regras_de_mrr.preco_em(bruto[c.id], dia) or ZERO) for c in por_grupo[g] if churn_valendo(c, dia)),
                   ZERO)

    def anuncio_e_saida(g: int) -> tuple[date, date] | None:
        """Do último contrato do grupo: quando o cliente pediu e quando sai de fato."""
        datas = [(ev.data_do_evento, ev.data_da_saida or ev.data_do_evento)
                 for c in por_grupo[g] if (ev := encerramento_vigente(c)) is not None and ev.data_do_evento <= ate]
        return max(datas) if datas else None

    def mrr_que_saiu(g: int) -> Decimal:
        """O MRR do grupo na véspera do pedido de saída (o que vai sair)."""
        datas = anuncio_e_saida(g)
        if datas is None:
            return ZERO
        valor = mrr_do_grupo(g, datas[0] - timedelta(days=1))
        if valor == 0:  # pediu no dia em que começou: vale o preço do contrato
            valor = sum(((regras_de_mrr.preco_em(bruto[c.id], datas[0]) or ZERO) for c in por_grupo[g]
                         if encerramento_vigente(c) is not None), ZERO)
        return valor.quantize(CENTAVOS)

    def no_mes(g: int) -> bool:
        datas = anuncio_e_saida(g)
        return datas is not None and de <= datas[0] <= ate

    def detalhe_da_saida(g: int) -> str:
        datas = anuncio_e_saida(g)
        if datas is None:
            return "perdeu o último contrato"
        return f"anunciou em {datas[0]:%d/%m/%Y} · sai em {datas[1]:%d/%m/%Y}" + (" · no mês" if no_mes(g) else "")

    nome = lambda g: nomes.get(g, "?")
    base = sorted((g for g in por_grupo if cliente_em(g, base_dia)), key=nome)
    perdidos_base = [g for g in base if not cliente_em(g, ate)]
    perdidos_base_mes = [g for g in perdidos_base if cliente_em(g, de - timedelta(days=1))]
    mrr_da_base = sum((mrr_do_grupo(g, base_dia) for g in base), ZERO).quantize(CENTAVOS)
    mrr_perdido = sum((mrr_que_saiu(g) for g in perdidos_base), ZERO)
    mrr_perdido_mes = sum((mrr_que_saiu(g) for g in perdidos_base_mes), ZERO)
    ano_anterior = [c for c in originais if (d := _encerramento(c, pelo_anuncio=True)) and d.year == de.year - 1]

    secao_saiu = f"Base de {base_dia:%d/%m/%Y} que saiu em {de.year}"
    secao_ficou = "Os demais clientes da base"
    kpi17 = Kpi(
        chave="churn", titulo="17 · Churn da base no ano",
        valor=_pct(Decimal(len(perdidos_base)), Decimal(len(base))) if base else None,
        unidade="%",
        resumo=f"{len(perdidos_base)} de {len(base)} cliente(s) da base de {base_dia:%d/%m/%Y} anunciaram a saída em "
               f"{de.year}",
        falta=([] if ano_anterior else [f"Os clientes perdidos em {de.year - 1}, para o baseline (contrato encerrado com a data)"]),
        meta=f"Abaixo do baseline de {de.year - 1} em 20%",
        extras={"perdidos_no_ano": len(perdidos_base), "base": len(base), "perdidos_no_mes": len(perdidos_base_mes),
                "mrr_perdido": mrr_perdido, "mrr_perdido_pct": _pct(mrr_perdido, mrr_da_base),
                "mrr_da_base": mrr_da_base, "mrr_perdido_no_mes": mrr_perdido_mes},
        itens=[Item(grupo=nome(g), detalhe=detalhe_da_saida(g), valor=mrr_que_saiu(g), secao=secao_saiu)
               for g in perdidos_base]
        + [Item(grupo=nome(g), detalhe=f"na base de {base_dia:%d/%m/%Y}", valor=mrr_do_grupo(g, base_dia).quantize(CENTAVOS),
                entra=False, secao=secao_ficou)
           for g in base if g not in perdidos_base],
        explicacao=f"Churn da base: clientes (grupos) com contrato valendo em {base_dia:%d/%m/%Y} que pediram para encerrar "
                   f"o último contrato entre 01/01/{de.year} e o fim do mês ÷ clientes da base. Ao lado, o MRR que eles "
                   f"tinham ÷ o MRR da base em {base_dia:%d/%m/%Y}. Conta no anúncio, mesmo com o MRR seguindo até a "
                   "saída efetiva. Encerrar um contrato de quem tem outro não conta: é contração, que fica no GRR e no "
                   f"Plano de MRR. Quem entrou e saiu em {de.year} está no 17b.",
    )

    # 17b: quem virou cliente no ano (fora da base) e já pediu para sair. Sinal de venda ou implantação.
    def inicio_no_ano(g: int) -> date | None:
        datas = [c.data_inicio for c in por_grupo[g] if c.data_inicio is not None and inicio_do_ano <= c.data_inicio <= ate
                 and c.situacao is not SituacaoContrato.AGUARDANDO_ASSINATURA]
        return min(datas) if datas else None

    novos = sorted((g for g in por_grupo if g not in set(base) and inicio_no_ano(g) is not None), key=nome)
    perdidos_novos = [g for g in novos if not cliente_em(g, ate) and anuncio_e_saida(g) is not None]
    perdidos_novos_mes = [g for g in perdidos_novos if no_mes(g)]
    mrr_dos_novos_perdidos = sum((mrr_que_saiu(g) for g in perdidos_novos), ZERO)
    meses_como_cliente = [Decimal((anuncio_e_saida(g)[0] - inicio_no_ano(g)).days) / Decimal("30.44") for g in perdidos_novos]
    tempo_medio = (sum(meses_como_cliente, Decimal(0)) / len(meses_como_cliente)).quantize(Decimal("0.1")) if meses_como_cliente else None

    kpi17b = Kpi(
        chave="churn_novos", titulo="17b · Churn de novos no ano", valor=Decimal(len(perdidos_novos)), unidade="clientes",
        resumo=f"de {len(novos)} cliente(s) que entraram em {de.year}"
               + (f" · {_pct(Decimal(len(perdidos_novos)), Decimal(len(novos)))}%".replace(".", ",") if novos else ""),
        falta=[],
        extras={"perdidos": len(perdidos_novos), "novos": len(novos), "perdidos_no_mes": len(perdidos_novos_mes),
                "perdidos_pct": _pct(Decimal(len(perdidos_novos)), Decimal(len(novos))),
                "mrr_perdido": mrr_dos_novos_perdidos, "tempo_medio_meses": tempo_medio},
        itens=[Item(grupo=nome(g), detalhe=f"entrou em {inicio_no_ano(g):%m/%Y} · {detalhe_da_saida(g)}",
                    valor=mrr_que_saiu(g), secao=f"Entraram e saíram em {de.year}") for g in perdidos_novos]
        + [Item(grupo=nome(g), detalhe=f"entrou em {inicio_no_ano(g):%m/%Y}", valor=mrr_do_grupo(g, ate).quantize(CENTAVOS),
                entra=False, secao=f"Os demais novos de {de.year}") for g in novos if g not in perdidos_novos],
        explicacao=f"Clientes (grupos) que não estavam na base de {base_dia:%d/%m/%Y}, começaram um contrato em {de.year} e "
                   "já pediram para encerrar o último, até o fim do mês. Ficam fora do churn da base (17) para não "
                   "distorcer a coorte, mas não somem: sair no mesmo ano em que entrou é sinal de venda (cliente fora do "
                   "ICP, expectativa mal vendida) ou de implantação, não de retenção. Conta no anúncio.",
    )

    # ------------------------------------------------ 21: cobertura de relacionamento
    classes, ultimas, cadencia = sucesso._classes(sessao), sucesso._ultimas(sessao), sucesso.cadencia_vigente(sessao)
    em_dia = total = 0
    sem_reuniao: list[str] = []
    com_reuniao: list[str] = []
    for g, _anterior in sucesso._grupos(sessao):
        classe = classes.get(g.id)
        tipos = [t for t in cadencia.get(classe or "", []) if regras_do_sucesso.tipo(t)]
        if not tipos:
            continue
        total += 1
        meses = min(regras_do_sucesso.tipo(t).meses for t in tipos)
        janela = regras_do_sucesso.mais_meses(ate, -meses)
        datas = [d for t, d in ultimas.get(g.id, {}).items() if t in tipos and janela < d <= ate]
        if datas:
            em_dia += 1
            com_reuniao.append(f"{g.nome}|reunião em {max(datas):%d/%m/%Y} (classe {classe})")
        else:
            sem_reuniao.append(f"{g.nome} (classe {classe})")
    kpi21 = Kpi(
        chave="cobertura", titulo="21 · Cobertura de relacionamento",
        valor=_pct(Decimal(em_dia), Decimal(total)) if total else None, unidade="%",
        resumo=f"{em_dia} de {total} cliente(s) com a reunião da classe realizada (A mensal, B trimestral, C semestral)",
        falta=([] if em_dia else ["Nenhuma reunião de resultado registrada na janela (Sucesso do Cliente)"]),
        meta="100% dos clientes-chave com reunião no trimestre",
        extras={"em_dia": em_dia, "total": total},
        itens=[Item(grupo=n.split("|")[0], detalhe=n.split("|")[1], valor=ZERO) for n in com_reuniao]
        + [Item(grupo=n, detalhe="sem reunião na janela da classe", valor=ZERO, entra=False) for n in sem_reuniao],
        explicacao="Clientes com classe que tiveram a reunião realizada dentro da janela da classe (A: 1 mês, B: 3 meses, "
                   "C: 6 meses) até o fim do mês ÷ clientes com classe. Só conta reunião registrada no Sucesso do Cliente.",
    )

    return KpisResposta(mes=mes, de=de, ate=ate, kpis=[kpi20, kpi19, kpi18, kpi17, kpi17b, kpi21])


def roteador_de_kpis(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["inteligência"])

    @r.get("/api/inteligencia/kpis-lideranca", response_model=KpisResposta)
    def kpis(
        mes: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
        hoje: date | None = None,
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> KpisResposta:
        """Só o Administrador (decisão de Eduardo, 09/10/2026). Sem login (a máquina do CRM), libera."""
        u = usuario_atual.get()
        if u is not None and not u.administrador:
            raise HTTPException(403, "os KPIs da liderança são só do Administrador")
        return calcular(sessao, mes, hoje or date.today())

    return r
