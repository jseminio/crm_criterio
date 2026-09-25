"""Devolve ao CRM a planilha de lacunas de contato preenchida.

    importar_lacunas_contato.py <planilha.xlsx>              # ensaio: mostra o que faria, não grava
    importar_lacunas_contato.py <planilha.xlsx> --aplicar    # grava (tudo ou nada), com backup antes
    ... --sobrescrever                                       # também troca valor já preenchido no CRM

⚠️ A planilha e o relatório têm dado de cliente. Não os grave no repositório.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.orm import Session  # noqa: E402

from crm.backup import exportar  # noqa: E402
from crm.carga.lacunas_contato import Relatorio, aplicar, ler  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("planilha")
    p.add_argument("--aplicar", action="store_true")
    p.add_argument("--sobrescrever", action="store_true")
    a = p.parse_args()

    rel = Relatorio()
    linhas = ler(Path(a.planilha), rel)
    engine = criar_engine()
    with Session(engine) as s:
        aplicar(s, linhas, rel, sobrescrever=a.sobrescrever)
        gravar = a.aplicar and rel.pode_aplicar
        if gravar:
            pasta = Path.home() / "Backups-CRM"
            pasta.mkdir(exist_ok=True, mode=0o700)
            copia = pasta / f"antes-de-importar-{datetime.now():%Y%m%d-%H%M%S}.zip"
            exportar(engine, copia)
            copia.chmod(0o600)
            print(f"Backup antes da importação: {copia}")
            s.commit()
        else:
            s.rollback()

    print(f"Linhas com dados: {rel.linhas_lidas - rel.linhas_vazias} de {rel.linhas_lidas} ({rel.linhas_vazias} em branco)")
    print(f"Empresas: {rel.empresas_criadas} novas, {rel.empresas_atualizadas} atualizadas")
    print(f"Contatos: {rel.contatos_criados} novos, {rel.contatos_atualizados} atualizados")
    for titulo, itens in (("ERROS (bloqueiam a gravação)", rel.erros), ("CONFLITOS (não alterados)", rel.conflitos), ("AVISOS", rel.avisos)):
        if itens:
            print(f"\n{titulo}: {len(itens)}")
            for x in itens[:40]:
                print("  •", x)
    if a.aplicar and not rel.pode_aplicar:
        print("\n✗ Nada foi gravado: corrija os erros e rode de novo.")
        return 1
    print("\n✓ Gravado." if a.aplicar else "\nEnsaio: nada foi gravado. Use --aplicar para gravar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
