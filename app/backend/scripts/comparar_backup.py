"""Compara um arquivo de backup com o banco do CRM, sem gravar nada (03/10/2026).

    comparar_backup.py <arquivo>

Para quando alguém trabalhou num **outro** CRM (outro computador, outra cópia do banco) e mandou o
backup: mostra, tabela por tabela, o que está **só no arquivo** (incluído lá), o que foi **alterado
lá depois** da versão daqui, e quantos registros estão só no banco daqui. Não importa nada.

Como reconhece "o mesmo registro" nas duas cópias: pela data de criação (ao segundo) mais o nome
(ou razão social, CNPJ, e-mail…). O número (id) não serve: as duas cópias deram números novos
cada uma por conta própria depois de se separarem.

⚠️ A saída tem nomes de clientes: fica na tela, não vai para o repositório nem para nota.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import sqlalchemy as sa  # noqa: E402

from crm.db.sessao import criar_engine  # noqa: E402

#: Tabelas que alguém inclui ou altera na tela, e o campo que diz quem é o registro.
ROTULOS: dict[str, tuple[str, ...]] = {
    "grupo_economico": ("nome",),
    "empresa": ("cnpj", "razao_social"),
    "pessoa_contato": ("email", "nome"),
    "vinculo_de_contato": ("papel", "cargo"),
    "oportunidade": ("nome",),
    "lead": ("nome", "email"),
    "contrato": ("escopo", "preco_mensal"),
    "evento_de_contrato": ("tipo", "data_do_evento"),
    "proposta": ("numero", "ano"),
    "pendencia_da_proposta": ("chave", "descricao"),
    "questionario_recebido": ("razao_social", "cnpj"),
    "classificacao_do_grupo": ("referencia", "classe"),
    "reuniao_de_resultado": ("tipo", "data"),
    "ajuste_tecnico": ("descricao",),
}
_IGNORAR_NA_DIFERENCA = {"id", "criado_em", "atualizado_em"}


#: Coluna que aponta para outro registro → a tabela dele. O rótulo leva o nome do apontado (o número
#: não serve: cada cópia numerou por conta própria).
REFERENCIAS = {
    "grupo_id": "grupo_economico", "empresa_id": "empresa", "pessoa_id": "pessoa_contato",
    "oportunidade_id": "oportunidade", "contrato_id": "contrato", "reuniao_id": "reuniao_de_resultado",
}

Nomes = dict[str, dict[object, str]]


def _rotulo_proprio(tabela: str, linha: dict) -> str:
    campos = ROTULOS.get(tabela, ("nome",))
    partes = [_valor(linha[c]) for c in campos if linha.get(c) not in (None, "")]
    return " · ".join(partes) or f"#{linha.get('id')}"


def _nomes(tabelas: dict[str, list[dict]]) -> Nomes:
    """id → rótulo, por tabela, dentro de uma cópia só."""
    return {t: {l.get("id"): _rotulo_proprio(t, l) for l in tabelas.get(t, [])} for t in set(REFERENCIAS.values())}


def _rotulo(tabela: str, linha: dict, nomes: Nomes | None = None) -> str:
    proprio = _rotulo_proprio(tabela, linha)
    if not nomes:
        return proprio
    apontados = [nomes[ref].get(linha[col], "?") for col, ref in REFERENCIAS.items()
                 if col in linha and linha[col] is not None and ref != tabela]
    return " / ".join([*apontados, proprio])


def _instante(v) -> str:
    """Data e hora em UTC, ao segundo: o arquivo e o banco podem vir em fusos diferentes."""
    if v in (None, ""):
        return ""
    try:
        d = v if isinstance(v, datetime) else datetime.fromisoformat(str(v))
    except ValueError:
        return str(v)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _valor(v) -> str:
    """O mesmo valor escrito do mesmo jeito: falso = 0, 1000 = 1000.00, data e hora em UTC."""
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, datetime):
        return _instante(v)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, ensure_ascii=False)
    texto = str(v)
    if texto in ("True", "False"):
        return "1" if texto == "True" else "0"
    try:
        return format(Decimal(texto).normalize(), "f")  # 8000.00 → "8000" (e não "8E+3")
    except InvalidOperation:
        pass
    if len(texto) >= 19 and texto[4] == "-" and texto[10] in " T":
        return _instante(texto)
    if texto.startswith(("{", "[")):
        try:
            return json.dumps(json.loads(texto), sort_keys=True, ensure_ascii=False)
        except ValueError:
            pass
    return texto


def _chave(tabela: str, linha: dict, nomes: Nomes) -> tuple:
    return (_instante(linha.get("criado_em")), _rotulo(tabela, linha, nomes).strip().casefold())


def _agrupar(tabela: str, linhas: list[dict], nomes: Nomes) -> dict[tuple, list[dict]]:
    """Por chave, todos os registros com ela: dois iguais criados no mesmo segundo contam como dois."""
    grupos: dict[tuple, list[dict]] = {}
    for l in linhas:
        grupos.setdefault(_chave(tabela, l, nomes), []).append(l)
    return grupos


def _do_arquivo(caminho: Path) -> dict[str, list[dict]]:
    with zipfile.ZipFile(caminho) as zf:
        manifesto = json.loads(zf.read("manifesto.json"))
        print(f"Arquivo: esquema {manifesto.get('revisao_do_esquema')}, criado em {manifesto.get('criado_em')}")
        tabelas = {}
        for nome in zf.namelist():
            if nome.startswith("dados/") and nome.endswith(".jsonl"):
                texto = zf.read(nome).decode("utf-8")
                tabelas[nome[6:-6]] = [json.loads(l) for l in texto.splitlines() if l.strip()]
        return tabelas


def _do_banco(engine: sa.Engine, tabela: str) -> list[dict] | None:
    with engine.connect() as c:
        if not sa.inspect(c).has_table(tabela):
            return None
        return [dict(r._mapping) for r in c.execute(sa.text(f'SELECT * FROM "{tabela}"'))]


def comparar(arquivo: dict[str, list[dict]], engine: sa.Engine) -> dict[str, dict]:
    """Por tabela: `so_no_arquivo`, `alterados_no_arquivo` (com os campos que mudaram) e
    `so_no_banco` (só a contagem). Tabelas que o banco daqui não tem vêm com `banco=None`."""
    resultado = {}
    do_banco = {t: _do_banco(engine, t) for t in arquivo}
    nomes_arquivo = _nomes(arquivo)
    nomes_banco = _nomes({t: v for t, v in do_banco.items() if v is not None})
    for tabela in sorted(arquivo):
        linhas_arquivo = arquivo[tabela]
        linhas_banco = do_banco[tabela]
        if linhas_banco is None:
            resultado[tabela] = {"banco": None, "arquivo": len(linhas_arquivo)}
            continue
        if tabela not in ROTULOS:
            continue  # tabelas técnicas (parâmetros, carga, perfis…): não são inclusões de tela
        banco = _agrupar(tabela, linhas_banco, nomes_banco)
        do_arquivo = _agrupar(tabela, linhas_arquivo, nomes_arquivo)
        so_no_arquivo, alterados = [], []
        for chave, ls in do_arquivo.items():
            daqui = banco.get(chave, [])
            so_no_arquivo += ls[len(daqui):]
            for l, d in zip(ls, daqui):
                if _instante(l.get("atualizado_em")) > _instante(d.get("atualizado_em")):
                    mudou = [c for c, v in l.items() if c not in _IGNORAR_NA_DIFERENCA and not c.endswith("_id")
                             and c in d and _valor(v) != _valor(d[c])]
                    if mudou:
                        alterados.append((l, mudou))
        resultado[tabela] = {
            "banco": len(linhas_banco), "arquivo": len(linhas_arquivo),
            "so_no_arquivo": so_no_arquivo, "alterados_no_arquivo": alterados,
            "so_no_banco": sum(max(0, len(d) - len(do_arquivo.get(k, []))) for k, d in banco.items()),
            "nomes": nomes_arquivo,
        }
    return resultado


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arquivo")
    a = p.parse_args()
    caminho = Path(a.arquivo).expanduser()
    if not caminho.exists():
        print(f"✗ Não achei o arquivo {caminho}.", file=sys.stderr)
        return 1
    resultado = comparar(_do_arquivo(caminho), criar_engine())
    print("Nada foi gravado.\n")
    for tabela, r in resultado.items():
        if r["banco"] is None:
            print(f"• {tabela}: só existe no CRM do arquivo ({r['arquivo']} registros) — esta versão não tem essa tabela.")
            continue
        novos, alterados = r["so_no_arquivo"], r["alterados_no_arquivo"]
        if not novos and not alterados:
            continue
        print(f"• {tabela}: {len(novos)} só no arquivo · {len(alterados)} alterados lá depois · {r['so_no_banco']} só no banco daqui")
        for l in sorted(novos, key=lambda x: str(x.get("criado_em"))):
            print(f"    + {_rotulo(tabela, l, r['nomes'])}   (criado em {str(l.get('criado_em'))[:16]})")
        for l, campos in alterados:
            print(f"    ~ {_rotulo(tabela, l, r['nomes'])}   (alterado em {str(l.get('atualizado_em'))[:16]}: {', '.join(campos)})")
    print("\nFim. Mande esta saída para o Claude decidir com você o que trazer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
