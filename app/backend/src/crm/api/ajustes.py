"""Ajustes da área técnica (aprovado por Eduardo em 02/10/2026): o que as reuniões de resultado
identificaram e a área técnica precisa fazer. Quem tem "Ajustes: ver os de todos" (ou vê o Funil do
Sucesso do Cliente) vê os de todo mundo; quem só tem "marcar feito" vê os seus (pela conta Microsoft com que entrou). Sem login, na máquina, vê tudo.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.acesso.auditoria import usuario_atual
from crm.api.acesso import quem_fez
from crm.db.base import agora
from crm.db.modelos import AjusteTecnico, GrupoEconomico, Perfil, ReuniaoDeResultado, Usuario

__all__ = ["AjusteResposta", "responsaveis_possiveis", "roteador_de_ajustes"]


class AjusteResposta(BaseModel):
    id: int
    reuniao_id: int
    reuniao_tipo: str
    reuniao_data: date
    grupo_id: int
    grupo_nome: str
    descricao: str
    responsavel_email: str
    responsavel_nome: str | None
    prazo: date | None
    feito_em: datetime | None
    feito_por: str | None
    observacao: str | None


class ResponsavelResposta(BaseModel):
    email: str
    nome: str | None
    perfil: str


class MarcarFeito(BaseModel):
    observacao: str | None = Field(default=None, max_length=500)


def resposta_do_ajuste(a: AjusteTecnico) -> AjusteResposta:
    return AjusteResposta(
        id=a.id, reuniao_id=a.reuniao_id, reuniao_tipo=a.reuniao.tipo, reuniao_data=a.reuniao.data,
        grupo_id=a.grupo_id, grupo_nome=a.grupo.nome, descricao=a.descricao,
        responsavel_email=a.responsavel_email, responsavel_nome=a.responsavel_nome, prazo=a.prazo,
        feito_em=a.feito_em, feito_por=a.feito_por, observacao=a.observacao,
    )


def responsaveis_possiveis(sessao: Session) -> list[Usuario]:
    """Pessoas ativas cujo perfil marca ajuste como feito (o Administrador também)."""
    usuarios = sessao.scalars(
        sa.select(Usuario).join(Perfil, Perfil.id == Usuario.perfil_id).where(Usuario.ativo.is_(True))
        .order_by(sa.func.coalesce(Usuario.nome, Usuario.email))
    )
    return [u for u in usuarios if u.perfil.administrador or "ajustes.concluir" in (u.perfil.permissoes or [])]


def _so_os_meus() -> str | None:
    """O e-mail de quem entrou, quando só pode ver os próprios ajustes; `None` quando vê todos."""
    quem = usuario_atual.get()
    if quem is None or quem.pode("ajustes.ver", "sucesso.ver"):
        return None
    return quem.email.lower()


def roteador_de_ajustes(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(prefix="/api/ajustes", tags=["ajustes"])

    def _ajuste(sessao: Session, ajuste_id: int) -> AjusteTecnico:
        a = sessao.get(AjusteTecnico, ajuste_id)
        meu = _so_os_meus()
        if a is None or (meu is not None and a.responsavel_email.lower() != meu):
            raise HTTPException(404, "Ajuste não encontrado")
        return a

    @r.get("", response_model=list[AjusteResposta])
    def listar(
        situacao: Literal["pendentes", "feitos", "todos"] = "pendentes", grupo_id: int | None = None,
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> list[AjusteResposta]:
        """Pendentes pelo prazo (sem prazo por último); feitos do mais recente para o mais antigo."""
        consulta = (
            sa.select(AjusteTecnico).join(ReuniaoDeResultado, ReuniaoDeResultado.id == AjusteTecnico.reuniao_id)
            .join(GrupoEconomico, GrupoEconomico.id == AjusteTecnico.grupo_id)
        )
        if situacao == "pendentes":
            consulta = consulta.where(AjusteTecnico.feito_em.is_(None)).order_by(
                AjusteTecnico.prazo.is_(None), AjusteTecnico.prazo, AjusteTecnico.id)
        elif situacao == "feitos":
            consulta = consulta.where(AjusteTecnico.feito_em.is_not(None)).order_by(AjusteTecnico.feito_em.desc())
        else:
            consulta = consulta.order_by(AjusteTecnico.id.desc())
        if grupo_id is not None:
            consulta = consulta.where(AjusteTecnico.grupo_id == grupo_id)
        meu = _so_os_meus()
        if meu is not None:
            consulta = consulta.where(sa.func.lower(AjusteTecnico.responsavel_email) == meu)
        return [resposta_do_ajuste(a) for a in sessao.scalars(consulta)]

    @r.get("/responsaveis", response_model=list[ResponsavelResposta])
    def responsaveis(sessao: Session = Depends(obter_sessao, scope="function")) -> list[ResponsavelResposta]:
        return [ResponsavelResposta(email=u.email, nome=u.nome, perfil=u.perfil.nome) for u in responsaveis_possiveis(sessao)]

    @r.post("/{ajuste_id}/feito", response_model=AjusteResposta)
    def feito(ajuste_id: int, corpo: MarcarFeito, sessao: Session = Depends(obter_sessao, scope="function")) -> AjusteResposta:
        a = _ajuste(sessao, ajuste_id)
        if a.feito_em is not None:
            raise HTTPException(422, "Este ajuste já está feito")
        a.feito_em, a.feito_por = agora(), quem_fez("") or None
        a.observacao = (corpo.observacao or "").strip() or None
        sessao.flush()
        return resposta_do_ajuste(a)

    @r.post("/{ajuste_id}/reabrir", response_model=AjusteResposta)
    def reabrir(ajuste_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> AjusteResposta:
        """Volta a pendente. A observação de quando foi feito fica, para o histórico."""
        a = _ajuste(sessao, ajuste_id)
        if a.feito_em is None:
            raise HTTPException(422, "Este ajuste ainda está pendente")
        a.feito_em, a.feito_por = None, None
        sessao.flush()
        return resposta_do_ajuste(a)

    return r
