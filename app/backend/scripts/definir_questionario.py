"""Grava no `.env` onde buscar os questionários do site e testa a busca na hora (01/10/2026).

Pergunta a URL do projeto Supabase e a chave secreta. A chave não aparece na tela, não vai para o
histórico do shell e não passa por chat nenhum. Só lê: não importa nem marca nada.

Uso, num Terminal de verdade:
    ~/.venvs/criterio-crm/bin/python scripts/definir_questionario.py
"""

from __future__ import annotations

import getpass
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO = RAIZ / ".env"
URL, CHAVE = "CRM_QUESTIONARIO_URL", "CRM_QUESTIONARIO_CHAVE"


def gravar(conteudo: str, valores: dict[str, str]) -> str:
    """Troca (ou acrescenta) só as linhas destas variáveis, preservando todo o resto do arquivo."""
    linhas = conteudo.splitlines()
    faltam = dict(valores)
    for i, linha in enumerate(linhas):
        for nome in list(faltam):
            if linha.strip().startswith(f"{nome}="):
                linhas[i] = f"{nome}={faltam.pop(nome)}"
    linhas += [f"{nome}={valor}" for nome, valor in faltam.items()]
    return "\n".join(linhas) + "\n"


def url_valida(url: str) -> str | None:
    """A URL do projeto, sem barra no fim; `None` se não parece uma."""
    url = url.strip().rstrip("/")
    return url if re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url) else None


def principal() -> int:
    if not sys.stdin.isatty():
        print("Este comando pede a chave e precisa de um Terminal de verdade.", file=sys.stderr)
        return 2
    if not ARQUIVO.is_file():
        print(f"✗ {ARQUIVO} não existe.", file=sys.stderr)
        return 1

    print("Onde o CRM busca os questionários do site.\n")
    url = url_valida(input("URL do projeto Supabase (https://xxxx.supabase.co): "))
    if not url:
        print("\n✗ Não parece a URL do projeto (https://xxxx.supabase.co). Nada foi gravado.")
        return 1
    print("\nChave SECRETA (começa com sb_secret_). Ela não aparece enquanto você cola — isso é normal.")
    chave = getpass.getpass("Chave secreta: ").strip()
    if chave.count("sb_secret_") > 1:
        print("\n✗ A chave veio colada mais de uma vez (nada aparece na tela, então é fácil repetir o Cmd+V).")
        print("  Rode de novo e cole uma vez só. Nada foi gravado.")
        return 1
    if not chave.startswith(("sb_secret_", "eyJ")):
        print("\n✗ Essa não é a chave secreta (sb_secret_…). A publicável não serve. Nada foi gravado.")
        return 1

    ARQUIVO.write_text(gravar(ARQUIVO.read_text(encoding="utf-8"), {URL: url, CHAVE: chave}), encoding="utf-8")
    ARQUIVO.chmod(0o600)
    print(f"\n✓ Gravado em {ARQUIVO.name}, legível só por você.")

    sys.path.insert(0, str(RAIZ / "src"))
    from crm.questionario.fonte import BuscaFalhou, FonteSupabase, ler_configuracao

    try:
        pendentes = FonteSupabase(ler_configuracao()).novos()
    except BuscaFalhou as falha:
        print(f"\n✗ Gravou, mas a busca não funcionou: {falha}")
        return 1
    print(f"✓ CONECTOU ao Supabase: {len(pendentes)} questionário(s) esperando o CRM.")
    print("\nPronto. No CRM, Funil → Buscar questionários. Volte ao Claude e diga que conectou.")
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
