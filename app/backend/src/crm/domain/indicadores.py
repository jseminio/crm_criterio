"""Indicadores do funil que a Etapa 1 consegue calcular sem decisão pendente.

**Este módulo calcula pouco de propósito.** Dos doze KPIs oficiais, só entram
aqui os que os dados de 2026 sustentam sem que ninguém tenha de escolher uma
definição. Cada um dos outros tem um motivo registrado para ficar de fora:

- **Taxa de conversão** — o anexo técnico diz *"não implementar sem a definição
  fixada"*. Sobre os mesmos dados, denominador de propostas decididas dá 38% e
  denominador de todas dá 26%: diagnósticos opostos. A escolha é de Eduardo.
- **Ticket médio** — não se sabe se é venda nova ou receita média por grupo.
- **Ciclo médio de vendas** — depende da data de aceite, que a planilha não
  registra, e a base do cálculo (a partir de quando?) não está documentada.
- **MRR** — o oficial é a receita contratada da *carteira inteira*. Aqui só há o
  preço mensal das propostas de 2026, que é outra grandeza. Dar o nome de MRR a
  esse número seria um valor certo com o rótulo errado.

Quando um indicador não é calculável, o resultado diz **por quê** e **o que
falta** — não devolve zero nem esconde o campo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Protocol

from crm.domain.listas import Situacao

__all__ = ["Indicadores", "Recorte", "PendenciaDoIndicador", "calcular"]

ZERO = Decimal("0.00")


class _Oportunidade(Protocol):
    situacao: Situacao
    preco_mensal: Decimal | None
    preco_anual: Decimal | None
    data_aceite: date | None


@dataclass(frozen=True)
class Recorte:
    """Um conjunto de oportunidades somado."""

    quantas: int
    valor_mensal: Decimal
    valor_anual: Decimal
    sem_preco_mensal: int
    """Quantas do conjunto **não têm** preço mensal.

    Consultoria de valor único não tem mensalidade, e a planilha de 2026 deixa o
    campo vazio de propósito. Sem este número, o total mensal parece cobrir o
    conjunto inteiro quando cobre só parte dele.
    """

    @property
    def com_preco_mensal(self) -> int:
        return self.quantas - self.sem_preco_mensal


@dataclass(frozen=True)
class PendenciaDoIndicador:
    """Um indicador que existe no desenho mas ainda não pode ser calculado."""

    calculavel: bool
    motivo: str
    o_que_falta: str


@dataclass(frozen=True)
class Indicadores:
    em_aberto: Recorte
    aceitas: Recorte
    aceitas_com_data_de_aceite: int
    ciclo_medio: PendenciaDoIndicador
    taxa_de_conversao: PendenciaDoIndicador


def _somar(oportunidades: list[_Oportunidade]) -> Recorte:
    return Recorte(
        quantas=len(oportunidades),
        valor_mensal=sum((o.preco_mensal or ZERO for o in oportunidades), ZERO),
        valor_anual=sum((o.preco_anual or ZERO for o in oportunidades), ZERO),
        sem_preco_mensal=sum(1 for o in oportunidades if o.preco_mensal is None),
    )


def calcular(oportunidades: Iterable[_Oportunidade]) -> Indicadores:
    """Soma o funil e diz o que ainda não dá para medir.

    **Em aberto** é tudo que ainda não foi decidido — o inverso de
    `Situacao.decidida`. Reaproveita o conceito do domínio em vez de listar as
    situações à mão: se a lista de situações mudar, esta conta muda junto.
    """
    todas = list(oportunidades)
    em_aberto = [o for o in todas if not o.situacao.decidida]
    aceitas = [o for o in todas if o.situacao.ganha]
    com_data = sum(1 for o in aceitas if o.data_aceite is not None)

    if not aceitas:
        ciclo = PendenciaDoIndicador(
            calculavel=False,
            motivo="Ainda não há proposta aceita neste recorte.",
            o_que_falta="Uma proposta aceita, com a data do aceite.",
        )
    else:
        ciclo = PendenciaDoIndicador(
            calculavel=False,
            # Mesmo com todas as datas, a base do cálculo — a partir de quando
            # se conta — não está documentada. Melhor dizer do que supor.
            motivo=(
                f"{com_data} de {len(aceitas)} propostas aceitas têm data de aceite."
                if com_data < len(aceitas)
                else "A base de cálculo do ciclo (contar a partir de quando) "
                "não está registrada."
            ),
            o_que_falta=(
                "A data de aceite de cada proposta aceita, e a confirmação de "
                "a partir de quando o ciclo é contado."
                if com_data < len(aceitas)
                else "Confirmar, na planilha oficial de KPIs, a partir de quando o "
                "ciclo é contado."
            ),
        )

    conversao = PendenciaDoIndicador(
        calculavel=False,
        motivo=(
            "O denominador da taxa de conversão não está definido: só as propostas "
            "decididas, ou todas as trabalhadas. Os dois dão diagnósticos opostos."
        ),
        o_que_falta="A definição do denominador, por Eduardo.",
    )

    return Indicadores(
        em_aberto=_somar(em_aberto),
        aceitas=_somar(aceitas),
        aceitas_com_data_de_aceite=com_data,
        ciclo_medio=ciclo,
        taxa_de_conversao=conversao,
    )
