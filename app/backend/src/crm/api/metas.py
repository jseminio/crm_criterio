"""Configurações › Metas (02/10/2026, aprovado por Eduardo): a meta e o alerta do MRR e da taxa de
conversão deixam de ser fixos no código. Quem altera é quem tem "Configurações: metas"; cada mudança
vai para o histórico de alterações."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.api.acesso import quem_fez
from crm.db.base import agora
from crm.db.modelos import MetaDeIndicador
from crm.domain.indicadores import ALERTA_DE_CONVERSAO, META_DE_CONVERSAO
from crm.domain.mrr import ALERTA_DE_MRR, META_DE_MRR

__all__ = ["PADROES", "metas_vigentes", "roteador_de_metas"]

PADROES: dict[str, tuple[Decimal, Decimal]] = {
    "mrr": (META_DE_MRR, ALERTA_DE_MRR),
    "conversao": (META_DE_CONVERSAO, ALERTA_DE_CONVERSAO),
}
"""O KPI oficial: vale enquanto ninguém mudou na tela."""


def metas_vigentes(sessao: Session) -> dict[str, tuple[Decimal, Decimal]]:
    """`{chave: (meta, alerta)}`, com o padrão do KPI oficial para o que não foi gravado."""
    gravadas = {m.chave: (m.meta, m.alerta) for m in sessao.query(MetaDeIndicador).all()}
    return {chave: gravadas.get(chave, padrao) for chave, padrao in PADROES.items()}


class MetaResposta(BaseModel):
    meta: Decimal
    alerta: Decimal
    alterado_por: str | None = None
    alterado_em: datetime | None = None


class MetasResposta(BaseModel):
    mrr: MetaResposta
    """Em reais por mês."""
    conversao: MetaResposta
    """Em % (aceitas ÷ decididas)."""


class MetaEdicao(BaseModel):
    meta: Decimal = Field(gt=0)
    alerta: Decimal = Field(gt=0)


class MetasEdicao(BaseModel):
    mrr: MetaEdicao | None = None
    conversao: MetaEdicao | None = None


def roteador_de_metas(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["metas"])

    def _resposta(sessao: Session) -> MetasResposta:
        vigentes = metas_vigentes(sessao)
        itens = {}
        for chave, (meta, alerta) in vigentes.items():
            linha = sessao.get(MetaDeIndicador, chave)
            itens[chave] = MetaResposta(
                meta=meta, alerta=alerta,
                alterado_por=linha.alterado_por if linha else None, alterado_em=linha.alterado_em if linha else None,
            )
        return MetasResposta(**itens)

    @r.get("/api/metas", response_model=MetasResposta)
    def ver(sessao: Session = Depends(obter_sessao, scope="function")) -> MetasResposta:
        return _resposta(sessao)

    @r.put("/api/metas", response_model=MetasResposta)
    def mudar(corpo: MetasEdicao, sessao: Session = Depends(obter_sessao, scope="function")) -> MetasResposta:
        """Só muda o indicador que veio. O alerta precisa ficar abaixo da meta; a conversão, até 100%."""
        for chave, nome in (("mrr", "MRR"), ("conversao", "taxa de conversão")):
            nova = getattr(corpo, chave)
            if nova is None:
                continue
            if nova.alerta >= nova.meta:
                raise HTTPException(422, f"{nome}: o alerta precisa ficar abaixo da meta")
            if chave == "conversao" and nova.meta > 100:
                raise HTTPException(422, "taxa de conversão: a meta vai até 100%")
            linha = sessao.get(MetaDeIndicador, chave)
            if linha is None:
                linha = MetaDeIndicador(chave=chave, meta=nova.meta, alerta=nova.alerta)
                sessao.add(linha)
            elif (linha.meta, linha.alerta) == (nova.meta, nova.alerta):
                continue
            linha.meta, linha.alerta = nova.meta, nova.alerta
            linha.alterado_por = (quem_fez("") or None)
            linha.alterado_em = agora()
        sessao.flush()
        return _resposta(sessao)

    return r
