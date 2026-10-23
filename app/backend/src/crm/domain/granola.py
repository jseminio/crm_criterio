"""Notas do Granola chegando sozinhas ao CRM (amostra aprovada por Eduardo em 23/10/2026).

A API do Granola não diz com que template a nota foi feita: o CRM separa pela **pasta** (decisão de 10/10/2026).
Nota da pasta das reuniões com o lead vai para a aba Granola da oportunidade; nota da pasta das Reuniões de
Resultado vai para a reunião do cliente no Funil do Sucesso. Em nenhum dos dois casos o CRM aplica nada sozinho:
a nota chega "a usar", e a pessoa usa (a IA sugere, a pessoa aplica) ou descarta.

Aqui ficam as listas e as regras puras, sem banco nem rede.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

__all__ = ["SituacaoDaNota", "TipoDaNota", "emails_de_fora", "falante", "participantes_em_texto"]


class TipoDaNota(Enum):
    LEAD = "Reunião com o lead"
    """Da pasta das reuniões com o lead (template [Potencial Cliente]). Do lead guarda-se **só o resumo**."""
    RESULTADO = "Reunião de Resultado"
    """Da pasta das Reuniões de Resultado: o resumo e a transcrição, para montar a ata."""


class SituacaoDaNota(Enum):
    A_USAR = "A usar"
    """Achou a oportunidade (ou o grupo) pelos participantes: espera alguém usar na aba certa."""
    PRECISA_DE_VOCE = "Precisa de você"
    """Nenhum participante casou, ou casou com mais de um: a pessoa escolhe onde a nota entra."""
    USADA = "Usada"
    DESCARTADA = "Descartada"
    """Fora do CRM: o resumo e a transcrição saem do banco; fica o ID, para a nota não voltar."""


def _dominio(email: str) -> str:
    return email.rsplit("@", 1)[-1] if "@" in email else ""


def emails_de_fora(emails: Iterable[str], dono: str | None, da_casa: Iterable[str] = ()) -> set[str]:
    """Os e-mails de quem não é da Critério: tira o dono da nota, quem tem o mesmo domínio dele e os usuários do CRM."""
    dono = (dono or "").strip().lower()
    casa = {e.strip().lower() for e in da_casa if e}
    dominios = {_dominio(dono), *(_dominio(e) for e in casa)} - {""}
    fora = set()
    for e in emails:
        e = (e or "").strip().lower()
        if "@" not in e or e == dono or e in casa or _dominio(e) in dominios:
            continue
        fora.add(e)
    return fora


def participantes_em_texto(pessoas: Iterable[tuple[str | None, str | None]], limite: int = 300) -> str | None:
    """"Ana Lima <ana@x.com.br>, carlos@y.com.br", cortado em `limite` (a coluna tem 300)."""
    partes = []
    for nome, email in pessoas:
        nome, email = (nome or "").strip(), (email or "").strip()
        if nome and email and nome.lower() != email.lower():
            partes.append(f"{nome} <{email}>")
        elif nome or email:
            partes.append(nome or email)
    texto = ", ".join(partes)
    if len(texto) > limite:
        texto = texto[: limite - 1].rstrip(", ") + "…"
    return texto or None


def falante(trecho: dict, dono: str | None) -> str:
    """Quem falou num trecho da transcrição: o nome, se o Granola souber; senão, o dono da nota (microfone) ou
    "Participante" (alto-falante)."""
    quem = trecho.get("speaker") or {}
    if (quem.get("name") or "").strip():
        return quem["name"].strip()
    if quem.get("attribution") == "me" or quem.get("source") == "microphone":
        return (dono or "").strip() or "Critério"
    return "Participante"
