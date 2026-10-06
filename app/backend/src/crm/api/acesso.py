"""Rotas do acesso (E1, 02/10/2026): como entrar, quem entrou, perfis, pessoas e o histórico de
alterações. A checagem de cada rota contra o perfil fica no meio do caminho (`crm.api.app`), pelo
mapa de `crm.acesso.catalogo`. Desde 05/10/2026 (#89), também o login com e-mail e senha, a troca da
própria senha e a senha que quem administra define para os outros."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.acesso.auditoria import usuario_atual
from crm.acesso.catalogo import MENUS, PERMISSOES
from crm.acesso.entrada import (
    ConfiguracaoDeEntrada, ConfiguracaoDeSenha, EntradaRecusada, abrir_sessao, barrar_se_bloqueado, entrar_com_senha,
    perfil_administrador,
)
from crm.acesso.senha import Tentativas, confere, gerar_hash, problema_na_senha
from crm.db.modelos import Perfil, RegistroDeAlteracao, Usuario

__all__ = ["roteador_do_acesso", "quem_fez"]


def quem_fez(informado: str | None) -> str | None:
    """Com login, quem fez é quem entrou (o nome, ou o e-mail de quem ainda não tem nome); sem login, o
    que a tela informou."""
    u = usuario_atual.get()
    return (u.nome or u.email) if u else informado


# ------------------------------------------------------------------ esquemas

class Entrada(BaseModel):
    modo: str
    """"senha" (e-mail e senha do CRM), "microsoft" ou "local" (sem login, só na máquina do CRM)."""
    tenant_id: str | None = None
    client_id: str | None = None
    escopo: str | None = None


class Login(BaseModel):
    email: str = Field(max_length=200)
    senha: str = Field(max_length=1000)


class Sessao(BaseModel):
    token: str
    expira_em: datetime
    email: str
    nome: str | None
    perfil: str
    administrador: bool


class TrocaDeSenha(BaseModel):
    senha_atual: str = Field(max_length=1000)
    senha_nova: str


class SenhaNova(BaseModel):
    senha: str


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
    perfil_id: int | None = None
    """Sem perfil, a pessoa nasce Administrador (decisão de Eduardo, 05/10/2026)."""
    senha: str | None = None
    """A senha provisória, que a pessoa troca depois se quiser. Obrigatória no modo e-mail e senha."""


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

def roteador_do_acesso(
    obter_sessao: Callable[[], Iterator[Session]],
    config: Callable[[], ConfiguracaoDeSenha | ConfiguracaoDeEntrada | None],
    tentativas: Tentativas | None = None,
) -> APIRouter:
    r = APIRouter(tags=["acesso"])
    tentativas = tentativas or Tentativas()

    def _modo_senha() -> ConfiguracaoDeSenha:
        c = config()
        if not isinstance(c, ConfiguracaoDeSenha):
            raise HTTPException(404, "a entrada com e-mail e senha não está ligada neste CRM")
        return c

    def _senha_valida(senha: str) -> str:
        problema = problema_na_senha(senha)
        if problema:
            raise HTTPException(422, problema)
        return senha

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

    # Só sai o que foi preenchido: no modo senha, `{"modo": "senha"}`; os outros dois seguem com os
    # campos da Microsoft, nulos ou não, como antes do #89.
    @r.get("/api/acesso/entrada", response_model=Entrada, response_model_exclude_unset=True)
    def entrada() -> Entrada:
        c = config()
        if c is None:
            return Entrada(modo="local", tenant_id=None, client_id=None, escopo=None)
        if isinstance(c, ConfiguracaoDeSenha):
            return Entrada(modo="senha")
        return Entrada(modo="microsoft", tenant_id=c.tenant_id, client_id=c.client_id, escopo=c.escopo)

    def _sessao(u: Usuario, token: str, expira: datetime) -> Sessao:
        return Sessao(token=token, expira_em=expira, email=u.email, nome=u.nome, perfil=u.perfil.nome,
                      administrador=u.perfil.administrador)

    def _ip(request: Request) -> str:
        # Atrás do proxy, o uvicorn de produção (`proxy_headers`) já pôs aqui o IP de quem chamou.
        return request.client.host if request.client else "?"

    @r.post("/api/acesso/login", response_model=Sessao)
    def login(corpo: Login, request: Request, sessao: Session = Depends(obter_sessao, scope="function")) -> Sessao:
        """Pública. Erros: 401 e-mail ou senha errados (a mesma frase para os dois), 403 conta
        desativada (só depois da senha certa), 429 no bloqueio por tentativas (`Tentativas`)."""
        c = _modo_senha()
        try:
            u, token, expira = entrar_com_senha(sessao, corpo.email, corpo.senha, c, tentativas, _ip(request))
        except EntradaRecusada as recusa:
            raise HTTPException(recusa.status, recusa.mensagem) from None
        return _sessao(u, token, expira)

    @r.post("/api/acesso/senha", response_model=Sessao)
    def trocar_minha_senha(corpo: TrocaDeSenha, request: Request, sessao: Session = Depends(obter_sessao, scope="function")) -> Sessao:
        """Quem entrou troca a própria senha. A troca derruba as sessões abertas com a senha antiga,
        inclusive a deste pedido: por isso devolve uma sessão nova, no formato do login, que a tela
        guarda no lugar da antiga. Senha atual errada conta como tentativa errada (e respeita o
        bloqueio): uma sessão roubada não serve para adivinhar a senha."""
        c = _modo_senha()
        quem = usuario_atual.get()
        u = sessao.scalar(sa.select(Usuario).where(Usuario.email == quem.email)) if quem else None
        if u is None:
            raise HTTPException(404, "pessoa não encontrada")
        ip = _ip(request)
        try:
            barrar_se_bloqueado(tentativas, ip, u.email)
        except EntradaRecusada as recusa:
            raise HTTPException(recusa.status, recusa.mensagem) from None
        if not confere(corpo.senha_atual, u.senha_hash):
            tentativas.errou(ip, u.email)
            raise HTTPException(400, "A senha atual não confere.")
        tentativas.acertou(ip, u.email)
        u.senha_hash = gerar_hash(_senha_valida(corpo.senha_nova))
        sessao.commit()
        return _sessao(u, *abrir_sessao(u, c))

    @r.get("/api/eu", response_model=Eu)
    def eu() -> Eu:
        u = usuario_atual.get()
        if u is None:  # sem login: a única pessoa é quem está na máquina do CRM
            return Eu(modo="local", email=None, nome=None, perfil="Sem login", administrador=True, permissoes=sorted(PERMISSOES))
        c = config()
        return Eu(modo=c.modo if c else "local", email=u.email, nome=u.nome, perfil=u.perfil, administrador=u.administrador,
                  permissoes=sorted(PERMISSOES) if u.administrador else sorted(u.permissoes))

    @r.get("/api/acesso/catalogo", response_model=list[Menu])
    def catalogo() -> list[Menu]:
        return [Menu(chave=m, rotulo=rot, funcionalidades=[Funcionalidade(chave=f"{m}.{f}", rotulo=fr) for f, fr in fs])
                for m, rot, fs in MENUS]

    @r.get("/api/acesso/perfis", response_model=list[PerfilResposta])
    def perfis(sessao: Session = Depends(obter_sessao, scope="function")) -> list[PerfilResposta]:
        return [_resposta_do_perfil(sessao, p) for p in sessao.scalars(sa.select(Perfil).order_by(Perfil.administrador.desc(), Perfil.nome))]

    @r.post("/api/acesso/perfis", response_model=PerfilResposta)
    def criar_perfil(corpo: PerfilNovo, sessao: Session = Depends(obter_sessao, scope="function")) -> PerfilResposta:
        nome = corpo.nome.strip()
        if sessao.scalar(sa.select(Perfil).where(sa.func.lower(Perfil.nome) == nome.lower())):
            raise HTTPException(422, f"já existe o perfil {nome}")
        p = Perfil(nome=nome, administrador=False, permissoes=_validas(corpo.permissoes))
        sessao.add(p)
        sessao.commit()
        return _resposta_do_perfil(sessao, p)

    @r.patch("/api/acesso/perfis/{perfil_id}", response_model=PerfilResposta)
    def mudar_perfil(perfil_id: int, corpo: PerfilMudanca, sessao: Session = Depends(obter_sessao, scope="function")) -> PerfilResposta:
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
    def usuarios(sessao: Session = Depends(obter_sessao, scope="function")) -> list[UsuarioResposta]:
        return [_resposta_do_usuario(u) for u in sessao.scalars(sa.select(Usuario).order_by(Usuario.ativo.desc(), Usuario.email))]

    @r.post("/api/acesso/usuarios", response_model=UsuarioResposta)
    def liberar(corpo: UsuarioNovo, sessao: Session = Depends(obter_sessao, scope="function")) -> UsuarioResposta:
        email = corpo.email.strip().lower()
        if corpo.perfil_id is not None and sessao.get(Perfil, corpo.perfil_id) is None:
            raise HTTPException(422, "perfil não encontrado")
        if corpo.senha is None and isinstance(config(), ConfiguracaoDeSenha):
            raise HTTPException(422, "Informe a senha provisória: sem ela a pessoa não consegue entrar.")
        senha_hash = gerar_hash(_senha_valida(corpo.senha)) if corpo.senha is not None else None
        u = sessao.scalar(sa.select(Usuario).where(Usuario.email == email))
        if u is not None:
            raise HTTPException(422, f"{email} já está na lista: mude o perfil ou reative por aqui")
        perfil_id = corpo.perfil_id if corpo.perfil_id is not None else perfil_administrador(sessao).id
        u = Usuario(email=email, perfil_id=perfil_id, liberado_por=quem_fez(None), senha_hash=senha_hash)
        sessao.add(u)
        sessao.commit()
        return _resposta_do_usuario(u)

    @r.post("/api/acesso/usuarios/{usuario_id}/senha", status_code=204)
    def redefinir_senha(usuario_id: int, corpo: SenhaNova, sessao: Session = Depends(obter_sessao, scope="function")) -> None:
        """Quem administra define uma senha nova para alguém (esqueceu, ou veio do tempo da Microsoft).
        Derruba as sessões abertas da pessoa (o carimbo da senha muda) e tira o bloqueio por tentativas
        erradas desse e-mail, em todos os IPs. Só no modo e-mail e senha, como as outras rotas de senha."""
        _modo_senha()
        u = sessao.get(Usuario, usuario_id)
        if u is None:
            raise HTTPException(404, "pessoa não encontrada")
        u.senha_hash = gerar_hash(_senha_valida(corpo.senha))
        sessao.commit()
        tentativas.liberar(u.email)

    @r.patch("/api/acesso/usuarios/{usuario_id}", response_model=UsuarioResposta)
    def mudar_usuario(usuario_id: int, corpo: UsuarioMudanca, sessao: Session = Depends(obter_sessao, scope="function")) -> UsuarioResposta:
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
        sessao: Session = Depends(obter_sessao, scope="function"),
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
