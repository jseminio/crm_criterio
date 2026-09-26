"""Busca e lacunas da área de Contatos.

Duas regras que a tela e a planilha de lacunas compartilham:

- **Busca sem acento e sem caixa**: "acao" acha "Ação". O PostgreSQL não faz isso sem uma
  extensão, e a base é pequena, então a filtragem é aqui, em Python.
- **Lacuna** = o que falta para poder falar com o cliente e mandar correspondência. São os
  mesmos sete itens da planilha de lacunas: contato, e-mail, telefone, logradouro, município,
  UF e CEP. Uma empresa com vários contatos **não** tem lacuna de e-mail se *algum* contato
  tem e-mail.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Protocol

__all__ = ["LACUNAS", "normalizar", "casa", "lacunas_de"]

LACUNAS = ("Contato", "E-mail", "Telefone", "Logradouro", "Município", "UF", "CEP")


def normalizar(texto: str | None) -> str:
    """Minúsculas, sem acento, espaços colapsados."""
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def _digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def casa(busca: str, *campos: str | None) -> bool:
    """Todas as palavras da busca aparecem em algum dos campos (em qualquer ordem).

    Busca só de números (CNPJ, telefone) também compara sem pontuação: "20.040" acha
    "20040-020". Busca vazia casa com tudo.
    """
    alvo = normalizar(busca)
    if not alvo:
        return True
    texto = " ".join(normalizar(c) for c in campos if c)
    numeros = " ".join(_digitos(c) for c in campos if c)
    for palavra in alvo.split():
        if palavra in texto:
            continue
        d = _digitos(palavra)
        if d and len(d) == len(palavra.replace(".", "").replace("-", "").replace("/", "")) and d in numeros:
            continue
        return False
    return True


class _Pessoa(Protocol):
    nome: str
    email: str | None
    telefone: str | None


class _Endereco(Protocol):
    logradouro: str | None
    municipio: str | None
    uf: str | None
    cep: str | None


def lacunas_de(endereco: _Endereco | None, pessoas: Iterable[_Pessoa]) -> list[str]:
    """Quais dos sete itens faltam. Sem empresa, o endereço inteiro falta."""
    pessoas = list(pessoas)
    falta: list[str] = []
    if not any((p.nome or "").strip() for p in pessoas):
        falta.append("Contato")
    if not any((p.email or "").strip() for p in pessoas):
        falta.append("E-mail")
    if not any((p.telefone or "").strip() for p in pessoas):
        falta.append("Telefone")
    for rotulo, campo in (("Logradouro", "logradouro"), ("Município", "municipio"), ("UF", "uf"), ("CEP", "cep")):
        if endereco is None or not (getattr(endereco, campo) or "").strip():
            falta.append(rotulo)
    return falta
