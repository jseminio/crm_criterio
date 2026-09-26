"""Carrega a carteira anterior ao CRM (planilha de saúde da carteira) como empresas e contratos.

    importar_carteira.py <Rentabilidade_Grupo_COMPLETO.xlsx>            # ensaio: não grava
    importar_carteira.py <Rentabilidade_Grupo_COMPLETO.xlsx> --aplicar  # grava (tudo ou nada), com backup antes

⚠️ A planilha tem dado de cliente: fica fora do repositório. O relatório traz contagens e valores
agregados; só os avisos citam o nome de um grupo, para você agir. Não grave a saída no repositório.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.orm import Session  # noqa: E402

from crm.backup import exportar  # noqa: E402
from crm.carga.carteira import Relatorio, aplicar, ler  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("planilha")
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()

    rel = Relatorio()
    linhas = ler(Path(a.planilha), rel)
    engine = criar_engine()
    with Session(engine) as s:
        if rel.pode_aplicar:
            aplicar(s, linhas, rel)
        if a.aplicar and rel.pode_aplicar:
            pasta = Path.home() / "Backups-CRM"
            pasta.mkdir(exist_ok=True, mode=0o700)
            copia = pasta / f"antes-de-importar-carteira-{datetime.now():%Y%m%d-%H%M%S}.zip"
            exportar(engine, copia)
            copia.chmod(0o600)
            print(f"Backup antes da importação: {copia}")
            s.commit()
        else:
            s.rollback()

    print(f"Empresas na planilha: {rel.linhas}  ·  honorário mensal somado: R$ {rel.total_mensal:,.2f}")
    print(f"Grupos: {rel.grupos_reaproveitados} reaproveitados do CRM, {rel.grupos_novos} novos"
          f" ({rel.prospects_que_viraram_cliente} prospects viraram cliente)")
    print(f"Empresas: {rel.empresas_criadas} novas, {rel.empresas_existentes} já existiam")
    print(f"Contratos: {rel.contratos_criados} novos, {rel.contratos_existentes} já existiam")
    for titulo, itens in (("ERROS (bloqueiam a gravação)", rel.erros), ("CONFLITOS (não alterados)", rel.conflitos), ("AVISOS", rel.avisos)):
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
