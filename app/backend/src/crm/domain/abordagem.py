"""Regras da abordagem de contas âncora — o agente SDR de 26/09/2026.

Lógica pura, sem banco nem rede. O agente prepara ficha e rascunho; **só uma
pessoa aprova**, e a aprovação só passa quando todas as conferências abaixo
estão ok. Elas existem porque o texto foi escrito por IA: são as travas que
o plano pediu (sem preço, sem "não contatar", só fato com fonte).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

from crm.domain.listas import CanalDeAbordagem, SituacaoAbordagem

__all__ = [
    "Conferencia",
    "MES",
    "conferir",
    "pode_aprovar",
    "situacao_exibida",
    "proximo_passo",
    "normalizar_destino",
    "link_whatsapp",
]

#: Mês de abordagem, `AAAA-MM`.
MES = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

#: O que conta como falar de preço. A IA não define preço (documento de
#: negócio, seção 16): o preço vem depois do diagnóstico, pela volumetria.
_PRECO = re.compile(
    r"R\$|\breais\b|\bpre[çc]o|\bhonor[áa]rio|\bdesconto|\bmensalidade|\d+\s*mil\b",
    re.IGNORECASE,
)
_COLCHETES = re.compile(r"\[[^\]]+\]")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True)
class Conferencia:
    """Uma regra conferida. `texto` diz a regra quando ok e o problema quando não."""

    regra: str
    ok: bool
    texto: str


def _digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def normalizar_destino(canal: CanalDeAbordagem, destino: str | None) -> str:
    """A forma comparável do destinatário: e-mail minúsculo, telefone só dígitos
    com o 55 do Brasil na frente."""
    if not destino:
        return ""
    if canal is CanalDeAbordagem.EMAIL:
        return destino.strip().casefold()
    digitos = _digitos(destino)
    if len(digitos) in (10, 11):
        digitos = "55" + digitos
    return digitos


def conferir(
    *,
    canal: CanalDeAbordagem,
    destinatario: str | None,
    assunto: str | None,
    mensagem: str | None,
    quem_apresenta: str | None,
    pesquisa: list[dict],
    bloqueados: set[str],
) -> list[Conferencia]:
    """Todas as conferências, na ordem em que a tela mostra.

    `bloqueados` são os destinos (já normalizados) de contatos marcados
    "não contatar" no CRM.
    """
    texto = f"{assunto or ''}\n{mensagem or ''}"
    destino = normalizar_destino(canal, destinatario)

    if canal is CanalDeAbordagem.EMAIL:
        destino_ok = bool(_EMAIL.match((destinatario or "").strip()))
        falta = "Falta o e-mail do contato"
    else:
        destino_ok = len(destino) in (12, 13)
        falta = "Falta o telefone do contato, com DDD"

    fontes_ok = all(
        str(item.get("fonte", "")).startswith(("http://", "https://")) for item in pesquisa
    )

    return [
        Conferencia(
            "mensagem",
            bool((mensagem or "").strip()),
            "Há mensagem para enviar" if (mensagem or "").strip() else "A mensagem está vazia",
        ),
        Conferencia(
            "sem_preco",
            not _PRECO.search(texto),
            "Sem preço na mensagem"
            if not _PRECO.search(texto)
            else "A mensagem fala de preço: o preço vem depois do diagnóstico",
        ),
        Conferencia(
            "nao_contatar",
            destino not in bloqueados,
            'Contato não está marcado como "não contatar"'
            if destino not in bloqueados
            else 'O contato está marcado como "não contatar" no CRM',
        ),
        Conferencia(
            "fontes",
            fontes_ok,
            "Só cita fatos do CRM ou com fonte"
            if fontes_ok
            else "Há fato da pesquisa sem fonte",
        ),
        Conferencia("destinatario", destino_ok, "Destinatário preenchido" if destino_ok else falta),
        Conferencia(
            "colchetes",
            not _COLCHETES.search(texto),
            "Sem campos entre colchetes para preencher"
            if not _COLCHETES.search(texto)
            else "Há campos entre colchetes para preencher, como [nome]",
        ),
        Conferencia(
            "quem_apresenta",
            bool((quem_apresenta or "").strip()),
            "Quem apresenta está definido"
            if (quem_apresenta or "").strip()
            else "Falta definir quem apresenta a conta",
        ),
    ]


def pode_aprovar(conferencias: list[Conferencia]) -> bool:
    return all(c.ok for c in conferencias)


def situacao_exibida(
    situacao: SituacaoAbordagem, quem_apresenta: str | None
) -> SituacaoAbordagem:
    """"Bloqueada" não é gravada: é uma abordagem a preparar sem quem a apresente."""
    if situacao is SituacaoAbordagem.A_PREPARAR and not (quem_apresenta or "").strip():
        return SituacaoAbordagem.BLOQUEADA
    return situacao


_PROXIMO_PASSO = {
    SituacaoAbordagem.A_PREPARAR: "Preparar a ficha",
    SituacaoAbordagem.BLOQUEADA: "Definir quem apresenta",
    SituacaoAbordagem.PESQUISANDO: "Aguardar a ficha",
    SituacaoAbordagem.AGUARDANDO_APROVACAO: "Revisar o rascunho",
    SituacaoAbordagem.APROVADA: "Enviar pelo WhatsApp e marcar como enviada",
    SituacaoAbordagem.ENVIADA: "Aguardar a resposta",
    SituacaoAbordagem.ERRO: "Ver o erro e tentar de novo",
    SituacaoAbordagem.DESCARTADA: "Nenhum",
}


def proximo_passo(situacao: SituacaoAbordagem, diagnostico_agendado: bool) -> str:
    if situacao is SituacaoAbordagem.ENVIADA and diagnostico_agendado:
        return "Fazer o diagnóstico"
    return _PROXIMO_PASSO[situacao]


def link_whatsapp(telefone: str | None, mensagem: str | None) -> str | None:
    """Link que abre a conversa com o texto pronto — o envio é da pessoa.

    Serve até a conta do WhatsApp Business estar verificada na Meta.
    """
    numero = normalizar_destino(CanalDeAbordagem.WHATSAPP, telefone)
    if len(numero) not in (12, 13):
        return None
    return f"https://wa.me/{numero}?text={quote(mensagem or '', safe='')}"
