"""Cifra dos segredos guardados pela tela (07/10/2026).

Os segredos ficam no banco cifrados com Fernet (AES-128 com autenticação). A chave da cifra vem de
`CRM_SEGREDO_SESSAO`, que o servidor já exige para subir: nada novo para configurar. Sem ela (o CRM na
máquina, sem login), a chave é um arquivo gerado na primeira vez ao lado do `.env`, fora do Git.

Trocar `CRM_SEGREDO_SESSAO` torna ilegíveis os segredos já salvos: a tela avisa "cadastre de novo" no
campo, e nada mais quebra. **Nenhum valor passa por log ou mensagem de erro.**
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from crm.db import sessao as _sessao
from crm.db.sessao import ler_ambiente

__all__ = ["SegredoIlegivel", "cifrar", "decifrar", "arquivo_da_chave"]

_CONTEXTO = b"crm-criterio:configuracao:v1:"


class SegredoIlegivel(ValueError):
    """O segredo foi cifrado com outra chave (o segredo das sessões mudou): cadastre de novo."""


def _chave() -> bytes:
    semente = (ler_ambiente().get("CRM_SEGREDO_SESSAO") or "").strip()
    if not semente:
        semente = _semente_local()
    return base64.urlsafe_b64encode(hashlib.sha256(_CONTEXTO + semente.encode()).digest())


def arquivo_da_chave() -> Path:
    """Ao lado do `.env` do backend (o teste troca o `.env` e leva o arquivo junto)."""
    return _sessao.ARQUIVO_ENV.parent / ".chave_da_configuracao"


def _semente_local() -> str:
    arquivo = arquivo_da_chave()
    if arquivo.is_file():
        return arquivo.read_text(encoding="utf-8").strip()
    semente = base64.urlsafe_b64encode(os.urandom(32)).decode()
    arquivo.write_text(semente + "\n", encoding="utf-8")
    try:
        arquivo.chmod(0o600)
    except OSError:  # pragma: no cover — sistema sem permissões POSIX
        pass
    return semente


def cifrar(valor: str) -> str:
    return Fernet(_chave()).encrypt(valor.encode()).decode()


def decifrar(cifrado: str) -> str:
    try:
        return Fernet(_chave()).decrypt(cifrado.encode()).decode()
    except InvalidToken as falha:
        raise SegredoIlegivel("o segredo foi salvo com outra chave: cadastre de novo") from falha
