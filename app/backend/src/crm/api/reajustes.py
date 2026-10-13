"""O reajuste anual de julho e o IPCA guardado no CRM (13/10/2026). Regras em `crm.domain.reajuste`.

- `GET /api/reajustes?ano=AAAA`: a tabela do reajuste de julho do ano, contrato a contrato, com o IPCA usado e o
  valor sugerido. Antes de montar, completa o IPCA no Banco Central se faltar o último mês (sem travar a tela se
  ele estiver fora).
- `POST /api/reajustes/aprovar`: aplica os reajustes escolhidos, com o valor que a pessoa confirmou ou
  alterou. Cada um vira um evento de Reajuste em 01/07, com o IPCA, o sugerido, o aprovado e **quem autorizou**.
  Tudo ou nada: se um contrato não pode, nenhum é aplicado.
- `GET /api/ipca` e `POST /api/ipca/atualizar`: a série guardada e a busca na hora.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from crm.api.acesso import quem_fez
from crm.db.modelos import Contrato, IpcaDoMes
from crm.domain import eventos_de_contrato as regras_de_eventos
from crm.domain import reajuste as regra
from crm.api.servicos_e_contratos import contrato_do_servico
from crm.domain.contrato_do_servico import ReajusteDoServico
from crm.domain.listas import IndiceDeReajuste, LinhaServico, SituacaoContrato, TipoDeEventoDeContrato
from crm.indices import ipca as indice
from crm.indices.bcb import buscar_ipca

__all__ = ["roteador_de_reajustes"]

T = TipoDeEventoDeContrato
MESES = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _mes(d: date) -> str:
    return f"{MESES[d.month - 1]}/{d.year}"


def _pct(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01'))}%".replace(".", ",")


def _reais(v: Decimal | None) -> str:
    if v is None:
        return "—"
    inteiro, centavos = f"{v:,.2f}".split(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


# ── Respostas ────────────────────────────────────────────────────────────────────────────────────────

class LinhaDoReajuste(BaseModel):
    contrato_id: int
    grupo: str
    empresa: str | None
    escopo: str | None
    recorrente: bool
    situacao: str
    observacao: str | None
    base: date | None
    base_presumida: bool
    de: date | None
    ate: date | None
    meses: int | None
    ipca: Decimal | None
    meses_faltando: list[date]
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    mensal_sugerido: Decimal | None
    anual_sugerido: Decimal | None
    adiado_para: int | None
    aprovavel: bool
    reajustado: str | None = None
    """Só em "Reajustado": o que o evento registrou (de quanto para quanto e quem autorizou)."""


class SituacaoDoIpca(BaseModel):
    ultimo_mes: date | None
    buscado_em: datetime | None
    aviso: str | None = None


class ReajusteDoAno(BaseModel):
    ano: int
    ipca: SituacaoDoIpca
    ipca_completo: bool
    """Junho do ano já publicado: só então dá para aprovar."""
    linhas: list[LinhaDoReajuste]


class MesDoIpca(BaseModel):
    mes: date
    variacao: Decimal


class ItemAprovado(BaseModel):
    contrato_id: int
    preco_mensal_novo: Decimal | None = Field(default=None, ge=0)
    preco_anual_novo: Decimal | None = Field(default=None, ge=0)


class Aprovacao(BaseModel):
    ano: int = Field(ge=2020, le=2100)
    itens: list[ItemAprovado] = Field(min_length=1)
    autorizador: str | None = Field(default=None, max_length=200)
    """Só sem login: o nome de quem autoriza. Com login, quem autoriza é quem entrou."""


class Aplicados(BaseModel):
    aplicados: int
    autorizado_por: str


# ── Montagem ─────────────────────────────────────────────────────────────────────────────────────────

def _recorrente(c: Contrato) -> bool:
    if c.recorrente is not None:
        return c.recorrente
    linha = c.oportunidade.linha_servico if c.oportunidade is not None else None
    if linha is not None:
        return linha is LinhaServico.C1
    return c.preco_mensal is not None


def _para_regra(c: Contrato) -> regra.ContratoParaReajuste:
    # O reajuste escolhido para o serviço (Configurações › Serviços e contratos, 13/10/2026): "Sem reajuste" vale
    # como o índice do contrato; "Caso a caso" passa a linha para "Você decide".
    escolha = contrato_do_servico(Session.object_session(c), c.oportunidade.servico) if c.oportunidade is not None else None
    reajuste_do_servico = escolha[1] if escolha is not None else None
    indice = c.oportunidade.reajuste if c.oportunidade is not None else None
    if reajuste_do_servico is ReajusteDoServico.SEM_REAJUSTE:
        indice = IndiceDeReajuste.SEM_REAJUSTE
    return regra.ContratoParaReajuste(
        id=c.id, situacao=c.situacao, recorrente=_recorrente(c), indice=indice,
        caso_a_caso=reajuste_do_servico is ReajusteDoServico.CASO_A_CASO,
        preco_mensal=c.preco_mensal, preco_anual=c.preco_anual, parcelas_no_ano=c.parcelas_no_ano,
        data_inicio=c.data_inicio, anterior_ao_crm=c.anterior_ao_crm, data_fim=c.data_fim, saida_em=c.saida_em,
        reajustes=tuple(ev.data_do_evento for ev in c.eventos if ev.tipo is T.REAJUSTE),
    )


def _contratos(sessao: Session, ids: list[int] | None = None) -> list[Contrato]:
    consulta = (
        sa.select(Contrato)
        .where(Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
        .options(selectinload(Contrato.eventos), selectinload(Contrato.oportunidade), selectinload(Contrato.grupo),
                 selectinload(Contrato.empresa))
        .order_by(Contrato.id)
    )
    if ids is not None:
        consulta = consulta.where(Contrato.id.in_(ids))
    return list(sessao.scalars(consulta))


def _reajustado(c: Contrato, ano: int) -> str | None:
    julho, proximo = date(ano, 7, 1), date(ano + 1, 7, 1)
    evento = next((ev for ev in c.eventos if ev.tipo is T.REAJUSTE and julho <= ev.data_do_evento < proximo), None)
    if evento is None:
        return None
    de_para = f"{_reais(evento.preco_mensal_anterior)} → {_reais(evento.preco_mensal_novo)}" if evento.preco_mensal_novo is not None \
        else f"{_reais(evento.preco_anual_anterior)} → {_reais(evento.preco_anual_novo)}"
    return f"{de_para} em {evento.data_do_evento:%d/%m/%Y}" + (f" · {evento.descricao}" if evento.descricao else "")


def _resposta(c: Contrato, linha: regra.LinhaDoReajuste, ano: int) -> LinhaDoReajuste:
    return LinhaDoReajuste(
        contrato_id=c.id, grupo=c.grupo.nome, empresa=c.empresa.razao_social if c.empresa else None, escopo=c.escopo,
        recorrente=_recorrente(c), situacao=linha.situacao.value, observacao=linha.observacao, base=linha.base,
        base_presumida=linha.base_presumida, de=linha.de, ate=linha.ate, meses=linha.meses, ipca=linha.ipca,
        meses_faltando=list(linha.meses_faltando), preco_mensal=linha.preco_mensal, preco_anual=linha.preco_anual,
        mensal_sugerido=linha.mensal_sugerido, anual_sugerido=linha.anual_sugerido, adiado_para=linha.adiado_para,
        aprovavel=linha.aprovavel,
        reajustado=_reajustado(c, ano) if linha.situacao is regra.SituacaoDoReajuste.REAJUSTADO else None,
    )


def _situacao_do_ipca(sessao: Session, aviso: str | None) -> SituacaoDoIpca:
    ultimo, buscado = sessao.execute(sa.select(sa.func.max(IpcaDoMes.mes), sa.func.max(IpcaDoMes.buscado_em))).one()
    return SituacaoDoIpca(ultimo_mes=ultimo, buscado_em=buscado, aviso=aviso)


ORDEM = {s: i for i, s in enumerate(regra.SituacaoDoReajuste)}


def roteador_de_reajustes(
    obter_sessao: Callable[[], Iterator[Session]],
    buscar: indice.BuscarIpca | None = None,
) -> APIRouter:
    r = APIRouter(tags=["contratos"])
    busca = buscar or buscar_ipca

    def _completar_ipca(sessao: Session, hoje: date) -> str | None:
        if not indice.precisa_atualizar(sessao, hoje):
            return None
        feito = indice.atualizar(sessao, hoje, busca)
        if feito.erro:
            return f"Não deu para atualizar o IPCA agora ({feito.erro}). Os valores usam o que já está guardado."
        return None

    @r.get("/api/reajustes", response_model=ReajusteDoAno)
    def ver_reajuste(
        ano: int | None = Query(default=None, ge=2020, le=2100),
        hoje: date | None = None,
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> ReajusteDoAno:
        """A tabela do reajuste de julho de `ano` (o deste ano, por padrão)."""
        hoje = hoje or date.today()
        ano = ano or hoje.year
        aviso = _completar_ipca(sessao, hoje)
        serie = indice.serie(sessao)
        linhas = []
        for c in _contratos(sessao):
            linha = regra.linha_do_reajuste(_para_regra(c), ano, serie)
            if linha is not None:
                linhas.append(_resposta(c, linha, ano))
        linhas.sort(key=lambda l: (ORDEM[regra.SituacaoDoReajuste(l.situacao)], l.grupo.casefold(), l.contrato_id))
        return ReajusteDoAno(
            ano=ano, ipca=_situacao_do_ipca(sessao, aviso), ipca_completo=date(ano, 6, 1) in serie, linhas=linhas,
        )

    @r.post("/api/reajustes/aprovar", response_model=Aplicados)
    def aprovar_reajuste(corpo: Aprovacao, sessao: Session = Depends(obter_sessao, scope="function")) -> Aplicados:
        """Aplica os reajustes escolhidos como eventos de Reajuste em 01/07 do ano."""
        from crm.api.app import _gravar_evento  # a gravação do evento mora com a rota de eventos

        quem = (quem_fez((corpo.autorizador or "").strip()) or "").strip()
        if not quem:
            raise HTTPException(422, "informe quem autoriza o reajuste")
        ids = [i.contrato_id for i in corpo.itens]
        if len(set(ids)) != len(ids):
            raise HTTPException(422, "um contrato aparece duas vezes na aprovação")
        ano = corpo.ano
        serie = indice.serie(sessao)
        contratos = {c.id: c for c in _contratos(sessao, ids)}
        julho = date(ano, 7, 1)
        for item in corpo.itens:
            c = contratos.get(item.contrato_id)
            linha = regra.linha_do_reajuste(_para_regra(c), ano, serie) if c is not None else None
            nome = c.grupo.nome if c is not None else f"contrato {item.contrato_id}"
            if linha is None or linha.situacao not in (regra.SituacaoDoReajuste.REAJUSTAR, regra.SituacaoDoReajuste.DECIDIR):
                situacao = linha.situacao.value.lower() if linha is not None else "fora do reajuste deste ano"
                raise HTTPException(409, f"{nome}: o contrato não está para reajustar em julho/{ano} ({situacao})")
            if not linha.ipca_completo:
                faltam = ", ".join(_mes(m) for m in linha.meses_faltando)
                raise HTTPException(409, f"{nome}: falta o IPCA de {faltam}; aprove quando o Banco Central publicar")
            if item.preco_mensal_novo is None and item.preco_anual_novo is None:
                raise HTTPException(422, f"{nome}: informe o valor reajustado")
            alterado = (item.preco_mensal_novo is not None and item.preco_mensal_novo != linha.mensal_sugerido) or (
                item.preco_anual_novo is not None and item.preco_anual_novo != linha.anual_sugerido)
            sugerido = linha.mensal_sugerido if item.preco_mensal_novo is not None else linha.anual_sugerido
            aprovado = item.preco_mensal_novo if item.preco_mensal_novo is not None else item.preco_anual_novo
            descricao = (
                f"Reajuste anual de julho/{ano}: IPCA {_pct(linha.ipca)} ({_mes(linha.de)} a {_mes(linha.ate)}). "
                f"Sugerido {_reais(sugerido)}; aprovado {_reais(aprovado)}{' (alterado à mão)' if alterado else ''}. "
                f"Autorizado por {quem}."
            )[:500]
            pedido = regras_de_eventos.Pedido(
                tipo=T.REAJUSTE, data_do_evento=julho, descricao=descricao,
                preco_mensal_novo=item.preco_mensal_novo, preco_anual_novo=item.preco_anual_novo,
            )
            try:
                efeito = regras_de_eventos.efeito_do_evento(c, pedido)
            except regras_de_eventos.ErroDeEvento as erro:
                raise HTTPException(erro.status, f"{nome}: {erro}") from erro
            _gravar_evento(sessao, c, pedido, efeito)
        return Aplicados(aplicados=len(corpo.itens), autorizado_por=quem)

    @r.get("/api/ipca", response_model=list[MesDoIpca])
    def ver_ipca(
        desde: date | None = None, sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> list[MesDoIpca]:
        """A série guardada, do mais recente para o mais antigo."""
        consulta = sa.select(IpcaDoMes).order_by(IpcaDoMes.mes.desc())
        if desde is not None:
            consulta = consulta.where(IpcaDoMes.mes >= desde.replace(day=1))
        return [MesDoIpca(mes=m.mes, variacao=m.variacao) for m in sessao.scalars(consulta)]

    @r.post("/api/ipca/atualizar", response_model=SituacaoDoIpca)
    def atualizar_ipca(
        hoje: date | None = None, sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> SituacaoDoIpca:
        """Busca agora no Banco Central, sem esperar o intervalo de 12 horas."""
        feito = indice.atualizar(sessao, hoje or date.today(), busca)
        if feito.erro:
            raise HTTPException(502, f"Não deu para atualizar o IPCA: {feito.erro}")
        return _situacao_do_ipca(sessao, None)

    return r
