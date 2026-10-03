"""Compara um arquivo de backup com o banco do CRM, sem gravar nada (03/10/2026).

    comparar_backup.py <arquivo>

Para quando alguém trabalhou num **outro** CRM (outro computador, outra cópia do banco) e mandou o
backup: mostra, tabela por tabela, o que está **só no arquivo** (incluído lá), o que tem **diferença**
entre as duas cópias e quantos registros estão só no banco daqui. Não importa nada.

Como reconhece "o mesmo registro" nas duas cópias (revisto em 03/10/2026, a pedido de Eduardo): pelo
que identifica o registro de verdade, e não pela hora em que nasceu (a mesma empresa pode ter nascido
em horas diferentes em cada cópia, quando a atualização do CRM rodou em momentos diferentes):

- grupo pelo nome; empresa pelo CNPJ (ou razão social e grupo, sem CNPJ); contato pelo e-mail (ou
  nome); vínculo pelo contato e pela empresa; oportunidade pela chave da planilha (ou grupo e nome);
  contrato pela oportunidade (ou grupo, empresa e escopo); proposta pelo número e ano; e assim por
  diante (`CHAVES`). Nome sem acento, sem caixa e sem espaço sobrando; CNPJ só com os dígitos.
- O número (id) não serve: cada cópia numerou por conta própria. As colunas que apontam para outro
  registro (`grupo_id`, `empresa_id`…) se comparam pelo registro apontado.

Cada diferença diz se é para **preencher** (vazio aqui, preenchido lá), um **conflito** (preenchido
nos dois, diferente) ou **vazio lá** (preenchido aqui, vazio lá), e qual cópia mexeu no registro por
último. `campos_do_crm` (controle interno) fica de fora.

⚠️ A saída tem nomes de clientes: fica na tela, não vai para o repositório nem para nota.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
import zipfile
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import sqlalchemy as sa  # noqa: E402

from crm.db.sessao import criar_engine  # noqa: E402

#: Como cada registro aparece na tela.
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
    "oportunidade_da_reuniao": ("servico", "lacuna"),
    "reuniao_da_carteira": ("data",),
}

#: Coluna que aponta para outro registro → a tabela dele.
REFERENCIAS = {
    "grupo_id": "grupo_economico", "empresa_id": "empresa", "pessoa_id": "pessoa_contato",
    "oportunidade_id": "oportunidade", "contrato_id": "contrato", "reuniao_id": "reuniao_de_resultado",
}

_IGNORAR = {"id", "criado_em", "atualizado_em", "campos_do_crm"}

Linha = dict
Chave = tuple


def _texto(v) -> str:
    """Sem acento, sem caixa e sem espaço sobrando: "Grupo  Blác" e "grupo blac" são o mesmo."""
    t = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(t.split())


def _digitos(v) -> str:
    return "".join(c for c in str(v or "") if c.isdigit())


def _cnpj(v) -> str | None:
    """Só os dígitos, com os zeros da frente (a planilha às vezes perde o primeiro zero)."""
    d = "".join(c for c in str(v or "") if c.isdigit())
    return d.zfill(14) if d else None


class _Chaves:
    """A chave natural de cada registro de uma cópia, por tabela e id: o que as referências usam."""

    def __init__(self) -> None:
        self.por_id: dict[str, dict[object, Chave]] = {}

    def de(self, tabela: str, id_) -> Chave | None:
        if id_ is None:
            return None
        return self.por_id.get(tabela, {}).get(id_, ("sem registro", tabela, id_))


def _ref(k: _Chaves, l: Linha, coluna: str) -> Chave | None:
    return k.de(REFERENCIAS[coluna], l.get(coluna))


#: A chave natural de cada tabela, na ordem em que as referências precisam (quem aponta vem depois).
CHAVES: dict[str, Callable[[Linha, _Chaves], Chave]] = {
    "grupo_economico": lambda l, k: ("grupo", _texto(l.get("nome"))),
    "empresa": lambda l, k: (("cnpj", _cnpj(l.get("cnpj"))) if _cnpj(l.get("cnpj"))
                             else ("empresa", _texto(l.get("razao_social")), _ref(k, l, "grupo_id"))),
    "pessoa_contato": lambda l, k: (("email", _texto(l.get("email"))) if l.get("email")
                                    else ("pessoa", _texto(l.get("nome")))),
    "oportunidade": lambda l, k: (("planilha", l["chave_origem"]) if l.get("chave_origem")
                                  else ("oportunidade", _ref(k, l, "grupo_id"), _texto(l.get("nome")))),
    "vinculo_de_contato": lambda l, k: ("vinculo", _ref(k, l, "pessoa_id"), _ref(k, l, "empresa_id")),
    "lead": lambda l, k: (("email", _texto(l.get("email"))) if l.get("email") else ("lead", _texto(l.get("nome")))),
    "contrato": lambda l, k: (("da oportunidade", _ref(k, l, "oportunidade_id")) if l.get("oportunidade_id")
                              else ("contrato", _ref(k, l, "grupo_id"), _texto(l.get("escopo")))),
    "evento_de_contrato": lambda l, k: ("evento", _ref(k, l, "contrato_id"), l.get("tipo"), _valor(l.get("data_do_evento"))),
    "proposta": lambda l, k: ("proposta", _valor(l.get("ano")), _valor(l.get("numero"))),
    "pendencia_da_proposta": lambda l, k: ("pendencia", _ref(k, l, "oportunidade_id"), l.get("chave")),
    "questionario_recebido": lambda l, k: ("questionario", l.get("externo_id")),
    "classificacao_do_grupo": lambda l, k: ("leitura", _ref(k, l, "grupo_id"), _valor(l.get("referencia")),
                                            _valor(l.get("revisao"))),
    "reuniao_de_resultado": lambda l, k: ("reuniao", _ref(k, l, "grupo_id"), l.get("tipo"), _valor(l.get("data"))),
    "ajuste_tecnico": lambda l, k: ("ajuste", _ref(k, l, "reuniao_id"), _texto(l.get("descricao"))),
    "oportunidade_da_reuniao": lambda l, k: ("venda", _ref(k, l, "reuniao_id"), l.get("servico"), _texto(l.get("lacuna"))),
    "reuniao_da_carteira": lambda l, k: ("carteira", _valor(l.get("data"))),
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


def _hora_local(v) -> str:
    """Para a tela: dd/mm hh:mm no horário de Brasília."""
    t = _instante(v)
    if not t:
        return "?"
    d = datetime.fromisoformat(t).replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=-3)))
    return d.strftime("%d/%m %H:%M")


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


def _agrupar(tabela: str, linhas: list[Linha], k: _Chaves) -> dict[Chave, list[Linha]]:
    """A chave natural de cada registro, guardada para as referências, e os registros por chave
    (dois com a mesma chave contam como dois)."""
    chave_de = CHAVES[tabela]
    k.por_id[tabela] = {}
    por_chave: dict[Chave, list[Linha]] = {}
    for l in sorted(linhas, key=lambda l: (_instante(l.get("criado_em")), str(l.get("id")))):
        chave = chave_de(l, k)
        k.por_id[tabela][l.get("id")] = chave
        por_chave.setdefault(chave, []).append(l)
    return por_chave


def _casar_empresa_sem_cnpj(la: dict[Chave, list[Linha]], aqui: dict[Chave, list[Linha]], k_la: _Chaves,
                            k_aqui: _Chaves) -> None:
    """A empresa com CNPJ de um lado e sem CNPJ do outro, com a mesma razão social no mesmo grupo, é a
    mesma: a daqui passa a ter a chave da de lá (e as referências a ela também)."""
    for chave, ls in la.items():
        if chave[0] != "cnpj" or chave in aqui:
            continue
        l = ls[0]
        candidata = ("empresa", _texto(l.get("razao_social")), _ref(k_la, l, "grupo_id"))
        if len(ls) == 1 and len(aqui.get(candidata, [])) == 1:
            d = aqui.pop(candidata)[0]
            aqui[chave] = [d]
            k_aqui.por_id["empresa"][d.get("id")] = chave


def casar(arquivo: dict[str, list[Linha]], banco: dict[str, list[Linha]]) -> tuple[dict, _Chaves, _Chaves]:
    """Tabela por tabela, na ordem das referências: os pares (lá, aqui), o que só está lá e quantos só
    aqui. Cada tabela se casa antes de a seguinte calcular as chaves, para a referência a um registro
    casado de outro jeito (empresa sem CNPJ) apontar para a mesma chave nos dois lados."""
    k_la, k_aqui = _Chaves(), _Chaves()
    saida: dict[str, dict] = {}
    for tabela in CHAVES:
        la = _agrupar(tabela, arquivo.get(tabela) or [], k_la)
        aqui = _agrupar(tabela, banco.get(tabela) or [], k_aqui)
        if tabela == "empresa":  # os grupos já casaram pelo nome: a chave do grupo é a mesma nos dois lados
            _casar_empresa_sem_cnpj(la, aqui, k_la, k_aqui)
        pares, so_la = [], []
        for chave, ls in la.items():
            daqui = aqui.get(chave, [])
            so_la += ls[len(daqui):]
            pares += list(zip(ls, daqui))
        saida[tabela] = {
            "pares": pares, "so_la": so_la,
            "so_aqui": sum(max(0, len(d) - len(la.get(c, []))) for c, d in aqui.items()),
        }
    return saida, k_la, k_aqui


def _diferencas(tabela: str, la: Linha, aqui: Linha, k_la: _Chaves, k_aqui: _Chaves, nomes_la: Nomes,
                nomes_aqui: Nomes) -> list[tuple[str, str, str, str]]:
    """(campo, valor aqui, valor lá, tipo) de cada campo diferente. Referência se compara pelo registro
    apontado e aparece pelo nome dele."""
    saida = []
    for campo in sorted(set(la) | set(aqui)):
        if campo in _IGNORAR or campo not in la or campo not in aqui:
            continue
        if campo in REFERENCIAS and REFERENCIAS[campo] != tabela:
            ref = REFERENCIAS[campo]
            if k_la.de(ref, la[campo]) == k_aqui.de(ref, aqui[campo]):
                continue
            v_la = nomes_la[ref].get(la[campo], "") if la[campo] is not None else ""
            v_aqui = nomes_aqui[ref].get(aqui[campo], "") if aqui[campo] is not None else ""
        elif campo.endswith("_id"):
            continue  # aponta para tabela técnica (matriz, fusão…): o número não diz nada
        else:
            v_la, v_aqui = _valor(la[campo]), _valor(aqui[campo])
            if v_la == v_aqui or (campo == "telefone" and _digitos(v_la) == _digitos(v_aqui)):
                continue  # "+351 963…" e "351 963…" são o mesmo telefone
        tipo = "preencher" if not v_aqui else ("vazio lá" if not v_la else "conflito")
        saida.append((campo, v_aqui, v_la, tipo))
    return saida


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
    """Por tabela: `so_no_arquivo` (linhas), `diferencas` [(linha lá, linha aqui, [(campo, aqui, lá,
    tipo)], lá mexeu por último)], `so_no_banco` (contagem) e `nomes` do arquivo. Tabelas que o banco
    daqui não tem vêm com `banco=None`; as técnicas (fora de `CHAVES`), de fora."""
    do_banco = {t: _do_banco(engine, t) for t in set(arquivo) | set(CHAVES)}
    banco = {t: v for t, v in do_banco.items() if v is not None}
    nomes_la, nomes_aqui = _nomes(arquivo), _nomes(banco)
    casados, k_la, k_aqui = casar(arquivo, banco)
    resultado: dict[str, dict] = {}
    for tabela in sorted(arquivo):
        if do_banco.get(tabela) is None:
            resultado[tabela] = {"banco": None, "arquivo": len(arquivo[tabela])}
            continue
        if tabela not in CHAVES:
            continue  # tabelas técnicas (parâmetros, carga, perfis…): não são inclusões de tela
        c = casados[tabela]
        diferencas = []
        for l, d in c["pares"]:
            campos = _diferencas(tabela, l, d, k_la, k_aqui, nomes_la, nomes_aqui)
            if campos:
                diferencas.append((l, d, campos, _instante(l.get("atualizado_em")) > _instante(d.get("atualizado_em"))))
        resultado[tabela] = {
            "banco": len(banco[tabela]), "arquivo": len(arquivo[tabela]),
            "so_no_arquivo": c["so_la"], "diferencas": diferencas, "so_no_banco": c["so_aqui"], "nomes": nomes_la,
        }
    return resultado


def _curto(v: str, tamanho: int = 60) -> str:
    if not v:
        return "—"
    return v if len(v) <= tamanho else v[: tamanho - 1] + "…"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("arquivo")
    a = p.parse_args()
    caminho = Path(a.arquivo).expanduser()
    if not caminho.exists():
        print(f"✗ Não achei o arquivo {caminho}.", file=sys.stderr)
        return 1
    resultado = comparar(_do_arquivo(caminho), criar_engine())
    print("Nada foi gravado. \"Lá\" é o arquivo; \"aqui\" é este banco. Horas no horário de Brasília.\n")
    for tabela, r in resultado.items():
        if r["banco"] is None:
            print(f"• {tabela}: só existe no CRM do arquivo ({r['arquivo']} registros) — esta versão não tem essa tabela.")
            continue
        novos, difs = r["so_no_arquivo"], r["diferencas"]
        if not novos and not difs:
            continue
        print(f"• {tabela}: {len(novos)} só lá · {len(difs)} com diferença · {r['so_no_banco']} só aqui")
        for l in sorted(novos, key=lambda x: _instante(x.get("criado_em"))):
            print(f"    + {_rotulo(tabela, l, r['nomes'])}   (criado lá em {_hora_local(l.get('criado_em'))})")
        for l, d, campos, depois in difs:
            quem = f"lá mexeu por último, {_hora_local(l.get('atualizado_em'))}" if depois \
                else f"aqui mexeu por último, {_hora_local(d.get('atualizado_em'))}"
            print(f"    ~ {_rotulo(tabela, l, r['nomes'])}   ({quem})")
            for campo, v_aqui, v_la, tipo in campos:
                print(f"        {campo} [{tipo}]: aqui {_curto(v_aqui)}  →  lá {_curto(v_la)}")
    print("\nFim. Mande esta saída para o Claude decidir com você o que trazer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
