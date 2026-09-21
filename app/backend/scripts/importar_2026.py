"""Importa a planilha de performance comercial de 2026 para o CRM.

Pode rodar quantas vezes for preciso: a identidade de cada proposta vem do
conteúdo, não da posição na aba.

Uso:
    ~/.venvs/criterio-crm/bin/python scripts/importar_2026.py <planilha> [--gravar]

Sem `--gravar`, faz tudo e **desfaz no fim**: mostra exatamente o que
aconteceria, sem tocar no banco. É o padrão de propósito.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from crm.carga.arquivo import ler_aba_propostas  # noqa: E402
from crm.carga.persistencia import importar, registrar_execucao  # noqa: E402
from crm.carga.planilha_2026 import carregar  # noqa: E402
from crm.db.modelos import GrupoEconomico, Oportunidade  # noqa: E402
from crm.db.sessao import criar_engine, url_do_banco  # noqa: E402


def principal(argumentos: list[str]) -> int:
    if not argumentos:
        print(__doc__)
        return 2

    caminho = argumentos[0]
    gravar = "--gravar" in argumentos

    print("=" * 66)
    print("LEITURA DA PLANILHA")
    print("=" * 66)
    propostas, relatorio_leitura = carregar(ler_aba_propostas(caminho))
    print(relatorio_leitura.resumo())

    engine = criar_engine(url_do_banco())
    with Session(engine, future=True) as sessao:
        print()
        print("=" * 66)
        print("GRAVAÇÃO NO BANCO" + ("" if gravar else "  (simulação — nada será mantido)"))
        print("=" * 66)
        resultado = importar(sessao, propostas)
        print(resultado.resumo())

        # Só uma carga que vale entra para o histórico. A simulação não deixa
        # rastro: um relatório de conferência cheio de ensaios deixaria de ser
        # prova do que realmente está no CRM.
        execucao = registrar_execucao(sessao, caminho, relatorio_leitura, resultado) if gravar else None

        print()
        print("=" * 66)
        print("COMO A CARTEIRA FICA")
        print("=" * 66)
        total = sessao.scalar(sa.select(sa.func.count()).select_from(Oportunidade))
        grupos = sessao.scalar(sa.select(sa.func.count()).select_from(GrupoEconomico))
        print(f"Oportunidades: {total} · Grupos econômicos: {grupos}")

        for titulo, coluna in (
            ("Por situação", Oportunidade.situacao),
            ("Por tipo de canal", Oportunidade.tipo_canal),
            ("Por captador", Oportunidade.captador),
        ):
            print(f"\n{titulo}:")
            linhas = sessao.execute(
                sa.select(coluna, sa.func.count())
                .group_by(coluna)
                .order_by(sa.func.count().desc())
            ).all()
            for valor, quantos in linhas:
                rotulo = getattr(valor, "value", valor) or "(vazio)"
                print(f"  {rotulo:28} {quantos:3}")

        print("\nGrupos com mais de uma proposta:")
        repetidos = sessao.execute(
            sa.select(sa.func.count())
            .select_from(
                sa.select(Oportunidade.grupo_id)
                .group_by(Oportunidade.grupo_id)
                .having(sa.func.count() > 1)
                .subquery()
            )
        ).scalar()
        print(f"  {repetidos} grupos — candidatos naturais a conferência")

        if gravar:
            sessao.commit()
            print(f"\n✓ GRAVADO. Relatório de conferência registrado como carga nº {execucao.id}:")
            print("  abra a tela Conferência para ver o que ficou pendente e o que foi ajustado.")
        else:
            sessao.rollback()
            print("\n↩ Desfeito. Rode de novo com --gravar para valer.")

    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
