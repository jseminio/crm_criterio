"""Escreve o `.env` com a senha do banco, sem que ela passe por lugar nenhum.

⚠️ **Caminho alternativo, não o principal.** O jeito recomendado é preencher
`CRM_DB_USER` e `CRM_DB_PASSWORD` no `.env`, com a senha crua: o código codifica
sozinho em `crm.db.sessao`. Este script só serve a quem prefere não abrir o
arquivo — e **exige um terminal de verdade**, porque pergunta a senha.

**Por que este script existe.** A URL de conexão é um endereço web, e senha com
caractere especial quebra dentro de um endereço:

- ``#`` inicia a âncora — **tudo depois dele é descartado**, então a senha chega
  truncada ao servidor e a autenticação falha;
- ``@`` separa credencial de servidor;
- ``/``, ``?``, ``:``, ``%`` e espaço também têm significado próprio.

Digitar a senha crua no `.env` funciona **só** quando ela não tem nenhum desses.
Este script codifica automaticamente.

A senha é pedida sem aparecer na tela, não vai para o histórico do shell, não é
impressa e não aparece em mensagem de erro.

Uso:  ~/.venvs/criterio-crm/bin/python scripts/configurar_env.py
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path
from urllib.parse import quote

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / ".env"

PADRAO_HOST = "localhost"
PADRAO_PORTA = "5432"
PADRAO_BANCO = "criterio_crm"
PADRAO_USUARIO = "criterio_crm"


def _perguntar(rotulo: str, padrao: str) -> str:
    resposta = input(f"{rotulo} [{padrao}]: ").strip()
    return resposta or padrao


def principal() -> int:
    if not sys.stdin.isatty():
        print(
            "Este script pergunta a senha e precisa de um terminal de verdade.\n"
            "Rodando por botão ou por pipe, ele morre antes de gravar qualquer\n"
            "coisa — foi o que aconteceu em 20/09/2026.\n\n"
            "Duas saídas:\n"
            "  1. Abrir o Terminal e rodar este mesmo comando lá; ou\n"
            "  2. Editar o .env num editor de texto e preencher CRM_DB_PASSWORD\n"
            "     com a senha CRUA — o código codifica sozinho. É o caminho\n"
            "     recomendado, e dispensa este script.",
            file=sys.stderr,
        )
        return 2

    print("Configuração do banco do Critério CRM")
    print("A senha não aparece na tela e não é gravada em log.\n")

    usuario = _perguntar("Usuário do banco", PADRAO_USUARIO)
    host = _perguntar("Servidor", PADRAO_HOST)
    porta = _perguntar("Porta", PADRAO_PORTA)
    banco = _perguntar("Banco", PADRAO_BANCO)

    senha = getpass.getpass("Senha: ")
    if not senha:
        print("\n✗ Senha vazia. Nada foi gravado.")
        return 1
    if senha != getpass.getpass("Confirme a senha: "):
        print("\n✗ As duas não conferem. Nada foi gravado.")
        return 1

    # `safe=""` codifica tudo que tem significado num endereço, inclusive o "#"
    # que truncaria a senha em silêncio.
    url = (
        f"postgresql+psycopg://{quote(usuario, safe='')}:{quote(senha, safe='')}"
        f"@{host}:{porta}/{banco}"
    )
    conteudo = (
        "# Gerado por scripts/configurar_env.py. Não versionado.\n"
        "# A senha está codificada para endereço — não a edite à mão.\n"
        f"CRM_DATABASE_URL={url}\n"
    )

    if ARQUIVO.exists():
        resposta = input(f"\n{ARQUIVO.name} já existe. Sobrescrever? [s/N]: ").strip().lower()
        if resposta not in {"s", "sim", "y"}:
            print("Nada foi gravado.")
            return 1

    ARQUIVO.write_text(conteudo, encoding="utf-8")
    ARQUIVO.chmod(0o600)  # só o dono lê
    print(f"\n✓ {ARQUIVO} gravado, legível só por você.")

    sys.path.insert(0, str(RAIZ / "src"))
    try:
        import sqlalchemy as sa

        from crm.db.sessao import criar_engine

        with criar_engine(url).connect() as conexao:
            print("✓ Conectou ao PostgreSQL", conexao.scalar(sa.text("show server_version")))
            print("  banco:", conexao.scalar(sa.text("select current_database()")))
            print("  usuário:", conexao.scalar(sa.text("select current_user")))
        print("\nPróximo passo:  ~/.venvs/criterio-crm/bin/alembic upgrade head")
        return 0
    except Exception as erro:  # noqa: BLE001 — qualquer falha aqui é informativa
        print("\n✗ O arquivo foi gravado, mas a conexão falhou:")
        print("  ", str(erro).splitlines()[0][:200])
        print("\n  Verifique, no psql como postgres, se o papel e o banco existem:")
        print("    \\du   e   \\l")
        return 1


if __name__ == "__main__":
    raise SystemExit(principal())
