"""Sugere quais grupos parecem ser o mesmo cliente, para Eduardo confirmar.

**Só sugere. Nunca funde.** A carga (caminho 2, decisão de 20/09/2026) criou um grupo
por proposta, e a coluna de origem mistura cliente e serviço: "Sete Brasil (Leo
Fraga) - BPO Contábil" e "Sete Brasil (Leo Fraga) - Regularização do Bacen" são o
mesmo cliente. Quem decide e clica é uma pessoa — a fusão nunca é automática.

Dois níveis de confiança, escolhidos por serem os que os dados reais sustentam:

- **alta** — a *chave* do nome é a mesma. Chave = nome sem acento e sem caixa, sem o
  que vem entre parênteses e sem o que vem depois de " - ".
- **média** — a chave de um contém a do outro, e a menor tem **duas palavras ou mais**
  ("Andréa Curcio" dentro de "BPO Contábil Andréa Curcio"). Cada sugestão média é
  **um par** de nomes, nunca uma corrente: "joao silva" e "silva santos" estão ambos
  dentro de "joao silva santos", mas isso não diz nada um sobre o outro. Encadear as
  ligações juntaria clientes diferentes num bloco só — e um clique fundiria todos.

**Ficou de fora de propósito:** nome de uma palavra só dentro de outro maior
("Aeskins" e "Horas adicionais Aeskins"), e nomes só parecidos na escrita
("BRA" e "BRAP"). São falso positivo demais para virar sugestão.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Protocol

__all__ = ["chave_do_nome", "sugerir", "Sugestao"]

_PALAVRAS_VAZIAS = {"ltda", "sa", "s", "a", "me", "epp", "eireli", "de", "da", "do", "dos", "das", "e", "grupo"}


class _Grupo(Protocol):
    id: int
    nome: str
    quantas_oportunidades: int


@dataclass(frozen=True)
class Sugestao:
    confianca: str  # "alta" | "média"
    motivo: str
    ids: list[int]
    principal_id: int
    """O grupo com mais propostas (desempate: o mais antigo). É só o padrão da tela;
    quem confirma pode escolher outro."""


def chave_do_nome(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.split(r"\s[-–—/]\s|\s[-–—/]$", s)[0]
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(t for t in s.split() if t not in _PALAVRAS_VAZIAS)


def _sugestao(confianca: str, motivo: str, ids: list[int], por_id: dict[int, _Grupo]) -> Sugestao:
    principal = max(ids, key=lambda i: (por_id[i].quantas_oportunidades, -i))
    return Sugestao(confianca=confianca, motivo=motivo, ids=sorted(ids), principal_id=principal)


def sugerir(grupos: Iterable[_Grupo]) -> list[Sugestao]:
    por_id = {g.id: g for g in grupos}
    por_chave: dict[str, list[int]] = {}
    for gid, g in por_id.items():
        chave = chave_do_nome(g.nome)
        if chave:
            por_chave.setdefault(chave, []).append(gid)

    sugestoes: list[Sugestao] = []

    # alta: mesma chave
    for chave, ids in por_chave.items():
        if len(ids) >= 2:
            sugestoes.append(_sugestao("alta", f"Mesmo nome de cliente: “{chave}”.", ids, por_id))

    # média: um par em que uma chave contém a outra e a menor tem 2+ palavras.
    # Par, e não união: "a ⊂ c" e "b ⊂ c" não fazem de "a" e "b" o mesmo cliente.
    distintas = sorted(por_chave, key=lambda c: len(c.split()))
    for i, menor in enumerate(distintas):
        palavras = set(menor.split())
        if len(palavras) < 2:
            continue
        for maior in distintas[i + 1:]:
            if palavras < set(maior.split()):
                sugestoes.append(
                    _sugestao(
                        "média",
                        f"Um nome contém o outro: {menor} ⊂ {maior}.",
                        por_chave[menor] + por_chave[maior],
                        por_id,
                    )
                )

    sugestoes.sort(key=lambda s: (s.confianca != "alta", -len(s.ids), s.ids))
    return sugestoes
