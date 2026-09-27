"""Mudanças de situação do lead — as mesmas para a pessoa e para o SDR de IA.

A tela (editar o lead) e o registro de conversa (encerrar como qualificado ou
fora do perfil) passam por aqui, para a regra existir uma vez só.
"""

from __future__ import annotations

from crm.db.base import agora
from crm.db.modelos import Lead
from crm.domain.listas import MotivoDeDescarte, SituacaoLead
from crm.domain.porte import Porte

__all__ = ["RegraDoLead", "validar_porte", "qualificar", "descartar", "reabrir", "marcar_nao_contatar"]

_PORTES = {p.value for p in Porte}


class RegraDoLead(Exception):
    """A mudança pedida fere uma regra. `status` é o código HTTP que a rota devolve."""

    def __init__(self, mensagem: str, status: int = 422):
        super().__init__(mensagem)
        self.status = status


def validar_porte(porte: str) -> str:
    if porte not in _PORTES:
        raise RegraDoLead(f"porte desconhecido: {porte!r}. Use um de: {', '.join(p.value for p in Porte)}")
    return porte


def marcar_nao_contatar(lead: Lead) -> None:
    if not lead.nao_contatar:
        lead.nao_contatar = True
        lead.nao_contatar_em = agora()


def qualificar(lead: Lead, porte_estimado: str | None = None) -> None:
    """Qualificado quer dizer "cabe no perfil", e o porte é parte do perfil."""
    porte = porte_estimado or lead.porte_estimado
    if not porte:
        raise RegraDoLead("para qualificar o lead, informe o porte estimado")
    lead.porte_estimado = validar_porte(porte)
    lead.situacao = SituacaoLead.QUALIFICADO
    lead.qualificado_em = lead.qualificado_em or agora()
    lead.descartado_em = None
    lead.motivo_descarte = None


def descartar(lead: Lead, motivo: MotivoDeDescarte | None = None) -> None:
    """Descartar exige o motivo: é ele que diz se o problema é a IA, o anúncio
    ou a lista. "Pediu para não ser contatado" também marca "não contatar"."""
    motivo = motivo or lead.motivo_descarte
    if motivo is None:
        raise RegraDoLead("para descartar o lead, informe o motivo")
    lead.situacao = SituacaoLead.DESCARTADO
    lead.motivo_descarte = motivo
    lead.descartado_em = lead.descartado_em or agora()
    lead.qualificado_em = None
    if motivo is MotivoDeDescarte.NAO_CONTATAR:
        marcar_nao_contatar(lead)


def reabrir(lead: Lead, situacao: SituacaoLead) -> None:
    """Volta para "Novo" ou "Em contato": a qualificação e o descarte de antes
    deixam de valer. O pedido de não contatar **não** se desfaz aqui."""
    lead.situacao = situacao
    lead.qualificado_em = None
    lead.descartado_em = None
    lead.motivo_descarte = None
