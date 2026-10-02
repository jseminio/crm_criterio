"""Funil do Sucesso do Cliente (aprovado por Eduardo em 02/10/2026): a etapa de cada grupo cliente,
o checklist da implantação e as reuniões de resultado com cadência pela classe. Regras em
`crm.domain.sucesso`."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from crm.api.acesso import quem_fez
from crm.db.base import agora
from crm.db.modelos import (
    CadenciaDeReuniao, ClassificacaoDoGrupo, Contrato, GrupoEconomico, JornadaDoCliente, ReuniaoDeResultado,
)
from crm.domain import sucesso as regra
from crm.domain.listas import SituacaoContrato

__all__ = ["roteador_do_sucesso"]

_VALENDO = (SituacaoContrato.AGUARDANDO_ASSINATURA, SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO)
_CLASSES = ("A", "B", "C")


class EtapaResposta(BaseModel):
    chave: str
    nome: str
    participantes: str | None


class ItemResposta(BaseModel):
    chave: str
    rotulo: str


class TipoResposta(BaseModel):
    chave: str
    nome: str
    meses: int
    participantes: str
    pauta: list[str]


class DevidaResposta(BaseModel):
    tipo: str
    ultima: date | None
    proxima: date | None
    atrasada: bool
    dias_de_atraso: int | None


class GrupoNoFunil(BaseModel):
    grupo_id: int
    nome: str
    etapa: str
    classe: str | None
    itens_feitos: list[str]
    etapa_desde: date | None
    """Vazia para o cliente anterior ao CRM, que já entra em curso."""
    em_curso_desde: date | None
    situacao: str | None
    """Só em curso: "em_dia", "atrasada" (alguma reunião vencida ou nunca registrada) ou "sem_classe"
    (sem leitura do Score, não há cadência para cobrar)."""
    reunioes: list[DevidaResposta]


class FunilDoSucesso(BaseModel):
    etapas: list[EtapaResposta]
    checklist: dict[str, list[ItemResposta]]
    tipos: list[TipoResposta]
    cadencia: dict[str, list[str]]
    grupos: list[GrupoNoFunil]


class ReuniaoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: str
    data: date
    participantes: str | None
    pauta: str | None
    dashboard: str | None
    decisoes: str | None
    proximos_passos: str | None
    registrada_por: str | None
    criado_em: datetime


class NovaReuniao(BaseModel):
    tipo: str
    data: date
    participantes: str | None = Field(default=None, max_length=300)
    pauta: str | None = None
    dashboard: str | None = Field(default=None, max_length=400)
    decisoes: str | None = None
    proximos_passos: str | None = None


class MarcarItem(BaseModel):
    item: str
    feito: bool


class CadenciaResposta(BaseModel):
    cadencia: dict[str, list[str]]
    alterado_por: str | None = None
    alterado_em: datetime | None = None


class CadenciaEdicao(BaseModel):
    cadencia: dict[str, list[str]]


def _texto(v: str | None) -> str | None:
    v = (v or "").strip()
    return v or None


def cadencia_vigente(sessao: Session) -> dict[str, list[str]]:
    gravadas = {c.classe: list(c.tipos) for c in sessao.scalars(sa.select(CadenciaDeReuniao))}
    return {cl: gravadas.get(cl, list(regra.CADENCIA_PADRAO[cl])) for cl in _CLASSES}


def roteador_do_sucesso(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(prefix="/api/sucesso", tags=["sucesso"])

    def _grupos(sessao: Session, so: int | None = None) -> list[tuple[GrupoEconomico, bool]]:
        """Grupos não fundidos com contrato valendo, e se algum deles é anterior ao CRM."""
        consulta = (
            sa.select(GrupoEconomico, sa.func.max(sa.cast(Contrato.anterior_ao_crm, sa.Integer)))
            .join(Contrato, Contrato.grupo_id == GrupoEconomico.id)
            .where(GrupoEconomico.fundido_em_id.is_(None), Contrato.situacao.in_(_VALENDO))
            .group_by(GrupoEconomico.id)
            .order_by(GrupoEconomico.nome)
        )
        if so is not None:
            consulta = consulta.where(GrupoEconomico.id == so)
        return [(g, bool(anterior)) for g, anterior in sessao.execute(consulta)]

    def _classes(sessao: Session) -> dict[int, str]:
        """A classe da leitura mais recente de cada grupo (referência maior, depois revisão maior)."""
        classes: dict[int, str] = {}
        for grupo_id, classe in sessao.execute(
            sa.select(ClassificacaoDoGrupo.grupo_id, ClassificacaoDoGrupo.classe)
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc())
        ):
            classes.setdefault(grupo_id, classe)
        return classes

    def _ultimas(sessao: Session) -> dict[int, dict[str, date]]:
        ultimas: dict[int, dict[str, date]] = {}
        for grupo_id, tipo, dia in sessao.execute(
            sa.select(ReuniaoDeResultado.grupo_id, ReuniaoDeResultado.tipo, sa.func.max(ReuniaoDeResultado.data))
            .group_by(ReuniaoDeResultado.grupo_id, ReuniaoDeResultado.tipo)
        ):
            ultimas.setdefault(grupo_id, {})[tipo] = dia
        return ultimas

    def _no_funil(
        g: GrupoEconomico, anterior: bool, jornada: JornadaDoCliente | None, classe: str | None,
        ultimas: dict[str, date], cadencia: dict[str, list[str]], hoje: date,
    ) -> GrupoNoFunil:
        etapa = jornada.etapa if jornada else ("em_curso" if anterior else "contrato")
        em_curso_desde = jornada.em_curso_desde if jornada else None
        devidas: list[regra.ReuniaoDevida] = []
        situacao = None
        if etapa == "em_curso":
            if classe is None:
                situacao = "sem_classe"
            else:
                devidas = regra.devidas(cadencia.get(classe, []), ultimas, em_curso_desde, hoje)
                situacao = "atrasada" if any(d.atrasada for d in devidas) else "em_dia"
        return GrupoNoFunil(
            grupo_id=g.id, nome=g.nome, etapa=etapa, classe=classe,
            itens_feitos=list(jornada.itens_feitos) if jornada else [],
            etapa_desde=jornada.etapa_desde if jornada else None, em_curso_desde=em_curso_desde,
            situacao=situacao, reunioes=[DevidaResposta(**d.__dict__) for d in devidas],
        )

    def _um(sessao: Session, grupo_id: int, hoje: date) -> GrupoNoFunil:
        achados = _grupos(sessao, grupo_id)
        if not achados:
            raise HTTPException(404, "Grupo sem contrato valendo: não está no Funil do Sucesso do Cliente")
        g, anterior = achados[0]
        return _no_funil(
            g, anterior, sessao.get(JornadaDoCliente, grupo_id), _classes(sessao).get(grupo_id),
            _ultimas(sessao).get(grupo_id, {}), cadencia_vigente(sessao), hoje,
        )

    def _jornada(sessao: Session, grupo_id: int, hoje: date) -> tuple[JornadaDoCliente, GrupoNoFunil]:
        """A linha da jornada, criada na primeira marcação com a etapa que o grupo já mostrava."""
        atual = _um(sessao, grupo_id, hoje)
        jornada = sessao.get(JornadaDoCliente, grupo_id)
        if jornada is None:
            jornada = JornadaDoCliente(grupo_id=grupo_id, etapa=atual.etapa, itens_feitos=[], etapa_desde=hoje)
            sessao.add(jornada)
        return jornada, atual

    @r.get("/funil", response_model=FunilDoSucesso)
    def funil(hoje: date | None = None, sessao: Session = Depends(obter_sessao)) -> FunilDoSucesso:
        """`hoje` existe para teste; sem ele vale a data do servidor."""
        dia = hoje or date.today()
        jornadas = {j.grupo_id: j for j in sessao.scalars(sa.select(JornadaDoCliente))}
        classes, ultimas, cadencia = _classes(sessao), _ultimas(sessao), cadencia_vigente(sessao)
        return FunilDoSucesso(
            etapas=[EtapaResposta(chave=c, nome=n, participantes=p) for c, n, p in regra.ETAPAS],
            checklist={e: [ItemResposta(chave=c, rotulo=r_) for c, r_ in itens] for e, itens in regra.CHECKLIST.items()},
            tipos=[TipoResposta(chave=t.chave, nome=t.nome, meses=t.meses, participantes=t.participantes, pauta=list(t.pauta))
                   for t in regra.TIPOS_DE_REUNIAO],
            cadencia=cadencia,
            grupos=[_no_funil(g, anterior, jornadas.get(g.id), classes.get(g.id), ultimas.get(g.id, {}), cadencia, dia)
                    for g, anterior in _grupos(sessao)],
        )

    @r.patch("/grupos/{grupo_id}/itens", response_model=GrupoNoFunil)
    def marcar(grupo_id: int, corpo: MarcarItem, sessao: Session = Depends(obter_sessao)) -> GrupoNoFunil:
        """Marca ou desmarca um item do checklist da etapa em que o grupo está."""
        hoje = date.today()
        jornada, atual = _jornada(sessao, grupo_id, hoje)
        da_etapa = {c for c, _ in regra.CHECKLIST.get(atual.etapa, ())}
        if corpo.item not in da_etapa:
            raise HTTPException(422, "Este item não é da etapa em que o grupo está")
        feitos = [i for i in jornada.itens_feitos if i != corpo.item]
        if corpo.feito:
            feitos.append(corpo.item)
        jornada.itens_feitos = feitos
        jornada.alterado_por = quem_fez("") or None
        sessao.flush()
        return _um(sessao, grupo_id, hoje)

    @r.post("/grupos/{grupo_id}/concluir-etapa", response_model=GrupoNoFunil)
    def concluir(grupo_id: int, sessao: Session = Depends(obter_sessao)) -> GrupoNoFunil:
        """Passa o grupo para a etapa seguinte, com o checklist da atual completo. Ao concluir o kickoff,
        o grupo entra em curso e as reuniões de resultado começam a contar a partir de hoje."""
        hoje = date.today()
        jornada, atual = _jornada(sessao, grupo_id, hoje)
        seguinte = regra.proxima_etapa(atual.etapa)
        if seguinte is None:
            raise HTTPException(422, "O grupo já está em curso: não há etapa seguinte")
        faltam = [rotulo for c, rotulo in regra.CHECKLIST.get(atual.etapa, ()) if c not in jornada.itens_feitos]
        if faltam:
            raise HTTPException(422, f"Faltam {len(faltam)} itens do checklist: {'; '.join(faltam)}")
        jornada.etapa, jornada.etapa_desde = seguinte, hoje
        if seguinte == "em_curso":
            jornada.em_curso_desde = hoje
        jornada.alterado_por = quem_fez("") or None
        sessao.flush()
        return _um(sessao, grupo_id, hoje)

    @r.get("/grupos/{grupo_id}/reunioes", response_model=list[ReuniaoResposta])
    def reunioes(grupo_id: int, sessao: Session = Depends(obter_sessao)) -> list[ReuniaoDeResultado]:
        """Da mais recente para a mais antiga."""
        return list(sessao.scalars(
            sa.select(ReuniaoDeResultado).where(ReuniaoDeResultado.grupo_id == grupo_id)
            .order_by(ReuniaoDeResultado.data.desc(), ReuniaoDeResultado.id.desc())
        ))

    @r.post("/grupos/{grupo_id}/reunioes", response_model=GrupoNoFunil, status_code=201)
    def registrar(grupo_id: int, corpo: NovaReuniao, sessao: Session = Depends(obter_sessao)) -> GrupoNoFunil:
        """Registra uma reunião já feita. Só para o grupo em curso; a data não pode ser futura."""
        hoje = date.today()
        if regra.tipo(corpo.tipo) is None:
            raise HTTPException(422, "Tipo de reunião desconhecido")
        if corpo.data > hoje:
            raise HTTPException(422, "A data da reunião não pode ser futura: registre depois de feita")
        if _um(sessao, grupo_id, hoje).etapa != "em_curso":
            raise HTTPException(422, "As reuniões de resultado começam quando o grupo entra em curso, depois do kickoff")
        sessao.add(ReuniaoDeResultado(
            grupo_id=grupo_id, tipo=corpo.tipo, data=corpo.data, participantes=_texto(corpo.participantes),
            pauta=_texto(corpo.pauta), dashboard=_texto(corpo.dashboard), decisoes=_texto(corpo.decisoes),
            proximos_passos=_texto(corpo.proximos_passos), registrada_por=quem_fez("") or None,
        ))
        sessao.flush()
        return _um(sessao, grupo_id, hoje)

    def _cadencia_resposta(sessao: Session) -> CadenciaResposta:
        mudadas = [c for c in sessao.scalars(sa.select(CadenciaDeReuniao)) if c.alterado_em]
        ultima = max(mudadas, key=lambda c: c.alterado_em, default=None)
        return CadenciaResposta(
            cadencia=cadencia_vigente(sessao),
            alterado_por=ultima.alterado_por if ultima else None, alterado_em=ultima.alterado_em if ultima else None,
        )

    @r.get("/cadencia", response_model=CadenciaResposta)
    def ver_cadencia(sessao: Session = Depends(obter_sessao)) -> CadenciaResposta:
        return _cadencia_resposta(sessao)

    @r.put("/cadencia", response_model=CadenciaResposta)
    def mudar_cadencia(corpo: CadenciaEdicao, sessao: Session = Depends(obter_sessao)) -> CadenciaResposta:
        """Só muda as classes que vieram. Cada classe precisa de ao menos uma reunião."""
        validos = [t.chave for t in regra.TIPOS_DE_REUNIAO]
        for classe, tipos in corpo.cadencia.items():
            if classe not in _CLASSES:
                raise HTTPException(422, f"Classe desconhecida: {classe}")
            if not tipos:
                raise HTTPException(422, f"Classe {classe}: escolha ao menos uma reunião")
            if any(t not in validos for t in tipos):
                raise HTTPException(422, f"Classe {classe}: tipo de reunião desconhecido")
            ordenados = [t for t in validos if t in tipos]
            linha = sessao.get(CadenciaDeReuniao, classe)
            if linha is None:
                linha = CadenciaDeReuniao(classe=classe, tipos=ordenados)
                sessao.add(linha)
            elif list(linha.tipos) == ordenados:
                continue
            linha.tipos = ordenados
            linha.alterado_por = quem_fez("") or None
            linha.alterado_em = agora()
        sessao.flush()
        return _cadencia_resposta(sessao)

    return r
