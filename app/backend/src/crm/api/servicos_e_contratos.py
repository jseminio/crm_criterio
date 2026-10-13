"""Configurações › Serviços e contratos (aprovado por Eduardo em 13/10/2026). Regras em `crm.domain.contrato_do_servico`.

- `GET /api/servicos/contratos`: cada serviço do catálogo com o tipo, as parcelas, o modelo de contrato e o reajuste.
- `PUT /api/servicos/contratos`: grava o modelo e o reajuste escolhidos. Voltar ao padrão do tipo apaga a escolha.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.db.modelos import ContratoDoServico
from crm.domain import contrato_do_servico as regra
from crm.domain.listas import LinhaServico
from crm.domain.servicos import CATALOGO, servico_do_catalogo

__all__ = ["roteador_de_servicos_e_contratos", "contrato_do_servico"]


class ServicoNoContrato(BaseModel):
    servico: str
    linha: LinhaServico
    tipo: str
    """"Recorrente" ou "Não recorrente": sai da linha do serviço."""
    parcelas: int | None
    temas: int
    modelo: regra.ModeloDeContrato
    situacao_do_modelo: str
    reajuste: regra.ReajusteDoServico
    modelos_possiveis: list[regra.ModeloDeContrato]
    reajustes_possiveis: list[regra.ReajusteDoServico]
    padrao: bool
    """Segue o padrão do tipo (ninguém mudou)."""


class EscolhaDoServico(BaseModel):
    servico: str = Field(max_length=120)
    modelo: regra.ModeloDeContrato
    reajuste: regra.ReajusteDoServico


class Escolhas(BaseModel):
    itens: list[EscolhaDoServico] = Field(min_length=1)


def contrato_do_servico(sessao: Session, nome: str | None) -> tuple[regra.ModeloDeContrato, regra.ReajusteDoServico] | None:
    """O modelo e o reajuste do serviço (o escolhido na tela ou o padrão do tipo); `None` fora do catálogo."""
    servico = servico_do_catalogo(nome)
    if servico is None:
        return None
    escolha = sessao.get(ContratoDoServico, servico.nome)
    if escolha is None:
        return regra.padrao(servico.linha)
    return regra.ModeloDeContrato(escolha.modelo), regra.ReajusteDoServico(escolha.reajuste)


def _lista(sessao: Session) -> list[ServicoNoContrato]:
    escolhas = {e.servico: e for e in sessao.scalars(sa.select(ContratoDoServico))}
    linhas = []
    for s in CATALOGO:
        modelo, reajuste = regra.padrao(s.linha)
        escolha = escolhas.get(s.nome)
        if escolha is not None:
            modelo, reajuste = regra.ModeloDeContrato(escolha.modelo), regra.ReajusteDoServico(escolha.reajuste)
        linhas.append(ServicoNoContrato(
            servico=s.nome, linha=s.linha, tipo=s.linha.descricao, parcelas=s.meses_no_ano, temas=len(s.temas),
            modelo=modelo, situacao_do_modelo=regra.MODELOS[modelo].situacao, reajuste=reajuste,
            modelos_possiveis=[m for m, d in regra.MODELOS.items() if d.linha is s.linha],
            reajustes_possiveis=list(regra.REAJUSTES[s.linha]),
            padrao=(modelo, reajuste) == regra.padrao(s.linha),
        ))
    return linhas


def roteador_de_servicos_e_contratos(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["contratos"])

    @r.get("/api/servicos/contratos", response_model=list[ServicoNoContrato])
    def ver(sessao: Session = Depends(obter_sessao, scope="function")) -> list[ServicoNoContrato]:
        return _lista(sessao)

    @r.put("/api/servicos/contratos", response_model=list[ServicoNoContrato])
    def gravar(corpo: Escolhas, sessao: Session = Depends(obter_sessao, scope="function")) -> list[ServicoNoContrato]:
        for item in corpo.itens:
            servico = servico_do_catalogo(item.servico)
            if servico is None:
                raise HTTPException(422, f"“{item.servico}” não está no catálogo de serviços")
            try:
                regra.validar(servico.linha, item.modelo, item.reajuste)
            except regra.ErroNoServico as erro:
                raise HTTPException(422, f"{servico.nome}: {erro}") from erro
            atual = sessao.get(ContratoDoServico, servico.nome)
            if (item.modelo, item.reajuste) == regra.padrao(servico.linha):
                if atual is not None:
                    sessao.delete(atual)
            elif atual is None:
                sessao.add(ContratoDoServico(servico=servico.nome, modelo=item.modelo.value, reajuste=item.reajuste.value))
            else:
                atual.modelo, atual.reajuste = item.modelo.value, item.reajuste.value
        sessao.flush()
        return _lista(sessao)

    return r
