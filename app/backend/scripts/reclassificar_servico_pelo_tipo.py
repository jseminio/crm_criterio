"""Corrige o serviço e preenche o tema das propostas "Consultoria" pelo tipo.

    reclassificar_servico_pelo_tipo.py            # ensaio: mostra o que muda, não grava
    reclassificar_servico_pelo_tipo.py --aplicar  # grava, com backup antes

Aprovado por Eduardo em 27/09/2026. Pela coluna "Tipo serviço": propostas marcadas
"Consultoria" que são de outro serviço do catálogo passam a esse serviço, e as
demais ganham o tema. Tema já escolhido por uma pessoa não é sobrescrito. Rodar de
novo depois de uma recarga da planilha pega as propostas novas.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.orm import Session  # noqa: E402

from crm.backup import exportar  # noqa: E402
from crm.db.servico_pelo_tipo import aplicar, planejar, resumir  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()
    engine = criar_engine()
    with Session(engine) as s:
        mudancas = planejar(s)
        print(f"Propostas que mudam: {len(mudancas)}")
        for linha in resumir(mudancas):
            print(linha)
        if not a.aplicar:
            print("Ensaio: nada foi gravado. Use --aplicar para gravar.")
            return 0
        if mudancas:
            pasta = Path.home() / "Backups-CRM"
            pasta.mkdir(exist_ok=True, mode=0o700)
            copia = pasta / f"antes-de-reclassificar-servico-{datetime.now():%Y%m%d-%H%M%S}.zip"
            exportar(engine, copia)
            copia.chmod(0o600)
            print(f"Backup antes: {copia}")
            aplicar(s, mudancas)
            s.commit()
        print(f"✓ {len(mudancas)} propostas atualizadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
