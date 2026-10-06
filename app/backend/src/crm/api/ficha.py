"""Rotas da ficha da oportunidade e do "o que falta para a proposta" (E4, 02/10/2026). Regras em
`crm.proposta.ficha` e `crm.proposta.pendencias`. Amostra aprovada por Eduardo em 02/10/2026.

Sem login (E1), quem corrige a ficha ou mexe numa pendência se identifica pelo nome, entre os que
revisam e enviam as propostas (Configurações › Propostas)."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.acesso.auditoria import usuario_atual
from crm.db.base import agora
from crm.db.modelos import (
    ConfiguracaoDeProposta, Empresa, MatrizDeProposta, Oportunidade, PendenciaDaProposta, PessoaContato,
    Proposta, QuestionarioRecebido, VinculoDeContato,
)
from crm.domain.listas import TipoDeMatriz
from crm.proposta import ficha as regras_da_ficha
from crm.proposta import pendencias as regras_das_pendencias
from crm.proposta.rascunho import base_da_proposta, porte_da_oportunidade

__all__ = ["ItemPendente", "pendencias_de", "roteador_da_ficha"]

_REVISORES_PADRAO = ["Eduardo", "Karine"]


# ------------------------------------------------------------------ respostas

class CampoResposta(BaseModel):
    chave: str
    rotulo: str
    tipo: str
    opcoes: list[str]
    sub: bool
    valor: str | list[str] | None
    origem: str | None
    por: str | None
    em: datetime | None


class SecaoResposta(BaseModel):
    numero: int
    titulo: str
    no_escopo: bool
    conta_pendencia: bool
    respondidas: int
    total: int
    campos: list[CampoResposta]


class FichaResposta(BaseModel):
    questionario_em: datetime | None
    respondidas: int
    total: int
    revisores: list[str]
    secoes: list[SecaoResposta]


class Correcao(BaseModel):
    valor: str | list[str] | None = None
    por: str = Field(min_length=1, max_length=60)


class PendenciaResposta(BaseModel):
    chave: str
    descricao: str
    automatica: bool
    aberta: bool
    responsavel: str | None
    prazo: date | None
    dias_de_atraso: int
    feita_em: datetime | None
    feita_por: str | None


class PendenciasResposta(BaseModel):
    abertas: int
    atrasadas: int
    feitas: int
    revisores: list[str]
    itens: list[PendenciaResposta]


class NovaPendencia(BaseModel):
    descricao: str = Field(min_length=1, max_length=300)
    responsavel: str | None = Field(default=None, max_length=60)
    prazo: date | None = None
    por: str = Field(min_length=1, max_length=60)


class MudancaDePendencia(BaseModel):
    """Só o que veio no pedido muda: `responsavel` ou `prazo` em `null` apagam o valor."""

    responsavel: str | None = Field(default=None, max_length=60)
    prazo: date | None = None
    feita: bool | None = None
    por: str = Field(min_length=1, max_length=60)


# ------------------------------------------------------------------- serviço

def _revisores(sessao: Session) -> list[str]:
    c = sessao.scalars(sa.select(ConfiguracaoDeProposta).order_by(ConfiguracaoDeProposta.id).limit(1)).first()
    return list(c.revisores) if c and c.revisores else list(_REVISORES_PADRAO)


def _questionario(sessao: Session, o: Oportunidade) -> QuestionarioRecebido | None:
    return sessao.scalars(
        sa.select(QuestionarioRecebido).where(QuestionarioRecebido.oportunidade_id == o.id)
        .order_by(QuestionarioRecebido.recebido_em.desc(), QuestionarioRecebido.id.desc()).limit(1)
    ).first()


def _ficha(sessao: Session, o: Oportunidade) -> tuple[regras_da_ficha.Ficha, QuestionarioRecebido | None]:
    q = _questionario(sessao, o)
    return regras_da_ficha.montar(q.respostas if q else None, o.ficha, q.recebido_em if q else None), q


def _matriz_utilizavel(sessao: Session, tipo: TipoDeMatriz) -> bool:
    m = sessao.scalars(
        sa.select(MatrizDeProposta).where(MatrizDeProposta.tipo == tipo)
        .order_by(MatrizDeProposta.enviada_em.desc(), MatrizDeProposta.id.desc()).limit(1)
    ).first()
    return m is not None and not m.faltando and not m.desconhecidos


def _contato_com_email(sessao: Session, o: Oportunidade) -> bool:
    return sessao.scalar(
        sa.select(sa.func.count()).select_from(PessoaContato)
        .join(VinculoDeContato, VinculoDeContato.pessoa_id == PessoaContato.id)
        .join(Empresa, Empresa.id == VinculoDeContato.empresa_id)
        .where(Empresa.grupo_id == o.grupo_id, PessoaContato.email.is_not(None), PessoaContato.email != "")
    ) > 0


@dataclass(frozen=True)
class ItemPendente:
    chave: str
    descricao: str
    automatica: bool
    aberta: bool
    responsavel: str | None
    prazo: date | None
    feita_em: datetime | None
    feita_por: str | None

    def dias_de_atraso(self, hoje: date) -> int:
        return (hoje - self.prazo).days if self.aberta and self.prazo and self.prazo < hoje else 0


def pendencias_de(sessao: Session, o: Oportunidade) -> list[ItemPendente]:
    """Os automáticos (na ordem das regras) e depois os manuais (na ordem em que nasceram)."""
    f, _ = _ficha(sessao, o)
    _, porte_confirmado = porte_da_oportunidade(o)
    matriz = base_da_proposta(sessao, o).matriz
    automaticas = regras_das_pendencias.conferir(
        f,
        porte_confirmado=bool(porte_confirmado),
        tem_proposta=sessao.scalar(sa.select(sa.func.count()).where(Proposta.oportunidade_id == o.id)) > 0,
        matriz=matriz.value,
        matriz_utilizavel=_matriz_utilizavel(sessao, matriz),
        contato_com_email=_contato_com_email(sessao, o),
    )
    linhas = list(sessao.scalars(
        sa.select(PendenciaDaProposta).where(PendenciaDaProposta.oportunidade_id == o.id).order_by(PendenciaDaProposta.id)
    ))
    por_chave = {p.chave: p for p in linhas if p.chave}
    itens = []
    for a in automaticas:
        p = por_chave.get(a.chave)
        itens.append(ItemPendente(a.chave, a.descricao, True, a.aberta, p.responsavel if p else None,
                                  p.prazo if p else None, None, None))
    for p in linhas:
        if p.chave:
            continue
        itens.append(ItemPendente(f"manual-{p.id}", p.descricao or "", False, p.feita_em is None,
                                  p.responsavel, p.prazo, p.feita_em, p.feita_por))
    return itens


def _resposta_das_pendencias(sessao: Session, o: Oportunidade, hoje: date) -> PendenciasResposta:
    itens = pendencias_de(sessao, o)
    return PendenciasResposta(
        abertas=sum(1 for i in itens if i.aberta),
        atrasadas=sum(1 for i in itens if i.dias_de_atraso(hoje) > 0),
        feitas=sum(1 for i in itens if not i.aberta),
        revisores=_revisores(sessao),
        itens=[PendenciaResposta(**i.__dict__, dias_de_atraso=i.dias_de_atraso(hoje)) for i in itens],
    )


def _resposta_da_ficha(sessao: Session, o: Oportunidade) -> FichaResposta:
    f, q = _ficha(sessao, o)
    return FichaResposta(
        questionario_em=q.recebido_em if q else None,
        respondidas=f.respondidas, total=f.total, revisores=_revisores(sessao),
        secoes=[
            SecaoResposta(
                numero=s.numero, titulo=s.titulo, no_escopo=s.no_escopo, conta_pendencia=s.conta_pendencia,
                respondidas=s.respondidas, total=s.total,
                campos=[
                    CampoResposta(
                        chave=c.campo.chave, rotulo=c.campo.rotulo, tipo=c.campo.tipo, opcoes=list(c.campo.opcoes),
                        sub=c.campo.sub, valor=c.valor, origem=c.origem, por=c.por, em=c.em,
                    )
                    for c in s.campos
                ],
            )
            for s in f.secoes
        ],
    )


def _validar_valor(campo: regras_da_ficha.Campo, valor: str | list[str] | None) -> str | list[str] | None:
    """Devolve o valor limpo, no formato do questionário; recusa o que o formulário não aceitaria."""
    if valor is None or valor == "" or valor == []:
        return None
    if campo.tipo == "varias":
        if not isinstance(valor, list) or any(v not in campo.opcoes for v in valor):
            raise HTTPException(422, f"{campo.rotulo}: escolha entre {', '.join(campo.opcoes)}")
        return [o for o in campo.opcoes if o in valor]  # na ordem do formulário, sem repetir
    if not isinstance(valor, str):
        raise HTTPException(422, f"{campo.rotulo}: valor inválido")
    valor = valor.strip()
    if campo.tipo == "uma" and valor not in campo.opcoes:
        raise HTTPException(422, f"{campo.rotulo}: escolha entre {', '.join(campo.opcoes)}")
    if campo.tipo == "numero" and not re.fullmatch(r"\d{1,9}", valor):
        raise HTTPException(422, f"{campo.rotulo}: use um número inteiro, sem ponto nem vírgula")
    if campo.tipo == "data":
        try:
            date.fromisoformat(valor)
        except ValueError as falha:
            raise HTTPException(422, f"{campo.rotulo}: data inválida") from falha
    if len(valor) > 2000:
        raise HTTPException(422, f"{campo.rotulo}: texto longo demais (máximo de 2000 caracteres)")
    return valor or None


# --------------------------------------------------------------------- rotas

def roteador_da_ficha(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["proposta"])

    def _oportunidade(sessao: Session, oportunidade_id: int) -> Oportunidade:
        o = sessao.get(Oportunidade, oportunidade_id)
        if o is None:
            raise HTTPException(404, "oportunidade não encontrada")
        return o

    def _quem(sessao: Session, por: str) -> str:
        """Com login, quem fez é quem entrou; sem login, um dos que revisam as propostas."""
        entrou = usuario_atual.get()
        if entrou is not None:
            return entrou.nome or entrou.email
        revisores = _revisores(sessao)
        if por not in revisores:
            raise HTTPException(422, f"quem preenche é {', '.join(revisores)}")
        return por

    def _responsavel(sessao: Session, nome: str) -> str:
        revisores = _revisores(sessao)
        if nome not in revisores:
            raise HTTPException(422, f"o responsável é um de {', '.join(revisores)}")
        return nome

    @r.get("/api/oportunidades/{oportunidade_id}/ficha", response_model=FichaResposta)
    def ver_ficha(oportunidade_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> FichaResposta:
        return _resposta_da_ficha(sessao, _oportunidade(sessao, oportunidade_id))

    @r.put("/api/oportunidades/{oportunidade_id}/ficha/{chave}", response_model=FichaResposta)
    def corrigir(oportunidade_id: int, chave: str, corpo: Correcao, sessao: Session = Depends(obter_sessao, scope="function")) -> FichaResposta:
        """Grava a resposta como Entrevista, com quem e quando. A do questionário fica guardada."""
        o = _oportunidade(sessao, oportunidade_id)
        campo = regras_da_ficha.campo(chave)
        if campo is None:
            raise HTTPException(404, "pergunta não encontrada na ficha")
        por = _quem(sessao, corpo.por)
        valor = _validar_valor(campo, corpo.valor)
        o.ficha = {**(o.ficha or {}), chave: {"valor": valor, "por": por, "em": agora().isoformat()}}
        sessao.commit()
        return _resposta_da_ficha(sessao, o)

    @r.get("/api/oportunidades/{oportunidade_id}/pendencias", response_model=PendenciasResposta)
    def ver_pendencias(oportunidade_id: int, hoje: date | None = None, sessao: Session = Depends(obter_sessao, scope="function")) -> PendenciasResposta:
        """`hoje` existe para teste; sem ele vale a data do servidor."""
        return _resposta_das_pendencias(sessao, _oportunidade(sessao, oportunidade_id), hoje or date.today())

    @r.post("/api/oportunidades/{oportunidade_id}/pendencias", response_model=PendenciasResposta)
    def nova_pendencia(oportunidade_id: int, corpo: NovaPendencia, sessao: Session = Depends(obter_sessao, scope="function")) -> PendenciasResposta:
        o = _oportunidade(sessao, oportunidade_id)
        por = _quem(sessao, corpo.por)
        if corpo.responsavel is not None:
            _responsavel(sessao, corpo.responsavel)
        sessao.add(PendenciaDaProposta(
            oportunidade_id=o.id, descricao=corpo.descricao.strip(), responsavel=corpo.responsavel,
            prazo=corpo.prazo, criada_por=por,
        ))
        sessao.commit()
        return _resposta_das_pendencias(sessao, o, date.today())

    @r.patch("/api/oportunidades/{oportunidade_id}/pendencias/{chave}", response_model=PendenciasResposta)
    def mudar_pendencia(
        oportunidade_id: int, chave: str, corpo: MudancaDePendencia, sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> PendenciasResposta:
        o = _oportunidade(sessao, oportunidade_id)
        por = _quem(sessao, corpo.por)
        campos = corpo.model_fields_set
        if "responsavel" in campos and corpo.responsavel is not None:
            _responsavel(sessao, corpo.responsavel)
        if chave.startswith("manual-"):
            p = sessao.get(PendenciaDaProposta, int(chave[7:])) if chave[7:].isdigit() else None
            if p is None or p.oportunidade_id != o.id or p.chave is not None:
                raise HTTPException(404, "pendência não encontrada")
            if "feita" in campos and corpo.feita is not None:
                p.feita_em, p.feita_por = (agora(), por) if corpo.feita else (None, None)
        else:
            if chave not in {a.chave for a in pendencias_de(sessao, o) if a.automatica}:
                raise HTTPException(404, "pendência não encontrada")
            if "feita" in campos and corpo.feita is not None:
                raise HTTPException(422, "item automático fecha sozinho quando o dado chega")
            p = sessao.scalars(sa.select(PendenciaDaProposta).where(
                PendenciaDaProposta.oportunidade_id == o.id, PendenciaDaProposta.chave == chave)).first()
            if p is None:
                p = PendenciaDaProposta(oportunidade_id=o.id, chave=chave, criada_por=por)
                sessao.add(p)
        if "responsavel" in campos:
            p.responsavel = corpo.responsavel
        if "prazo" in campos:
            p.prazo = corpo.prazo
        sessao.commit()
        return _resposta_das_pendencias(sessao, o, date.today())

    return r
