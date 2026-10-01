"""Um questionário buscado no site vira cliente e oportunidade no CRM (pedido de Eduardo, 01/10/2026).

- O **CNPJ** é a identidade: empresa já cadastrada leva a oportunidade para o grupo dela.
- Grupo com oportunidade **em aberto** não ganha outra sozinho: o questionário fica "Precisa de
  você", e a pessoa escolhe anexar à existente ou criar nova.
- A oportunidade nasce em "Enviar proposta", com os nove direcionadores marcados como vindos do
  "Questionário". O **porte não é confirmado** aqui: a régua só sugere (`crm.domain.porte`).
- Anexar só preenche o que está vazio na oportunidade existente: nada do que já foi digitado some.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Empresa, GrupoEconomico, Oportunidade, PessoaContato, QuestionarioRecebido, VinculoDeContato
from crm.domain.listas import Origem, OrigemDoDado, Situacao, SituacaoDoQuestionario, SituacaoGrupo
from crm.questionario.leitura import Leitura, ler

__all__ = ["LinhaInvalida", "importar", "anexar", "criar_nova", "leitura_de", "EM_ABERTO"]

EM_ABERTO = (Situacao.ENVIAR_PROPOSTA, Situacao.EM_AVALIACAO, Situacao.ON_HOLD)


class LinhaInvalida(ValueError):
    """A linha do Supabase não tem o mínimo para virar cliente (razão social, CNPJ, contato)."""


def _digitos(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def _texto(v: Any, limite: int) -> str | None:
    t = str(v).strip() if v is not None else ""
    return t[:limite] or None


def leitura_de(q: QuestionarioRecebido) -> Leitura:
    return ler(q.respostas, recebido_em=q.recebido_em.date())


def _grupo_vivo(sessao: Session, grupo: GrupoEconomico) -> GrupoEconomico:
    """Grupo fundido aponta para quem o absorveu: a oportunidade vai para o que ficou."""
    while grupo.fundido_em_id is not None:
        grupo = sessao.get(GrupoEconomico, grupo.fundido_em_id)
    return grupo


def _nova_oportunidade(sessao: Session, q: QuestionarioRecebido, grupo: GrupoEconomico, leitura: Leitura) -> Oportunidade:
    preenchidos = {k: v for k, v in leitura.volumetria.items() if v is not None}
    oportunidade = Oportunidade(
        grupo_id=grupo.id, nome=(q.nome_fantasia or q.razao_social)[:200], situacao=Situacao.ENVIAR_PROPOSTA,
        data_colocacao=q.recebido_em.date(), origem=Origem.QUESTIONARIO,
        servico_descricao=f"Escopo pedido no questionário: {', '.join(leitura.servicos)}" if leitura.servicos else None,
        servicos_contratados_alem_do_primeiro=leitura.servicos_contratados_alem_do_primeiro,
        tem_consolidacao_de_grupo=leitura.tem_consolidacao_de_grupo, e_auditada=leitura.e_auditada,
        complexidade=leitura.nota_complexidade, risco_tecnico=leitura.nota_risco,
        origem_da_volumetria={k: OrigemDoDado.QUESTIONARIO.value for k in preenchidos},
        **leitura.volumetria,
    )
    sessao.add(oportunidade)
    sessao.flush()
    return oportunidade


def _contato(sessao: Session, q: QuestionarioRecebido, grupo: GrupoEconomico, empresa: Empresa) -> bool:
    """Cria o contato do questionário, a não ser que o grupo já tenha alguém com o mesmo e-mail."""
    email = (q.contato_email or "").strip().lower()
    nas_empresas_do_grupo = (
        sa.select(VinculoDeContato.pessoa_id)
        .join(Empresa, Empresa.id == VinculoDeContato.empresa_id)
        .where(Empresa.grupo_id == grupo.id)
    )
    if email and sessao.scalar(sa.select(PessoaContato.id).where(
        PessoaContato.id.in_(nas_empresas_do_grupo), sa.func.lower(PessoaContato.email) == email,
    )):
        return False
    # Contato é ligado só a empresas (`VinculoDeContato`), nunca ao grupo — 01/10/2026.
    sessao.add(PessoaContato(
        nome=q.contato_nome, cargo=q.contato_cargo,
        email=q.contato_email, telefone=q.contato_celular,
        vinculos=[VinculoDeContato(empresa_id=empresa.id)],
    ))
    return True


def importar(sessao: Session, linha: dict[str, Any]) -> QuestionarioRecebido:
    """Grava o questionário e faz o que dá para fazer sem perguntar. Não faz commit."""
    cnpj = _digitos(linha.get("cnpj"))
    razao = _texto(linha.get("razao_social"), 200)
    contato = _texto(linha.get("contato_nome"), 200)
    if len(cnpj) != 14 or not razao or not contato:
        raise LinhaInvalida("sem razão social, CNPJ de 14 dígitos ou nome do contato")
    avaliacao = linha.get("avaliacao") if isinstance(linha.get("avaliacao"), dict) else None
    q = QuestionarioRecebido(
        externo_id=str(linha["id"]), recebido_em=datetime.fromisoformat(str(linha["criado_em"])),
        versao=_texto(linha.get("versao_questionario"), 60) or "—", razao_social=razao,
        nome_fantasia=_texto(linha.get("nome_fantasia"), 200), cnpj=cnpj, contato_nome=contato,
        contato_cargo=_texto(linha.get("contato_cargo"), 100), contato_celular=_texto(linha.get("contato_celular"), 30),
        contato_email=_texto(linha.get("contato_email"), 200),
        respostas=linha.get("respostas") if isinstance(linha.get("respostas"), dict) else {},
        avaliacao_do_site=avaliacao, pdf_base64=linha.get("pdf_base64") or None,
        porte_site=_texto(linha.get("porte_sugerido") or (avaliacao or {}).get("porte_sugerido"), 20),
        situacao=SituacaoDoQuestionario.IMPORTADO, o_que_fez="",
    )
    leitura = leitura_de(q)
    q.porte_crm = leitura.porte

    empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == cnpj))
    if empresa is None:
        nome = q.nome_fantasia or q.razao_social
        homonimo = sessao.scalar(sa.select(GrupoEconomico.nome).where(
            sa.func.lower(GrupoEconomico.nome) == nome.casefold(), GrupoEconomico.fundido_em_id.is_(None),
        ))
        grupo = GrupoEconomico(nome=nome, situacao=SituacaoGrupo.PROSPECT, origem=Origem.QUESTIONARIO)
        sessao.add(grupo)
        sessao.flush()
        empresa = Empresa(
            grupo_id=grupo.id, razao_social=q.razao_social, nome_fantasia=q.nome_fantasia, cnpj=cnpj,
            regime_tributario=leitura.regimes[0][:40] if len(leitura.regimes) == 1 else None,
        )
        sessao.add(empresa)
        sessao.flush()
        _contato(sessao, q, grupo, empresa)
        oportunidade = _nova_oportunidade(sessao, q, grupo, leitura)
        q.cliente_novo, q.grupo_id, q.oportunidade_id = True, grupo.id, oportunidade.id
        q.o_que_fez = 'Criou grupo, empresa, contato e a oportunidade em "Enviar proposta".'
        if homonimo:
            q.o_que_fez += (f' Já existe um grupo chamado "{homonimo}" sem este CNPJ: se for o mesmo cliente, '
                            "use Fundir grupos.")
    else:
        grupo = _grupo_vivo(sessao, sessao.get(GrupoEconomico, empresa.grupo_id))
        q.grupo_id = grupo.id
        aberta = sessao.scalars(
            sa.select(Oportunidade).where(Oportunidade.grupo_id == grupo.id, Oportunidade.situacao.in_(EM_ABERTO))
            .order_by(Oportunidade.criado_em.desc(), Oportunidade.id.desc()).limit(1)
        ).first()
        if aberta is not None:
            q.situacao, q.oportunidade_em_aberto_id = SituacaoDoQuestionario.PRECISA_DE_VOCE, aberta.id
            q.o_que_fez = (f'Já existe oportunidade em aberto para este CNPJ ("{aberta.nome}", {aberta.situacao.value}). '
                           "Não criei outra, para não duplicar. Escolha: anexar a ela ou criar nova.")
        else:
            novo_contato = _contato(sessao, q, grupo, empresa)
            oportunidade = _nova_oportunidade(sessao, q, grupo, leitura)
            q.oportunidade_id = oportunidade.id
            q.o_que_fez = (f'Entrou no grupo "{grupo.nome}"; criou a oportunidade'
                           + (" e o contato." if novo_contato else ". O contato já estava cadastrado."))
    sessao.add(q)
    sessao.flush()
    return q


def _exigir_pendente(q: QuestionarioRecebido) -> None:
    if q.situacao is not SituacaoDoQuestionario.PRECISA_DE_VOCE:
        raise ValueError("este questionário já foi resolvido")


def anexar(sessao: Session, q: QuestionarioRecebido) -> int:
    """Preenche na oportunidade em aberto só o que está vazio. Devolve quantos campos preencheu."""
    _exigir_pendente(q)
    oportunidade = sessao.get(Oportunidade, q.oportunidade_em_aberto_id)
    leitura = leitura_de(q)
    origem = dict(oportunidade.origem_da_volumetria or {})
    preenchidos = 0
    for campo, valor in leitura.volumetria.items():
        if valor is not None and getattr(oportunidade, campo) is None:
            setattr(oportunidade, campo, valor)
            origem[campo] = OrigemDoDado.QUESTIONARIO.value
            preenchidos += 1
    for campo, valor in (("complexidade", leitura.nota_complexidade), ("risco_tecnico", leitura.nota_risco)):
        if getattr(oportunidade, campo) is None:
            setattr(oportunidade, campo, valor)
            preenchidos += 1
    oportunidade.origem_da_volumetria = origem  # dict novo: o JSON só grava se o objeto muda
    empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == q.cnpj))
    _contato(sessao, q, sessao.get(GrupoEconomico, q.grupo_id), empresa)
    q.situacao, q.oportunidade_id = SituacaoDoQuestionario.IMPORTADO, oportunidade.id
    q.o_que_fez = (f'Anexado à oportunidade "{oportunidade.nome}": preencheu {preenchidos} campo(s) vazio(s), '
                   "sem apagar nada do que já estava lá.")
    return preenchidos


def criar_nova(sessao: Session, q: QuestionarioRecebido) -> Oportunidade:
    _exigir_pendente(q)
    grupo = sessao.get(GrupoEconomico, q.grupo_id)
    empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == q.cnpj))
    _contato(sessao, q, grupo, empresa)
    oportunidade = _nova_oportunidade(sessao, q, grupo, leitura_de(q))
    q.situacao, q.oportunidade_id = SituacaoDoQuestionario.IMPORTADO, oportunidade.id
    q.o_que_fez = f'Criou uma oportunidade nova no grupo "{grupo.nome}", ao lado da que já estava em aberto.'
    return oportunidade
