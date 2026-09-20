"""A identidade estável de uma proposta vinda da planilha.

Eduardo decidiu em 20/09/2026 rodar o CRM **em paralelo** com a planilha. A
carga passa a rodar mais de uma vez, e sem identidade estável a segunda rodada
duplicaria tudo.

Número de linha não serve: desloca quando alguém insere uma linha no meio.

**A chave adotada** é nome da oportunidade + data de colocação + serviço + tipo
de serviço, cada parte normalizada. Medida contra as 157 propostas de 2026:

| Chave | Distintas | Colisões |
|---|---|---|
| nome | 141 | 16 |
| nome + data | 146 | 11 |
| nome + data + serviço | 151 | 6 |
| **nome + data + serviço + tipo** | **156** | **1** |

As cinco colisões que o tipo de serviço desfaz são propostas legítimas: mesmo
cliente, mesma data, mesmo serviço, **valores diferentes**. São cenários
alternativos oferecidos ao cliente, e fundi-los apagaria a negociação.

A colisão que sobra é defeito da planilha, tratado por `detectar_duplicatas`.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from datetime import date
from typing import Iterable, Protocol

__all__ = ["chave_de_origem", "detectar_duplicatas", "Duplicata"]

SEPARADOR = "|"


class _TemIdentidade(Protocol):
    linha: int
    nome_oportunidade: str | None
    data_colocacao: date | None
    servico: str | None
    tipo_servico: str | None


def _parte(valor: str | date | None) -> str:
    """Normaliza um pedaço da chave: sem acento, sem caixa, sem sobra.

    Usa a mesma redução de `crm.domain.listas`, para que "Sogamax" e "SOGAMAX "
    sejam o mesmo registro na recarga. Data vira ISO; ausência vira vazio — e
    vazio é um valor legítimo, porque há propostas sem data de colocação.
    """
    if valor is None:
        return ""
    if isinstance(valor, date):
        return valor.isoformat()
    sem_acento = unicodedata.normalize("NFKD", str(valor))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.casefold().split())


def chave_de_origem(proposta: _TemIdentidade) -> str:
    """Monta a identidade da proposta na planilha."""
    return SEPARADOR.join(
        (
            _parte(proposta.nome_oportunidade),
            _parte(proposta.data_colocacao),
            _parte(proposta.servico),
            _parte(proposta.tipo_servico),
        )
    )


class Duplicata:
    """Duas ou mais linhas da planilha com a mesma identidade.

    Distingue os dois casos, porque o tratamento é oposto:

    - **idêntica**: todos os campos comparados batem. É linha repetida, defeito
      da planilha. Importar as duas infla contagem e valor do funil.
    - **divergente**: mesma identidade, campos diferentes. A chave não foi capaz
      de separar duas propostas que são de fato distintas — aí o defeito é da
      chave, não da planilha, e ninguém deve escolher por conta própria.
    """

    def __init__(self, chave: str, linhas: list[int], identicas: bool, campos: list[str]):
        self.chave = chave
        self.linhas = linhas
        self.identicas = identicas
        self.campos_divergentes = campos

    @property
    def texto(self) -> str:
        onde = " e ".join(str(n) for n in self.linhas)
        if self.identicas:
            return (
                f"linhas {onde} são idênticas em todos os campos — "
                f"linha repetida na planilha, importada uma só vez"
            )
        return (
            f"linhas {onde} têm a mesma identidade mas diferem em "
            f"{', '.join(self.campos_divergentes)} — conferir antes de importar"
        )

    def __repr__(self) -> str:
        return f"<Duplicata {self.linhas} identicas={self.identicas}>"


#: Campos comparados para decidir se duas linhas são a mesma proposta.
#:
#: `linha` fica de fora de propósito: é a posição na aba, não o conteúdo.
CAMPOS_COMPARADOS = (
    "nome_oportunidade",
    "data_colocacao",
    "servico",
    "tipo_servico",
    "linha_servico",
    "captador",
    "canal",
    "tipo_canal",
    "situacao",
    "temperatura",
    "data_aceite",
    "motivo_recusa",
    "motivo_recusa_original",
    "preco_mensal",
    "preco_anual",
    "valor_mensalizado",
)


def detectar_duplicatas(propostas: Iterable[_TemIdentidade]) -> list[Duplicata]:
    """Acha as propostas que disputam a mesma identidade.

    Devolve lista vazia quando a planilha está limpa. Não decide nada: só
    descreve, para que uma pessoa confirme.
    """
    por_chave: dict[str, list] = defaultdict(list)
    for proposta in propostas:
        por_chave[chave_de_origem(proposta)].append(proposta)

    duplicatas = []
    for chave, grupo in por_chave.items():
        if len(grupo) < 2:
            continue
        primeira = grupo[0]
        divergentes = sorted(
            campo
            for campo in CAMPOS_COMPARADOS
            if any(getattr(p, campo) != getattr(primeira, campo) for p in grupo[1:])
        )
        duplicatas.append(
            Duplicata(
                chave=chave,
                linhas=[p.linha for p in grupo],
                identicas=not divergentes,
                campos=divergentes,
            )
        )
    return sorted(duplicatas, key=lambda d: d.linhas[0])
