"""Concilia o kit de transferência que o Bruno passou em 22/09/2026 contra a
carteira já carregada, usando a mesma identidade da carga (nome + data de
colocação + serviço + tipo de serviço).

Eduardo pediu (22/09/2026) para complementar só os dados de 2026, vindos da
recuperação de e-mail/WhatsApp do Bruno enquanto foi o comercial exclusivo.
O diagnóstico prévio, feito à mão sobre as mesmas 19 propostas que não batem
pela chave completa, achou dois padrões:

- **Reclassificação**: mesma proposta (nome + data), só o serviço ou o tipo de
  serviço do kit corrige o que a planilha tinha. Não é dado novo — é a
  conciliação que o Bruno já pagou o preço de fazer. `chave_origem` **não**
  muda (ela é o que casa com a recarga semanal da planilha); só o campo
  corrigido entra em `campos_do_crm`, para a recarga não apagar de volta.
- **Genuinamente nova**: nome + data também não batem. Aqui o script não
  decide sozinho — só os nomes em `NOVAS_CONFIRMADAS` (explicitamente
  aprovados por Eduardo) são inseridos. As demais (Empresa XPTO, suspeita de
  nome-placeholder; CFO AaS - Restaurante Igor Dutra, que o próprio arquivo do
  Bruno marca "pesquisar") ficam de fora até confirmação.

Uso:
    ~/.venvs/criterio-crm/bin/python scripts/conciliar_kit_bruno.py <kit.csv> [--gravar]

Sem `--gravar`, mostra tudo e desfaz no fim — é o padrão de propósito.
"""

from __future__ import annotations

import csv
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from crm.carga.identidade import _parte, chave_de_origem  # noqa: E402
from crm.db.modelos import GrupoEconomico, Oportunidade  # noqa: E402
from crm.db.sessao import criar_engine, url_do_banco  # noqa: E402
from crm.domain.listas import Origem, Situacao, SituacaoGrupo  # noqa: E402

CENTAVO = Decimal("0.01")

#: Nomes do kit ("cliente") explicitamente aprovados para virar oportunidade
#: nova. "CFO AaS - Restaurante Igor Dutra" fica de fora por decisão de
#: Eduardo em 22/09/2026: o próprio arquivo do Bruno marca "pesquisar" — nem
#: ele tinha fechado essa.
NOVAS_CONFIRMADAS = {"CIH", "BPO Contábil Andréa Curcio", "Empresa XPTO"}

#: "Empresa XPTO" não era placeholder: Eduardo confirmou em 22/09/2026 que é
#: codinome para "Tailor Made (Roger)". Vira o nome real ao inserir — o kit
#: nunca guarda "Empresa XPTO" além deste ponto.
RENOMEAR_AO_INSERIR = {"Empresa XPTO": "Tailor Made (Roger)"}

#: status do kit → Situacao do CRM. Só para o relatório saber comparar; a
#: reclassificação nunca toca a situação de um registro que já existe.
MAPA_SITUACAO = {
    "Enviar proposta": Situacao.ENVIAR_PROPOSTA,
    "Em avaliação pelo cliente": Situacao.EM_AVALIACAO,
    "On hold": Situacao.ON_HOLD,
    "Aceita": Situacao.ACEITA,
    "Recusada": Situacao.RECUSADA,
    "Perdido": Situacao.PERDIDO,
    "Proposta enviada": Situacao.ENVIAR_PROPOSTA,
}


@dataclass
class LinhaKit:
    linha: int
    cliente: str
    data_colocacao: date | None
    servico: str | None
    tipo_servico: str | None
    status: str
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    valor_mensalizado: Decimal | None
    metodo_conciliacao: str
    confianca: str

    @property
    def nome_oportunidade(self) -> str:
        return self.cliente


def _data(valor: str) -> date | None:
    valor = valor.strip()
    if not valor:
        return None
    return datetime.strptime(valor, "%Y-%m-%d").date()


def _dinheiro(valor: str) -> Decimal | None:
    valor = valor.strip()
    if not valor:
        return None
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def ler_kit(caminho: str) -> list[LinhaKit]:
    linhas = []
    with open(caminho, newline="", encoding="utf-8") as arquivo:
        leitor = csv.DictReader(arquivo, delimiter=";")
        for i, bruta in enumerate(leitor, start=2):
            if bruta.get("ano") != "2026":
                continue
            linhas.append(
                LinhaKit(
                    linha=i,
                    cliente=bruta["cliente"].strip(),
                    data_colocacao=_data(bruta["data_colocacao"]),
                    servico=bruta.get("linha_servico", "").strip() or None,
                    tipo_servico=bruta.get("tipo_servico", "").strip() or None,
                    status=bruta.get("status", "").strip(),
                    preco_mensal=_dinheiro(bruta.get("preco_mensal", "")),
                    preco_anual=_dinheiro(bruta.get("preco_anual", "")),
                    valor_mensalizado=_dinheiro(bruta.get("valor_mensalizado", "")),
                    metodo_conciliacao=bruta.get("metodo_conciliacao", "").strip(),
                    confianca=bruta.get("confianca", "").strip(),
                )
            )
    return linhas


def _chave_solta(nome: str, data_colocacao: date | None) -> str:
    """nome + data, sem serviço/tipo — pega a mesma proposta reclassificada."""
    return f"{_parte(nome)}|{_parte(data_colocacao)}"


def principal(argumentos: list[str]) -> int:
    if not argumentos:
        print(__doc__)
        return 2

    caminho = argumentos[0]
    gravar = "--gravar" in argumentos

    print("=" * 70)
    print("LEITURA DO KIT")
    print("=" * 70)
    linhas_kit = ler_kit(caminho)
    print(f"{len(linhas_kit)} propostas de 2026 no kit.")

    engine = criar_engine(url_do_banco())
    with Session(engine, future=True) as sessao:
        existentes = sessao.scalars(sa.select(Oportunidade)).all()
        por_chave_completa = {o.chave_origem: o for o in existentes if o.chave_origem}
        por_chave_solta: dict[str, list[Oportunidade]] = {}
        for o in existentes:
            por_chave_solta.setdefault(_chave_solta(o.nome, o.data_colocacao), []).append(o)

        exatas = []
        reclassificar = []
        candidatas_novas = []

        for linha in linhas_kit:
            chave_completa = chave_de_origem(linha)
            if chave_completa in por_chave_completa:
                exatas.append(linha)
                continue

            # Nomes que o kit usa como codinome (ex. "Empresa XPTO") são
            # buscados pelo nome real já gravado, não pelo codinome — senão
            # uma segunda rodada do script nunca mais encontraria o registro
            # que a primeira já inseriu, e duplicaria.
            nome_para_casar = RENOMEAR_AO_INSERIR.get(
                linha.nome_oportunidade, linha.nome_oportunidade
            )
            grupo_solto = por_chave_solta.get(
                _chave_solta(nome_para_casar, linha.data_colocacao), []
            )
            if len(grupo_solto) == 1:
                existente = grupo_solto[0]
                mudou_servico = (existente.servico or None) != linha.servico
                mudou_tipo = (existente.tipo_servico or None) != linha.tipo_servico
                if mudou_servico or mudou_tipo:
                    reclassificar.append((linha, existente, mudou_servico, mudou_tipo))
                    continue
                # Já bate por nome real + data + serviço + tipo — só falta a
                # chave completa por causa do codinome. Nada a fazer.
                exatas.append(linha)
                continue

            candidatas_novas.append(linha)

        print(f"\nBatem pela chave completa (nada a fazer): {len(exatas)}")

        print(f"\n{'=' * 70}")
        print(f"RECLASSIFICAÇÃO — mesma proposta, serviço/tipo corrigido pelo Bruno: {len(reclassificar)}")
        print("=" * 70)
        for linha, existente, mudou_servico, mudou_tipo in reclassificar:
            print(f"\n· {existente.nome} ({existente.data_colocacao})  [id={existente.id}]")
            if mudou_servico:
                print(f"    servico:      {existente.servico!r:40} → {linha.servico!r}")
            if mudou_tipo:
                print(f"    tipo_servico: {existente.tipo_servico!r:40} → {linha.tipo_servico!r}")

        print(f"\n{'=' * 70}")
        print(f"CANDIDATAS A NOVA — nome+data também não batem: {len(candidatas_novas)}")
        print("=" * 70)
        for linha in candidatas_novas:
            aprovada = linha.cliente in NOVAS_CONFIRMADAS
            marca = "✓ aprovada por Eduardo — será inserida" if aprovada else "✗ fora do escopo — aguardando confirmação"
            print(f"\n· {linha.cliente} ({linha.data_colocacao}) — {marca}")
            print(f"    serviço: {linha.servico} / {linha.tipo_servico} · status: {linha.status}")
            print(f"    preço mensal: {linha.preco_mensal} · anual: {linha.preco_anual}")
            print(f"    confiança do Bruno: {linha.confianca} · método: {linha.metodo_conciliacao}")

        print(f"\n{'=' * 70}")
        print("GRAVAÇÃO" + ("" if gravar else "  (simulação — nada será mantido)"))
        print("=" * 70)

        corrigidas = 0
        for linha, existente, mudou_servico, mudou_tipo in reclassificar:
            editados = set(existente.campos_do_crm or [])
            if mudou_servico:
                existente.servico = linha.servico
                editados.add("servico")
            if mudou_tipo:
                existente.tipo_servico = linha.tipo_servico
                editados.add("tipo_servico")
            existente.campos_do_crm = sorted(editados)
            corrigidas += 1
        print(f"{corrigidas} oportunidades corrigidas (servico/tipo_servico), chave_origem preservada.")

        criadas = 0
        for linha in candidatas_novas:
            if linha.cliente not in NOVAS_CONFIRMADAS:
                continue
            nome_real = RENOMEAR_AO_INSERIR.get(linha.cliente, linha.cliente)
            grupo = sessao.scalar(
                sa.select(GrupoEconomico).where(
                    sa.func.lower(GrupoEconomico.nome) == nome_real.casefold(),
                    GrupoEconomico.fundido_em_id.is_(None),
                )
            )
            if grupo is None:
                grupo = GrupoEconomico(nome=nome_real, situacao=SituacaoGrupo.PROSPECT, origem=Origem.KIT_BRUNO_2026)
                sessao.add(grupo)
                sessao.flush()

            situacao = MAPA_SITUACAO.get(linha.status, Situacao.ENVIAR_PROPOSTA)
            codinome = (
                f" Codinome no kit: {linha.cliente!r}." if nome_real != linha.cliente else ""
            )
            sessao.add(
                Oportunidade(
                    grupo_id=grupo.id,
                    nome=nome_real,
                    servico=linha.servico,
                    tipo_servico=linha.tipo_servico,
                    situacao=situacao,
                    data_colocacao=linha.data_colocacao,
                    preco_mensal=linha.preco_mensal,
                    preco_anual=linha.preco_anual,
                    valor_mensalizado=linha.valor_mensalizado,
                    origem=Origem.KIT_BRUNO_2026,
                    observacao=(
                        f"Importado do kit de transferência do Bruno (22/09/2026).{codinome} "
                        f"Confiança dele: {linha.confianca}. Método: {linha.metodo_conciliacao}."
                    ),
                )
            )
            criadas += 1
        print(f"{criadas} oportunidades novas inseridas, com Origem.KIT_BRUNO_2026.")

        if gravar:
            sessao.commit()
            print("\n✓ GRAVADO.")
        else:
            sessao.rollback()
            print("\n↩ Desfeito. Rode de novo com --gravar para valer.")

    return 0


if __name__ == "__main__":
    raise SystemExit(principal(sys.argv[1:]))
