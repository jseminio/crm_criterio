"""Entrada no CRM com a conta Microsoft (E1, 02/10/2026).

A tela entra pela Microsoft (Entra ID) e manda o token em cada pedido; aqui se confere a assinatura,
o emissor (o tenant da Critério) e o destinatário (o aplicativo do CRM), e se acha a pessoa em
`usuario`. A Microsoft confere quem é; o CRM decide o que pode (o perfil).

Configuração no `.env` (sem segredo: o tenant e o id do aplicativo não são senha):

    CRM_ENTRA_TENANT_ID=…        o "ID do diretório (locatário)" no Entra
    CRM_ENTRA_CLIENT_ID=…        o "ID do aplicativo (cliente)" do CRM
    CRM_ADMINISTRADORES=…        e-mails que entram como Administrador na primeira vez (vírgula)

Sem `CRM_ENTRA_TENANT_ID` e `CRM_ENTRA_CLIENT_ID`, o CRM segue **sem login**, como até o E1: só na
máquina do CRM, e a tela avisa.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.acesso.auditoria import UsuarioAtual
from crm.db.modelos import Perfil, Usuario
from crm.db.sessao import ler_ambiente

__all__ = ["ConfiguracaoDeEntrada", "EntradaRecusada", "ler_configuracao", "validador_da_microsoft", "pessoa_do_token"]

ADMINISTRADOR = "Administrador"


class EntradaRecusada(Exception):
    def __init__(self, status: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status
        self.mensagem = mensagem


@dataclass(frozen=True)
class ConfiguracaoDeEntrada:
    tenant_id: str
    client_id: str
    administradores: frozenset[str]

    @property
    def escopo(self) -> str:
        return f"api://{self.client_id}/acesso"


def ler_configuracao(valores: dict[str, str] | None = None) -> ConfiguracaoDeEntrada | None:
    v = valores if valores is not None else ler_ambiente()
    tenant, cliente = (v.get("CRM_ENTRA_TENANT_ID") or "").strip(), (v.get("CRM_ENTRA_CLIENT_ID") or "").strip()
    if not tenant or not cliente:
        return None
    admins = frozenset(e.strip().lower() for e in (v.get("CRM_ADMINISTRADORES") or "").split(",") if e.strip())
    return ConfiguracaoDeEntrada(tenant, cliente, admins)


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
        admin = sessao.scalar(sa.select(Perfil).where(Perfil.administrador.is_(True)).order_by(Perfil.id).limit(1))
        if admin is None:
            admin = Perfil(nome=ADMINISTRADOR, administrador=True, permissoes=[])
            sessao.add(admin)
            sessao.flush()
        u = Usuario(email=email, nome=nome, perfil_id=admin.id, liberado_por="CRM_ADMINISTRADORES")
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
    p = u.perfil
    return UsuarioAtual(email=email, nome=u.nome, perfil=p.nome, administrador=p.administrador,
                        permissoes=frozenset(p.permissoes or []))
