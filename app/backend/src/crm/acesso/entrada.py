"""Entrada no CRM: com e-mail e senha, com a conta Microsoft, ou sem login (E1, 02/10/2026; #89, 05/10/2026).

**Três modos, nesta ordem de precedência** (decisão de Eduardo, 05/10/2026):

1. **E-mail e senha** (`"senha"`), quando há `CRM_ADMIN_EMAIL`. A senha é do próprio CRM
   (`crm.acesso.senha`); a tela entra por `POST /api/acesso/login` e manda o token da sessão em cada
   pedido. É o modo do servidor.
2. **Conta Microsoft** (`"microsoft"`), quando há os dois IDs do Entra e não há `CRM_ADMIN_EMAIL`. O
   token vem da Microsoft; aqui se confere a assinatura, o emissor (o tenant da Critério) e o
   destinatário (o aplicativo do CRM). Desligado no servidor, mas guardado: voltar é tirar
   `CRM_ADMIN_EMAIL` do `.env`.
3. **Sem login** (`"local"`), sem nenhuma das duas: só na máquina do CRM, e a tela avisa.

Nos dois primeiros, a pessoa precisa estar em `usuario`, ativa: quem entra é conferido pela senha
ou pela Microsoft; o que pode, o CRM decide (o perfil).

Configuração no `.env`:

    CRM_ADMIN_EMAIL=…            liga o modo e-mail e senha; a conta nasce Administrador
    CRM_ADMIN_SENHA_INICIAL=…    a senha dessa conta quando ela é criada (o .env só semeia)
    CRM_SEGREDO_SESSAO=…         assina as sessões; gere com `openssl rand -hex 32`
    CRM_ENTRA_TENANT_ID=…        o "ID do diretório (locatário)" no Entra
    CRM_ENTRA_CLIENT_ID=…        o "ID do aplicativo (cliente)" do CRM
    CRM_ADMINISTRADORES=…        e-mails que entram como Administrador na primeira vez (vírgula)
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import hmac

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.acesso.auditoria import UsuarioAtual
from crm.acesso.senha import (
    SESSAO_INVALIDA, Tentativas, carimbo_da_senha, confere, emitir_sessao, gerar_hash, problema_na_senha,
)
from crm.db.modelos import Perfil, Usuario
from crm.db.sessao import ler_ambiente

__all__ = [
    "VARIAVEIS", "ConfiguracaoDeEntrada", "ConfiguracaoDeSenha", "EntradaMalConfigurada", "EntradaRecusada",
    "abrir_sessao", "barrar_se_bloqueado", "entrar_com_senha", "ler_configuracao", "perfil_administrador", "pessoa_do_email", "pessoa_do_token",
    "semear_administrador", "validador_da_microsoft",
]

ADMINISTRADOR = "Administrador"
VARIAVEIS = ("CRM_ADMIN_EMAIL", "CRM_ADMIN_SENHA_INICIAL", "CRM_SEGREDO_SESSAO",
             "CRM_ENTRA_TENANT_ID", "CRM_ENTRA_CLIENT_ID", "CRM_ADMINISTRADORES")
SEGREDO_MINIMO = 32
SENHA_ERRADA = "E-mail ou senha incorretos."
"""A mesma frase para e-mail que não existe e senha errada: a tela não revela quem tem conta."""
DESATIVADA = "Esta conta está desativada no CRM. Fale com quem administra o CRM."


class EntradaRecusada(Exception):
    def __init__(self, status: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


class EntradaMalConfigurada(RuntimeError):
    """O `.env` pede um modo de entrada que não fecha. A API não sobe: subir sem a trava publicaria a
    carteira, e inventar um segredo derrubaria as sessões a cada reinício."""


@dataclass(frozen=True)
class ConfiguracaoDeEntrada:
    """A entrada pela conta Microsoft."""

    tenant_id: str
    client_id: str
    administradores: frozenset[str]
    modo = "microsoft"

    @property
    def escopo(self) -> str:
        return f"api://{self.client_id}/acesso"


@dataclass(frozen=True)
class ConfiguracaoDeSenha:
    """A entrada com e-mail e senha. Segredo e senha ficam fora do `repr`: imprimir a configuração
    num log não os mostra."""

    admin_email: str
    segredo: str = field(repr=False)
    admin_senha_inicial: str | None = field(default=None, repr=False)
    modo = "senha"


def ler_configuracao(valores: dict[str, str] | None = None) -> ConfiguracaoDeSenha | ConfiguracaoDeEntrada | None:
    """O modo de entrada pelo `.env`: e-mail e senha, conta Microsoft ou `None` (sem login)."""
    v = valores if valores is not None else ler_ambiente()
    admin = (v.get("CRM_ADMIN_EMAIL") or "").strip().lower()
    if admin:
        if "@" not in admin:
            raise EntradaMalConfigurada("CRM_ADMIN_EMAIL no backend/.env não parece um e-mail. A API não subiu.")
        segredo = (v.get("CRM_SEGREDO_SESSAO") or "").strip()
        if not segredo:
            raise EntradaMalConfigurada(
                "CRM_ADMIN_EMAIL liga a entrada com e-mail e senha, mas falta CRM_SEGREDO_SESSAO no backend/.env "
                "(gere com: openssl rand -hex 32). A API não subiu."
            )
        if len(segredo) < SEGREDO_MINIMO:  # segredo curto deixa forjar sessão por força bruta, em qualquer forma de subir a API
            raise EntradaMalConfigurada(
                f"CRM_SEGREDO_SESSAO precisa de pelo menos {SEGREDO_MINIMO} caracteres (gere com: openssl rand -hex 32). "
                "A API não subiu."
            )
        return ConfiguracaoDeSenha(admin, segredo, v.get("CRM_ADMIN_SENHA_INICIAL") or None)
    tenant, cliente = (v.get("CRM_ENTRA_TENANT_ID") or "").strip(), (v.get("CRM_ENTRA_CLIENT_ID") or "").strip()
    if not tenant or not cliente:
        return None
    admins = frozenset(e.strip().lower() for e in (v.get("CRM_ADMINISTRADORES") or "").split(",") if e.strip())
    return ConfiguracaoDeEntrada(tenant, cliente, admins)


def perfil_administrador(sessao: Session) -> Perfil:
    """O perfil Administrador; a migração o cria, mas um banco sem ele ganha um aqui."""
    admin = sessao.scalar(sa.select(Perfil).where(Perfil.administrador.is_(True)).order_by(Perfil.id).limit(1))
    if admin is None:
        admin = Perfil(nome=ADMINISTRADOR, administrador=True, permissoes=[])
        sessao.add(admin)
        sessao.flush()
    return admin


def _quem(u: Usuario) -> UsuarioAtual:
    p = u.perfil
    return UsuarioAtual(email=u.email, nome=u.nome, perfil=p.nome, administrador=p.administrador,
                        permissoes=frozenset(p.permissoes or []))


# ------------------------------------------------------------------ conta Microsoft

def validador_da_microsoft(config: ConfiguracaoDeEntrada) -> Callable[[str], dict[str, Any]]:
    """Confere o token com as chaves públicas do tenant (guardadas em memória pelo PyJWKClient)."""
    import jwt

    chaves = jwt.PyJWKClient(f"https://login.microsoftonline.com/{config.tenant_id}/discovery/v2.0/keys", cache_keys=True)

    def validar(token: str) -> dict[str, Any]:
        try:
            chave = chaves.get_signing_key_from_jwt(token)
            return jwt.decode(
                token, chave.key, algorithms=["RS256"],
                audience=[config.client_id, f"api://{config.client_id}"],
                issuer=f"https://login.microsoftonline.com/{config.tenant_id}/v2.0",
            )
        except jwt.PyJWTError as falha:
            raise EntradaRecusada(401, "A entrada expirou ou não vale. Entre de novo.") from falha

    return validar


def pessoa_do_token(sessao: Session, claims: dict[str, Any], config: ConfiguracaoDeEntrada) -> UsuarioAtual:
    """Acha a pessoa pelo e-mail da conta Microsoft. E-mail em `CRM_ADMINISTRADORES` que ainda não
    existe nasce Administrador: é assim que o primeiro acesso acontece."""
    email = str(claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "").strip().lower()
    if not email:
        raise EntradaRecusada(401, "A conta Microsoft não informou o e-mail.")
    nome = claims.get("name")
    u = sessao.scalar(sa.select(Usuario).where(Usuario.email == email))
    if u is None and email in config.administradores:
        u = Usuario(email=email, nome=nome, perfil_id=perfil_administrador(sessao).id, liberado_por="CRM_ADMINISTRADORES")
        sessao.add(u)
        sessao.commit()
    if u is None or not u.ativo:
        raise EntradaRecusada(
            403, f"A conta {email} ainda não tem perfil no CRM. Peça a quem administra para liberar em "
                 "Configurações › Perfis e acesso.",
        )
    if nome and u.nome != nome:  # o nome vem da Microsoft; fica guardado para o histórico
        u.nome = nome
        sessao.commit()
    return _quem(u)


# ------------------------------------------------------------------ e-mail e senha

def semear_administrador(sessao: Session, config: ConfiguracaoDeSenha) -> None:
    """O primeiro acesso no modo e-mail e senha, ao subir a API: sem conta para `CRM_ADMIN_EMAIL`,
    ela nasce Administrador com `CRM_ADMIN_SENHA_INICIAL`. **O `.env` só semeia:** conta que já
    existe fica como está, e a senha trocada na tela não volta a ser a do `.env` a cada reinício. A
    única exceção é a conta que existe **sem senha nenhuma** (vinda do tempo do login Microsoft):
    ela recebe a inicial, senão ninguém entraria."""
    u = sessao.scalar(sa.select(Usuario).where(Usuario.email == config.admin_email))
    if u is not None and u.senha_hash:
        return
    if not config.admin_senha_inicial:
        raise EntradaMalConfigurada(
            f"A conta {config.admin_email} (CRM_ADMIN_EMAIL) ainda não tem senha, e falta CRM_ADMIN_SENHA_INICIAL "
            "no backend/.env para criá-la. A API não subiu."
        )
    problema = problema_na_senha(config.admin_senha_inicial)
    if problema:
        raise EntradaMalConfigurada(f"CRM_ADMIN_SENHA_INICIAL não serve: {problema} A API não subiu.")
    if u is None:
        u = Usuario(email=config.admin_email, perfil_id=perfil_administrador(sessao).id, liberado_por="CRM_ADMIN_EMAIL")
        sessao.add(u)
    u.senha_hash = gerar_hash(config.admin_senha_inicial)
    sessao.commit()


def barrar_se_bloqueado(tentativas: Tentativas, ip: str, email: str) -> None:
    """429 enquanto esse IP está bloqueado para esse e-mail (ou para todos), mesmo com a senha certa:
    senão o bloqueio não freava nada."""
    minutos = tentativas.minutos_de_bloqueio(ip, email)
    if minutos:
        raise EntradaRecusada(429, f"Muitas tentativas. Tente de novo em {minutos} {'minuto' if minutos == 1 else 'minutos'}.")


def abrir_sessao(u: Usuario, config: ConfiguracaoDeSenha) -> tuple[str, datetime]:
    """O token, com o carimbo da senha atual: trocar a senha derruba as sessões anteriores."""
    return emitir_sessao(u.email, config.segredo, carimbo=carimbo_da_senha(u.senha_hash))


def entrar_com_senha(
    sessao: Session, email: str, senha: str, config: ConfiguracaoDeSenha, tentativas: Tentativas, ip: str = "?",
) -> tuple[Usuario, str, datetime]:
    """Confere e-mail e senha e abre a sessão: a pessoa, o token e quando ele vence.

    Recusa com 429 no bloqueio (`barrar_se_bloqueado`), 401 para e-mail ou senha errados, e 403 para
    conta desativada — esse só depois da senha certa, para a frase não revelar a quem não sabe a senha
    que a conta existe."""
    email = email.strip().lower()
    barrar_se_bloqueado(tentativas, ip, email)
    u = sessao.scalar(sa.select(Usuario).where(Usuario.email == email))
    if not confere(senha, u.senha_hash if u is not None else None):
        tentativas.errou(ip, email)
        raise EntradaRecusada(401, SENHA_ERRADA)
    tentativas.acertou(ip, email)
    if not u.ativo:
        raise EntradaRecusada(403, DESATIVADA)
    token, expira = abrir_sessao(u, config)
    return u, token, expira


def pessoa_do_email(sessao: Session, email: str | None, carimbo: str | None = None) -> UsuarioAtual:
    """Quem é o dono da sessão, relido do banco a cada pedido: perfil mudado vale no pedido seguinte;
    conta desativada é recusada mesmo com a sessão ainda no prazo; senha trocada ou redefinida
    (carimbo diferente) derruba a sessão."""
    if not email:
        raise EntradaRecusada(401, SESSAO_INVALIDA)
    u = sessao.scalar(sa.select(Usuario).where(Usuario.email == email))
    if u is None or not hmac.compare_digest(carimbo or "", carimbo_da_senha(u.senha_hash)):
        raise EntradaRecusada(401, SESSAO_INVALIDA)
    if not u.ativo:
        raise EntradaRecusada(401, DESATIVADA)
    return _quem(u)
