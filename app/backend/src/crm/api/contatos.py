"""API da área de Contatos: pessoas e empresas de clientes e de prospects, segregados.

- **Clientes** = grupos com situação Cliente; a unidade é a **empresa** (CNPJ).
- **Prospects** = grupos ainda não clientes; a unidade é o grupo (ou a empresa, se já tiver).
- Busca por **empresa** (razão social, fantasia, CNPJ, nome do grupo) ou por **pessoa** (nome, cargo,
  e-mail, telefone), sem depender de acento nem de caixa.
- Contato pode estar ligado à **empresa** ou só ao **grupo**; o de grupo aparece em todas as
  empresas dele e é marcado como "do grupo".
- `nao_contatar` é respeitado pela área de campanhas: aqui só é exibido e editável.
"""

from __future__ import annotations

import re
from typing import Callable, Iterator, Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from crm.db.base import agora
from crm.db.modelos import Contrato, Empresa, GrupoEconomico, Oportunidade, PessoaContato
from crm.domain.contatos import casa, lacunas_de
from crm.domain.listas import PapelContato, SituacaoContrato, SituacaoGrupo

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
Tipo = Literal["cliente", "prospect"]


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pessoa(Base):
    id: int
    nome: str
    cargo: str | None = None
    email: str | None = None
    telefone: str | None = None
    papel: PapelContato | None = None
    observacao: str | None = None
    nao_contatar: bool = False
    empresa_id: int | None = None
    grupo_id: int | None = None
    do_grupo: bool = False
    """Ligada só ao grupo, não a esta empresa."""


class Endereco(Base):
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None


class Entidade(Base):
    tipo: Tipo
    grupo_id: int
    grupo_nome: str
    empresa_id: int | None = None
    razao_social: str | None = None
    nome_fantasia: str | None = None
    cnpj: str | None = None
    endereco: Endereco = Endereco()
    mensalidade: str | None = None
    """Só cliente: preço mensal do contrato em vigor."""
    recorrente: bool = False
    """Cliente com contrato recorrente em vigor. Cliente sem ele é **não recorrente** (por exemplo,
    consultoria pontual): decisão de Eduardo, 26/09/2026. Sempre falso para prospect."""
    propostas: int = 0
    """Só prospect: quantas propostas o grupo tem."""
    contatos: list[Pessoa] = []
    lacunas: list[str] = []


class PessoaComOrigem(Pessoa):
    tipo: Tipo
    grupo_nome: str
    razao_social: str | None = None


class Pagina(BaseModel):
    total: int
    itens: list


class PessoaNova(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    cargo: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=30)
    papel: PapelContato | None = None
    observacao: str | None = None
    nao_contatar: bool = False
    empresa_id: int | None = None
    grupo_id: int | None = None


class PessoaEdicao(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    cargo: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=30)
    papel: PapelContato | None = None
    observacao: str | None = None
    nao_contatar: bool | None = None


class EmpresaEdicao(BaseModel):
    razao_social: str | None = Field(default=None, min_length=1, max_length=200)
    nome_fantasia: str | None = Field(default=None, max_length=200)
    cnpj: str | None = None
    logradouro: str | None = Field(default=None, max_length=200)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=100)
    bairro: str | None = Field(default=None, max_length=100)
    municipio: str | None = Field(default=None, max_length=100)
    uf: str | None = Field(default=None, max_length=2)
    cep: str | None = None


class EmpresaNova(BaseModel):
    razao_social: str | None = Field(default=None, max_length=200)
    cnpj: str | None = None


# ------------------------------------------------------------------ validação

def _digitos(v: str | None) -> str | None:
    if v is None:
        return None
    d = re.sub(r"\D", "", v)
    return d or None


def _validar_email(v: str | None) -> str | None:
    if v is None or not v.strip():
        return None
    v = v.strip().lower()
    if not _EMAIL.match(v):
        raise HTTPException(422, f"e-mail inválido: {v!r}")
    return v


def _limpar(v: str | None) -> str | None:
    if v is None:
        return None
    v = " ".join(v.split())
    return v or None


def _cnpj_ok(cnpj: str) -> bool:
    from crm.carga.lacunas_contato import cnpj_valido

    return cnpj_valido(cnpj)


# ------------------------------------------------------------------- consultas

def roteador(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(prefix="/api/contatos", tags=["contatos"])

    def _mensalidades(sessao: Session) -> dict[int, sa.Numeric]:
        linhas = sessao.execute(
            sa.select(Contrato.empresa_id, sa.func.sum(Contrato.preco_mensal))
            .where(Contrato.empresa_id.is_not(None),
                   Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
            .group_by(Contrato.empresa_id)
        ).all()
        return {e: v for e, v in linhas}

    def _pessoa(p: PessoaContato, empresa_id: int | None = None) -> Pessoa:
        out = Pessoa.model_validate(p)
        out.do_grupo = empresa_id is not None and p.empresa_id is None
        return out

    def _entidades(sessao: Session, tipo: Tipo) -> list[Entidade]:
        situacao = SituacaoGrupo.CLIENTE if tipo == "cliente" else SituacaoGrupo.PROSPECT
        grupos = list(sessao.scalars(
            sa.select(GrupoEconomico).where(GrupoEconomico.situacao == situacao, GrupoEconomico.fundido_em_id.is_(None))
            .order_by(GrupoEconomico.nome)
        ))
        ids = [g.id for g in grupos]
        if not ids:
            return []
        empresas: dict[int, list[Empresa]] = {}
        for e in sessao.scalars(sa.select(Empresa).where(Empresa.grupo_id.in_(ids)).order_by(Empresa.razao_social)):
            empresas.setdefault(e.grupo_id, []).append(e)
        pessoas = list(sessao.scalars(sa.select(PessoaContato).order_by(PessoaContato.nome)))
        por_empresa: dict[int, list[PessoaContato]] = {}
        por_grupo: dict[int, list[PessoaContato]] = {}
        for p in pessoas:
            if p.empresa_id is not None:
                por_empresa.setdefault(p.empresa_id, []).append(p)
            elif p.grupo_id is not None:
                por_grupo.setdefault(p.grupo_id, []).append(p)
        propostas = dict(sessao.execute(
            sa.select(Oportunidade.grupo_id, sa.func.count()).where(Oportunidade.grupo_id.in_(ids)).group_by(Oportunidade.grupo_id)
        ).all())
        mensal = _mensalidades(sessao)

        saida: list[Entidade] = []
        for g in grupos:
            do_grupo = por_grupo.get(g.id, [])
            emps = empresas.get(g.id, [])
            if not emps:
                # Cliente sem empresa cadastrada = cliente **não recorrente** (a carteira sempre cria a
                # empresa; a consultoria pontual não). Aparece pelo grupo, como o prospect.
                ps = [_pessoa(p, None) for p in do_grupo]
                saida.append(Entidade(tipo=tipo, grupo_id=g.id, grupo_nome=g.nome, propostas=propostas.get(g.id, 0),
                                      contatos=ps, lacunas=lacunas_de(None, ps)))
                continue
            for e in emps:
                ps = [_pessoa(p, e.id) for p in por_empresa.get(e.id, [])] + [_pessoa(p, e.id) for p in do_grupo]
                v = mensal.get(e.id)
                saida.append(Entidade(
                    tipo=tipo, grupo_id=g.id, grupo_nome=g.nome, empresa_id=e.id, razao_social=e.razao_social,
                    nome_fantasia=e.nome_fantasia, cnpj=e.cnpj, endereco=Endereco.model_validate(e),
                    mensalidade=str(v) if v is not None else None, recorrente=v is not None and tipo == "cliente",
                    propostas=propostas.get(g.id, 0),
                    contatos=ps, lacunas=lacunas_de(e, ps),
                ))
        return saida

    @r.get("/empresas", response_model=Pagina)
    def por_empresa(
        tipo: Tipo,
        busca: str = "",
        so_com_lacunas: bool = False,
        limite: int = Query(default=50, ge=1, le=500),
        salto: int = Query(default=0, ge=0),
        sessao: Session = Depends(obter_sessao),
    ) -> dict:
        """Empresas (cliente) ou grupos/empresas (prospect), com os contatos e as lacunas."""
        itens = [
            e for e in _entidades(sessao, tipo)
            if casa(busca, e.razao_social, e.nome_fantasia, e.cnpj, e.grupo_nome)
            and (not so_com_lacunas or e.lacunas)
        ]
        return {"total": len(itens), "itens": itens[salto:salto + limite]}

    @r.get("/pessoas", response_model=Pagina)
    def por_pessoa(
        tipo: Tipo,
        busca: str = "",
        limite: int = Query(default=50, ge=1, le=500),
        salto: int = Query(default=0, ge=0),
        sessao: Session = Depends(obter_sessao),
    ) -> dict:
        """Pessoas de contato, de clientes ou de prospects, com a empresa/grupo delas."""
        situacao = SituacaoGrupo.CLIENTE if tipo == "cliente" else SituacaoGrupo.PROSPECT
        # a pessoa pertence ao grupo direto ou pela empresa
        linhas = sessao.execute(
            sa.select(PessoaContato, GrupoEconomico, Empresa)
            .outerjoin(Empresa, PessoaContato.empresa_id == Empresa.id)
            .join(GrupoEconomico, GrupoEconomico.id == sa.func.coalesce(PessoaContato.grupo_id, Empresa.grupo_id))
            .where(GrupoEconomico.situacao == situacao, GrupoEconomico.fundido_em_id.is_(None))
            .order_by(PessoaContato.nome)
        ).all()
        itens = []
        for p, g, e in linhas:
            if not casa(busca, p.nome, p.cargo, p.email, p.telefone):
                continue
            base = Pessoa.model_validate(p).model_dump()
            base["grupo_id"] = g.id  # o grupo dela, ligada direto ou pela empresa
            itens.append(PessoaComOrigem(**base, tipo=tipo, grupo_nome=g.nome, razao_social=e.razao_social if e else None))
        return {"total": len(itens), "itens": itens[salto:salto + limite]}

    # ----------------------------------------------------------------- pessoas
    def _aplicar_pessoa(p: PessoaContato, dados: dict) -> None:
        for campo, valor in dados.items():
            if campo == "email":
                valor = _validar_email(valor)
            elif campo in ("nome", "cargo", "telefone", "observacao"):
                valor = _limpar(valor)
                if campo == "nome" and valor is None:
                    raise HTTPException(422, "o nome não pode ficar vazio")
            setattr(p, campo, valor)

    @r.post("/pessoas", response_model=Pessoa, status_code=201)
    def criar_pessoa(corpo: PessoaNova, sessao: Session = Depends(obter_sessao)) -> Pessoa:
        if (corpo.empresa_id is None) == (corpo.grupo_id is None):
            raise HTTPException(422, "informe a empresa OU o grupo do contato")
        if corpo.empresa_id is not None and sessao.get(Empresa, corpo.empresa_id) is None:
            raise HTTPException(404, "empresa não encontrada")
        if corpo.grupo_id is not None and sessao.get(GrupoEconomico, corpo.grupo_id) is None:
            raise HTTPException(404, "grupo não encontrado")
        p = PessoaContato(nome="x", empresa_id=corpo.empresa_id, grupo_id=corpo.grupo_id)
        dados = corpo.model_dump(exclude={"empresa_id", "grupo_id"})
        _aplicar_pessoa(p, dados)
        if p.nao_contatar:
            p.nao_contatar_em = agora()
        sessao.add(p)
        sessao.flush()
        return Pessoa.model_validate(p)

    @r.patch("/pessoas/{pessoa_id}", response_model=Pessoa)
    def editar_pessoa(pessoa_id: int, corpo: PessoaEdicao, sessao: Session = Depends(obter_sessao)) -> Pessoa:
        p = sessao.get(PessoaContato, pessoa_id)
        if p is None:
            raise HTTPException(404, "contato não encontrado")
        dados = corpo.model_dump(exclude_unset=True)
        antes = p.nao_contatar
        _aplicar_pessoa(p, dados)
        if "nao_contatar" in dados and p.nao_contatar != antes:
            p.nao_contatar_em = agora() if p.nao_contatar else None
        sessao.flush()
        return Pessoa.model_validate(p)

    return r


def roteador_de_empresas(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    """Endereço e dados cadastrais da empresa (fora do prefixo /contatos)."""
    r = APIRouter(tags=["contatos"])

    @r.patch("/api/empresas/{empresa_id}", response_model=Endereco)
    def editar_empresa(empresa_id: int, corpo: EmpresaEdicao, sessao: Session = Depends(obter_sessao)) -> Endereco:
        e = sessao.get(Empresa, empresa_id)
        if e is None:
            raise HTTPException(404, "empresa não encontrada")
        for campo, valor in corpo.model_dump(exclude_unset=True).items():
            if campo == "cnpj":
                valor = _digitos(valor)
                if valor is not None:
                    if not _cnpj_ok(valor):
                        raise HTTPException(422, "CNPJ inválido")
                    dono = sessao.scalars(sa.select(Empresa).where(Empresa.cnpj == valor, Empresa.id != e.id)).first()
                    if dono is not None:
                        raise HTTPException(409, "este CNPJ já está cadastrado em outra empresa")
            elif campo == "cep":
                valor = _digitos(valor)
                if valor is not None and len(valor) != 8:
                    raise HTTPException(422, "o CEP precisa ter 8 dígitos")
            elif campo == "uf":
                valor = (valor or "").strip().upper() or None
                if valor is not None and valor not in UFS:
                    raise HTTPException(422, "UF inválida")
            else:
                valor = _limpar(valor)
                if campo == "razao_social" and valor is None:
                    raise HTTPException(422, "a razão social não pode ficar vazia")
            setattr(e, campo, valor)
        sessao.flush()
        return Endereco.model_validate(e)

    @r.post("/api/grupos/{grupo_id}/empresas", status_code=201)
    def criar_empresa(grupo_id: int, corpo: EmpresaNova, sessao: Session = Depends(obter_sessao)) -> dict:
        """Cria a empresa de um grupo (o prospect ainda não tem), para guardar o endereço."""
        g = sessao.get(GrupoEconomico, grupo_id)
        if g is None:
            raise HTTPException(404, "grupo não encontrado")
        cnpj = _digitos(corpo.cnpj)
        if cnpj is not None:
            if not _cnpj_ok(cnpj):
                raise HTTPException(422, "CNPJ inválido")
            if sessao.scalars(sa.select(Empresa).where(Empresa.cnpj == cnpj)).first() is not None:
                raise HTTPException(409, "este CNPJ já está cadastrado")
        e = Empresa(grupo_id=g.id, razao_social=_limpar(corpo.razao_social) or g.nome, cnpj=cnpj)
        sessao.add(e)
        sessao.flush()
        return {"id": e.id, "razao_social": e.razao_social, "cnpj": e.cnpj}

    return r
