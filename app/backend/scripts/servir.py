"""Sobe a API para desenvolvimento local.

    ~/.venvs/criterio-crm/bin/python scripts/servir.py

⚠️ Escuta **só em 127.0.0.1**, de propósito. A API não tem autenticação
enquanto o E1 não trouxer o login pela conta corporativa Microsoft. Expor esta
porta na rede publicaria a carteira inteira sem senha.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(
        "crm.api.app:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(RAIZ / "src")],
    )
