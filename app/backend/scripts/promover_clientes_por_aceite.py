"""Promove a Cliente os grupos que têm proposta aceita e ainda constam como Prospect.

    promover_clientes_por_aceite.py            # ensaio: conta, não grava
    promover_clientes_por_aceite.py --aplicar  # grava, com backup antes

Decisão de Eduardo em 26/09/2026: quem fechou uma proposta é cliente, recorrente (contrato) ou não
(consultoria pontual). Antes, só a carteira recorrente era "Cliente". A regra passou a valer sozinha
daqui em diante (ao aceitar a proposta e na recarga da planilha); este script corrige o que já existia.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from crm.backup import exportar  # noqa: E402
from crm.db.modelos import GrupoEconomico, Oportunidade  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402
from crm.domain.listas import Situacao, SituacaoGrupo  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()
    engine = criar_engine()
    with Session(engine) as s:
        ids = list(s.scalars(
            sa.select(GrupoEconomico.id).where(
                GrupoEconomico.situacao == SituacaoGrupo.PROSPECT,
                GrupoEconomico.fundido_em_id.is_(None),
                GrupoEconomico.id.in_(sa.select(Oportunidade.grupo_id).where(Oportunidade.situacao == Situacao.ACEITA)),
            )
        ))
        print(f"Grupos Prospect com proposta aceita: {len(ids)}")
        if not a.aplicar:
            print("Ensaio: nada foi gravado. Use --aplicar para gravar.")
            return 0
        if ids:
            pasta = Path.home() / "Backups-CRM"
            pasta.mkdir(exist_ok=True, mode=0o700)
            copia = pasta / f"antes-de-promover-clientes-{datetime.now():%Y%m%d-%H%M%S}.zip"
            exportar(engine, copia)
            copia.chmod(0o600)
            print(f"Backup antes: {copia}")
            s.execute(sa.update(GrupoEconomico).where(GrupoEconomico.id.in_(ids)).values(situacao=SituacaoGrupo.CLIENTE))
            s.commit()
        print(f"✓ {len(ids)} grupos agora são Cliente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
