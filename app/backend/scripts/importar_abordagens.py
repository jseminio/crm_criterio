"""Coloca as contas âncora de um mês na fila do agente SDR, a partir de um CSV.

O CSV fica **fora do repositório** (dado de cliente). Colunas, com cabeçalho:

    conta;mes;quem_apresenta;canal;destinatario;contexto

`mes` é AAAA-MM; `canal` é "E-mail" ou "WhatsApp" (vazio = E-mail);
`destinatario`, `contexto` e `quem_apresenta` podem ficar vazios. Aceita `;`
ou `,` como separador.

Uso:
    ~/.venvs/criterio-crm/bin/python scripts/importar_abordagens.py <arquivo.csv> [--gravar]

Sem `--gravar`, faz tudo e **desfaz no fim**: mostra o que entraria. Rodar
duas vezes não duplica — a conta que já está na fila do mês é pulada.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from crm.db.abordagens import ContaNaoInformada, JaNaFila, enfileirar  # noqa: E402
from crm.db.sessao import criar_engine, url_do_banco  # noqa: E402
from crm.domain.abordagem import MES  # noqa: E402
from crm.domain.listas import CanalDeAbordagem  # noqa: E402


def ler_csv(caminho: str | Path) -> list[dict[str, str]]:
    texto = Path(caminho).read_text(encoding="utf-8-sig")
    separador = ";" if texto.splitlines()[0].count(";") >= texto.splitlines()[0].count(",") else ","
    return [
        {chave.strip().lower(): (valor or "").strip() for chave, valor in linha.items() if chave}
        for linha in csv.DictReader(texto.splitlines(), delimiter=separador)
    ]


def enfileirar_linhas(sessao: Session, linhas: list[dict[str, str]]) -> list[str]:
    """Enfileira cada linha e devolve o relatório, uma frase por linha do CSV."""
    relatorio = []
    canais = {c.value.casefold(): c for c in CanalDeAbordagem}
    for numero, linha in enumerate(linhas, start=2):
        conta, mes = linha.get("conta", ""), linha.get("mes", "")
        if not MES.match(mes):
            relatorio.append(f"linha {numero}: mês inválido {mes!r} — pulada")
            continue
        canal = canais.get((linha.get("canal") or "E-mail").casefold())
        if canal is None:
            relatorio.append(f"linha {numero}: canal {linha.get('canal')!r} desconhecido — pulada")
            continue
        try:
            abordagem = enfileirar(
                sessao,
                mes=mes,
                grupo_nome=conta,
                quem_apresenta=linha.get("quem_apresenta"),
                canal=canal,
                destinatario=linha.get("destinatario"),
                contexto=linha.get("contexto"),
            )
        except ContaNaoInformada:
            relatorio.append(f"linha {numero}: sem o nome da conta — pulada")
            continue
        except JaNaFila:
            relatorio.append(f"linha {numero}: {conta} já está na fila de {mes} — pulada")
            continue
        aviso = "" if abordagem.quem_apresenta else " (bloqueada: falta quem apresenta)"
        relatorio.append(f"linha {numero}: {conta} entrou na fila de {mes}{aviso}")
    return relatorio


def principal(argumentos: list[str]) -> int:
    if not argumentos:
        print(__doc__)
        return 2
    gravar = "--gravar" in argumentos
    linhas = ler_csv(argumentos[0])
    engine = criar_engine(url_do_banco())
    with Session(engine, future=True) as sessao:
        for frase in enfileirar_linhas(sessao, linhas):
            print(frase)
        if gravar:
            sessao.commit()
            print("\nGravado.")
        else:
            sessao.rollback()
            print("\nSimulação: nada foi mantido. Rode com --gravar para valer.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
