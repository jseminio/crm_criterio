"""Copia para a tela Configurações › Integrações o que está nas variáveis de ambiente (07/10/2026).

Pedido de Eduardo: tudo que estava no painel do servidor aparece preenchido na tela, e daí em diante
vale a tela. Só copia o que a tela ainda não tem; segredo vai cifrado. As variáveis ficam no painel,
sem uso — ninguém precisa apagá-las.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crm.configuracao import copiar_do_ambiente

QUEM = "atualizador (copiado do servidor)"


def executar(sessao: Session) -> str:
    copiadas = copiar_do_ambiente(sessao, QUEM)
    return f"{len(copiadas)} campo(s) copiado(s) para a tela" + (f": {', '.join(copiadas)}" if copiadas else "")
