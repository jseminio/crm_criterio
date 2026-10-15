"""Mesclar um questionário com uma oportunidade já aberta (amostra aprovada por Eduardo em 15/10/2026).

O caso clássico: o vendedor abre o card a partir do lead (sem CNPJ) e depois manda o questionário; quando ele
chega, o CNPJ não bate com nada e o CRM criava grupo, empresa e oportunidade de novo (a Mainô). Agora:

- **Sugestões** (`sugestoes`): oportunidades abertas do mesmo CNPJ, do mesmo contato (e-mail ou celular de quem
  respondeu), do lead convertido com esse contato e de nome parecido, cada uma com o motivo.
- **Regra D** (`par_por_contato`, usada na importação): achou oportunidade aberta pelo contato ou pelo lead, o
  CRM **não cria nada** e põe o questionário em "Precisa de você" (decisão de 15/10/2026).
- **Mesclar** (`mesclar`): o questionário só **preenche o vazio** do card; onde o valor difere, fica o do card,
  salvo os campos que a pessoa marcar para usar o do questionário (volumetria e notas). Preço, captador,
  temperatura, serviço e datas do vendedor nunca mudam.
- **Grupos:** CNPJ que ainda não existe é cadastrado no grupo do card; grupo criado pelo próprio questionário é
  **fundido** no grupo do card (`crm.db.grupos.fundir_grupos`, desfazível); CNPJ de outro grupo que já existia
  é recusado: funda os grupos antes, em Grupos.
- **Duplicada:** a oportunidade que o questionário criou pode sair no mesmo passo (`crm.db.excluir_oportunidade`),
  com o motivo no histórico. A tela só a marca quando ninguém mexeu nela.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db import excluir_oportunidade
from crm.db.grupos import fundir_grupos
from crm.db.modelos import (
    Empresa, GrupoEconomico, Lead, Oportunidade, PessoaContato, Proposta, QuestionarioRecebido, RegistroDeAlteracao,
    VinculoDeContato,
)
from crm.domain.listas import Origem, OrigemDoDado, Situacao, SituacaoDoQuestionario
from crm.domain.porte import DIRECIONADORES
from crm.questionario import importacao
from crm.questionario.endereco import BuscaDeEndereco

__all__ = ["Sugestao", "Campo", "Previa", "MesclaRecusada", "sugestoes", "par_por_contato", "previa", "mesclar",
           "intocada"]

_ROTULO = {d.campo: d.rotulo for d in DIRECIONADORES} | {
    "complexidade": "Nota de complexidade", "risco_tecnico": "Nota de risco técnico",
}
_PODE_TROCAR = frozenset(_ROTULO)
"""Onde o valor do questionário pode substituir o do card, se a pessoa pedir: volumetria e notas."""


class MesclaRecusada(ValueError):
    """A mescla pedida não pode ser feita; a mensagem diz o que fazer no lugar."""


@dataclass(frozen=True)
class Sugestao:
    oportunidade: Oportunidade
    motivo: str


@dataclass(frozen=True)
class Campo:
    campo: str
    rotulo: str
    no_card: str | None
    no_questionario: str
    acao: str
    """preenche · igual · diferente (fica o do card, salvo se a pessoa pedir) · fica (o do card, sem troca)"""


@dataclass
class Previa:
    campos: list[Campo] = field(default_factory=list)
    recusa: str | None = None
    fusao: tuple[str, str] | None = None
    """(grupo do questionário que será fundido, grupo do card que fica)."""
    cnpj_novo_no_grupo: str | None = None
    """O CNPJ ainda não existe: será cadastrado neste grupo (o do card)."""
    duplicada: Oportunidade | None = None
    duplicada_intocada: bool = False
    duplicada_recusa: str | None = None


# ------------------------------------------------------------ quem é quem
def _celular(v: str | None) -> str:
    d = re.sub(r"\D", "", v or "")
    if len(d) > 11 and d.startswith("55"):
        d = d[2:]
    return d if len(d) >= 10 else ""


def _vivo(sessao: Session, grupo_id: int) -> int:
    return importacao._grupo_vivo(sessao, sessao.get(GrupoEconomico, grupo_id)).id


def _abertas_do_grupo(sessao: Session, grupo_id: int) -> list[Oportunidade]:
    return list(sessao.scalars(
        sa.select(Oportunidade).where(Oportunidade.grupo_id == grupo_id, Oportunidade.situacao.in_(importacao.EM_ABERTO))
        .order_by(Oportunidade.criado_em.desc(), Oportunidade.id.desc())
    ))


def _pelo_contato(sessao: Session, q: QuestionarioRecebido) -> list[tuple[Oportunidade, str]]:
    """Oportunidades abertas do mesmo contato (pessoa cadastrada ou lead convertido): a base da regra D."""
    email = (q.contato_email or "").strip().casefold()
    celular = _celular(q.contato_celular)
    achadas: list[tuple[Oportunidade, str]] = []
    if email or celular:
        pessoas = sessao.scalars(sa.select(PessoaContato).where(
            sa.or_(sa.func.lower(PessoaContato.email) == email if email else sa.false(),
                   PessoaContato.telefone.is_not(None) if celular else sa.false())))
        for p in pessoas:
            por_email = bool(email) and (p.email or "").strip().casefold() == email
            por_celular = bool(celular) and _celular(p.telefone) == celular
            if not (por_email or por_celular):
                continue
            motivo = "mesmo e-mail do contato" if por_email else "mesmo celular do contato"
            for v in sessao.scalars(sa.select(VinculoDeContato).where(VinculoDeContato.pessoa_id == p.id)):
                for op in _abertas_do_grupo(sessao, _vivo(sessao, v.empresa.grupo_id)):
                    achadas.append((op, motivo))
    leads = sessao.scalars(sa.select(Lead).where(Lead.convertido_em_id.is_not(None)))
    for lead in leads:
        bate = ((email and (lead.email or "").strip().casefold() == email)
                or (celular and _celular(lead.telefone) == celular)
                or (len(q.cnpj) == 14 and re.sub(r"\D", "", lead.cnpj or "") == q.cnpj))
        if bate:
            op = sessao.get(Oportunidade, lead.convertido_em_id)
            if op is not None and op.situacao in importacao.EM_ABERTO:
                achadas.append((op, f'lead convertido "{lead.nome}"'))
    return achadas


def _nome_parecido(sessao: Session, q: QuestionarioRecebido) -> list[tuple[Oportunidade, str]]:
    palavras = [p for p in re.findall(r"\w+", (q.nome_fantasia or q.razao_social).casefold())
                if len(p) >= 4 and p not in {"ltda", "eireli", "servicos", "serviços", "comercio", "comércio",
                                             "industria", "indústria", "participacoes", "participações", "brasil"}]
    if not palavras:
        return []
    chave = palavras[0]
    ops = sessao.scalars(
        sa.select(Oportunidade).join(GrupoEconomico, GrupoEconomico.id == Oportunidade.grupo_id)
        .where(Oportunidade.situacao.in_(importacao.EM_ABERTO),
               sa.or_(sa.func.lower(GrupoEconomico.nome).contains(chave), sa.func.lower(Oportunidade.nome).contains(chave)))
        .order_by(Oportunidade.id.desc()).limit(10)
    )
    return [(op, "nome parecido") for op in ops]


def sugestoes(sessao: Session, q: QuestionarioRecebido) -> list[Sugestao]:
    """As prováveis oportunidades deste questionário, da mais forte para a mais fraca, sem repetir."""
    candidatas: list[tuple[Oportunidade, str]] = []
    empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == q.cnpj))
    if empresa is not None:
        candidatas += [(op, "mesmo CNPJ") for op in _abertas_do_grupo(sessao, _vivo(sessao, empresa.grupo_id))]
    candidatas += _pelo_contato(sessao, q) + _nome_parecido(sessao, q)
    vistas, saida = {q.oportunidade_id}, []
    for op, motivo in candidatas:
        if op.id not in vistas:
            vistas.add(op.id)
            saida.append(Sugestao(op, motivo))
    return saida


def par_por_contato(sessao: Session, q: QuestionarioRecebido) -> tuple[Oportunidade, str] | None:
    """Regra D: a oportunidade aberta deste contato (ou do lead convertido), se houver. A mais recente. Card já ligado
    a outro CNPJ não conta: é outra empresa (as sugestões da tela ainda o mostram)."""
    def de_outro_cnpj(op: Oportunidade) -> bool:
        """Card já ligado a outro CNPJ: a mesma pessoa (um contador, por exemplo) respondendo por outra empresa."""
        empresa = sessao.get(Empresa, op.empresa_id) if op.empresa_id else None
        return empresa is not None and bool(empresa.cnpj) and empresa.cnpj != q.cnpj

    achadas = [(op, motivo) for op, motivo in _pelo_contato(sessao, q) if not de_outro_cnpj(op)]
    if not achadas:
        return None
    return max(achadas, key=lambda a: (a[0].criado_em, a[0].id))


# ------------------------------------------------------------ a mescla
def intocada(sessao: Session, op: Oportunidade) -> bool:
    """A oportunidade que o questionário criou e ninguém mexeu: dá para excluir sem perder trabalho."""
    if op.origem is not Origem.QUESTIONARIO or op.situacao is not Situacao.ENVIAR_PROPOSTA:
        return False
    if op.preco_mensal or op.preco_anual or op.captador or op.temperatura or op.proxima_acao:
        return False
    if sessao.scalar(sa.select(Proposta.id).where(Proposta.oportunidade_id == op.id).limit(1)) is not None:
        return False
    return sessao.scalar(sa.select(RegistroDeAlteracao.id).where(
        RegistroDeAlteracao.tabela == "oportunidade", RegistroDeAlteracao.registro_id == op.id,
        RegistroDeAlteracao.acao == "alterou").limit(1)) is None


def _texto(v) -> str | None:
    if v is None:
        return None
    return getattr(v, "value", v) if not isinstance(v, (int, str)) else str(v)


def _valores_do_questionario(q: QuestionarioRecebido) -> dict[str, object]:
    leitura = importacao.leitura_de(q)
    valores: dict[str, object] = {k: v for k, v in leitura.volumetria.items() if v is not None}
    valores["complexidade"], valores["risco_tecnico"] = leitura.nota_complexidade, leitura.nota_risco
    tipo_canal, canal = importacao.origem_declarada(q.respostas or {})
    valores["tipo_canal"], valores["canal"] = tipo_canal, canal
    return {k: v for k, v in valores.items() if v is not None}


def _plano_do_grupo(sessao: Session, q: QuestionarioRecebido, destino: Oportunidade) -> tuple[str | None, GrupoEconomico | None, bool]:
    """(recusa, grupo a fundir no do card, CNPJ será cadastrado no grupo do card)."""
    empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == q.cnpj))
    if empresa is None:
        return None, None, True
    grupo_da_empresa = _vivo(sessao, empresa.grupo_id)
    if grupo_da_empresa == destino.grupo_id:
        return None, None, False
    grupo = sessao.get(GrupoEconomico, grupo_da_empresa)
    if q.cliente_novo and q.grupo_id == grupo.id and grupo.origem is Origem.QUESTIONARIO:
        return None, grupo, False
    destino_grupo = sessao.get(GrupoEconomico, destino.grupo_id)
    return (f'O CNPJ {q.cnpj} já é do grupo "{grupo.nome}" e o card está em "{destino_grupo.nome}". '
            "Se forem o mesmo cliente, funda os grupos em Grupos e mescle depois."), None, False


def previa(sessao: Session, q: QuestionarioRecebido, destino: Oportunidade) -> Previa:
    p = Previa()
    if destino.situacao not in importacao.EM_ABERTO:
        p.recusa = f'A oportunidade "{destino.nome}" não está em aberto ({destino.situacao.value}).'
        return p
    if q.oportunidade_id == destino.id:
        p.recusa = "O questionário já está nesta oportunidade."
        return p
    p.recusa, fundir, cnpj_novo = _plano_do_grupo(sessao, q, destino)
    if fundir is not None:
        p.fusao = (fundir.nome, sessao.get(GrupoEconomico, destino.grupo_id).nome)
    if cnpj_novo:
        p.cnpj_novo_no_grupo = sessao.get(GrupoEconomico, destino.grupo_id).nome
    if destino.empresa_id is None:
        p.campos.append(Campo("empresa_id", "CNPJ (empresa)", None, q.cnpj, "preenche"))
    for campo, valor in _valores_do_questionario(q).items():
        no_card = getattr(destino, campo)
        rotulo = _ROTULO.get(campo) or {"tipo_canal": "Tipo de canal", "canal": "Canal (como conheceu)"}[campo]
        if no_card is None or no_card == "":
            acao = "preenche"
        elif _texto(no_card) == _texto(valor):
            acao = "igual"
        else:
            acao = "diferente" if campo in _PODE_TROCAR else "fica"
        p.campos.append(Campo(campo, rotulo, _texto(no_card), _texto(valor), acao))
    if q.oportunidade_id is not None:
        dup = sessao.get(Oportunidade, q.oportunidade_id)
        if dup is not None and dup.id != destino.id:
            p.duplicada = dup
            p.duplicada_intocada = intocada(sessao, dup)
            p.duplicada_recusa = excluir_oportunidade.o_que_sai(sessao, dup).recusa
    return p


def mesclar(sessao: Session, q: QuestionarioRecebido, destino: Oportunidade, *, usar_do_questionario: set[str] = frozenset(),
            excluir_duplicada: bool = False, buscar_endereco: BuscaDeEndereco | None = None) -> int:
    """Leva o questionário para a oportunidade `destino`. Devolve quantos campos preencheu ou trocou. Não faz commit."""
    invalidos = set(usar_do_questionario) - _PODE_TROCAR
    if invalidos:
        raise MesclaRecusada(f"Só volumetria e notas podem trocar o valor do card: {', '.join(sorted(invalidos))}.")
    p = previa(sessao, q, destino)
    if p.recusa:
        raise MesclaRecusada(p.recusa)
    if excluir_duplicada and p.duplicada is not None and p.duplicada_recusa:
        raise MesclaRecusada(p.duplicada_recusa)

    # 1) Grupo e empresa: antes de tudo, para o card ganhar o CNPJ.
    empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == q.cnpj))
    grupo_do_card = sessao.get(GrupoEconomico, destino.grupo_id)
    leitura = importacao.leitura_de(q)
    endereco = ""
    if empresa is None:
        empresa = Empresa(grupo_id=grupo_do_card.id, razao_social=q.razao_social, nome_fantasia=q.nome_fantasia,
                          cnpj=q.cnpj, regime_tributario=leitura.regimes[0][:40] if len(leitura.regimes) == 1 else None)
        sessao.add(empresa)
        sessao.flush()
        endereco = importacao._preencher_endereco(empresa, buscar_endereco)

    # 2) A duplicada sai antes da fusão: assim a fusão não a carrega para o grupo do card.
    duplicada_nome = None
    if excluir_duplicada and p.duplicada is not None:
        duplicada_nome = p.duplicada.nome
        excluir_oportunidade.excluir(sessao, p.duplicada,
                                     f'Duplicada: o questionário de {q.razao_social} foi mesclado em "{destino.nome}".')
    fusao = ""
    if p.fusao is not None:
        absorvido = sessao.get(GrupoEconomico, _vivo(sessao, empresa.grupo_id))
        fusao = " " + fundir_grupos(sessao, grupo_do_card, absorvido).texto + " (dá para desfazer em Grupos)."

    # 3) Os campos: só o vazio, e o diferente que a pessoa pediu.
    origem = dict(destino.origem_da_volumetria or {})
    mexidos = 0
    for campo, valor in _valores_do_questionario(q).items():
        atual = getattr(destino, campo)
        vazio = atual is None or atual == ""
        if vazio or (campo in usar_do_questionario and _texto(atual) != _texto(valor)):
            setattr(destino, campo, valor)
            if campo in leitura.volumetria:
                origem[campo] = OrigemDoDado.QUESTIONARIO.value
            mexidos += 1
    destino.origem_da_volumetria = origem  # dict novo: o JSON só grava se o objeto muda
    if destino.empresa_id is None:
        destino.empresa_id = empresa.id
        mexidos += 1
    novo_contato = importacao._contato(sessao, q, grupo_do_card, empresa)

    q.situacao, q.oportunidade_id, q.oportunidade_em_aberto_id = SituacaoDoQuestionario.IMPORTADO, destino.id, None
    q.grupo_id = destino.grupo_id
    q.o_que_fez = (f'Mesclado em "{destino.nome}": {mexidos} campo(s) preenchido(s) ou trocado(s), sem mexer em preço, '
                   "captador, temperatura, serviço e datas."
                   + (" Contato criado." if novo_contato else "")
                   + (f' A oportunidade duplicada "{duplicada_nome}" foi excluída.' if duplicada_nome else "")
                   + fusao + endereco)
    sessao.flush()
    return mexidos
