"""Colocar uma conta na fila de abordagens — usado pela API e pelo script de carga.

Um lugar só para a regra: o grupo vem pelo id ou pelo nome (e nasce prospect
se não existir, como na conversão de lead), e a mesma conta não entra duas
vezes na fila do mesmo mês, a não ser que a anterior tenha sido descartada.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Abordagem, GrupoEconomico
from crm.domain.listas import CanalDeAbordagem, Origem, SituacaoAbordagem, SituacaoGrupo

__all__ = ["ContaNaoInformada", "GrupoNaoEncontrado", "JaNaFila", "enfileirar", "grupo_pelo_nome"]


class ContaNaoInformada(ValueError):
    pass


class GrupoNaoEncontrado(LookupError):
    pass


class JaNaFila(ValueError):
    pass


def grupo_pelo_nome(sessao: Session, nome: str) -> GrupoEconomico | None:
    """O grupo ativo com esse nome, sem diferença de maiúsculas. Grupo fundido
    em outro não conta: quem responde por ele é o que o absorveu."""
    return sessao.scalar(
        sa.select(GrupoEconomico)
        .where(
            sa.func.lower(GrupoEconomico.nome) == nome.strip().lower(),
            GrupoEconomico.fundido_em_id.is_(None),
        )
        .order_by(GrupoEconomico.id)
        .limit(1)
    )


def enfileirar(
    sessao: Session,
    *,
    mes: str,
    grupo_id: int | None = None,
    grupo_nome: str | None = None,
    quem_apresenta: str | None = None,
    canal: CanalDeAbordagem = CanalDeAbordagem.EMAIL,
    destinatario: str | None = None,
    contexto: str | None = None,
) -> Abordagem:
    if grupo_id is not None:
        grupo = sessao.get(GrupoEconomico, grupo_id)
        if grupo is None:
            raise GrupoNaoEncontrado("grupo não encontrado")
    elif grupo_nome and grupo_nome.strip():
        grupo = grupo_pelo_nome(sessao, grupo_nome)
        if grupo is None:
            grupo = GrupoEconomico(
                nome=grupo_nome.strip(), situacao=SituacaoGrupo.PROSPECT, origem=Origem.CRM
            )
            sessao.add(grupo)
            sessao.flush()
    else:
        raise ContaNaoInformada("informe o grupo ou o nome da conta")

    repetida = sessao.scalar(
        sa.select(Abordagem.id).where(
            Abordagem.grupo_id == grupo.id,
            Abordagem.mes == mes,
            Abordagem.situacao != SituacaoAbordagem.DESCARTADA,
        )
    )
    if repetida is not None:
        raise JaNaFila("esta conta já está na fila deste mês")

    abordagem = Abordagem(
        grupo_id=grupo.id,
        mes=mes,
        quem_apresenta=(quem_apresenta or "").strip() or None,
        canal=canal,
        destinatario=(destinatario or "").strip() or None,
        contexto=(contexto or "").strip() or None,
        situacao=SituacaoAbordagem.A_PREPARAR,
    )
    sessao.add(abordagem)
    sessao.flush()
    return abordagem
