"""Lista os grupos econômicos com mais de uma proposta, para conferência humana.

A carga agrupa pelo nome do cliente: se duas linhas dizem o mesmo nome, são o
mesmo cliente. É o que o dado sustenta sozinho — mas **nome igual não prova
grupo igual**, e nome diferente não prova grupo diferente. Só uma pessoa que
conhece a carteira decide.

Este relatório mostra o que a carga agrupou, para que essa decisão seja fácil.

Uso:
    ~/.venvs/criterio-crm/bin/python scripts/conferir_grupos.py [arquivo de saída]

⚠️ A saída contém **nome de cliente e valor de proposta**. Não a grave dentro
do repositório: `workspaces/` é versionado e dado de cliente não entra em git.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from crm.db.modelos import GrupoEconomico, Oportunidade  # noqa: E402
from crm.db.sessao import criar_engine, url_do_banco  # noqa: E402

#: Palavras que aparecem em nome de empresa sem identificar ninguém.
RUIDO = {
    "ltda", "sa", "eireli", "epp", "cia", "inc", "llc", "grupo", "holding",
    "participacoes", "comercio", "industria", "servicos", "brasil", "nordeste",
    "rio", "sao",
}

#: Acima de quantos grupos um termo deixa de ser nome e vira palavra de serviço.
#:
#: "aeskins" em 4 grupos é um cliente com quatro propostas. "contabilidade" em
#: 4 grupos é o serviço que a Critério vende. O corte separa os dois sem
#: precisar de lista de palavras — e o que passar errado, a pessoa descarta.
LIMITE_DE_GENERICO = 4


def _tokens(nome: str) -> set[str]:
    texto = unicodedata.normalize("NFKD", nome)
    texto = "".join(c for c in texto if not unicodedata.combining(c)).casefold()
    texto = re.sub(r"[^a-z0-9 ]", " ", texto)
    return {t for t in texto.split() if len(t) > 2 and t not in RUIDO}


def _candidatos_a_fusao(sessao: Session) -> list[tuple[str, list]]:
    """Grupos distintos cujos nomes compartilham um termo identificador.

    Heurística deliberadamente grosseira: ela **sugere**, e uma pessoa decide.
    Errar para mais é barato — quem confere descarta. Errar para menos esconde
    um grupo econômico inteiro, que é o que aconteceu com a carga por nome.
    """
    grupos = sessao.scalars(sa.select(GrupoEconomico)).all()
    onde: dict[str, set[int]] = defaultdict(set)
    for grupo in grupos:
        for termo in _tokens(grupo.nome):
            onde[termo].add(grupo.id)

    por_id = {g.id: g for g in grupos}
    conjuntos: dict[frozenset, tuple[str, list]] = {}
    for termo, ids in onde.items():
        if not 2 <= len(ids) <= LIMITE_DE_GENERICO + 5:
            continue
        chave = frozenset(ids)
        if chave in conjuntos:
            continue
        conjuntos[chave] = (termo, [por_id[i] for i in ids])

    return sorted(conjuntos.values(), key=lambda par: (-len(par[1]), par[0]))


def _dinheiro(valor: Decimal | None) -> str:
    if valor is None:
        return "—"
    inteiro, _, centavos = f"{valor:,.2f}".partition(".")
    return f"R$ {inteiro.replace(',', '.')},{centavos}"


def _rotulo(valor) -> str:
    return getattr(valor, "value", valor) or "—"


def gerar() -> str:
    linhas: list[str] = []
    engine = criar_engine(url_do_banco())

    with Session(engine, future=True) as sessao:
        repetidos = sessao.execute(
            sa.select(Oportunidade.grupo_id, sa.func.count().label("quantas"))
            .group_by(Oportunidade.grupo_id)
            .having(sa.func.count() > 1)
            .order_by(sa.func.count().desc())
        ).all()

        linhas.append("GRUPOS COM MAIS DE UMA PROPOSTA EM 2026")
        linhas.append("=" * 74)
        linhas.append("")
        linhas.append(
            f"{len(repetidos)} grupos, formados pelo nome do cliente na planilha."
        )
        linhas.append("")
        linhas.append("Para cada um, a pergunta é uma só:")
        linhas.append("  São mesmo o mesmo cliente, ou a planilha repetiu um nome?")
        linhas.append("")
        linhas.append("E, olhando as propostas lado a lado:")
        linhas.append("  • serviços diferentes, valores diferentes → propostas legítimas")
        linhas.append("  • tudo igual menos o valor → cenários oferecidos ao cliente")
        linhas.append("  • tudo igual → conferir com quem digitou")
        linhas.append("")

        for posicao, (grupo_id, quantas) in enumerate(repetidos, start=1):
            grupo = sessao.get(GrupoEconomico, grupo_id)
            propostas = sessao.scalars(
                sa.select(Oportunidade)
                .where(Oportunidade.grupo_id == grupo_id)
                .order_by(Oportunidade.data_colocacao, Oportunidade.linha_planilha)
            ).all()

            linhas.append("-" * 74)
            linhas.append(f"{posicao:2}. {grupo.nome}   ({quantas} propostas)")
            linhas.append("")
            for p in propostas:
                data = p.data_colocacao.strftime("%d/%m/%Y") if p.data_colocacao else "sem data"
                linhas.append(
                    f"    linha {p.linha_planilha:>3} · {data} · {_rotulo(p.situacao)}"
                )
                linhas.append(
                    f"              serviço: {_rotulo(p.servico)} / {_rotulo(p.tipo_servico)}"
                )
                linhas.append(
                    f"              captador: {_rotulo(p.captador)} · "
                    f"canal: {_rotulo(p.tipo_canal)} / {_rotulo(p.canal)}"
                )
                linhas.append(
                    f"              mensal: {_dinheiro(p.preco_mensal)} · "
                    f"anual: {_dinheiro(p.preco_anual)}"
                )
                if p.motivo_recusa_original:
                    linhas.append(f"              motivo: {p.motivo_recusa_original}")
                linhas.append("")

        linhas.append("=" * 74)
        linhas.append("O QUE FAZER COM CADA UM")
        linhas.append("")
        linhas.append("  Está certo        → nada a fazer.")
        linhas.append("  Não é o mesmo     → separar; vira dois grupos.")
        linhas.append("  Falta um irmão    → fundir com o outro grupo, por fundir_grupos.")
        linhas.append("")
        linhas.append("")
        linhas.append("=" * 74)
        linhas.append("PARTE 2 — GRUPOS SEPARADOS QUE TALVEZ SEJAM O MESMO CLIENTE")
        linhas.append("=" * 74)
        linhas.append("")
        linhas.append("A carga agrupa por nome exato, e a coluna 'Nome da oportunidade'")
        linhas.append("mistura cliente com serviço: 'Sete Brasil (Leo Fraga) - Regularização")
        linhas.append("do Bacen' é uma coisa só. Por isso o mesmo cliente aparece em vários")
        linhas.append("grupos, e a Parte 1 sozinha subestima muito o reagrupamento.")
        linhas.append("")
        linhas.append("Abaixo, grupos distintos que compartilham um termo do nome.")
        linhas.append("⚠️ É SUGESTÃO, não conclusão. Alguns são coincidência de palavra de")
        linhas.append("   serviço — 'transação tributária' não é cliente. Descarte esses.")
        linhas.append("")

        contagem = dict(
            sessao.execute(
                sa.select(Oportunidade.grupo_id, sa.func.count()).group_by(
                    Oportunidade.grupo_id
                )
            ).all()
        )
        candidatos = _candidatos_a_fusao(sessao)
        linhas.append(f"{len(candidatos)} conjuntos candidatos.")
        linhas.append("")

        for posicao, (termo, grupos_do_termo) in enumerate(candidatos, start=1):
            total = sum(contagem.get(g.id, 0) for g in grupos_do_termo)
            linhas.append("-" * 74)
            linhas.append(
                f"{posicao:2}. termo em comum: '{termo}'   "
                f"({len(grupos_do_termo)} grupos, {total} propostas)"
            )
            for grupo in sorted(grupos_do_termo, key=lambda g: -contagem.get(g.id, 0)):
                linhas.append(f"      · {grupo.nome}  ({contagem.get(grupo.id, 0)}p)")
            linhas.append("")

    return "\n".join(linhas)


if __name__ == "__main__":
    texto = gerar()
    if len(sys.argv) > 1:
        destino = Path(sys.argv[1])
        destino.write_text(texto, encoding="utf-8")
        print(f"Gravado em {destino}")
    else:
        print(texto)
