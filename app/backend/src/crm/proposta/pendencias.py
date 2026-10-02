"""O que falta para a proposta: as regras que o CRM confere sozinho (E4, 02/10/2026).

Cada regra tem uma `chave` fixa: é por ela que o responsável e o prazo dados a um item automático
ficam guardados (`PendenciaDaProposta`). O item fecha quando o dado chega, sem ninguém marcar.
A lista avisa e **não bloqueia** a geração da proposta (decisão de Eduardo em 02/10/2026).
"""

from __future__ import annotations

from dataclasses import dataclass

from crm.proposta.ficha import Ficha

__all__ = ["Automatica", "conferir"]


@dataclass(frozen=True)
class Automatica:
    chave: str
    descricao: str
    aberta: bool


def conferir(
    ficha: Ficha,
    *,
    porte_confirmado: bool,
    tem_proposta: bool,
    matriz: str,
    matriz_utilizavel: bool,
    contato_com_email: bool,
) -> list[Automatica]:
    """Todas as regras, abertas e fechadas: a tela mostra as fechadas riscadas, como feitas."""
    itens: list[Automatica] = []
    volumes = next(s for s in ficha.secoes if s.numero == 3)
    faltam = volumes.total - volumes.respondidas
    itens.append(Automatica(
        "volumes",
        f"Volumetria: {faltam} de {volumes.total} volumes sem resposta" if faltam
        else f"Volumetria: os {volumes.total} volumes respondidos",
        faltam > 0,
    ))
    for s in ficha.secoes:
        if s.numero == 3 or not s.conta_pendencia:
            continue
        vazia = s.total > 0 and s.respondidas == 0
        itens.append(Automatica(
            f"secao-{s.numero}",
            f"{s.titulo}: seção inteira sem resposta" if vazia else f"{s.titulo}: com resposta",
            vazia,
        ))
    itens.append(Automatica("porte", "Porte confirmado" if porte_confirmado else "Porte não confirmado", not porte_confirmado))
    itens.append(Automatica(
        "matriz",
        f"Matriz {matriz} subida, com os marcadores" if matriz_utilizavel
        else f"Matriz {matriz} não subida ou com marcador faltando (Configurações › Propostas)",
        not matriz_utilizavel,
    ))
    itens.append(Automatica(
        "contato-email",
        "Contato com e-mail" if contato_com_email else "Nenhum contato com e-mail nas empresas do grupo",
        not contato_com_email,
    ))
    itens.append(Automatica("proposta", "Proposta gerada" if tem_proposta else "Proposta ainda não gerada", not tem_proposta))
    return itens
