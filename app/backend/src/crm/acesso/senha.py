"""Senha, sessão e tentativas erradas da entrada com e-mail e senha (#89, 05/10/2026).

Decisão de Eduardo: o login pela conta Microsoft fica desligado (o código fica, em
`crm.acesso.entrada`) e cada pessoa entra com e-mail e senha cadastrados no próprio CRM. Três peças,
todas da biblioteca padrão mais a PyJWT, que já era dependência:

- **A senha guardada** é só o hash `scrypt`, com sal aleatório, num texto que diz como foi feito
  (`scrypt$n$r$p$sal$hash`): se um dia o custo subir, os hashes antigos continuam conferindo. A
  conferência é em tempo constante (`hmac.compare_digest`).
- **A sessão** é um JWT HS256 assinado com `CRM_SEGREDO_SESSAO`, com o e-mail em `sub` e validade de
  12 horas (um dia de trabalho). O token só diz quem é: o que a pessoa pode, e se ainda está ativa,
  a API relê do banco a cada pedido. Desativar corta o acesso no pedido seguinte.
- **Tentativas erradas:** 5 seguidas para o mesmo e-mail em 15 minutos bloqueiam esse e-mail por 15
  minutos. Ficam na memória do processo: a API de produção roda num processo só
  (`servir_producao.py`), e reiniciar zera — aceitável para quem só quer frear a adivinhação.

**Senha e segredo nunca vão para log nem para mensagem de erro.**
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import math
import secrets
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

__all__ = [
    "SESSAO_INVALIDA", "Tentativas", "carimbo_da_senha", "confere", "email_da_sessao", "emitir_sessao", "gerar_hash",
    "ler_sessao", "problema_na_senha",
]

MINIMO = 8
MAXIMO = 200
"""Teto só para ninguém mandar um texto enorme para o scrypt; não é regra de negócio."""
VALIDADE = timedelta(hours=12)
TENTATIVAS = 5
JANELA = timedelta(minutes=15)
"""Vale para as duas coisas: o tempo em que os erros se somam e o tempo do bloqueio."""
SESSAO_INVALIDA = "Sessão expirada ou inválida. Entre de novo."

# Custo do scrypt: 16 MiB de memória e uns 50 ms por conferência. Cabe no limite padrão do OpenSSL
# (32 MiB) e torna a adivinhação em massa cara, sem pesar no login de quem acerta.
_N, _R, _P, _TAMANHO = 2**14, 8, 1, 32
_DE_MENTIRA = f"scrypt${_N}${_R}${_P}${base64.b64encode(bytes(16)).decode()}${base64.b64encode(bytes(_TAMANHO)).decode()}"
"""Conferido quando o e-mail não existe ou nunca teve senha: a resposta leva o mesmo tempo, e o
tempo não conta quem tem conta no CRM."""


def problema_na_senha(senha: str) -> str | None:
    """A regra de senha nova, com a frase que a tela mostra; `None` quando está boa."""
    if len(senha) < MINIMO:
        return f"A senha precisa ter pelo menos {MINIMO} caracteres."
    if len(senha) > MAXIMO:
        return f"A senha pode ter no máximo {MAXIMO} caracteres."
    return None


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def gerar_hash(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode("utf-8"), salt=sal, n=_N, r=_R, p=_P, dklen=_TAMANHO)
    return f"scrypt${_N}${_R}${_P}${_b64(sal)}${_b64(h)}"


def confere(senha: str, guardado: str | None) -> bool:
    """A senha bate com o hash guardado? Hash ausente ou estragado é sempre "não", depois de gastar
    o mesmo tempo de uma conferência de verdade."""
    try:
        algoritmo, n, r, p, sal, h = (guardado or _DE_MENTIRA).split("$")
        esperado = base64.b64decode(h, validate=True)
        calculado = hashlib.scrypt(senha.encode("utf-8"), salt=base64.b64decode(sal, validate=True),
                                   n=int(n), r=int(r), p=int(p), dklen=len(esperado))
    except (ValueError, TypeError):
        return False
    return guardado is not None and algoritmo == "scrypt" and hmac.compare_digest(calculado, esperado)


def carimbo_da_senha(senha_hash: str | None) -> str:
    """Muda sempre que a senha muda (o hash tem sal novo a cada troca). Vai na sessão como `sv`: senha
    trocada ou redefinida derruba as sessões abertas com a senha anterior. Não revela o hash."""
    return hashlib.sha256((senha_hash or "").encode("utf-8")).hexdigest()[:16]


def emitir_sessao(email: str, segredo: str, agora: datetime | None = None, carimbo: str = "") -> tuple[str, datetime]:
    """O token da sessão e quando ele vence."""
    import jwt

    inicio = agora or datetime.now(timezone.utc)
    expira = inicio + VALIDADE
    return jwt.encode({"sub": email, "sv": carimbo, "iat": inicio, "exp": expira}, segredo, algorithm="HS256"), expira


def ler_sessao(token: str, segredo: str) -> tuple[str, str] | None:
    """O e-mail de quem entrou e o carimbo da senha, ou `None` quando o token não vale (assinatura,
    formato ou validade). Token sem carimbo vem com `""`, que não bate com senha nenhuma."""
    import jwt

    try:
        claims = jwt.decode(token, segredo, algorithms=["HS256"], options={"require": ["sub", "exp"]})
    except jwt.PyJWTError:
        return None
    email = str(claims.get("sub") or "").strip().lower()
    return (email, str(claims.get("sv") or "")) if email else None


def email_da_sessao(token: str, segredo: str) -> str | None:
    """Só o e-mail de `ler_sessao`."""
    lida = ler_sessao(token, segredo)
    return lida[0] if lida else None


TENTATIVAS_POR_IP = 20
"""Erros de um mesmo IP, com qualquer e-mail, na janela: freia quem testa uma senha em muitas contas."""

_Chave = tuple[str, ...]


class Tentativas:
    """Os erros de senha na memória do processo, em duas contas (endurecimento de 05/10/2026, #89):

    - **(IP, e-mail):** 5 erros seguidos bloqueiam aquele e-mail **só para aquele IP**. Contar só pelo
      e-mail deixaria qualquer um trancar o Administrador de fora errando a senha dele de propósito.
    - **IP:** 20 erros com quaisquer e-mails bloqueiam o IP inteiro (quem testa uma senha comum em
      muitas contas).

    "Seguidos": acertar zera a conta daquele e-mail naquele IP; a do IP só a janela zera."""

    def __init__(self, relogio: Callable[[], datetime] | None = None) -> None:
        self._relogio = relogio or (lambda: datetime.now(timezone.utc))
        self._erros: dict[_Chave, list[datetime]] = {}
        self._bloqueado_ate: dict[_Chave, datetime] = {}
        self._trava = threading.Lock()  # o login roda nas threads do FastAPI

    def minutos_de_bloqueio(self, ip: str, email: str) -> int | None:
        """Quantos minutos faltam, arredondados para cima; `None` quando o IP pode tentar esse e-mail."""
        with self._trava:
            agora = self._relogio()
            faltam = None
            for chave in (("par", ip, email), ("ip", ip)):
                ate = self._bloqueado_ate.get(chave)
                if ate is not None and ate <= agora:
                    del self._bloqueado_ate[chave]
                elif ate is not None:
                    faltam = max(faltam or 0, math.ceil((ate - agora).total_seconds() / 60), 1)
            return faltam

    def errou(self, ip: str, email: str) -> None:
        """Mais um erro, nas duas contas; a que chega ao limite dentro da janela bloqueia pela janela inteira."""
        with self._trava:
            agora = self._relogio()
            for chave, limite in ((("par", ip, email), TENTATIVAS), (("ip", ip), TENTATIVAS_POR_IP)):
                erros = [t for t in self._erros.get(chave, []) if agora - t < JANELA] + [agora]
                if len(erros) >= limite:
                    self._erros.pop(chave, None)
                    self._bloqueado_ate[chave] = agora + JANELA
                else:
                    self._erros[chave] = erros
            if len(self._erros) > 1000:  # e-mails inventados não ficam ocupando memória para sempre
                self._erros = {c: ts for c, ts in self._erros.items() if agora - ts[-1] < JANELA}
            if len(self._bloqueado_ate) > 1000:  # idem para os bloqueios que já venceram
                self._bloqueado_ate = {c: ate for c, ate in self._bloqueado_ate.items() if ate > agora}

    def acertou(self, ip: str, email: str) -> None:
        """Acertou a senha: os erros daquele e-mail naquele IP deixam de contar."""
        with self._trava:
            self._erros.pop(("par", ip, email), None)
            self._bloqueado_ate.pop(("par", ip, email), None)

    def liberar(self, email: str) -> None:
        """Quem administra redefiniu a senha: o e-mail sai do bloqueio em todos os IPs."""
        with self._trava:
            for d in (self._erros, self._bloqueado_ate):
                for chave in [c for c in d if c[0] == "par" and c[2] == email]:
                    del d[chave]
