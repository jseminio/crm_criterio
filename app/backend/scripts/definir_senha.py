"""Grava a senha do banco no `.env` e testa a conexão na hora.

Uma pergunta só. A senha não aparece na tela, não vai para o histórico do
shell e não passa por chat nenhum.

Uso, num Terminal de verdade:
    ~/.venvs/criterio-crm/bin/python scripts/definir_senha.py
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / ".env"
CHAVE = "CRM_DB_PASSWORD"


def _trocar_a_linha(conteudo: str, senha: str) -> str:
    """Substitui só a linha da senha, preservando todo o resto do arquivo."""
    linhas = conteudo.splitlines()
    for indice, linha in enumerate(linhas):
        if linha.strip().startswith(f"{CHAVE}="):
            linhas[indice] = f"{CHAVE}={senha}"
            return "\n".join(linhas) + "\n"
    linhas.append(f"{CHAVE}={senha}")
    return "\n".join(linhas) + "\n"


def principal() -> int:
    if not sys.stdin.isatty():
        print(
            "Este comando pede a senha e precisa de um Terminal de verdade.\n"
            "Digite-o no Terminal — não use botão de executar.",
            file=sys.stderr,
        )
        return 2

    if not ARQUIVO.is_file():
        print(f"✗ {ARQUIVO} não existe.", file=sys.stderr)
        return 1

    print(f"Senha do usuário criterio_crm no PostgreSQL.")
    print("Ela não aparece enquanto você digita — isso é normal.\n")

    senha = getpass.getpass("Senha: ")
    if not senha:
        print("\n✗ Senha vazia. Nada foi gravado.")
        return 1
    if senha != getpass.getpass("Digite de novo: "):
        print("\n✗ As duas não conferem. Nada foi gravado.")
        return 1

    ARQUIVO.write_text(
        _trocar_a_linha(ARQUIVO.read_text(encoding="utf-8"), senha), encoding="utf-8"
    )
    ARQUIVO.chmod(0o600)
    print(f"\n✓ Gravada em {ARQUIVO.name}, legível só por você.")

    sys.path.insert(0, str(RAIZ / "src"))
    try:
        import sqlalchemy as sa

        from crm.db.sessao import criar_engine, url_do_banco

        with criar_engine(url_do_banco()).connect() as conexao:
            print("✓ CONECTOU ao PostgreSQL", conexao.scalar(sa.text("show server_version")))
            print("  banco:", conexao.scalar(sa.text("select current_database()")))
            print("  usuário:", conexao.scalar(sa.text("select current_user")))
        print("\nPronto. Volte ao Claude e diga que conectou.")
        return 0
    except Exception as erro:  # noqa: BLE001
        primeira = str(erro).splitlines()[0]
        print("\n✗ Gravou, mas não conectou:")
        print("  ", primeira[:200])
        if "password authentication failed" in primeira:
            print("\n  A senha não confere com a do papel criterio_crm.")
            print("  Para redefini-la, no Terminal:")
            print('    /Library/PostgreSQL/18/bin/psql -h localhost -U postgres '
                  '-c "\\password criterio_crm"')
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
