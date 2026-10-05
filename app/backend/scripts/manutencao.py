"""Aplica as tarefas de manutenção de dados pendentes (#93). Chamado pelo `atualizador.sh` no Redeploy.

    python scripts/manutencao.py            # aplica as pendentes, em ordem, cada uma na sua transação
    python scripts/manutencao.py --listar   # mostra cada tarefa: aplicada (quando, resultado) ou pendente

A lista está em `crm/manutencao/registro.py` (como acrescentar uma tarefa: lá). Saída: 0 = ok (aplicou
ou nada a fazer); 1 = uma tarefa falhou (nada dela ficou no banco; as seguintes não rodaram) ou o
banco não está pronto. Nada aqui imprime dado de cliente nem a URL do banco.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from crm.manutencao import FalhaNaTarefa, aplicar_pendentes, estado  # noqa: E402
from crm.manutencao.registro import TAREFAS  # noqa: E402


def _fabrica():
    from crm.db.sessao import criar_engine, criar_fabrica_de_sessao, url_do_banco

    return criar_fabrica_de_sessao(criar_engine(url_do_banco()))


def listar(fabrica, tarefas) -> int:
    linhas, orfaos = estado(fabrica, tarefas)
    if not linhas:
        print("nenhuma tarefa registrada em crm/manutencao/registro.py.")
    for tarefa, registro in linhas:
        if registro is None:
            print(f"PENDENTE  {tarefa.id} — {tarefa.descricao}")
        else:
            quando = registro.aplicada_em.strftime("%d/%m/%Y %H:%M") if registro.aplicada_em else "?"
            print(f"aplicada  {tarefa.id} em {quando}" + (f" — {registro.resultado}" if registro.resultado else ""))
    for r in orfaos:
        print(f"registro sem tarefa no código: {r.id} (aplicada por uma versão que a tinha; fica como histórico)")
    return 0


def aplicar(fabrica, tarefas) -> int:
    tarefas = list(tarefas)
    if not tarefas:
        print("nenhuma tarefa registrada — nada a fazer.")
        return 0
    try:
        aplicadas = aplicar_pendentes(fabrica, tarefas)
    except FalhaNaTarefa as falha:
        print(f"ERRO: a tarefa {falha} falhou; nada dela ficou no banco e as seguintes não rodaram.", file=sys.stderr)
        return 1
    if aplicadas:
        print(f"{len(aplicadas)} tarefa(s) aplicada(s) agora; {len(tarefas)} no registro.")
    else:
        print(f"todas as {len(tarefas)} tarefa(s) já aplicadas — nada a fazer.")
    return 0


def main(argv: list[str] | None = None, *, fabrica=None, tarefas=None) -> int:
    ap = argparse.ArgumentParser(description="Tarefas de manutenção de dados (#93).")
    ap.add_argument("--listar", action="store_true", help="só mostra o estado de cada tarefa")
    args = ap.parse_args(argv)
    tarefas = TAREFAS if tarefas is None else tarefas
    try:
        if args.listar:
            return listar(fabrica or _fabrica(), tarefas)
        if not tarefas:  # sem tarefa nenhuma, nem conecta
            return aplicar(None, tarefas)
        return aplicar(fabrica or _fabrica(), tarefas)
    except Exception as exc:  # noqa: BLE001 — banco fora, tabela ausente: a causa, sem valor de config
        primeira = (str(exc).strip().splitlines() or [""])[0][:300]
        print(f"ERRO: {type(exc).__name__}: {primeira}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
