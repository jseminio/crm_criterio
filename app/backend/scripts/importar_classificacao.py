"""Carrega a classificação da carteira (planilha de saúde da carteira) e a confere.

    importar_classificacao.py <Classificacao_Grupo_COMPLETO.xlsx> <Rentabilidade_Grupo_COMPLETO.xlsx>
    importar_classificacao.py ... --aplicar [--referencia 2026-07-31]

Sem `--aplicar` é ensaio: lê, liga as unidades aos grupos pelo CNPJ, recalcula tudo com a regra do CRM e
compara com a planilha, sem gravar. Divergência é erro e bloqueia a gravação. Tudo ou nada, com backup.

⚠️ As planilhas têm dado de cliente: ficam fora do repositório. A saída traz só contagens e valores.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.orm import Session  # noqa: E402

from crm.backup import exportar  # noqa: E402
from crm.carga.classificacao import Relatorio, aplicar, ler  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("classificacao")
    p.add_argument("rentabilidade")
    p.add_argument("--aplicar", action="store_true")
    p.add_argument("--referencia", default="2026-07-31", help="data a que a planilha se refere (AAAA-MM-DD)")
    a = p.parse_args()
    referencia = date.fromisoformat(a.referencia)

    rel = Relatorio()
    engine = criar_engine()
    with Session(engine) as s:
        linhas = ler(Path(a.classificacao), Path(a.rentabilidade), s, rel)
        if a.aplicar and rel.pode_aplicar:
            pasta = Path.home() / "Backups-CRM"
            pasta.mkdir(exist_ok=True, mode=0o700)
            copia = pasta / f"antes-da-classificacao-{datetime.now():%Y%m%d-%H%M%S}.zip"
            exportar(engine, copia)
            copia.chmod(0o600)
            print(f"Backup antes: {copia}")
            aplicar(s, linhas, rel, referencia, f"Planilha de saúde da carteira ({Path(a.classificacao).name})")
            s.commit()
        else:
            s.rollback()

    print(f"Unidades na planilha: {rel.unidades}  ·  ligadas a um grupo do CRM: {len(linhas)}")
    print("Por classe:", dict(sorted(rel.por_classe.items())))
    if rel.isc_do_crm:
        i = rel.isc_do_crm
        print(f"ISC do CRM: {float(i.valor):.2f} ({i.zona})  ·  da planilha: {float(rel.isc_da_planilha):.2f}"
              f"  ·  classe {float(i.componente_classe):.2f} · semáforo {float(i.componente_semaforo):.2f} · churn {float(i.componente_churn):.2f}"
              f"  ·  receita {float(i.receita_total):,.2f}")
    if a.aplicar:
        print(f"Snapshots: {rel.criadas} novos, {rel.ja_existiam} já existiam")
    for titulo, itens in (("ERROS (bloqueiam a gravação)", rel.erros), ("AVISOS", rel.avisos)):
        if itens:
            print(f"\n{titulo}: {len(itens)}")
            for x in itens[:30]:
                print("  •", x)
    if a.aplicar and not rel.pode_aplicar:
        print("\n✗ Nada foi gravado: corrija os erros e rode de novo.")
        return 1
    print("\n✓ Gravado." if a.aplicar else "\nEnsaio: nada foi gravado. Use --aplicar para gravar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
