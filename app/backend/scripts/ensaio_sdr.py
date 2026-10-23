"""Ensaio fiel do SDR de IA (04/10/2026).

    ensaio_sdr.py <pasta de saída> [--modelo MODELO] [--paralelo N]
    ensaio_sdr.py <pasta de saída> --roteador [--paralelo N]

**--roteador** (fase 1, 23/10/2026): o ensaio passa pelo mesmo roteador das respostas no WhatsApp: regras,
modelo leve, principal e travas, com os modelos e as chaves de Configurações › Integrações (abas IA e
Respostas do SDR). O relatório traz a rota e o custo de cada resposta e o custo médio por conversa. É este o
ensaio que libera o modo automático: zero violação de P1 a P12 e a passagem certa em todos os gatilhos T.

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

from crm import configuracao  # noqa: E402
from crm.agente import ensaio_sdr as ensaio  # noqa: E402
from crm.agente.roteador_do_sdr import ler_configuracao_das_respostas  # noqa: E402
from crm.agente.sdr import AgenteFalhou  # noqa: E402
from crm.api.respostas_do_sdr import clientes_reais  # noqa: E402
from crm.agente.config import ler_configuracao  # noqa: E402
from crm.db.modelos import FichaDaBase  # noqa: E402
from crm.db.sessao import BancoNaoConfigurado, criar_engine, criar_fabrica_de_sessao  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("saida", type=Path, help="pasta onde gravar respostas.json e relatorio.md")
    args.add_argument("--modelo", help="modelo a usar; padrão: o do agente")
    args.add_argument("--paralelo", type=int, default=4, help="chamadas simultâneas (padrão 4)")
    args.add_argument("--roteador", action="store_true", help="pelo roteador de custo, como no WhatsApp")
    a = args.parse_args(argv)

    saida = a.saida.resolve()
    if saida == REPO or REPO in saida.parents:
        print("✗ Use uma pasta fora do repositório.", file=sys.stderr)
        return 2
    try:
        fabrica = criar_fabrica_de_sessao(criar_engine())
        configuracao.registrar_fabrica(fabrica)  # a tela de Integrações vale mais que o .env
    except BancoNaoConfigurado:
        fabrica = None
    config = ler_configuracao()
    if not a.roteador and not config.chave:
        print("✗ Falta a chave da Anthropic (Configurações › Integrações, ou ANTHROPIC_API_KEY no .env). "
              "Nada foi chamado.", file=sys.stderr)
        return 2
    if fabrica is None:
        print("✗ O banco não está configurado no .env. Nada foi chamado.", file=sys.stderr)
        return 2

    prompt = ensaio.ler_prompt((REPO / "sdr-ia-roteiro-spin.md").read_text())
    perguntas = ensaio.ler_perguntas((REPO / "sdr-ia-perguntas-teste.md").read_text())
    with fabrica() as sessao:
        fichas = list(sessao.scalars(sa.select(FichaDaBase).order_by(FichaDaBase.id)))
        sistema, codigos = ensaio.montar_contexto(prompt, fichas, date.today(), config.link_do_questionario)
    if a.roteador:
        try:
            clientes = clientes_reais(ler_configuracao_das_respostas())()
        except AgenteFalhou as falha:
            print(f"✗ {falha} Nada foi chamado.", file=sys.stderr)
            return 2
        print(f"Ensaio pelo roteador: {len(perguntas)} perguntas, {len(ensaio.CENARIOS)} conversas, "
              f"{len(codigos)} fichas, {clientes.modelo_leve} → {clientes.modelo_principal}…")
        resultado = ensaio.rodar_roteador(clientes, sistema, codigos, perguntas, config.link_do_questionario,
                                          paralelo=a.paralelo)
    else:
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
