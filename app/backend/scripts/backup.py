"""Backup lógico do CRM pela linha de comando.

    backup.py exportar [arquivo]        grava o backup (padrão: ~/Backups-CRM/…)
    backup.py verificar <arquivo>       confere a integridade, sem tocar no banco
    backup.py importar <arquivo> [--substituir]

⚠️ O arquivo tem todos os dados de cliente, sem criptografia. Fica fora do
repositório: o padrão é ~/Backups-CRM, com permissão só do dono.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from crm.backup import ErroDeBackup, exportar, importar, verificar  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402

PASTA_PADRAO = Path.home() / "Backups-CRM"


def _mostrar(resumo) -> None:
    for nome, n in resumo.tabelas.items():
        print(f"  {nome:<24}{n:>8}")
    print(f"  {'TOTAL':<24}{resumo.total:>8}   (esquema {resumo.revisao_do_esquema})")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("exportar"); e.add_argument("arquivo", nargs="?")
    v = sub.add_parser("verificar"); v.add_argument("arquivo")
    i = sub.add_parser("importar"); i.add_argument("arquivo"); i.add_argument("--substituir", action="store_true")
    a = p.parse_args()
    try:
        if a.cmd == "exportar":
            destino = Path(a.arquivo) if a.arquivo else PASTA_PADRAO / f"crm-{datetime.now():%Y%m%d-%H%M%S}.zip"
            destino.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(destino.parent, 0o700) if not a.arquivo else None
            resumo = exportar(criar_engine(), destino)
            os.chmod(destino, 0o600)
            print(f"✓ Backup gravado em {destino}"); _mostrar(resumo)
        elif a.cmd == "verificar":
            print("✓ Arquivo íntegro"); _mostrar(verificar(Path(a.arquivo)))
        else:
            if a.substituir and input("Isto APAGA os dados atuais do destino. Digite SUBSTITUIR para continuar: ") != "SUBSTITUIR":
                print("Cancelado."); return 1
            resumo = importar(criar_engine(), Path(a.arquivo), substituir=a.substituir)
            print("✓ Importado"); _mostrar(resumo)
    except ErroDeBackup as erro:
        print(f"✗ {erro}", file=sys.stderr); return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
