"""Ensaio fiel do SDR de IA (04/10/2026).

    ensaio_sdr.py <pasta de saída> [--modelo MODELO] [--paralelo N]

Põe o modelo do agente (o de `CRM_AGENTE_MODELO`, ou o padrão) no papel do SDR, com o prompt de
sistema do roteiro SPIN e as fichas que valem para a IA no banco, e grava na pasta de saída
`respostas.json` e `relatorio.md` para a correção. Precisa de `ANTHROPIC_API_KEY` no `.env`.

Custo: cerca de 130 chamadas por rodada (96 perguntas e as falas das 6 conversas), com o texto de
sistema em cache. Nada é enviado a lead nenhum.

⚠️ Use uma pasta de saída **fora do repositório**: o relatório é material de trabalho.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REPO = RAIZ.parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import anthropic  # noqa: E402
import sqlalchemy as sa  # noqa: E402

from crm.agente import ensaio_sdr as ensaio  # noqa: E402
from crm.agente.config import ler_configuracao  # noqa: E402
from crm.db.modelos import FichaDaBase  # noqa: E402
from crm.db.sessao import criar_engine, criar_fabrica_de_sessao  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("saida", type=Path, help="pasta onde gravar respostas.json e relatorio.md")
    args.add_argument("--modelo", help="modelo a usar; padrão: o do agente")
    args.add_argument("--paralelo", type=int, default=4, help="chamadas simultâneas (padrão 4)")
    a = args.parse_args(argv)

    saida = a.saida.resolve()
    if saida == REPO or REPO in saida.parents:
        print("✗ Use uma pasta fora do repositório.", file=sys.stderr)
        return 2
    config = ler_configuracao()
    if not config.chave:
        print("✗ Falta ANTHROPIC_API_KEY no .env. Nada foi chamado.", file=sys.stderr)
        return 2

    prompt = ensaio.ler_prompt((REPO / "sdr-ia-roteiro-spin.md").read_text())
    perguntas = ensaio.ler_perguntas((REPO / "sdr-ia-perguntas-teste.md").read_text())
    with criar_fabrica_de_sessao(criar_engine())() as sessao:
        fichas = list(sessao.scalars(sa.select(FichaDaBase).order_by(FichaDaBase.id)))
        sistema, codigos = ensaio.montar_contexto(prompt, fichas, date.today(), config.link_do_questionario)
    modelo = a.modelo or config.modelo
    print(f"Ensaio: {len(perguntas)} perguntas, {len(ensaio.CENARIOS)} conversas, "
          f"{len(codigos)} fichas, modelo {modelo}…")

    resultado = ensaio.rodar(anthropic.Anthropic(api_key=config.chave), modelo, sistema, codigos,
                             perguntas, paralelo=a.paralelo)
    saida.mkdir(parents=True, exist_ok=True)
    (saida / "respostas.json").write_text(json.dumps(asdict(resultado), ensure_ascii=False, indent=1))
    (saida / "relatorio.md").write_text(ensaio.relatorio(resultado))
    print(f"✓ Gravado em {saida} (respostas.json e relatorio.md). Recusas do modelo: {resultado.recusas}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
