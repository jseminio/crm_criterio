"""Identidade do build que está no ar (18/10/2026): o commit publicado e a data do build da API.

Substitui o "Versão 1.0" escrito à mão na tela, que ninguém incrementava. A tela mostra
`v2026.10.18 · a90b952`: a data diz "de quando é", o commit diz "qual código exatamente" — o mesmo que
se abre no GitHub.

- **Commit:** no container, `SOURCE_COMMIT`, que o Coolify entrega ao container em execução (não ao
  build: lá ele fica de fora por padrão, para não perder o cache das camadas). No desenvolvimento, sem
  a variável, pergunta ao git. Sem nenhum dos dois, `None` — a tela mostra só a data.
- **Data:** gravada em `DATA_DO_BUILD` pelo Dockerfile, na mesma camada que copia o código (muda quando
  o código da API muda). No desenvolvimento, a data do último commit.

Lido uma vez por processo: nada disso muda com a API no ar.
"""

from __future__ import annotations

import functools
import os
import re
import subprocess
from pathlib import Path

__all__ = ["identidade", "commit_curto"]

BACKEND = Path(__file__).resolve().parents[2]
ARQUIVO_DA_DATA = BACKEND / "DATA_DO_BUILD"
_HEX = re.compile(r"[0-9a-f]{7,40}")
_DATA = re.compile(r"\d{4}-\d{2}-\d{2}")


def commit_curto(valor: str | None) -> str | None:
    """Os 7 primeiros caracteres de um hash de commit; `None` para vazio ou o que não parece hash."""
    valor = (valor or "").strip().lower()
    return valor[:7] if _HEX.fullmatch(valor) else None


def _git(*argumentos: str) -> str | None:
    try:
        saida = subprocess.run(["git", *argumentos], cwd=BACKEND, capture_output=True, text=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout.strip() or None


def _data_do_build() -> str | None:
    try:
        texto = ARQUIVO_DA_DATA.read_text(encoding="utf-8").strip()
    except OSError:
        texto = _git("log", "-1", "--format=%cs") or ""
    return texto if _DATA.fullmatch(texto) else None


@functools.cache
def identidade() -> dict[str, str | None]:
    commit = commit_curto(os.environ.get("SOURCE_COMMIT")) or commit_curto(_git("rev-parse", "HEAD"))
    return {"commit": commit, "data_do_build": _data_do_build()}
