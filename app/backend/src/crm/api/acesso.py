"""Rotas do acesso (E1, 02/10/2026): como entrar, quem entrou, perfis, pessoas e o histórico de
alterações. A checagem de cada rota contra o perfil fica no meio do caminho (`crm.api.app`), pelo
mapa de `crm.acesso.catalogo`."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.acesso.auditoria import usuario_atual
from crm.acesso.catalogo import MENUS, PERMISSOES
from crm.acesso.entrada import ConfiguracaoDeEntrada
from crm.db.modelos import Perfil, RegistroDeAlteracao, Usuario

__all__ = ["roteador_do_acesso", "quem_fez"]


def quem_fez(informado: str | None) -> str | None:
    """Com login, quem fez é quem entrou (o nome da conta Microsoft); sem login, o que a tela informou."""
    u = usuario_atual.get()
    return (u.nome or u.email) if u else informado


# ------------------------------------------------------------------ esquemas

class Entrada(BaseModel):
    modo: str
    """"microsoft" ou "local" (sem login, só na máquina do CRM)."""
    tenant_id: str | None = None
    client_id: str | None = None
    escopo: str | None = None


class Eu(BaseModel):
    modo: str
    email: str | None
    nome: str | None
    perfil: str
    administrador: bool
    permissoes: list[str]


class Funcionalidade(BaseModel):
    chave: str
    rotulo: str


class Menu(BaseModel):
    chave: str
    rotulo: str
    funcionalidades: list[Funcionalidade]


class PerfilResposta(BaseModel):
    id: int
    nome: str
    administrador: bool
    permissoes: list[str]
    pessoas: int


class PerfilNovo(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    permissoes: list[str] = []


class PerfilMudanca(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=60)
    permissoes: list[str] | None = None


class UsuarioResposta(BaseModel):
    id: int
    email: str
    nome: str | None
    perfil_id: int
    perfil: str
    ativo: bool
    liberado_por: str | None
    criado_em: datetime


class UsuarioNovo(BaseModel):
    email: str = Field(min_length=3, max_length=200, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    perfil_id: int


class UsuarioMudanca(BaseModel):
    perfil_id: int | None = None
    ativo: bool | None = None


class AlteracaoResposta(BaseModel):
    id: int
    quando: datetime
    usuario_email: str
    usuario_nome: str | None
    acao: str
    tabela: str
    registro_id: int | None
    descricao: str | None
    campo: str | None
    antes: str | None
    depois: str | None


# O histórico de um registro, aberto no painel dele, pede só o "ver" do menu dono da tabela.
_FUSO = ZoneInfo("America/Sao_Paulo")
"""O período do filtro é o dia de quem usa o CRM, não o dia em UTC."""

_MENU_DA_TABELA = {
    "oportunidade": "funil.ver", "lead": "funil.ver", "proposta": "funil.ver", "pendencia_da_proposta": "funil.ver",
    "pessoa_contato": "contatos.ver", "empresa": "contatos.ver", "vinculo_de_contato": "contatos.ver",
    "contrato": "contratos.ver", "evento_de_contrato": "contratos.ver", "pedido_de_aprovacao": "contratos.ver", "grupo_economico": "grupos.ver",
}


# --------------------------------------------------------------------- rotas

def roteador_do_acesso(obter_sessao: Callable[[], Iterator[Session]], config: Callable[[], ConfiguracaoDeEntrada | None]) -> APIRouter:
    r = APIRouter(tags=["acesso"])

    def _resposta_do_perfil(sessao: Session, p: Perfil) -> PerfilResposta:
        pessoas = sessao.scalar(sa.select(sa.func.count()).where(Usuario.perfil_id == p.id, Usuario.ativo.is_(True)))
        return PerfilResposta(id=p.id, nome=p.nome, administrador=p.administrador,
                              permissoes=sorted(PERMISSOES) if p.administrador else sorted(p.permissoes or []), pessoas=pessoas)

    def _resposta_do_usuario(u: Usuario) -> UsuarioResposta:
        return UsuarioResposta(id=u.id, email=u.email, nome=u.nome, perfil_id=u.perfil_id, perfil=u.perfil.nome,
                               ativo=u.ativo, liberado_por=u.liberado_por, criado_em=u.criado_em)

    def _validas(permissoes: list[str]) -> list[str]:
        desconhecidas = sorted(set(permissoes) - PERMISSOES)
        if desconhecidas:
            raise HTTPException(422, f"funcionalidade desconhecida: {', '.join(desconhecidas)}")
        return sorted(set(permissoes))

    def _sobra_administrador(sessao: Session, sem_usuario: int) -> bool:
        return sessao.scalar(
            sa.select(sa.func.count()).select_from(Usuario).join(Perfil, Perfil.id == Usuario.perfil_id)
            .where(Perfil.administrador.is_(True), Usuario.ativo.is_(True), Usuario.id != sem_usuario)
        ) > 0

    @r.get("/api/acesso/entrada", response_model=Entrada)
    def entrada() -> Entrada:
        c = config()
        if c is None:
            return Entrada(modo="local")
        return Entrada(modo="microsoft", tenant_id=c.tenant_id, client_id=c.client_id, escopo=c.escopo)

    @r.get("/api/eu", response_model=Eu)
    def eu() -> Eu:
        u = usuario_atual.get()
        if u is None:  # sem login: a única pessoa é quem está na máquina do CRM
            return Eu(modo="local", email=None, nome=None, perfil="Sem login", administrador=True, permissoes=sorted(PERMISSOES))
        return Eu(modo="microsoft", email=u.email, nome=u.nome, perfil=u.perfil, administrador=u.administrador,
                  permissoes=sorted(PERMISSOES) if u.administrador else sorted(u.permissoes))

    @r.get("/api/acesso/catalogo", response_model=list[Menu])
    def catalogo() -> list[Menu]:
        return [Menu(chave=m, rotulo=rot, funcionalidades=[Funcionalidade(chave=f"{m}.{f}", rotulo=fr) for f, fr in fs])
                for m, rot, fs in MENUS]

    @r.get("/api/acesso/perfis", response_model=list[PerfilResposta])
    def perfis(sessao: Session = Depends(obter_sessao)) -> list[PerfilResposta]:
        return [_resposta_do_perfil(sessao, p) for p in sessao.scalars(sa.select(Perfil).order_by(Perfil.administrador.desc(), Perfil.nome))]

    @r.post("/api/acesso/perfis", response_model=PerfilResposta)
    def criar_perfil(corpo: PerfilNovo, sessao: Session = Depends(obter_sessao)) -> PerfilResposta:
        nome = corpo.nome.strip()
        if sessao.scalar(sa.select(Perfil).where(sa.func.lower(Perfil.nome) == nome.lower())):
            raise HTTPException(422, f"já existe o perfil {nome}")
        p = Perfil(nome=nome, administrador=False, permissoes=_validas(corpo.permissoes))
        sessao.add(p)
        sessao.commit()
        return _resposta_do_perfil(sessao, p)

    @r.patch("/api/acesso/perfis/{perfil_id}", response_model=PerfilResposta)
    def mudar_perfil(perfil_id: int, corpo: PerfilMudanca, sessao: Session = Depends(obter_sessao)) -> PerfilResposta:
        p = sessao.get(Perfil, perfil_id)
        if p is None:
            raise HTTPException(404, "perfil não encontrado")
        if p.administrador:
            raise HTTPException(422, "o Administrador tem tudo e não se muda: crie outro perfil")
        if corpo.nome is not None:
            nome = corpo.nome.strip()
            if sessao.scalar(sa.select(Perfil).where(sa.func.lower(Perfil.nome) == nome.lower(), Perfil.id != p.id)):
                raise HTTPException(422, f"já existe o perfil {nome}")
            p.nome = nome
        if corpo.permissoes is not None:
            p.permissoes = _validas(corpo.permissoes)
        sessao.commit()
        return _resposta_do_perfil(sessao, p)

    @r.get("/api/acesso/usuarios", response_model=list[UsuarioResposta])
    def usuarios(sessao: Session = Depends(obter_sessao)) -> list[UsuarioResposta]:
        return [_resposta_do_usuario(u) for u in sessao.scalars(sa.select(Usuario).order_by(Usuario.ativo.desc(), Usuario.email))]

    @r.post("/api/acesso/usuarios", response_model=UsuarioResposta)
    def liberar(corpo: UsuarioNovo, sessao: Session = Depends(obter_sessao)) -> UsuarioResposta:
        email = corpo.email.strip().lower()
        if sessao.get(Perfil, corpo.perfil_id) is None:
            raise HTTPException(422, "perfil não encontrado")
        u = sessao.scalar(sa.select(Usuario).where(Usuario.email == email))
        if u is not None:
            raise HTTPException(422, f"{email} já está na lista: mude o perfil ou reative por aqui")
        u = Usuario(email=email, perfil_id=corpo.perfil_id, liberado_por=quem_fez(None))
        sessao.add(u)
        sessao.commit()
        return _resposta_do_usuario(u)

    @r.patch("/api/acesso/usuarios/{usuario_id}", response_model=UsuarioResposta)
    def mudar_usuario(usuario_id: int, corpo: UsuarioMudanca, sessao: Session = Depends(obter_sessao)) -> UsuarioResposta:
        u = sessao.get(Usuario, usuario_id)
        if u is None:
            raise HTTPException(404, "pessoa não encontrada")
        perde_admin = (corpo.ativo is False) or (
            corpo.perfil_id is not None and not (sessao.get(Perfil, corpo.perfil_id) or Perfil(administrador=False)).administrador
        )
        if u.perfil.administrador and perde_admin and not _sobra_administrador(sessao, u.id):
            raise HTTPException(422, "precisa sobrar pelo menos um Administrador ativo")
        if corpo.perfil_id is not None:
            if sessao.get(Perfil, corpo.perfil_id) is None:
                raise HTTPException(422, "perfil não encontrado")
            u.perfil_id = corpo.perfil_id
        if corpo.ativo is not None:
            u.ativo = corpo.ativo
        sessao.commit()
        sessao.refresh(u)
        return _resposta_do_usuario(u)

    @r.get("/api/historico", response_model=list[AlteracaoResposta])
    def historico(
        sessao: Session = Depends(obter_sessao),
        usuario: str | None = None,
        tabela: str | None = None,
        registro_id: int | None = None,
        de: date | None = None,
        ate: date | None = None,
        limite: int = Query(default=200, ge=1, le=1000),
    ) -> list[AlteracaoResposta]:
        """Geral (Configurações › Histórico) pede `configuracoes.historico`; o de um registro, aberto no
        painel dele, pede só o "ver" do menu dono da tabela."""
        u = usuario_atual.get()
        if u is not None:
            de_um_registro = tabela is not None and registro_id is not None
            pedida = _MENU_DA_TABELA.get(tabela or "") if de_um_registro else None
            if not (u.pode("configuracoes.historico") or (pedida and u.pode(pedida))):
                raise HTTPException(403, "o seu perfil não libera o histórico de alterações")
        q = sa.select(RegistroDeAlteracao)
        if usuario:
            q = q.where(RegistroDeAlteracao.usuario_email == usuario.strip().lower())
        if tabela:
            q = q.where(RegistroDeAlteracao.tabela == tabela)
        if registro_id is not None:
            q = q.where(RegistroDeAlteracao.registro_id == registro_id)
        if de:
            q = q.where(RegistroDeAlteracao.quando >= datetime.combine(de, time.min, _FUSO).astimezone(timezone.utc))
        if ate:
            q = q.where(RegistroDeAlteracao.quando < datetime.combine(ate + timedelta(days=1), time.min, _FUSO).astimezone(timezone.utc))
        q = q.order_by(RegistroDeAlteracao.quando.desc(), RegistroDeAlteracao.id.desc()).limit(limite)
        return [AlteracaoResposta.model_validate(x, from_attributes=True) for x in sessao.scalars(q)]

    return r
