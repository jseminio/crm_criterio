"""Confere as variáveis de ambiente contra o catálogo único (`crm/config.py`, #93).

    python scripts/conferir_ambiente.py

Chamado pelo `atualizador.sh` antes de tocar no banco. Obrigatória ausente ou inválida: diz qual e
onde configurar (Coolify › crmcs › Environment Variables) e sai com 1 — a API não sobe. Opcional
ausente: diz que usa o padrão (ou que a função fica desligada). **Nunca imprime valor**: só nomes.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from crm.config import conferir  # noqa: E402
from crm.db.sessao import ler_ambiente  # noqa: E402


def main(valores: dict[str, str] | None = None) -> int:
    resultado = conferir(ler_ambiente() if valores is None else valores)
    for linha in resultado.linhas():
        print(linha, file=sys.stderr if linha.startswith("ERRO:") else sys.stdout)
    return 0 if resultado.ok else 1


if __name__ == "__main__":
    sys.exit(main())
