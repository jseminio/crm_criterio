"""Backup automático do CRM — o que o agendamento diário executa.

    backup_agendado.py [--pasta DIR] [--manter N]

Grava `crm-auto-AAAAMMDD-HHMMSS.zip` em ~/Backups-CRM, confere o arquivo e mantém
os últimos N automáticos (padrão 14). Erro sai com código 1 e vai para o log
`backup.log` da mesma pasta, que nunca contém dado de cliente.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from crm.backup.agendado import executar  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402

PASTA = Path.home() / "Backups-CRM"


def _log(pasta: Path, texto: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    with (pasta / "backup.log").open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S}  {texto}\n")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pasta", type=Path, default=PASTA)
    p.add_argument("--manter", type=int, default=14)
    a = p.parse_args()
    try:
        r = executar(criar_engine(), a.pasta, manter=a.manter)
    except Exception as erro:  # noqa: BLE001 — qualquer falha precisa ficar visível
        _log(a.pasta, f"FALHOU: {type(erro).__name__}")  # sem a mensagem: pode citar host/usuário
        subprocess.run(
            ["osascript", "-e", 'display notification "O backup automático do CRM falhou. Veja ~/Backups-CRM/backup.log" with title "Critério CRM"'],
            check=False,
        )
        print(f"✗ Backup falhou: {type(erro).__name__}", file=sys.stderr)
        return 1
    _log(a.pasta, f"OK {r.arquivo.name} · {r.registros} registros · {r.bytes} bytes · {len(r.apagados)} antigo(s) apagado(s)")
    print(f"✓ {r.arquivo} ({r.registros} registros, {len(r.apagados)} antigo(s) apagado(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
