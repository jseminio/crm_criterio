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

__all__ = ["chave_do_nome", "sugerir", "sugerir_clientes", "Sugestao"]

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


# ----------------------------------------------------------- prospect que já é cliente

#: Palavras que aparecem em muitos nomes e não identificam ninguém. Não é uma lista fechada:
#: a exigência de a palavra apontar para **um único** cliente já filtra a maior parte do ruído.
_GENERICAS = {
    "ltda", "sa", "grupo", "group", "brasil", "brasileira", "comercio", "servicos", "industria", "ind", "com",
    "participacoes", "empreendimentos", "imobiliarios", "consultoria", "assessoria", "gestao", "holding",
    "investimentos", "capital", "empresa", "empresas", "sociedade", "bpo", "contabil", "contabilidade",
    "financeiro", "fiscal", "tributaria", "tributario", "transacao", "retomada", "pelo", "pela", "horas",
    "adicionais", "pro", "bono", "filial", "proposta", "contrato", "formalizar", "retificacao", "migracao",
    "encerramento", "constituicao", "abertura", "calculo", "calculos", "distribuicao", "dividendos", "ata",
    "reajuste", "volume", "passado", "individual", "indicacao", "revisao", "sao", "santa", "santo", "dos", "das",
    "nossa", "novo", "nova", "faltam", "posto", "casa", "saude", "tecnologia", "plataforma", "digital",
}


class _GrupoComEmpresas(Protocol):
    id: int
    nome: str
    quantas_oportunidades: int
    empresas: list[str]
    """Razões sociais das empresas do grupo. Vazio para prospect sem empresa."""


def _palavras(*textos: str) -> set[str]:
    juntos = " ".join(t for t in textos if t)
    s = unicodedata.normalize("NFKD", juntos).encode("ascii", "ignore").decode().lower()
    return {t for t in re.findall(r"[a-z0-9]{3,}", s) if t not in _GENERICAS and not t.isdigit()}


def sugerir_clientes(
    prospects: Iterable[_GrupoComEmpresas], clientes: Iterable[_GrupoComEmpresas]
) -> list[Sugestao]:
    """Prospects que provavelmente já são um cliente da carteira, pelo nome das empresas.

    A carga da carteira usa o nome do grupo econômico e a razão social das empresas, e as
    propostas de 2026 usam o nome que o comercial digitou ("ASM retomada pelo Antonio - 3AW"
    para o cliente "Grupo 3AW"). A busca por nome do grupo não vê isso.

    Regra: a **palavra em comum** (sem acento, 3+ letras, fora de uma lista de genéricas) precisa
    apontar para **exatamente um cliente**. "Gestão" aparece em vários e não conta; "3aw" aparece
    em um só e conta. **Cada sugestão é um par** (cliente, prospect), com o cliente como principal:
    nada de corrente que junte clientes diferentes num clique só.
    """
    clientes = list(clientes)
    palavras_do_cliente = {c.id: _palavras(c.nome, *c.empresas) for c in clientes}
    dono: dict[str, set[int]] = {}
    for cid, ps in palavras_do_cliente.items():
        for p in ps:
            dono.setdefault(p, set()).add(cid)
    por_id = {c.id: c for c in clientes}

    sugestoes: list[Sugestao] = []
    for pr in prospects:
        achou: dict[int, list[str]] = {}
        for p in _palavras(pr.nome, *pr.empresas):
            donos = dono.get(p, set())
            if len(donos) == 1:
                achou.setdefault(next(iter(donos)), []).append(p)
        if len(achou) != 1:
            continue  # nenhuma, ou a mesma prospect aponta para clientes diferentes: ambíguo
        cid, comuns = next(iter(achou.items()))
        cliente = por_id[cid]
        no_nome = _palavras(cliente.nome)
        onde = [
            f"“{w}” (no nome do grupo)" if w in no_nome
            else f"“{w}” (na empresa {next((r for r in cliente.empresas if w in _palavras(r)), '?')})"
            for w in sorted(comuns)
        ]
        sugestoes.append(
            Sugestao(
                confianca="média",
                motivo=f"Já é cliente? Em comum com {cliente.nome}: " + "; ".join(onde) + ".",
                ids=sorted([cid, pr.id]),
                principal_id=cid,
            )
        )
    sugestoes.sort(key=lambda x: (x.principal_id, x.ids))
    return sugestoes
