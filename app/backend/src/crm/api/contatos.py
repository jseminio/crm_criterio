"""API da área de Contatos: pessoas e empresas de clientes e de prospects, segregados.

- **Clientes** = grupos com situação Cliente; a unidade é a **empresa** (CNPJ).
- **Prospects** = grupos ainda não clientes; a unidade é o grupo (ou a empresa, se já tiver).
- Busca por **empresa** (razão social, fantasia, CNPJ, nome do grupo) ou por **pessoa** (nome, cargo,
  e-mail, telefone), sem depender de acento nem de caixa.
- Contato é ligado **só a empresas** (`VinculoDeContato`), uma ou várias, ou ainda a nenhuma — nunca
  ao grupo, porque as empresas de uma pessoa nem sempre são do mesmo grupo (Karine, 01/10/2026). O
  grupo é informado na **empresa**. Pessoa sem empresa aparece em Prospects, como "Sem empresa".
  Cada empresa pode ter vários contatos principais. Pedido de Karine em 30/09/2026.
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
from crm.db.modelos import Contrato, Empresa, GrupoEconomico, Oportunidade, PessoaContato, VinculoDeContato
from crm.domain.contatos import casa, lacunas_de
from crm.domain.listas import Origem, PapelContato, SituacaoContrato, SituacaoGrupo

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UFS = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
Tipo = Literal["cliente", "prospect"]


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EmpresaDaPessoa(BaseModel):
    """Uma empresa em que a pessoa está, e se é contato principal nela."""

    empresa_id: int
    razao_social: str
    grupo_id: int
    grupo_nome: str
    principal: bool = False


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
    """Grupo da empresa desta linha — informação, não ligação da pessoa."""
    principal: bool = False
    """Contato principal desta empresa (vale para o vínculo, não para a pessoa)."""
    empresas: list[EmpresaDaPessoa] = []
    """Todas as empresas em que a pessoa está."""


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
    tem_contrato: bool = False
    """A empresa tem contrato (em qualquer situação): não pode ser excluída."""
    contatos: list[Pessoa] = []
    lacunas: list[str] = []


class PessoaComOrigem(Pessoa):
    tipo: Tipo
    grupo_nome: str | None = None
    """Nulo quando a pessoa ainda não está em empresa nem grupo."""
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
    """Opcional: a pessoa pode nascer sem empresa e ser vinculada depois."""
    principal: bool = False
    """Só com `empresa_id`: já nasce como contato principal da empresa."""


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
    nome_do_grupo: str | None = Field(default=None, max_length=200)
    """Grupo (o cliente) da empresa, informado por nome: reaproveita o que existir ou nasce um
    prospect novo. Empresa com contrato não troca de grupo."""


class EmpresaNova(BaseModel):
    razao_social: str | None = Field(default=None, max_length=200)
    cnpj: str | None = None


class ContatoParaVincular(BaseModel):
    pessoa_id: int
    principal: bool = False


class EmpresaCompleta(EmpresaEdicao):
    """A empresa nascendo em Contatos > Nova empresa, já com os contatos.

    O grupo (o cliente) é reaproveitado pelo nome; se não houver, nasce um
    prospect novo — mesmo padrão da Nova oportunidade.
    """

    razao_social: str = Field(min_length=1, max_length=200)
    contatos: list[ContatoParaVincular] = []


class MudancaDeVinculo(BaseModel):
    principal: bool


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

    def _pessoa(p: PessoaContato, empresa_id: int | None = None, *, principal: bool = False) -> Pessoa:
        out = Pessoa.model_validate(p)
        out.empresa_id = empresa_id
        out.principal = principal
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
        por_empresa: dict[int, list[tuple[PessoaContato, bool]]] = {}
        for v, p in sessao.execute(
            sa.select(VinculoDeContato, PessoaContato)
            .join(PessoaContato, PessoaContato.id == VinculoDeContato.pessoa_id)
            .order_by(PessoaContato.nome)
        ).all():
            por_empresa.setdefault(v.empresa_id, []).append((p, v.principal))
        propostas = dict(sessao.execute(
            sa.select(Oportunidade.grupo_id, sa.func.count()).where(Oportunidade.grupo_id.in_(ids)).group_by(Oportunidade.grupo_id)
        ).all())
        mensal = _mensalidades(sessao)
        com_contrato = set(sessao.scalars(sa.select(Contrato.empresa_id).where(Contrato.empresa_id.is_not(None)).distinct()))

        saida: list[Entidade] = []
        for g in grupos:
            emps = empresas.get(g.id, [])
            if not emps:
                # Cliente sem empresa cadastrada = cliente **não recorrente** (a carteira sempre cria a
                # empresa; a consultoria pontual não). Aparece pelo grupo, como o prospect.
                saida.append(Entidade(tipo=tipo, grupo_id=g.id, grupo_nome=g.nome, propostas=propostas.get(g.id, 0),
                                      contatos=[], lacunas=lacunas_de(None, [])))
                continue
            for e in emps:
                ps = [_pessoa(p, e.id, principal=pr) for p, pr in por_empresa.get(e.id, [])]
                v = mensal.get(e.id)
                saida.append(Entidade(
                    tipo=tipo, grupo_id=g.id, grupo_nome=g.nome, empresa_id=e.id, razao_social=e.razao_social,
                    nome_fantasia=e.nome_fantasia, cnpj=e.cnpj, endereco=Endereco.model_validate(e),
                    mensalidade=str(v) if v is not None else None, recorrente=v is not None and tipo == "cliente",
                    propostas=propostas.get(g.id, 0), tem_contrato=e.id in com_contrato,
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
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> dict:
        """Empresas (cliente) ou grupos/empresas (prospect), com os contatos e as lacunas."""
        itens = [
            e for e in _entidades(sessao, tipo)
            if casa(busca, e.razao_social, e.nome_fantasia, e.cnpj, e.grupo_nome)
            and (not so_com_lacunas or e.lacunas)
        ]
        return {"total": len(itens), "itens": itens[salto:salto + limite]}

    def _empresas_por_pessoa(sessao: Session) -> dict[int, list[EmpresaDaPessoa]]:
        saida: dict[int, list[EmpresaDaPessoa]] = {}
        for v, e, g in sessao.execute(
            sa.select(VinculoDeContato, Empresa, GrupoEconomico)
            .join(Empresa, Empresa.id == VinculoDeContato.empresa_id)
            .join(GrupoEconomico, GrupoEconomico.id == Empresa.grupo_id)
            .order_by(Empresa.razao_social)
        ).all():
            saida.setdefault(v.pessoa_id, []).append(EmpresaDaPessoa(
                empresa_id=e.id, razao_social=e.razao_social, grupo_id=g.id, grupo_nome=g.nome, principal=v.principal,
            ))
        return saida

    @r.get("/pessoas", response_model=Pagina)
    def por_pessoa(
        tipo: Tipo,
        busca: str = "",
        limite: int = Query(default=50, ge=1, le=500),
        salto: int = Query(default=0, ge=0),
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> dict:
        """Pessoas de contato, de clientes ou de prospects, com as empresas delas.

        A pessoa aparece na aba das empresas em que está; a que ainda não está em nenhuma aparece em
        Prospects, como "Sem empresa".
        """
        situacao = SituacaoGrupo.CLIENTE if tipo == "cliente" else SituacaoGrupo.PROSPECT
        grupos = {g.id: g for g in sessao.scalars(sa.select(GrupoEconomico).where(GrupoEconomico.fundido_em_id.is_(None)))}
        empresas = _empresas_por_pessoa(sessao)
        itens = []
        for p in sessao.scalars(sa.select(PessoaContato).order_by(PessoaContato.nome)):
            if not casa(busca, p.nome, p.cargo, p.email, p.telefone):
                continue
            todas = empresas.get(p.id, [])
            nesta_aba = [v for v in todas if v.grupo_id in grupos and grupos[v.grupo_id].situacao is situacao]
            if not (nesta_aba or (not todas and tipo == "prospect")):
                continue
            base = Pessoa.model_validate(p).model_dump(exclude={"empresas", "empresa_id", "grupo_id"})
            primeira = nesta_aba[0] if nesta_aba else None
            itens.append(PessoaComOrigem(
                **base, tipo=tipo, empresas=todas,
                empresa_id=primeira.empresa_id if primeira else None,
                grupo_id=primeira.grupo_id if primeira else None,
                grupo_nome=primeira.grupo_nome if primeira else None,
                razao_social=primeira.razao_social if primeira else None,
            ))
        return {"total": len(itens), "itens": itens[salto:salto + limite]}

    @r.get("/pessoas/busca", response_model=list[Pessoa])
    def buscar_pessoas(busca: str = "", sessao: Session = Depends(obter_sessao, scope="function")) -> list[Pessoa]:
        """Toda a base de contatos, clientes e prospects juntos, por nome, e-mail ou telefone —
        para vincular uma pessoa já cadastrada a uma empresa."""
        if len(busca.strip()) < 2:
            return []
        empresas = _empresas_por_pessoa(sessao)
        saida = []
        for p in sessao.scalars(sa.select(PessoaContato).order_by(PessoaContato.nome)):
            if casa(busca, p.nome, p.email, p.telefone):
                pessoa = Pessoa.model_validate(p)
                pessoa.empresas = empresas.get(p.id, [])
                saida.append(pessoa)
            if len(saida) == 20:
                break
        return saida

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
    def criar_pessoa(corpo: PessoaNova, sessao: Session = Depends(obter_sessao, scope="function")) -> Pessoa:
        if corpo.empresa_id is not None and sessao.get(Empresa, corpo.empresa_id) is None:
            raise HTTPException(404, "empresa não encontrada")
        p = PessoaContato(nome="x")
        if corpo.empresa_id is not None:
            p.vinculos.append(VinculoDeContato(empresa_id=corpo.empresa_id, principal=corpo.principal))
        dados = corpo.model_dump(exclude={"empresa_id", "principal"})
        _aplicar_pessoa(p, dados)
        if p.nao_contatar:
            p.nao_contatar_em = agora()
        sessao.add(p)
        sessao.flush()
        out = Pessoa.model_validate(p)
        out.empresa_id = corpo.empresa_id
        out.principal = corpo.empresa_id is not None and corpo.principal
        return out

    @r.patch("/pessoas/{pessoa_id}", response_model=Pessoa)
    def editar_pessoa(pessoa_id: int, corpo: PessoaEdicao, sessao: Session = Depends(obter_sessao, scope="function")) -> Pessoa:
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

    @r.delete("/pessoas/{pessoa_id}", status_code=204)
    def excluir_pessoa(pessoa_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> None:
        """Apaga a pessoa da base e de todas as empresas em que está. Irreversível: a tela pede
        confirmação antes. Pedido de Karine em 30/09/2026."""
        p = sessao.get(PessoaContato, pessoa_id)
        if p is None:
            raise HTTPException(404, "contato não encontrado")
        sessao.delete(p)
        sessao.flush()

    return r


def roteador_de_empresas(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    """Endereço e dados cadastrais da empresa (fora do prefixo /contatos)."""
    r = APIRouter(tags=["contatos"])

    def _grupo_pelo_nome(sessao: Session, nome: str) -> GrupoEconomico:
        """O grupo com este nome (sem caixa), ou um prospect novo — mesmo padrão da Nova oportunidade."""
        grupo = sessao.scalar(
            sa.select(GrupoEconomico).where(
                sa.func.lower(GrupoEconomico.nome) == nome.casefold(),
                GrupoEconomico.fundido_em_id.is_(None),
            )
        )
        if grupo is None:
            grupo = GrupoEconomico(nome=nome, situacao=SituacaoGrupo.PROSPECT, origem=Origem.CRM)
            sessao.add(grupo)
            sessao.flush()
        return grupo

    def _aplicar_empresa(sessao: Session, e: Empresa, dados: dict) -> None:
        for campo, valor in dados.items():
            if campo == "nome_do_grupo":
                continue
            if campo == "cnpj":
                valor = _digitos(valor)
                if valor is not None:
                    if not _cnpj_ok(valor):
                        raise HTTPException(422, "CNPJ inválido")
                    dono = sessao.scalars(
                        sa.select(Empresa).where(Empresa.cnpj == valor, Empresa.id.is_distinct_from(e.id))
                    ).first()
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

    @r.patch("/api/empresas/{empresa_id}", response_model=Endereco)
    def editar_empresa(empresa_id: int, corpo: EmpresaEdicao, sessao: Session = Depends(obter_sessao, scope="function")) -> Endereco:
        e = sessao.get(Empresa, empresa_id)
        if e is None:
            raise HTTPException(404, "empresa não encontrada")
        dados = corpo.model_dump(exclude_unset=True)
        _aplicar_empresa(sessao, e, dados)
        nome = _limpar(dados.get("nome_do_grupo"))
        if nome is not None and nome.casefold() != e.grupo.nome.casefold():
            if sessao.scalar(sa.select(Contrato.id).where(Contrato.empresa_id == e.id).limit(1)) is not None:
                raise HTTPException(409, "esta empresa tem contrato e não troca de grupo; use a fusão de grupos")
            e.grupo_id = _grupo_pelo_nome(sessao, nome).id
        sessao.flush()
        return Endereco.model_validate(e)

    @r.post("/api/empresas", status_code=201)
    def criar_empresa_completa(corpo: EmpresaCompleta, sessao: Session = Depends(obter_sessao, scope="function")) -> dict:
        """Contatos > Nova empresa: dados cadastrais, endereço e os contatos já cadastrados que
        forem vinculados. Pedido de Karine em 30/09/2026."""
        pessoas: dict[int, bool] = {}
        for c in corpo.contatos:
            if sessao.get(PessoaContato, c.pessoa_id) is None:
                raise HTTPException(404, f"contato {c.pessoa_id} não encontrado")
            pessoas[c.pessoa_id] = c.principal
        nome_do_grupo = _limpar(corpo.nome_do_grupo) or _limpar(corpo.razao_social)
        if nome_do_grupo is None:
            raise HTTPException(422, "a razão social não pode ficar vazia")
        e = Empresa(razao_social="x")
        _aplicar_empresa(sessao, e, corpo.model_dump(exclude={"contatos"}))
        grupo = _grupo_pelo_nome(sessao, nome_do_grupo)
        e.grupo_id = grupo.id
        sessao.add(e)
        sessao.flush()
        for pessoa_id, principal in pessoas.items():
            sessao.add(VinculoDeContato(pessoa_id=pessoa_id, empresa_id=e.id, principal=principal))
        sessao.flush()
        return {"id": e.id, "razao_social": e.razao_social, "cnpj": e.cnpj, "grupo_id": grupo.id, "grupo_nome": grupo.nome}

    @r.get("/api/empresas/busca")
    def buscar_empresas(busca: str = "", limite: int = Query(default=30, ge=1, le=100),
                        sessao: Session = Depends(obter_sessao, scope="function")) -> list[dict]:
        """A base de empresas, para escolher a da oportunidade no Funil: por nome fantasia, razão
        social ou CNPJ (com ou sem pontuação). Em branco, as primeiras em ordem alfabética.
        Pedido de Karine em 01/10/2026."""
        digitos = re.sub(r"\D", "", busca)
        saida = []
        for e, g in sessao.execute(
            sa.select(Empresa, GrupoEconomico).join(GrupoEconomico, GrupoEconomico.id == Empresa.grupo_id)
            .where(GrupoEconomico.fundido_em_id.is_(None)).order_by(Empresa.razao_social)
        ).all():
            if busca.strip() and not (casa(busca, e.razao_social, e.nome_fantasia, g.nome)
                                      or (len(digitos) >= 3 and digitos in (e.cnpj or ""))):
                continue
            saida.append({
                "id": e.id, "razao_social": e.razao_social, "nome_fantasia": e.nome_fantasia, "cnpj": e.cnpj,
                "grupo_id": g.id, "grupo_nome": g.nome,
                "tipo": "cliente" if g.situacao is SituacaoGrupo.CLIENTE else "prospect",
            })
            if len(saida) == limite:
                break
        return saida

    @r.delete("/api/empresas/{empresa_id}", status_code=204)
    def excluir_empresa(empresa_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> None:
        """Apaga a empresa. Os contatos continuam na base (só o vínculo some) e o grupo fica.
        Empresa com contrato não sai: apagar quebraria o histórico, o MRR e a carteira.
        Pedido de Karine em 30/09/2026, com essa trava aprovada."""
        e = sessao.get(Empresa, empresa_id)
        if e is None:
            raise HTTPException(404, "empresa não encontrada")
        if sessao.scalar(sa.select(Contrato.id).where(Contrato.empresa_id == empresa_id).limit(1)) is not None:
            raise HTTPException(409, "esta empresa tem contrato; encerre ou mova o contrato antes de excluir")
        sessao.execute(sa.delete(VinculoDeContato).where(VinculoDeContato.empresa_id == empresa_id))
        # As oportunidades dela continuam no grupo, só sem empresa escolhida.
        sessao.execute(sa.update(Oportunidade).where(Oportunidade.empresa_id == empresa_id).values(empresa_id=None))
        sessao.delete(e)
        sessao.flush()

    def _vinculo(sessao: Session, empresa_id: int, pessoa_id: int) -> VinculoDeContato:
        v = sessao.scalar(sa.select(VinculoDeContato).where(
            VinculoDeContato.empresa_id == empresa_id, VinculoDeContato.pessoa_id == pessoa_id))
        if v is None:
            raise HTTPException(404, "este contato não está vinculado a esta empresa")
        return v

    @r.post("/api/empresas/{empresa_id}/contatos", status_code=201)
    def vincular_contato(empresa_id: int, corpo: ContatoParaVincular, sessao: Session = Depends(obter_sessao, scope="function")) -> dict:
        """Liga uma pessoa já cadastrada à empresa. A pessoa continua nas outras empresas dela."""
        if sessao.get(Empresa, empresa_id) is None:
            raise HTTPException(404, "empresa não encontrada")
        if sessao.get(PessoaContato, corpo.pessoa_id) is None:
            raise HTTPException(404, "contato não encontrado")
        ja = sessao.scalar(sa.select(VinculoDeContato).where(
            VinculoDeContato.empresa_id == empresa_id, VinculoDeContato.pessoa_id == corpo.pessoa_id))
        if ja is not None:
            raise HTTPException(409, "este contato já está vinculado a esta empresa")
        sessao.add(VinculoDeContato(empresa_id=empresa_id, pessoa_id=corpo.pessoa_id, principal=corpo.principal))
        sessao.flush()
        return {"empresa_id": empresa_id, "pessoa_id": corpo.pessoa_id, "principal": corpo.principal}

    @r.patch("/api/empresas/{empresa_id}/contatos/{pessoa_id}")
    def mudar_vinculo(empresa_id: int, pessoa_id: int, corpo: MudancaDeVinculo,
                      sessao: Session = Depends(obter_sessao, scope="function")) -> dict:
        """Marca ou desmarca o contato como principal nesta empresa (pode haver mais de um)."""
        v = _vinculo(sessao, empresa_id, pessoa_id)
        v.principal = corpo.principal
        sessao.flush()
        return {"empresa_id": empresa_id, "pessoa_id": pessoa_id, "principal": v.principal}

    @r.delete("/api/empresas/{empresa_id}/contatos/{pessoa_id}", status_code=204)
    def desvincular_contato(empresa_id: int, pessoa_id: int, sessao: Session = Depends(obter_sessao, scope="function")) -> None:
        """Tira a pessoa desta empresa. A pessoa continua na base de contatos e nas outras empresas."""
        sessao.delete(_vinculo(sessao, empresa_id, pessoa_id))
        sessao.flush()

    @r.post("/api/grupos/{grupo_id}/empresas", status_code=201)
    def criar_empresa(grupo_id: int, corpo: EmpresaNova, sessao: Session = Depends(obter_sessao, scope="function")) -> dict:
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
