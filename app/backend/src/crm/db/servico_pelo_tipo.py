"""Corrige o serviço e preenche o tema das propostas "Consultoria" — 27/09/2026.

Aprovado por Eduardo: pela coluna "Tipo serviço" da planilha, 17 propostas
marcadas "Consultoria" são de outro serviço do catálogo (Legalização
Empresarial, Auditoria, FSCP, Perícia, DIRPF), e as demais ganham o tema.

- A troca de serviço entra em `campos_do_crm`, para a recarga da planilha
  não desfazer; a chave de origem não muda (mesmo padrão da conciliação com o
  kit do Bruno, 22/09/2026).
- O tema só é preenchido quando a proposta ainda não tem um: tema escolhido
  por uma pessoa nunca é sobrescrito.
- A linha acompanha o serviço. Todos os destinos são C2, como Consultoria.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Oportunidade
from crm.domain.servicos import CONSULTORIA_SERVICO, linha_do_servico, reclassificar_pelo_tipo

__all__ = ["Mudanca", "planejar", "aplicar", "resumir"]


@dataclass(frozen=True)
class Mudanca:
    oportunidade_id: int
    tipo: str | None
    servico_antes: str
    servico_depois: str
    tema_depois: str | None

    @property
    def troca_servico(self) -> bool:
        return self.servico_depois != self.servico_antes


def planejar(sessao: Session) -> list[Mudanca]:
    """O que mudaria, sem gravar nada."""
    mudancas = []
    consulta = sa.select(
        Oportunidade.id, Oportunidade.servico, Oportunidade.tipo_servico, Oportunidade.servico_tema
    ).order_by(Oportunidade.id)
    for id_, servico, tipo, tema in sessao.execute(consulta):
        destino = reclassificar_pelo_tipo(servico, tipo)
        if destino is None:
            continue
        novo_servico, novo_tema = destino
        if novo_servico != CONSULTORIA_SERVICO:
            mudancas.append(Mudanca(id_, tipo, servico, novo_servico, None))
        elif tema is None and novo_tema is not None:
            mudancas.append(Mudanca(id_, tipo, servico, servico, novo_tema))
    return mudancas


def aplicar(sessao: Session, mudancas: list[Mudanca]) -> None:
    for m in mudancas:
        oportunidade = sessao.get(Oportunidade, m.oportunidade_id)
        if m.troca_servico:
            oportunidade.servico = m.servico_depois
            oportunidade.servico_tema = None
            editados = {"servico"}
            linha = linha_do_servico(m.servico_depois)
            if linha is not None and linha is not oportunidade.linha_servico:
                oportunidade.linha_servico = linha
                editados.add("linha_servico")
            oportunidade.campos_do_crm = sorted(set(oportunidade.campos_do_crm or []) | editados)
        else:
            oportunidade.servico_tema = m.tema_depois
    sessao.flush()


def resumir(mudancas: list[Mudanca]) -> list[str]:
    """Uma linha por destino, com a contagem: primeiro as trocas de serviço, depois os temas."""
    trocas = Counter(m.servico_depois for m in mudancas if m.troca_servico)
    temas = Counter(m.tema_depois for m in mudancas if not m.troca_servico)
    linhas = [f"{n:>4}  Consultoria → {servico}" for servico, n in sorted(trocas.items())]
    linhas += [f"{n:>4}  Consultoria ganha o tema: {tema}" for tema, n in sorted(temas.items())]
    return linhas
