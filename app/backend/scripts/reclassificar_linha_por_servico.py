"""Reclassifica C1/C2 das oportunidades já gravadas pelo serviço.

    reclassificar_linha_por_servico.py            # ensaio: mostra o que muda, não grava
    reclassificar_linha_por_servico.py --aplicar  # grava, com backup antes

Regra de Eduardo em 27/09/2026: C1 é recorrente, C2 não é recorrente, e a linha
sai do serviço no passado e daqui para frente. A carga e a tela já seguem a regra;
este script corrige o que foi gravado antes. Serviço fora do catálogo não muda.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.orm import Session  # noqa: E402

from crm.backup import exportar  # noqa: E402
from crm.db.linha_por_servico import aplicar, planejar, resumir  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()
    engine = criar_engine()
    with Session(engine) as s:
        mudancas = planejar(s)
        print(f"Oportunidades que mudam de linha: {len(mudancas)}")
        for linha in resumir(mudancas):
            print(linha)
        if not a.aplicar:
            print("Ensaio: nada foi gravado. Use --aplicar para gravar.")
            return 0
        if mudancas:
            pasta = Path.home() / "Backups-CRM"
            pasta.mkdir(exist_ok=True, mode=0o700)
            copia = pasta / f"antes-de-reclassificar-linha-{datetime.now():%Y%m%d-%H%M%S}.zip"
            exportar(engine, copia)
            copia.chmod(0o600)
            print(f"Backup antes: {copia}")
            aplicar(s, mudancas)
            s.commit()
        print(f"✓ {len(mudancas)} oportunidades reclassificadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
