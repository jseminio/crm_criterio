"""Refaz o registro das fusões feitas ANTES de o registro existir, para poderem ser desfeitas.

    reconstruir_fusoes.py <backup.zip>             # ensaio: mostra o que reconstruiria, não grava
    reconstruir_fusoes.py <backup.zip> --aplicar   # grava os registros (só cria linhas novas)

Use o backup **imediatamente anterior** às fusões: nele cada item ainda tem o grupo de origem, e
é isso que diz o que a fusão moveu. Só reconstrói grupos que estão fundidos hoje **e não estavam
no backup**, e que ainda não têm registro. Registros reconstruídos ficam marcados (`reconstruida`).
Limite: o instante da fusão é aproximado pela última alteração do grupo absorvido.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from crm.db.modelos import Contrato, Empresa, FusaoDeGrupos, GrupoEconomico, Oportunidade, PessoaContato  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402

TABELAS = (("empresa", Empresa), ("oportunidade", Oportunidade), ("pessoa_contato", PessoaContato), ("contrato", Contrato))


def _linhas(zf: zipfile.ZipFile, tabela: str) -> list[dict]:
    return [json.loads(x) for x in zf.read(f"dados/{tabela}.jsonl").splitlines()]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("backup")
    p.add_argument("--aplicar", action="store_true")
    a = p.parse_args()

    with zipfile.ZipFile(a.backup) as zf:
        grupos_antes = {g["id"]: g for g in _linhas(zf, "grupo_economico")}
        dono_antes = {chave: {r["id"]: r["grupo_id"] for r in _linhas(zf, chave)} for chave, _ in TABELAS}

    engine = criar_engine()
    criadas, sem_dono, total_itens = [], 0, 0
    with Session(engine) as s:
        ja_tem = set(s.scalars(sa.select(FusaoDeGrupos.absorvido_id)))
        fundidos = s.scalars(
            sa.select(GrupoEconomico).where(GrupoEconomico.fundido_em_id.is_not(None)).order_by(GrupoEconomico.atualizado_em, GrupoEconomico.id)
        ).all()
        for g in fundidos:
            antes = grupos_antes.get(g.id)
            if antes is None or antes["situacao"] == "Fundido" or g.id in ja_tem:
                continue  # não é uma fusão do lote (ou já tem registro)
            principal = s.get(GrupoEconomico, g.fundido_em_id)
            p_antes = grupos_antes.get(principal.id)
            if p_antes is None:
                sem_dono += 1
                continue
            movidos = {chave: sorted(i for i, gid in dono_antes[chave].items() if gid == g.id) for chave, _ in TABELAS}
            total_itens += sum(len(v) for v in movidos.values())
            entrada = date.fromisoformat(p_antes["data_entrada"]) if p_antes.get("data_entrada") else None
            f = FusaoDeGrupos(
                principal_id=principal.id, absorvido_id=g.id, movidos=movidos, reconstruida=True, feita_em=g.atualizado_em,
                absorvido_situacao_antes=antes["situacao"],
                principal_situacao_antes=p_antes["situacao"], principal_situacao_depois=principal.situacao.value,
                principal_data_entrada_antes=entrada, principal_data_entrada_depois=principal.data_entrada,
            )
            criadas.append(f)
        print(f"Fusões a reconstruir: {len(criadas)}  ·  itens registrados: {total_itens}  ·  sem correspondência no backup: {sem_dono}")
        por_tipo = {chave: sum(len(f.movidos[chave]) for f in criadas) for chave, _ in TABELAS}
        print("  itens por tipo:", por_tipo)
        if not a.aplicar:
            print("Ensaio: nada foi gravado. Use --aplicar para gravar.")
            s.rollback()
            return 0
        s.add_all(criadas)
        s.commit()
        print(f"✓ {len(criadas)} registros gravados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
