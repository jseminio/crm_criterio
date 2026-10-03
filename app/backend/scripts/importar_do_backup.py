"""Traz para este banco o que foi feito num **outro** CRM, sem apagar nada daqui (03/10/2026).

    importar_do_backup.py <arquivo>            só mostra o que faria
    importar_do_backup.py <arquivo> --gravar   grava, numa transação só

Para o backup da Karine, depois da comparação (`comparar_backup.py`), com as regras que Eduardo
aprovou em 03/10/2026. Reconhece "o mesmo registro" do mesmo jeito que a comparação.

**Acrescenta** (o que só existe lá):
- empresas (no grupo de mesmo nome daqui; grupo novo não entra), contatos e vínculos de contato. O
  contato sem e-mail cujo nome está contido no de outro contato da mesma empresa ("Rafael" e "Rafael
  Monteiro Machado") é o mesmo: não se duplica, e o vínculo vai para o que já existe. Contato cujas
  empresas não entram (a de um grupo de teste apagado aqui) também não entra.

**Preenche** (vazio aqui, preenchido lá) em empresas, contatos e oportunidades: CNPJ, telefone,
cargo, papel, observação, data de aceite, data de colocação…

**Troca** (preenchido nos dois, diferente) só quando lá mexeu por último e o campo é um destes: nos
contatos, nome, cargo, papel, observação e telefone (os nomes completos dela; a observação junta as
duas, para não perder o texto daqui); nas oportunidades, temperatura e nome. O resto dos conflitos (preço, parcelas, situação, data de colocação) fica como
está aqui e aparece na lista, para decidir à mão.

**Não toca**: o que está vazio lá e preenchido aqui; contratos, propostas, leituras do Score e as
outras tabelas; nada é apagado. Empresa cujo CNPJ já está em outra empresa daqui não entra (avisa).

⚠️ A saída tem nomes de clientes: fica na tela.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import sqlalchemy as sa  # noqa: E402

import comparar_backup as cb  # noqa: E402
from crm.backup.formato import _do_json  # noqa: E402,PLC2701 — a mesma conversão do backup
from crm.db.base import Base, agora  # noqa: E402
from crm.db.sessao import criar_engine  # noqa: E402

#: Onde se preenche e onde se troca o valor daqui pelo de lá.
TABELAS_QUE_MUDAM = ("empresa", "pessoa_contato", "oportunidade")
TROCA_QUANDO_LA_E_MAIS_NOVO = {
    "pessoa_contato": {"nome", "cargo", "papel", "observacao", "telefone"},
    "oportunidade": {"temperatura", "nome"},
}
_NAO_COPIAR = {"id", "atualizado_em"}


@dataclass
class Plano:
    inserir: dict[str, list[dict]] = field(default_factory=dict)
    """Por tabela, os registros novos já com as referências daqui."""
    mudar: list[tuple[str, int, str, dict, list[tuple[str, str, str]]]] = field(default_factory=list)
    """(tabela, id daqui, rótulo, {campo: valor}, [(campo, de, para)])."""
    pendentes: list[tuple[str, str, str, str, str]] = field(default_factory=list)
    """Conflitos que ficam como estão aqui: (tabela, rótulo, campo, aqui, lá)."""
    avisos: list[str] = field(default_factory=list)


def _valor_da_coluna(tabela: str, campo: str, bruto):
    return _do_json(Base.metadata.tables[tabela].c[campo], bruto)


def _novo(tabela: str, l: dict, refs: dict[str, int | None]) -> dict:
    colunas = Base.metadata.tables[tabela].c
    registro = {c: _valor_da_coluna(tabela, c, v) for c, v in l.items()
                if c in colunas and c not in _NAO_COPIAR and c not in refs}
    registro.update(refs)
    registro["atualizado_em"] = agora()
    return registro


def _palavras(nome) -> list[str]:
    return cb._texto(nome).split()


def montar(arquivo: dict[str, list[dict]], engine: sa.Engine) -> Plano:
    banco = {t: v for t in cb.CHAVES if (v := cb._do_banco(engine, t)) is not None}
    casados, k_la, k_aqui = cb.casar(arquivo, banco)
    nomes_la, nomes_aqui = cb._nomes(arquivo), cb._nomes(banco)
    plano = Plano()
    # id lá → id daqui, dos casados; os novos entram com um id provisório negativo
    mapa: dict[str, dict] = {t: {l["id"]: d["id"] for l, d in c["pares"]} for t, c in casados.items()}

    # ---- empresas novas
    cnpjs_daqui = {cb._cnpj(e.get("cnpj")) for e in banco.get("empresa", []) if e.get("cnpj")}
    for i, l in enumerate(casados["empresa"]["so_la"], 1):
        grupo = mapa["grupo_economico"].get(l.get("grupo_id"))
        rotulo = cb._rotulo("empresa", l, nomes_la)
        if grupo is None:
            plano.avisos.append(f"empresa {rotulo}: o grupo dela não existe aqui; não entra")
            continue
        if cb._cnpj(l.get("cnpj")) in cnpjs_daqui:
            plano.avisos.append(f"empresa {rotulo}: o CNPJ já está em outra empresa daqui; não entra")
            continue
        mapa["empresa"][l["id"]] = -i
        plano.inserir.setdefault("empresa", []).append({**_novo("empresa", l, {"grupo_id": grupo}), "_id": -i, "_rotulo": rotulo})

    # ---- contatos novos, sem duplicar o que é o mesmo
    empresas_do_contato_la: dict[object, set] = {}
    for v in arquivo.get("vinculo_de_contato", []):
        empresas_do_contato_la.setdefault(v["pessoa_id"], set()).add(v["empresa_id"])
    pessoas_la = {p["id"]: p for p in arquivo.get("pessoa_contato", [])}
    novos_ids = {p["id"] for p in casados["pessoa_contato"]["so_la"]}
    for i, l in enumerate(casados["pessoa_contato"]["so_la"], 1):
        rotulo = cb._rotulo("pessoa_contato", l, nomes_la)
        if not l.get("email"):
            palavras = _palavras(l.get("nome"))
            mesmo = [p for pid, p in pessoas_la.items() if pid != l["id"] and pid not in novos_ids
                     and empresas_do_contato_la.get(pid, set()) & empresas_do_contato_la.get(l["id"], set())
                     and palavras and _palavras(p.get("nome"))[:1] == palavras[:1]
                     and set(palavras) <= set(_palavras(p.get("nome")))]
            if len(mesmo) == 1 and mesmo[0]["id"] in mapa["pessoa_contato"]:
                mapa["pessoa_contato"][l["id"]] = mapa["pessoa_contato"][mesmo[0]["id"]]
                plano.avisos.append(f"contato {rotulo}: é {mesmo[0].get('nome')}, que já existe; não duplica")
                continue
        mapa["pessoa_contato"][l["id"]] = -i
        plano.inserir.setdefault("pessoa_contato", []).append({**_novo("pessoa_contato", l, {}), "_id": -i, "_rotulo": rotulo})

    # ---- vínculos novos (sem repetir pessoa e empresa); contato novo sem vínculo que entre fica de fora
    com_vinculo: set[int] = set()
    ja = {(v["pessoa_id"], v["empresa_id"]) for v in banco.get("vinculo_de_contato", [])}
    for l in casados["vinculo_de_contato"]["so_la"]:
        pessoa, empresa = mapa["pessoa_contato"].get(l["pessoa_id"]), mapa["empresa"].get(l["empresa_id"])
        rotulo = cb._rotulo("vinculo_de_contato", l, nomes_la)
        if pessoa is None or empresa is None:
            plano.avisos.append(f"vínculo {rotulo}: a pessoa ou a empresa não entrou; não entra")
            continue
        com_vinculo.add(pessoa)
        if (pessoa, empresa) in ja:
            continue
        ja.add((pessoa, empresa))
        plano.inserir.setdefault("vinculo_de_contato", []).append(
            {**_novo("vinculo_de_contato", l, {"pessoa_id": pessoa, "empresa_id": empresa}), "_rotulo": rotulo})

    tinham_vinculo = {v["pessoa_id"] for v in arquivo.get("vinculo_de_contato", [])}
    novos = []
    for r in plano.inserir.get("pessoa_contato", []):
        la_id = next(i for i, m in mapa["pessoa_contato"].items() if m == r["_id"])
        if la_id in tinham_vinculo and r["_id"] not in com_vinculo:
            plano.avisos.append(f"contato {r['_rotulo']}: nenhuma empresa dele entra; não entra")
            continue
        novos.append(r)
    if "pessoa_contato" in plano.inserir:
        plano.inserir["pessoa_contato"] = novos

    # ---- preencher e trocar
    for tabela in TABELAS_QUE_MUDAM:
        for l, d in casados[tabela]["pares"]:
            campos = cb._diferencas(tabela, l, d, k_la, k_aqui, nomes_la, nomes_aqui)
            depois = cb._instante(l.get("atualizado_em")) > cb._instante(d.get("atualizado_em"))
            rotulo = cb._rotulo(tabela, d, nomes_aqui)
            valores, mostrar = {}, []
            for campo, v_aqui, v_la, tipo in campos:
                if campo in cb.REFERENCIAS:
                    continue
                troca = tipo == "conflito" and depois and campo in TROCA_QUANDO_LA_E_MAIS_NOVO.get(tabela, set())
                if tipo == "preencher" or troca:
                    if campo == "cnpj" and cb._cnpj(l[campo]) in cnpjs_daqui:
                        plano.avisos.append(f"{tabela} {rotulo}: o CNPJ {l[campo]} já está em outra empresa daqui; fica sem")
                        continue
                    valor = _valor_da_coluna(tabela, campo, l[campo])
                    if campo == "observacao" and troca:  # a observação nunca perde o texto daqui
                        valor = f"{l[campo]}\n{d[campo]}"
                    valores[campo] = valor
                    mostrar.append((campo, v_aqui, cb._valor(valor) if isinstance(valor, str) else v_la))
                elif tipo == "conflito":
                    plano.pendentes.append((tabela, rotulo, campo, v_aqui, v_la))
            if valores:
                plano.mudar.append((tabela, d["id"], rotulo, valores, mostrar))
    return plano


def gravar(plano: Plano, engine: sa.Engine) -> None:
    """Numa transação só: entra tudo ou nada."""
    with engine.begin() as c:
        ids: dict[str, dict[int, int]] = {}
        for tabela in ("empresa", "pessoa_contato", "vinculo_de_contato"):
            t = Base.metadata.tables[tabela]
            for r in plano.inserir.get(tabela, []):
                registro = {k: v for k, v in r.items() if not k.startswith("_")}
                for col, ref in (("pessoa_id", "pessoa_contato"), ("empresa_id", "empresa")):
                    if isinstance(registro.get(col), int) and registro[col] < 0:
                        registro[col] = ids[ref][registro[col]]
                novo_id = c.execute(sa.insert(t).values(**registro).returning(t.c.id)).scalar_one()
                if "_id" in r:
                    ids.setdefault(tabela, {})[r["_id"]] = novo_id
        for tabela, id_, _, valores, _ in plano.mudar:
            t = Base.metadata.tables[tabela]
            c.execute(sa.update(t).where(t.c.id == id_).values(**valores, atualizado_em=agora()))


def _mostrar(plano: Plano) -> None:
    for tabela, novos in plano.inserir.items():
        print(f"• {tabela}: {len(novos)} novos")
        for r in novos:
            print(f"    + {r['_rotulo']}")
    por_tabela: dict[str, list] = {}
    for m in plano.mudar:
        por_tabela.setdefault(m[0], []).append(m)
    for tabela, mudancas in por_tabela.items():
        print(f"• {tabela}: {len(mudancas)} com campo preenchido ou trocado")
        for _, _, rotulo, _, mostrar in mudancas:
            print(f"    ~ {rotulo}")
            for campo, de, para in mostrar:
                print(f"        {campo}: {cb._curto(de)}  →  {cb._curto(para)}")
    if plano.pendentes:
        print(f"• Ficam como estão aqui ({len(plano.pendentes)} conflitos, para decidir à mão se quiser):")
        for tabela, rotulo, campo, aqui, la in plano.pendentes:
            print(f"    = {tabela} {rotulo} · {campo}: aqui {cb._curto(aqui)} · lá {cb._curto(la)}")
    for aviso in plano.avisos:
        print(f"  ⚠ {aviso}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arquivo")
    p.add_argument("--gravar", action="store_true")
    a = p.parse_args()
    caminho = Path(a.arquivo).expanduser()
    if not caminho.exists():
        print(f"✗ Não achei o arquivo {caminho}.", file=sys.stderr)
        return 1
    engine = criar_engine()
    plano = montar(cb._do_arquivo(caminho), engine)
    _mostrar(plano)
    if not a.gravar:
        print("\nNada foi gravado. Para gravar, rode de novo com --gravar.")
        return 0
    gravar(plano, engine)
    print("\n✓ Gravado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
