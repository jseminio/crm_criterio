"""Sobe a API no servidor (05/10/2026), atrás do proxy que serve a tela e o HTTPS.

    python scripts/servir_producao.py

Passo a passo completo em `app/IMPLANTACAO.md`. Diferenças do `servir.py` (desenvolvimento):

- **Recusa subir sem o login da Microsoft** (`CRM_ENTRA_TENANT_ID` e `CRM_ENTRA_CLIENT_ID` no
  ambiente ou no `backend/.env`). Sem eles a API não pede entrada: no servidor, isso publicaria a
  carteira inteira sem senha.
- Sem recarga automática e com **um processo só**: a busca automática dos questionários roda dentro
  da API, e vários processos a repetiriam.
- Escuta em `CRM_HOST`:`CRM_PORTA` (padrão `127.0.0.1:8000`): só o proxy da mesma máquina fala com
  ela. Confia nos cabeçalhos `X-Forwarded-*` só desse proxy.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from crm.acesso.entrada import ler_configuracao  # noqa: E402
from crm.db.sessao import ler_ambiente  # noqa: E402

SEM_LOGIN = (
    "✗ Faltam CRM_ENTRA_TENANT_ID e CRM_ENTRA_CLIENT_ID no backend/.env. Sem eles a API sobe sem login "
    "e a carteira fica aberta a quem achar o endereço. Veja app/IMPLANTACAO.md, passo 4. Nada foi iniciado."
)


def parametros(ambiente: dict[str, str]) -> dict:
    """O que o uvicorn recebe, ou `SystemExit` quando falta o login. Separado para o teste."""
    if ler_configuracao(ambiente) is None:
        raise SystemExit(SEM_LOGIN)
    host = (ambiente.get("CRM_HOST") or "127.0.0.1").strip()
    return {
        "host": host,
        "port": int((ambiente.get("CRM_PORTA") or "8000").strip()),
        "workers": 1,
        "proxy_headers": True,
        "forwarded_allow_ips": "127.0.0.1",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("crm.api.app:app", **parametros(ler_ambiente()))
