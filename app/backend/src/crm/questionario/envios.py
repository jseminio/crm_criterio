"""Mais de um envio da mesma empresa: comparar e ficar com um, ou combinar campo a campo (amostra aprovada por
Eduardo em 11/11/2026).

O questionário tem um link único para todos. Quem respondeu é identificado pelo que preencheu: o CNPJ e o primeiro
nome. Quando a mesma empresa envia de novo (a mesma pessoa ou outra), nada é substituído nem atualizado sozinho: o
envio novo fica "Precisa de você" e quem resolve compara os dois.

- **Comparar** (`comparacao`): os envios lado a lado, campo a campo, com o que é igual, o que difere e o que um
  preencheu e o outro deixou vazio.
- **Combinar** (`combinar`): para cada campo que difere, quem resolve diz de qual envio vem; campo vazio num envio
  é preenchido pelo outro sem perguntar. As respostas combinadas ficam no envio novo, que então segue o caminho de
  sempre (`importacao.decidir`): vira oportunidade, ou para em "Precisa de você" se a empresa já tem uma aberta, e
  aí a mescla com o card é a de sempre. As respostas que o envio tinha antes ficam guardadas em `combinacao`.
- **Ficar com o anterior** (`descartar`): o envio novo é guardado como "Descartado" e não vira nada.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from crm.db.base import agora
from crm.db.modelos import QuestionarioRecebido
from crm.domain.listas import SituacaoDoQuestionario
from crm.proposta import ficha
from crm.questionario import importacao
from crm.questionario.endereco import BuscaDeEndereco

__all__ = ["EnvioDaEmpresa", "CampoComparado", "Comparacao", "comparacao", "combinar", "descartar", "e_comparacao"]

Estado = Literal["igual", "diferente", "completa", "vazio"]
"""igual: todos iguais · diferente: precisa escolher · completa: só um preencheu · vazio: ninguém preencheu."""

_CONTATO = (("contato_nome", 200), ("contato_cargo", 100), ("contato_celular", 30), ("contato_email", 200))


@dataclass(frozen=True)
class EnvioDaEmpresa:
    id: int
    numero: str | None
    recebido_em: datetime
    contato_nome: str
    chave_do_preenchedor: str | None
    situacao: str
    oportunidade_id: int | None


@dataclass(frozen=True)
class CampoComparado:
    chave: str
    secao: int
    rotulo: str
    valores: dict[int, str | None]
    """Por id de envio, o valor já como texto (lista vira "a, b")."""
    estado: Estado
    sugestao: int | None
    """O envio que vale se ninguém escolher: o único que preencheu, ou o mais novo quando há diferença."""


@dataclass(frozen=True)
class Comparacao:
    envios: list[EnvioDaEmpresa]
    campos: list[CampoComparado]


def e_comparacao(sessao: Session, q: QuestionarioRecebido) -> bool:
    """O envio está parado porque a empresa já tinha enviado (e não por oportunidade aberta)."""
    return (q.situacao is SituacaoDoQuestionario.PRECISA_DE_VOCE and q.oportunidade_em_aberto_id is None
            and bool(importacao.outros_envios(sessao, q)))


def _texto(v: Any) -> str | None:
    if v in (None, "", []):
        return None
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) or None
    t = str(v).strip()
    return t or None


def _envio(q: QuestionarioRecebido) -> EnvioDaEmpresa:
    return EnvioDaEmpresa(
        id=q.id, numero=importacao.numero_do_envio(q.numero), recebido_em=q.recebido_em, contato_nome=q.contato_nome,
        chave_do_preenchedor=q.chave_do_preenchedor, situacao=q.situacao.value, oportunidade_id=q.oportunidade_id,
    )


def _envios(sessao: Session, q: QuestionarioRecebido) -> list[QuestionarioRecebido]:
    return [*importacao.outros_envios(sessao, q), q]


def comparacao(sessao: Session, q: QuestionarioRecebido) -> Comparacao:
    """Os envios da empresa (os anteriores e este, o mais novo por último) e cada campo da ficha comparado."""
    envios = _envios(sessao, q)
    campos: list[CampoComparado] = []
    for c in ficha.CAMPOS:
        valores = {e.id: _texto(ficha.valor_do_questionario(e.respostas, c.chave)) for e in envios}
        preenchidos = {i: v for i, v in valores.items() if v is not None}
        if not preenchidos:
            continue  # ninguém respondeu: nem aparece
        distintos = set(preenchidos.values())
        if len(distintos) > 1:
            estado: Estado = "diferente"
        elif len(preenchidos) < len(valores):
            estado = "completa"
        else:
            estado = "igual"
        sugestao = max(preenchidos)  # o mais novo que preencheu (ids crescem com o tempo de chegada)
        campos.append(CampoComparado(chave=c.chave, secao=c.secao, rotulo=c.rotulo, valores=valores, estado=estado,
                                     sugestao=sugestao))
    return Comparacao(envios=[_envio(e) for e in envios], campos=campos)


def _valor_cru(respostas: dict, chave: str) -> Any:
    if chave.startswith("vol."):
        return (respostas.get("vol") or {}).get(chave[4:])
    if chave.startswith("sistemas."):
        return (respostas.get("sistemas") or {}).get(chave[9:])
    return respostas.get(chave)


def _gravar(respostas: dict, chave: str, valor: Any) -> None:
    for prefixo in ("vol.", "sistemas."):
        if chave.startswith(prefixo):
            bloco = dict(respostas.get(prefixo[:-1]) or {})
            if valor is None:
                bloco.pop(chave[len(prefixo):], None)
            else:
                bloco[chave[len(prefixo):]] = copy.deepcopy(valor)
            respostas[prefixo[:-1]] = bloco
            return
    if valor is None:
        respostas.pop(chave, None)
    else:
        respostas[chave] = copy.deepcopy(valor)


def _exigir_comparacao(sessao: Session, q: QuestionarioRecebido) -> None:
    if not e_comparacao(sessao, q):
        raise ValueError("este envio não está esperando comparação: a empresa não tem outro envio pendente de escolha")


def combinar(sessao: Session, q: QuestionarioRecebido, escolhas: dict[str, int], quem: str,
             buscar_endereco: BuscaDeEndereco | None = None) -> None:
    """Monta as respostas combinadas no envio `q` (o mais novo) e segue o caminho de sempre. Não faz commit.

    `escolhas`: para cada campo **diferente**, o id do envio de onde vem. Campo só de um envio vem dele; campo
    igual fica como está. Faltou escolher um campo diferente: recusa, para nada ir pela metade."""
    _exigir_comparacao(sessao, q)
    comp = comparacao(sessao, q)
    por_id = {e.id: e for e in _envios(sessao, q)}
    faltando = [c.rotulo for c in comp.campos if c.estado == "diferente" and c.chave not in escolhas]
    if faltando:
        raise ValueError("escolha de qual envio vem: " + "; ".join(faltando[:5]) + ("…" if len(faltando) > 5 else ""))
    desconhecidos = {i for i in escolhas.values() if i not in por_id}
    if desconhecidos:
        raise ValueError("escolha aponta para um envio que não é desta empresa")

    original = copy.deepcopy(q.respostas or {})
    novas = copy.deepcopy(q.respostas or {})
    origem: dict[str, str | None] = {}
    for c in comp.campos:
        if c.estado == "igual":
            continue
        de = escolhas.get(c.chave, c.sugestao) if c.estado == "diferente" else c.sugestao
        _gravar(novas, c.chave, _valor_cru(por_id[de].respostas or {}, c.chave))
        origem[c.chave] = importacao.numero_do_envio(por_id[de].numero)
        if c.chave == "cnpjs_escopo":  # a tabela de empresas anda junto com a lista que ela gera
            _gravar(novas, "empresas", (por_id[de].respostas or {}).get("empresas"))

    q.respostas = novas
    for campo, limite in _CONTATO:
        valor = _texto(novas.get(campo))
        if valor:
            setattr(q, campo, valor[:limite])
    outros = [e for e in por_id.values() if e.id != q.id]
    q.combinacao = {
        "de": [importacao.numero_do_envio(e.numero) for e in [*outros, q]],
        "campos": origem, "por": quem, "em": agora().isoformat(), "respostas_antes": original,
    }
    for e in outros:  # os anteriores que ainda esperavam escolha deixam de esperar: o combinado os representa
        if e.situacao is SituacaoDoQuestionario.PRECISA_DE_VOCE and e.oportunidade_id is None:
            e.situacao = SituacaoDoQuestionario.DESCARTADO
            e.o_que_fez = f"Combinado no envio {importacao.numero_do_envio(q.numero)} por {quem}."
    leitura = importacao.leitura_de(q)
    q.porte_crm = leitura.porte
    importacao.decidir(sessao, q, leitura, buscar_endereco)
    numeros = ", ".join(x for x in q.combinacao["de"] if x)
    q.o_que_fez = f"Combinado por {quem} a partir de {numeros}. " + q.o_que_fez
    sessao.flush()


def descartar(sessao: Session, q: QuestionarioRecebido, quem: str) -> None:
    """Fica com o envio anterior: este é guardado como "Descartado" e não vira nada. Não faz commit."""
    _exigir_comparacao(sessao, q)
    anterior = importacao.outros_envios(sessao, q)[-1]
    q.situacao = SituacaoDoQuestionario.DESCARTADO
    q.o_que_fez = (f"Descartado por {quem}: vale o envio {importacao.numero_do_envio(anterior.numero) or 'anterior'} "
                   f"({anterior.contato_nome}). Este fica guardado para consulta.")
    sessao.flush()
