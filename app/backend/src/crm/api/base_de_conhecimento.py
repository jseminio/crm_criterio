"""A base de conhecimento do SDR de IA — 03/10/2026, amostra aprovada por Eduardo no mesmo dia.

Recepciona as fichas que a SDR de IA vai consultar. As regras ficam em
`crm.domain.base_de_conhecimento`; aqui só a gravação:

- editar o conteúdo de uma ficha aprovada a devolve para "Em revisão" e apaga a aprovação;
- ficha arquivada não se edita: reabre (volta para "Rascunho");
- aprovar exige título, texto, fonte e dono, e o texto não pode falar de preço (422);
- quem aprova é quem entrou (com login) ou quem a tela informou (sem login), e o servidor
  carimba a data e a validade;
- a carga inicial só acrescenta: ficha cujo código já existe não entra de novo.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from datetime import date, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.api.acesso import quem_fez
from crm.db.base import agora
from crm.db.modelos import FichaDaBase
from crm.domain import base_de_conhecimento as regras
from crm.domain.base_de_conhecimento import BlocoDaBase, SituacaoDaFicha

__all__ = ["roteador_da_base"]

_CONTEUDO = ("titulo", "bloco", "servico", "texto", "nunca_dizer", "como_o_lead_pergunta", "fonte", "depende_de_hipotese")


class FichaResposta(BaseModel):
    id: int
    codigo: str | None
    titulo: str
    bloco: str
    servico: str | None
    texto: str | None
    nunca_dizer: str | None
    como_o_lead_pergunta: str | None
    fonte: str | None
    dono: str | None
    depende_de_hipotese: bool
    situacao: str
    validade: date | None
    aprovada_por: str | None
    aprovada_em: datetime | None
    atualizado_em: datetime
    vencida: bool
    vale_para_a_ia: bool
    problemas_para_aprovar: list[str]


class BlocoResposta(BaseModel):
    bloco: str
    total: int
    valem: int
    em_revisao: int
    rascunhos: int
    vencidas: int
    vai_para_a_ia: bool


class BaseResposta(BaseModel):
    blocos: list[BlocoResposta]
    situacoes: list[str]
    fichas: list[FichaResposta]


class FichaNova(BaseModel):
    titulo: str = Field(min_length=1, max_length=200)
    bloco: BlocoDaBase
    servico: str | None = Field(default=None, max_length=120)
    texto: str | None = None
    nunca_dizer: str | None = None
    como_o_lead_pergunta: str | None = None
    fonte: str | None = Field(default=None, max_length=300)
    dono: str | None = Field(default=None, max_length=120)
    depende_de_hipotese: bool = False


class FichaAlterada(BaseModel):
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    bloco: BlocoDaBase | None = None
    servico: str | None = Field(default=None, max_length=120)
    texto: str | None = None
    nunca_dizer: str | None = None
    como_o_lead_pergunta: str | None = None
    fonte: str | None = Field(default=None, max_length=300)
    dono: str | None = Field(default=None, max_length=120)
    depende_de_hipotese: bool | None = None


class Aprovacao(BaseModel):
    aprovador: str | None = Field(default=None, max_length=200)
    """Sem login, quem aprova (a tela pede). Com login, vale quem entrou."""


class CargaResposta(BaseModel):
    acrescentadas: int
    ja_existiam: int


def _limpo(valor):
    if isinstance(valor, str):
        valor = valor.strip()
        return valor or None
    return valor


def _resposta(f: FichaDaBase, hoje: date) -> FichaResposta:
    return FichaResposta(
        id=f.id, codigo=f.codigo, titulo=f.titulo, bloco=f.bloco.value, servico=f.servico,
        texto=f.texto, nunca_dizer=f.nunca_dizer, como_o_lead_pergunta=f.como_o_lead_pergunta,
        fonte=f.fonte, dono=f.dono, depende_de_hipotese=f.depende_de_hipotese,
        situacao=f.situacao.value, validade=f.validade, aprovada_por=f.aprovada_por,
        aprovada_em=f.aprovada_em, atualizado_em=f.atualizado_em,
        vencida=regras.vencida(f, hoje), vale_para_a_ia=regras.vale_para_a_ia(f, hoje),
        problemas_para_aprovar=regras.problemas_para_aprovar(f),
    )


def _desaprovar(f: FichaDaBase) -> None:
    f.situacao = SituacaoDaFicha.EM_REVISAO
    f.validade = None
    f.aprovada_por = None
    f.aprovada_em = None


def roteador_da_base(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(prefix="/api/sdr/base", tags=["sdr"])

    def _ficha(sessao: Session, ficha_id: int) -> FichaDaBase:
        f = sessao.get(FichaDaBase, ficha_id)
        if f is None:
            raise HTTPException(404, "ficha não encontrada")
        return f

    def _gravar(sessao: Session, f: FichaDaBase) -> FichaResposta:
        sessao.flush()
        sessao.commit()
        return _resposta(f, date.today())

    @r.get("", response_model=BaseResposta)
    def ler(sessao: Session = Depends(obter_sessao)) -> BaseResposta:
        hoje = date.today()
        fichas = sessao.scalars(sa.select(FichaDaBase).order_by(FichaDaBase.id)).all()
        ordem = {b: i for i, b in enumerate(BlocoDaBase)}
        fichas = sorted(fichas, key=lambda f: (ordem[f.bloco], f.id))
        return BaseResposta(
            blocos=[BlocoResposta(**vars(b)) for b in regras.resumir(fichas, hoje)],
            situacoes=[s.value for s in SituacaoDaFicha],
            fichas=[_resposta(f, hoje) for f in fichas],
        )

    @r.post("/fichas", response_model=FichaResposta, status_code=201)
    def criar(corpo: FichaNova, sessao: Session = Depends(obter_sessao)) -> FichaResposta:
        dados = {k: _limpo(v) for k, v in corpo.model_dump().items()}
        if not dados["titulo"]:
            raise HTTPException(422, "Falta o título")
        f = FichaDaBase(**dados, situacao=SituacaoDaFicha.RASCUNHO)
        sessao.add(f)
        return _gravar(sessao, f)

    @r.patch("/fichas/{ficha_id}", response_model=FichaResposta)
    def alterar(ficha_id: int, corpo: FichaAlterada, sessao: Session = Depends(obter_sessao)) -> FichaResposta:
        f = _ficha(sessao, ficha_id)
        if f.situacao is SituacaoDaFicha.ARQUIVADA:
            raise HTTPException(409, "a ficha está arquivada: reabra antes de editar")
        mudou_conteudo = False
        for campo, valor in corpo.model_dump(exclude_unset=True).items():
            valor = _limpo(valor)
            if campo == "titulo" and not valor:
                raise HTTPException(422, "Falta o título")
            if campo in ("bloco", "depende_de_hipotese") and valor is None:
                continue
            if getattr(f, campo) != valor:
                setattr(f, campo, valor)
                mudou_conteudo = mudou_conteudo or campo in _CONTEUDO
        if mudou_conteudo and f.situacao is SituacaoDaFicha.APROVADA:
            _desaprovar(f)
        return _gravar(sessao, f)

    @r.post("/fichas/{ficha_id}/revisao", response_model=FichaResposta)
    def enviar_para_revisao(ficha_id: int, sessao: Session = Depends(obter_sessao)) -> FichaResposta:
        f = _ficha(sessao, ficha_id)
        if f.situacao is not SituacaoDaFicha.RASCUNHO:
            raise HTTPException(409, f"só rascunho vai para revisão (a ficha está {f.situacao.value})")
        f.situacao = SituacaoDaFicha.EM_REVISAO
        return _gravar(sessao, f)

    @r.post("/fichas/{ficha_id}/aprovar", response_model=FichaResposta)
    def aprovar(ficha_id: int, corpo: Aprovacao, sessao: Session = Depends(obter_sessao)) -> FichaResposta:
        f = _ficha(sessao, ficha_id)
        if f.situacao is SituacaoDaFicha.APROVADA:
            raise HTTPException(409, "a ficha já está aprovada")
        problemas = regras.problemas_para_aprovar(f)
        if problemas:
            raise HTTPException(422, "; ".join(problemas))
        quem = _limpo(quem_fez(_limpo(corpo.aprovador)))
        if not quem:
            raise HTTPException(422, "Diga quem aprova")
        hoje = date.today()
        f.situacao = SituacaoDaFicha.APROVADA
        f.aprovada_por = quem
        f.aprovada_em = agora()
        f.validade = regras.validade_ao_aprovar(hoje, f.depende_de_hipotese)
        return _gravar(sessao, f)

    @r.post("/fichas/{ficha_id}/arquivar", response_model=FichaResposta)
    def arquivar(ficha_id: int, sessao: Session = Depends(obter_sessao)) -> FichaResposta:
        f = _ficha(sessao, ficha_id)
        if f.situacao is SituacaoDaFicha.ARQUIVADA:
            raise HTTPException(409, "a ficha já está arquivada")
        f.situacao = SituacaoDaFicha.ARQUIVADA
        f.validade = None
        return _gravar(sessao, f)

    @r.post("/fichas/{ficha_id}/reabrir", response_model=FichaResposta)
    def reabrir(ficha_id: int, sessao: Session = Depends(obter_sessao)) -> FichaResposta:
        f = _ficha(sessao, ficha_id)
        if f.situacao is not SituacaoDaFicha.ARQUIVADA:
            raise HTTPException(409, "só ficha arquivada se reabre")
        f.situacao = SituacaoDaFicha.RASCUNHO
        f.aprovada_por = None
        f.aprovada_em = None
        return _gravar(sessao, f)

    @r.post("/carga-inicial", response_model=CargaResposta)
    def carga_inicial(sessao: Session = Depends(obter_sessao)) -> CargaResposta:
        """Só acrescenta. A ficha cujo código já está no banco — mesmo editada ou arquivada — fica
        como está."""
        existentes = set(sessao.scalars(sa.select(FichaDaBase.codigo).where(FichaDaBase.codigo.is_not(None))))
        novas = [i for i in regras.FICHAS_INICIAIS if i.codigo not in existentes]
        for i in novas:
            sessao.add(FichaDaBase(
                codigo=i.codigo, titulo=i.titulo, bloco=i.bloco, servico=i.servico, texto=i.texto,
                nunca_dizer=i.nunca_dizer, como_o_lead_pergunta=i.como_o_lead_pergunta, fonte=i.fonte,
                dono=i.dono, depende_de_hipotese=i.depende_de_hipotese, situacao=i.situacao,
            ))
        sessao.flush()
        sessao.commit()
        return CargaResposta(acrescentadas=len(novas), ja_existiam=len(regras.FICHAS_INICIAIS) - len(novas))

    return r
