"""O contrato de cada serviço: tipo, modelo e reajuste (aprovado por Eduardo em 13/10/2026).

O **tipo** (recorrente ou não) sai da linha do serviço no catálogo (`crm.domain.servicos`: C1 recorrente, C2 não
recorrente) e não se edita aqui: é decisão de 27/09/2026. Por serviço, a tela Configurações › Serviços e contratos
escolhe o **modelo de contrato** e o **reajuste**. Na conversão da oportunidade em contrato, o tipo do serviço é a
sugestão; a pessoa confirma ou troca, e o tipo fica gravado no contrato.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from crm.domain.listas import LinhaServico

__all__ = ["ModeloDeContrato", "ReajusteDoServico", "MODELOS", "ErroNoServico", "padrao", "validar"]


class ModeloDeContrato(Enum):
    RECORRENTE_PADRAO = "Recorrente padrão"
    NAO_RECORRENTE_V1_1 = "Não recorrente v1.1"


class ReajusteDoServico(Enum):
    IPCA_EM_JULHO = "IPCA em julho"
    CASO_A_CASO = "Caso a caso"
    SEM_REAJUSTE = "Sem reajuste"


@dataclass(frozen=True)
class Modelo:
    linha: LinhaServico
    situacao: str
    """Onde o arquivo do modelo está: sem ele, o CRM ainda não gera o contrato."""


MODELOS: dict[ModeloDeContrato, Modelo] = {
    ModeloDeContrato.RECORRENTE_PADRAO: Modelo(LinhaServico.C1, "aguardando arquivo"),
    ModeloDeContrato.NAO_RECORRENTE_V1_1: Modelo(LinhaServico.C2, "minuta v1.1 · falta a revisão do advogado"),
}

REAJUSTES: dict[LinhaServico, tuple[ReajusteDoServico, ...]] = {
    LinhaServico.C1: (ReajusteDoServico.IPCA_EM_JULHO, ReajusteDoServico.CASO_A_CASO, ReajusteDoServico.SEM_REAJUSTE),
    # Não recorrente nunca reajusta sozinho: com mais de 12 meses, a pessoa decide (13/10/2026).
    LinhaServico.C2: (ReajusteDoServico.CASO_A_CASO, ReajusteDoServico.SEM_REAJUSTE),
}


class ErroNoServico(ValueError):
    pass


def padrao(linha: LinhaServico) -> tuple[ModeloDeContrato, ReajusteDoServico]:
    if linha is LinhaServico.C1:
        return ModeloDeContrato.RECORRENTE_PADRAO, ReajusteDoServico.IPCA_EM_JULHO
    return ModeloDeContrato.NAO_RECORRENTE_V1_1, ReajusteDoServico.CASO_A_CASO


def validar(linha: LinhaServico, modelo: ModeloDeContrato, reajuste: ReajusteDoServico) -> None:
    if MODELOS[modelo].linha is not linha:
        raise ErroNoServico(f"o modelo “{modelo.value}” é de contrato {MODELOS[modelo].linha.descricao.lower()}")
    if reajuste not in REAJUSTES[linha]:
        raise ErroNoServico(f"serviço {linha.descricao.lower()} não aceita reajuste “{reajuste.value}”")
