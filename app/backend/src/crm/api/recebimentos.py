"""O MRR da carteira por cliente, o recebido e a importação da planilha de recebimentos (10/10/2026).

- `GET /api/mrr/carteira`: o contratado (a mesma conta do MRR atual) e, na competência, o esperado e o
  recebido de cada grupo, com a situação. É o que abre o botão "Ver composição" do MRR da carteira.
- `GET /api/mrr/movimento`: cada contrato ou evento que compõe uma linha do movimento do MRR.
- `POST /api/recebimentos/previa` e `/importar`: a planilha (base64), só o Administrador. A prévia não
  grava; a importação substitui os meses que a planilha traz (as linhas antigas ficam, desligadas).
"""

from __future__ import annotations

import base64
import binascii
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, selectinload

from crm.acesso.auditoria import usuario_atual
from crm.api.acesso import quem_fez
from crm.api.classificacao import parametros_vigentes
from crm.api.metas import metas_vigentes
from crm.db.base import agora
from crm.db.modelos import Contrato, Empresa, GrupoEconomico, ImportacaoDeRecebimentos, Recebimento
from crm.db.saidas import efetivar_saidas
from crm.domain import mrr as regras
from crm.domain import recebimentos as regra

__all__ = ["roteador_de_recebimentos", "reconhecer"]

ZERO = Decimal("0.00")
COMPETENCIA = r"^\d{4}-(0[1-9]|1[0-2])$"


def _mes(texto: str | None, hoje: date) -> date:
    if not texto:
        return hoje.replace(day=1)
    ano, mes = texto.split("-")
    return date(int(ano), int(mes), 1)


def _fim_do_mes(inicio: date) -> date:
    return (inicio.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)


# ── Respostas ────────────────────────────────────────────────────────────────────────────────────────

class ContratoDoGrupo(BaseModel):
    id: int
    escopo: str | None
    empresa: str | None
    parte: str
    """"somado", "suspenso", "sem_preco" ou "encerrado" (fora do MRR de hoje, mas faturava na competência)."""
    mrr: Decimal | None
    esperado: Decimal
    """A parcela em bruto que o caixa espera na competência (zero se não faturava nela), com a 13ª quando cabe."""
    saida_em: date | None = None
    """Saída efetiva anunciada (aviso de saída, 10/10/2026)."""


class GrupoDaCarteira(BaseModel):
    grupo_id: int
    grupo: str
    contratos: int
    mrr: Decimal
    esperado: Decimal
    recebido: Decimal
    situacao: str | None
    """Em dia · Parcial · Em aberto · Sem registro; `None` para quem só recebeu (sem parcela esperada)."""
    itens: list[ContratoDoGrupo] = []


class CarteiraResposta(BaseModel):
    competencia: str
    mrr: Decimal
    contratos: int
    grupos: int
    suspenso: Decimal
    sem_preco_mensal: int
    em_aviso: Decimal = Decimal("0")
    """MRR de contratos em aviso de saída: ainda somam, mas saem na data anunciada (10/10/2026)."""
    em_aviso_contratos: int = 0
    meta: Decimal
    alerta: Decimal
    esperado: Decimal
    recebido: Decimal
    """Só dos grupos com parcela esperada: é o que se compara com o esperado."""
    recebido_fora: Decimal
    """Recebido de grupos sem parcela esperada na competência (pontual, contrato encerrado): fora da conta."""
    mes_importado: bool
    importado_em: datetime | None
    importado_por: str | None
    grupos_registrados: int
    """Grupos com parcela esperada que aparecem na planilha da competência."""
    itens: list[GrupoDaCarteira]


class ItemDoMovimentoResposta(BaseModel):
    categoria: str
    grupo_id: int
    grupo: str
    contrato_id: int
    escopo: str | None
    valor: Decimal
    data: date | None
    motivo: str | None = None
    """No churn: o motivo do encerramento (lista aprovada em 10/10/2026)."""
    iniciativa: str | None = None


class MovimentoResposta(BaseModel):
    de: date
    ate: date
    itens: list[ItemDoMovimentoResposta]


class Planilha(BaseModel):
    arquivo: str = Field(min_length=1, max_length=200)
    conteudo_base64: str = Field(min_length=1)


class ProblemaResposta(BaseModel):
    linha: int
    motivo: str
    trecho: str


class MesDaPrevia(BaseModel):
    competencia: str
    linhas: int
    total: Decimal
    substitui: Decimal | None
    """O total que já estava gravado para o mês e será substituído; `None` se o mês é novo."""


class PreviaResposta(BaseModel):
    arquivo: str
    reconhecidas: int
    total: Decimal
    meses: list[MesDaPrevia]
    problemas: list[ProblemaResposta]


class ImportacaoResposta(BaseModel):
    id: int
    arquivo: str
    importado_por: str | None
    importado_em: datetime
    competencias: list[str]
    linhas: int
    total: Decimal
    fora: int


# ── Regras com o banco ───────────────────────────────────────────────────────────────────────────────

def _contratos(sessao: Session) -> list[Contrato]:
    return list(sessao.scalars(sa.select(Contrato).options(selectinload(Contrato.eventos), selectinload(Contrato.empresa))))


def carteira(sessao: Session, competencia: date, hoje: date | None = None) -> CarteiraResposta:
    registrados = _contratos(sessao)
    por_id = {c.id: c for c in registrados}
    imposto = parametros_vigentes(sessao)[1].imposto
    em_mrr = regras.em_bruto(registrados, imposto)
    parcelas = {c.id: c for c in regras.em_bruto(registrados, imposto, em_mrr=False)}
    atual = regras.mrr_atual(em_mrr)
    fim = _fim_do_mes(competencia)

    itens: dict[int, list[ContratoDoGrupo]] = defaultdict(list)
    esperado_do_grupo: dict[int, Decimal] = defaultdict(lambda: ZERO)
    mrr_do_grupo: dict[int, Decimal] = defaultdict(lambda: ZERO)
    partes = {i.contrato_id: i for i in regras.itens_do_mrr(em_mrr)}
    em_aviso, em_aviso_contratos = ZERO, 0
    for p in parcelas.values():
        esperado = ZERO
        saida = regras.saida_vigente(p)
        if regras.fatura_entre(p, competencia, fim):
            preco = regras.preco_em(p, min(fim, saida) if saida else fim)
            if preco and preco > 0:
                esperado = regra.esperado_no_mes(preco, competencia, p.data_inicio, saida)
        item = partes.get(p.id)
        if item is None and esperado <= 0:
            continue
        c = por_id[p.id]
        if item is not None and item.parte == "somado":
            mrr_do_grupo[c.grupo_id] += item.valor
        esperado_do_grupo[c.grupo_id] += esperado
        aviso = saida if (item is not None and item.parte == "somado" and saida and saida > (hoje or date.today())) else None
        if aviso:
            em_aviso += item.valor
            em_aviso_contratos += 1
        itens[c.grupo_id].append(ContratoDoGrupo(
            id=c.id, escopo=c.escopo,
            empresa=(c.empresa.nome_fantasia or c.empresa.razao_social) if c.empresa else None,
            parte=item.parte if item else "encerrado", mrr=item.valor if item else None, esperado=esperado,
            saida_em=aviso,
        ))

    recebidos = list(sessao.scalars(
        sa.select(Recebimento).where(Recebimento.competencia == competencia, Recebimento.ativo.is_(True))
    ))
    recebido_do_grupo: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for r in recebidos:
        recebido_do_grupo[r.grupo_id] += r.valor
    importacao = sessao.scalars(
        sa.select(ImportacaoDeRecebimentos)
        .where(ImportacaoDeRecebimentos.id.in_({r.importacao_id for r in recebidos} or {0}))
        .order_by(ImportacaoDeRecebimentos.importado_em.desc())
    ).first()
    mes_importado = bool(recebidos)

    grupos_ids = set(itens) | set(recebido_do_grupo)
    nomes = dict(sessao.execute(sa.select(GrupoEconomico.id, GrupoEconomico.nome).where(GrupoEconomico.id.in_(grupos_ids or {0}))).all())
    linhas = []
    for gid in grupos_ids:
        esperado, recebido = esperado_do_grupo[gid], recebido_do_grupo[gid]
        linhas.append(GrupoDaCarteira(
            grupo_id=gid, grupo=nomes.get(gid, f"Grupo {gid}"),
            contratos=sum(1 for i in itens[gid] if i.parte == "somado"),
            mrr=mrr_do_grupo[gid], esperado=esperado, recebido=recebido,
            situacao=regra.situacao(esperado, recebido, mes_importado) if esperado > 0 else None,
            itens=sorted(itens[gid], key=lambda i: -(i.mrr or ZERO)),
        ))
    linhas.sort(key=lambda g: (-g.mrr, -g.recebido, g.grupo))
    com_esperado = [g for g in linhas if g.esperado > 0]
    meta, alerta = metas_vigentes(sessao)["mrr"]
    return CarteiraResposta(
        competencia=competencia.strftime("%Y-%m"), mrr=atual.valor, contratos=atual.contratos, grupos=atual.grupos,
        suspenso=atual.suspenso_valor, sem_preco_mensal=atual.sem_preco_mensal, meta=meta, alerta=alerta,
        em_aviso=em_aviso, em_aviso_contratos=em_aviso_contratos,
        esperado=sum((g.esperado for g in com_esperado), ZERO),
        recebido=sum((g.recebido for g in com_esperado), ZERO),
        recebido_fora=sum((g.recebido for g in linhas if g.esperado <= 0), ZERO),
        mes_importado=mes_importado,
        importado_em=importacao.importado_em if importacao else None,
        importado_por=importacao.importado_por if importacao else None,
        grupos_registrados=sum(1 for g in com_esperado if g.recebido > 0),
        itens=linhas,
    )


def reconhecer(sessao: Session, leitura: regra.Leitura) -> tuple[list[regra.LinhaReconhecida], list[regra.Problema]]:
    """Casa cada linha com o cliente: pelo CNPJ (empresa cadastrada) ou pelo nome do grupo, da empresa
    (razão social ou fantasia), sem acento e sem diferença de maiúscula. Nome que casa com mais de um
    grupo não entra: vira problema, para a pessoa usar o CNPJ."""
    por_cnpj = {e.cnpj: e for e in sessao.scalars(sa.select(Empresa).where(Empresa.cnpj.is_not(None)))}
    por_nome: dict[str, set[tuple[int, int | None]]] = defaultdict(set)
    for g in sessao.scalars(sa.select(GrupoEconomico).where(GrupoEconomico.fundido_em_id.is_(None))):
        por_nome[regra.normalizar(g.nome)].add((g.id, None))
    for e in sessao.scalars(sa.select(Empresa)):
        for nome in (e.razao_social, e.nome_fantasia):
            if nome:
                por_nome[regra.normalizar(nome)].add((e.grupo_id, e.id))
    reconhecidas, problemas = [], list(leitura.problemas)
    for linha in leitura.linhas:
        trecho = f"{linha.cnpj or linha.grupo} · {linha.competencia:%m/%Y} · {linha.valor}"
        if linha.cnpj:
            empresa = por_cnpj.get(linha.cnpj)
            if empresa is None:
                problemas.append(regra.Problema(linha.numero, "CNPJ não cadastrado em nenhuma empresa do CRM", trecho))
                continue
            reconhecidas.append(regra.LinhaReconhecida(linha, empresa.grupo_id, empresa.id))
            continue
        achados = por_nome.get(regra.normalizar(linha.grupo), set())
        grupos = {g for g, _ in achados}
        if not grupos:
            problemas.append(regra.Problema(linha.numero, "nome não encontrado entre os grupos e empresas do CRM", trecho))
        elif len(grupos) > 1:
            problemas.append(regra.Problema(linha.numero, "nome casa com mais de um grupo: use o CNPJ", trecho))
        else:
            empresas = {e for _, e in achados if e is not None}
            reconhecidas.append(regra.LinhaReconhecida(linha, grupos.pop(), empresas.pop() if len(empresas) == 1 else None))
    problemas.sort(key=lambda p: p.numero)
    return reconhecidas, problemas


def _ler(corpo: Planilha) -> regra.Leitura:
    try:
        conteudo = base64.b64decode(corpo.conteudo_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(422, "o arquivo não chegou inteiro: escolha a planilha de novo")
    try:
        return regra.ler_planilha(conteudo, corpo.arquivo)
    except ValueError as erro:
        raise HTTPException(422, str(erro))
    except Exception:
        raise HTTPException(422, "não consegui abrir a planilha: confira se é .xlsx ou .csv")


def _so_administrador() -> None:
    u = usuario_atual.get()
    if u is not None and not u.administrador:
        raise HTTPException(403, "importar recebimentos é só do Administrador")


def _previa(sessao: Session, corpo: Planilha) -> tuple[PreviaResposta, list[regra.LinhaReconhecida], list[regra.Problema]]:
    reconhecidas, problemas = reconhecer(sessao, _ler(corpo))
    por_mes: dict[date, list[regra.LinhaReconhecida]] = defaultdict(list)
    for r in reconhecidas:
        por_mes[r.linha.competencia].append(r)
    meses = []
    for mes in sorted(por_mes):
        antes = sessao.scalar(
            sa.select(sa.func.sum(Recebimento.valor)).where(Recebimento.competencia == mes, Recebimento.ativo.is_(True))
        )
        meses.append(MesDaPrevia(
            competencia=mes.strftime("%Y-%m"), linhas=len(por_mes[mes]),
            total=sum((r.linha.valor for r in por_mes[mes]), ZERO), substitui=antes,
        ))
    return PreviaResposta(
        arquivo=corpo.arquivo, reconhecidas=len(reconhecidas), total=sum((r.linha.valor for r in reconhecidas), ZERO),
        meses=meses, problemas=[ProblemaResposta(linha=p.numero, motivo=p.motivo, trecho=p.trecho) for p in problemas],
    ), reconhecidas, problemas


def roteador_de_recebimentos(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["contratos"])

    @r.get("/api/mrr/carteira", response_model=CarteiraResposta)
    def ver_carteira(
        competencia: str | None = Query(default=None, pattern=COMPETENCIA),
        hoje: date | None = None,
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> CarteiraResposta:
        """O MRR da carteira por grupo e, na competência (padrão: o mês corrente), o esperado e o recebido."""
        dia = hoje or date.today()
        efetivar_saidas(sessao, dia)
        return carteira(sessao, _mes(competencia, dia), dia)

    @r.get("/api/mrr/movimento", response_model=MovimentoResposta)
    def ver_movimento(
        de: date,
        ate: date | None = None,
        hoje: date | None = None,
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> MovimentoResposta:
        """Cada contrato ou evento que compõe as linhas do movimento do MRR no período (a mesma conta)."""
        fim = ate or (hoje or date.today())
        efetivar_saidas(sessao, hoje or date.today())
        if de > fim:
            raise HTTPException(422, "o início do período não pode ser depois do fim")
        registrados = _contratos(sessao)
        por_id = {c.id: c for c in registrados}
        contratos = regras.em_bruto(registrados, parametros_vigentes(sessao)[1].imposto)
        itens = regras.itens_do_movimento(contratos, de, fim)
        eventos = {ev.id: ev for c in registrados for ev in c.eventos}
        nomes = dict(sessao.execute(sa.select(GrupoEconomico.id, GrupoEconomico.nome)
                                    .where(GrupoEconomico.id.in_({i.grupo_id for i in itens} or {0}))).all())
        return MovimentoResposta(de=de, ate=fim, itens=[
            ItemDoMovimentoResposta(
                categoria=i.categoria, grupo_id=i.grupo_id, grupo=nomes.get(i.grupo_id, f"Grupo {i.grupo_id}"),
                contrato_id=i.contrato_id, escopo=por_id[i.contrato_id].escopo, valor=i.valor, data=i.data,
                motivo=(ev.motivo_categoria.value if (ev := eventos.get(i.evento_id)) and ev.motivo_categoria else None),
                iniciativa=(ev.iniciativa.value if ev and ev.iniciativa else None),
            )
            for i in sorted(itens, key=lambda i: (regras.CATEGORIAS_DO_MOVIMENTO.index(i.categoria), -i.valor))
        ])

    @r.post("/api/recebimentos/previa", response_model=PreviaResposta)
    def previa(corpo: Planilha, sessao: Session = Depends(obter_sessao, scope="function")) -> PreviaResposta:
        """Lê a planilha e diz o que entraria, sem gravar nada."""
        _so_administrador()
        return _previa(sessao, corpo)[0]

    @r.post("/api/recebimentos/importar", response_model=ImportacaoResposta)
    def importar(corpo: Planilha, sessao: Session = Depends(obter_sessao, scope="function")) -> ImportacaoResposta:
        """Grava as linhas reconhecidas. Os meses que a planilha traz substituem o que havia (desligado)."""
        _so_administrador()
        resposta, reconhecidas, problemas = _previa(sessao, corpo)
        if not reconhecidas:
            raise HTTPException(422, "nenhuma linha reconhecida: nada foi importado")
        meses = sorted({r.linha.competencia for r in reconhecidas})
        sessao.execute(sa.update(Recebimento).where(Recebimento.competencia.in_(meses), Recebimento.ativo.is_(True))
                       .values(ativo=False))
        imp = ImportacaoDeRecebimentos(
            arquivo=corpo.arquivo, importado_por=quem_fez("") or None, importado_em=agora(),
            competencias=[m.strftime("%Y-%m") for m in meses], linhas=len(reconhecidas), total=resposta.total,
            fora=len(problemas),
        )
        sessao.add(imp)
        sessao.flush()
        for rec in reconhecidas:
            sessao.add(Recebimento(
                importacao_id=imp.id, grupo_id=rec.grupo_id, empresa_id=rec.empresa_id, competencia=rec.linha.competencia,
                valor=rec.linha.valor, data_do_recebimento=rec.linha.data,
            ))
        sessao.flush()
        return ImportacaoResposta.model_validate(imp, from_attributes=True)

    @r.get("/api/recebimentos/importacoes", response_model=list[ImportacaoResposta])
    def importacoes(sessao: Session = Depends(obter_sessao, scope="function")) -> list[ImportacaoResposta]:
        """As planilhas importadas, da mais recente para a mais antiga (inclusive as substituídas)."""
        return [ImportacaoResposta.model_validate(i, from_attributes=True) for i in sessao.scalars(
            sa.select(ImportacaoDeRecebimentos).order_by(ImportacaoDeRecebimentos.importado_em.desc()).limit(50)
        )]

    return r
