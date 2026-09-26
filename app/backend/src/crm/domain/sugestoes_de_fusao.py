"""Sugere quais grupos parecem ser o mesmo cliente, para Eduardo confirmar.

**Só sugere. Nunca funde.** A carga (caminho 2, decisão de 20/09/2026) criou um grupo
por proposta, e a coluna de origem mistura cliente e serviço: "Sete Brasil (Leo
Fraga) - BPO Contábil" e "Sete Brasil (Leo Fraga) - Regularização do Bacen" são o
mesmo cliente. Quem decide e clica é uma pessoa — a fusão nunca é automática.

Dois níveis de confiança, escolhidos por serem os que os dados reais sustentam:

- **alta** — a *chave* do nome é a mesma. Chave = nome sem acento e sem caixa, sem o
  que vem entre parênteses e sem o que vem depois de " - ".
- **média** — a chave de um contém a do outro, e a menor tem **duas palavras ou mais**
  ("Andréa Curcio" dentro de "BPO Contábil Andréa Curcio").

**Ficou de fora de propósito:** nome de uma palavra só dentro de outro maior
("Aeskins" e "Horas adicionais Aeskins"), e nomes só parecidos na escrita
("BRA" e "BRAP"). São falso positivo demais para virar sugestão.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
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


@dataclass
class _Uniao:
    pai: dict[int, int] = field(default_factory=dict)

    def achar(self, x: int) -> int:
        self.pai.setdefault(x, x)
        while self.pai[x] != x:
            self.pai[x] = self.pai[self.pai[x]]
            x = self.pai[x]
        return x

    def unir(self, a: int, b: int) -> None:
        self.pai[self.achar(a)] = self.achar(b)


def sugerir(grupos: Iterable[_Grupo]) -> list[Sugestao]:
    lista = [g for g in grupos]
    chaves = {g.id: chave_do_nome(g.nome) for g in lista}
    por_id = {g.id: g for g in lista}
    uniao = _Uniao()
    ligacoes_medias: set[int] = set()

    # alta: mesma chave
    por_chave: dict[str, list[int]] = {}
    for gid, chave in chaves.items():
        if chave:
            por_chave.setdefault(chave, []).append(gid)
    for ids in por_chave.values():
        for outro in ids[1:]:
            uniao.unir(ids[0], outro)

    # média: uma chave contém a outra e a menor tem 2+ palavras
    distintas = sorted(por_chave, key=lambda c: len(c.split()))
    for i, menor in enumerate(distintas):
        palavras = set(menor.split())
        if len(palavras) < 2:
            continue
        for maior in distintas[i + 1:]:
            if palavras < set(maior.split()):
                uniao.unir(por_chave[menor][0], por_chave[maior][0])
                ligacoes_medias.update(por_chave[menor] + por_chave[maior])

    blocos: dict[int, list[int]] = {}
    for gid in chaves:
        if chaves[gid]:
            blocos.setdefault(uniao.achar(gid), []).append(gid)

    sugestoes: list[Sugestao] = []
    for ids in blocos.values():
        if len(ids) < 2:
            continue
        mesmas = len({chaves[i] for i in ids}) == 1
        principal = max(ids, key=lambda i: (por_id[i].quantas_oportunidades, -i))
        sugestoes.append(
            Sugestao(
                confianca="alta" if mesmas else "média",
                motivo=(
                    f"Mesmo nome de cliente: “{chaves[ids[0]]}”."
                    if mesmas
                    else "Um nome contém o outro: " + " ⊂ ".join(sorted({chaves[i] for i in ids}, key=len)) + "."
                ),
                ids=sorted(ids),
                principal_id=principal,
            )
        )
    sugestoes.sort(key=lambda s: (s.confianca != "alta", -len(s.ids), s.ids[0]))
    return sugestoes
