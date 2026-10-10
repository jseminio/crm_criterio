"""O que a aba "Proposta" já traz preenchido: matriz, carta, contextualização e perfil do cliente,
a partir da oportunidade, do questionário (quando houver) e do grupo. Tudo é sugestão: a pessoa muda
na tela ou no PowerPoint. O que não se sabe sai "N/D", como nas propostas enviadas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import (
    Empresa, GrupoEconomico, Oportunidade, PessoaContato, QuestionarioRecebido, ReuniaoComLead, VinculoDeContato,
)
from crm.domain import porte as regras_de_porte
from crm.domain.listas import TipoDeMatriz
from crm.proposta.conta import faturamento_por_extenso
from crm.questionario.leitura import inteiro_ou_nada

__all__ = ["CAMPOS_DO_PERFIL", "FRASE_PADRAO", "ND", "Base", "base_da_proposta", "reunioes_com_o_lead", "porte_da_oportunidade", "matriz_pelos_servicos", "cnpj_formatado"]

ND = "N/D"
FRASE_PADRAO = (
    "Esta proposta foi construída para acompanhar de perto essa transição, buscando a melhoria dos "
    "processos e a segurança nas informações que apoiam a tomada de decisão da empresa."
)
"""A frase que fecha toda contextualização, venha do questionário ou da reunião com o lead."""
CAMPOS_DO_PERFIL: dict[TipoDeMatriz, dict[str, tuple[str, str]]] = {
    TipoDeMatriz.CONTABIL: {
        "movimentacao": ("Movimentação", "lançamentos contábeis por mês, só o número"),
        "faturamento": ("Faturamento", "faturamento anual, por extenso (ex.: R$ 18 milhões)"),
        "instituicoes": ("Instituições", "quantidade de contas bancárias, só o número"),
        "funcionarios": ("Funcionários", "empregados CLT + PJs, só o número"),
        "regime": ("Regime", "regime tributário (Simples Nacional, Lucro Presumido, Lucro Real)"),
        "sistema": ("Sistema", "ERP ou sistema contábil usado hoje"),
        "empresas": ("Empresas", "quantos CNPJs entram no escopo (ex.: 3 empresas)"),
        "localidade": ("Localidade", "cidades/UF onde opera"),
    },
    TipoDeMatriz.FINANCEIRO: {
        "volume_documentos": ("Volume de documentos", "documentos financeiros por mês, só o número"),
        "faturamento": ("Faturamento", "faturamento anual, por extenso (ex.: R$ 18 milhões)"),
        "instituicoes": ("Instituições", "quantidade de contas bancárias, só o número"),
        "meios_de_pagamento": ("Meios de pagamento", "como recebe e paga (boleto, cartão, Pix…)"),
        "regime": ("Regime", "regime tributário (Simples Nacional, Lucro Presumido, Lucro Real)"),
        "sistema": ("Sistema", "ERP ou sistema financeiro usado hoje"),
        "segmento": ("Segmento", "atividade da empresa"),
        "localidade": ("Localidade", "cidades/UF onde opera"),
    },
}
"""Os campos do perfil do cliente em cada matriz, como a aba Proposta mostra: rótulo e o que a IA deve
trazer da reunião com o lead."""
_SERVICOS_NO_TEXTO = {"Contábil": "contábeis", "Fiscal": "fiscais", "Folha / DP": "de departamento pessoal",
                      "Financeiro": "financeiros"}


@dataclass(frozen=True)
class Base:
    matriz: TipoDeMatriz
    servicos: list[str]
    tem_dp: bool
    cliente: str
    tratamento: str
    contextualizacao: str
    perfil: dict[str, str]
    """Os marcadores do perfil do cliente já como texto final."""
    questionario_id: int | None
    pjs_estagiarios: int | None
    """PJs e estagiários do questionário (entram no honorário de DP com os CLT da oportunidade)."""
    jovens_aprendizes: int | None
    """Do questionário desde 03/10/2026; o que chegou antes conta zero."""
    perfil_da_reuniao: tuple[str, ...] = ()
    """Os campos do perfil que vieram da reunião com o lead (a tela marca "da reunião")."""


def cnpj_formatado(cnpj: str | None) -> str:
    d = re.sub(r"\D", "", cnpj or "")
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else (cnpj or ND)


def matriz_pelos_servicos(servicos: list[str]) -> TipoDeMatriz:
    """Só Financeiro → matriz Financeiro; qualquer outra combinação (ou nenhuma) → Contábil."""
    return TipoDeMatriz.FINANCEIRO if servicos == ["Financeiro"] else TipoDeMatriz.CONTABIL


def porte_da_oportunidade(o: Oportunidade) -> tuple[str | None, bool]:
    """O porte confirmado; sem ele, o que a régua sugere pela volumetria. Devolve (porte, confirmado)."""
    if o.porte:
        return o.porte, True
    sugestao = regras_de_porte.sugerir_porte(regras_de_porte.Volumetria(
        **{d.campo: getattr(o, d.campo) for d in regras_de_porte.DIRECIONADORES},
        servicos_contratados_alem_do_primeiro=o.servicos_contratados_alem_do_primeiro,
        tem_consolidacao_de_grupo=o.tem_consolidacao_de_grupo, e_auditada=o.e_auditada,
    ))
    return (sugestao.porte.value if sugestao.porte else None), False


def _dinheiro(texto: Any) -> Decimal | None:
    """ "R$ 4.800.000,00" (máscara do formulário) → 4800000."""
    if texto is None or texto == "":
        return None
    if isinstance(texto, (int, float)):
        return Decimal(str(texto))
    d = re.sub(r"\D", "", str(texto))
    try:
        return Decimal(d) / 100 if d else None
    except InvalidOperation:
        return None


def _ou_nd(v: Any) -> str:
    return ND if v is None or str(v).strip() == "" else str(v).strip()


def _lista_em_texto(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def _contextualizacao(cliente: str, r: dict[str, Any], servicos: list[str]) -> str:
    atividade = (r.get("atividade") or "").strip()
    local = (r.get("filiais_localidades") or r.get("municipios_ufs") or "").strip()
    no_texto = [_SERVICOS_NO_TEXTO[s] for s in servicos if s in _SERVICOS_NO_TEXTO]
    servicos_txt = f"os serviços {_lista_em_texto(no_texto)}" if no_texto else "os serviços desta proposta"
    verbo = (f"avalia contar com um parceiro para {servicos_txt}" if r.get("operacao") == "Interna"
             else f"busca um novo parceiro para {servicos_txt}")
    if atividade:
        frase = f"A {cliente} atua no segmento de {atividade}" + (f", com operação em {local}" if local else "") + f", e {verbo}."
    elif local:
        frase = f"A {cliente}, com operação em {local}, {verbo}."
    else:
        frase = f"A {cliente} {verbo}."
    return f"{frase}\n{FRASE_PADRAO}"


def reunioes_com_o_lead(sessao: Session, oportunidade_id: int) -> list[ReuniaoComLead]:
    """Da mais recente para a mais antiga."""
    return list(sessao.scalars(
        sa.select(ReuniaoComLead).where(ReuniaoComLead.oportunidade_id == oportunidade_id)
        .order_by(ReuniaoComLead.data.desc(), ReuniaoComLead.id.desc())
    ))


def base_da_proposta(sessao: Session, o: Oportunidade) -> Base:
    q = sessao.scalars(
        sa.select(QuestionarioRecebido).where(QuestionarioRecebido.oportunidade_id == o.id)
        .order_by(QuestionarioRecebido.recebido_em.desc()).limit(1)
    ).first()
    r: dict[str, Any] = (q.respostas if q else None) or {}
    grupo = sessao.get(GrupoEconomico, o.grupo_id)
    empresa = None
    if q is not None:
        empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == q.cnpj))
    if empresa is None:
        empresa = sessao.scalars(
            sa.select(Empresa).where(Empresa.grupo_id == grupo.id).order_by(Empresa.id).limit(1)
        ).first()

    servicos = [s for s in (r.get("servicos") or []) if isinstance(s, str)]
    cliente = (q.nome_fantasia or q.razao_social) if q else (empresa.nome_fantasia or empresa.razao_social if empresa else grupo.nome)
    if q is not None:
        contato = q.contato_nome
    else:
        # Contato é ligado às empresas do grupo, não ao grupo (01/10/2026); o principal vem primeiro.
        pessoa = sessao.scalars(
            sa.select(PessoaContato)
            .join(VinculoDeContato, VinculoDeContato.pessoa_id == PessoaContato.id)
            .join(Empresa, Empresa.id == VinculoDeContato.empresa_id)
            .where(Empresa.grupo_id == grupo.id)
            .order_by(VinculoDeContato.principal.desc(), PessoaContato.id)
            .limit(1)
        ).first()
        contato = pessoa.nome if pessoa else "[NOME]"

    regimes = [x for x in (r.get("regime_tributario") or []) if isinstance(x, str) and x != "Outro"]
    regime = " / ".join(regimes) if regimes else (empresa.regime_tributario if empresa else None)
    faturamento = _dinheiro(r.get("faturamento_anual"))
    sistemas = r.get("sistemas") if isinstance(r.get("sistemas"), dict) else {}
    sistema = next(((sistemas.get(k) or {}).get("sistema") for k in ("erp", "contabil") if (sistemas.get(k) or {}).get("sistema")), None)
    n_empresas = o.cnpjs_no_escopo
    local = r.get("filiais_localidades") or r.get("municipios_ufs")
    if not local and empresa and empresa.municipio:
        local = f"{empresa.municipio}/{empresa.uf}" if empresa.uf else empresa.municipio
    perfil = {
        "cnpj": cnpj_formatado(q.cnpj if q else (empresa.cnpj if empresa else None)),
        "regime": _ou_nd(regime),
        "faturamento": faturamento_por_extenso(faturamento) if faturamento else ND,
        "funcionarios": _ou_nd(o.empregados_clt),
        "movimentacao": _ou_nd(o.lancamentos_contabeis_mes),
        "volume_documentos": _ou_nd(o.documentos_fiscais_mes),
        "instituicoes": _ou_nd(o.contas_bancarias),
        "meios_de_pagamento": ND,
        "sistema": _ou_nd(sistema),
        "segmento": _ou_nd(r.get("atividade")),
        "empresas": ND if not n_empresas else f"{n_empresas} empresa{'s' if n_empresas > 1 else ''}",
        "localidade": _ou_nd(local),
    }
    # A reunião com o lead (10/10/2026): o que a pessoa aplicou vale por cima do questionário, a mais
    # nova por cima das outras; a contextualização é a da mais nova que trouxe uma.
    contextualizacao = _contextualizacao(cliente, r, servicos)
    da_reuniao: list[str] = []
    for reuniao in reunioes_com_o_lead(sessao, o.id)[::-1]:
        for campo, valor in (reuniao.perfil or {}).items():
            if campo in perfil and campo != "cnpj" and str(valor).strip():
                perfil[campo] = str(valor).strip()
                if campo not in da_reuniao:
                    da_reuniao.append(campo)
        if reuniao.contextualizacao:
            contextualizacao = reuniao.contextualizacao
    return Base(
        matriz=matriz_pelos_servicos(servicos), servicos=servicos, tem_dp="Folha / DP" in servicos or not servicos,
        cliente=cliente, tratamento=f"Prezado(a) Sr(a). {contato}",
        contextualizacao=contextualizacao, perfil=perfil, perfil_da_reuniao=tuple(da_reuniao),
        questionario_id=q.id if q else None,
        pjs_estagiarios=inteiro_ou_nada((r.get("vol") or {}).get("pjs_estagiarios")),
        jovens_aprendizes=inteiro_ou_nada((r.get("vol") or {}).get("jovens_aprendizes")),
    )
