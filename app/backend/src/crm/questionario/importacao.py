"""Um questionário buscado no site vira cliente e oportunidade no CRM (pedido de Eduardo, 01/10/2026).

- O **CNPJ** é a identidade: empresa já cadastrada leva a oportunidade para o grupo dela.
- Grupo com oportunidade **em aberto** não ganha outra sozinho: o questionário fica "Precisa de
  você", e a pessoa escolhe mesclar com a existente ou criar nova. Desde 15/10/2026 vale também para a
  oportunidade aberta do **mesmo contato** (regra D), mesmo sem o CNPJ, e qualquer questionário pode ser
  mesclado com outra oportunidade aberta depois (`crm.questionario.mescla`).
- A oportunidade nasce em "Enviar proposta", com os nove direcionadores marcados como vindos do
  "Questionário". O **porte não é confirmado** aqui: a régua só sugere (`crm.domain.porte`).
- Anexar só preenche o que está vazio na oportunidade existente: nada do que já foi digitado some.
- Pedido de Karine (01/10/2026): a oportunidade nasce **ligada à empresa**; a pessoa que já está na
  base (mesmo e-mail) é **reaproveitada** e só ganha o vínculo com a empresa; e o **endereço** da
  empresa vem do cadastro público do CNPJ, preenchendo só o que está vazio.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from crm.db.modelos import Empresa, GrupoEconomico, Oportunidade, PessoaContato, QuestionarioRecebido, VinculoDeContato
from crm.domain.listas import Origem, OrigemDoDado, Situacao, SituacaoDoQuestionario, SituacaoGrupo, TipoCanal
from crm.questionario.endereco import BuscaDeEndereco
from crm.questionario.leitura import Leitura, ler

__all__ = ["LinhaInvalida", "importar", "anexar", "criar_nova", "leitura_de", "origem_declarada", "EM_ABERTO",
           "CANAL_DE_COMO_CONHECEU"]

EM_ABERTO = (Situacao.ENVIAR_PROPOSTA, Situacao.EM_AVALIACAO, Situacao.ON_HOLD)


CANAL_DE_COMO_CONHECEU: dict[str, TipoCanal | None] = {
    "Indicação de cliente da Critério": TipoCanal.CARTEIRA,
    "Indicação de parceiro (contador, consultor, banco)": TipoCanal.PARCEIROS,
    "Indicação de advogado": TipoCanal.ADVOGADOS,
    "Indicação de sócio ou colaborador da Critério": None,  # Sócios ou Colaboradores: a pessoa escolhe
    "Contato da equipe Critério (ligação, WhatsApp, e-mail)": TipoCanal.PROSPECCAO_ATIVA,
    "Anúncio (Google, Instagram, LinkedIn)": TipoCanal.TRAFEGO_PAGO,
    "Pesquisa no Google ou site da Critério": None,  # sem canal "Orgânico" no CRM (pendência, 12/10/2026)
    "LinkedIn ou Instagram (sem ser anúncio)": None,
    "Evento, palestra ou associação empresarial": None,  # sem canal "Eventos" no CRM (pendência)
    "Outros": None,
}
"""Pergunta "Como conheceu a Critério?" do site (lista aprovada por Eduardo em 12/10/2026), na ordem
do formulário. A escolha vira o tipo de canal da oportunidade quando a tradução é única; nas demais o
tipo fica vazio para a pessoa escolher, e o texto do cliente vai sempre para `canal`."""


def origem_declarada(respostas: dict[str, Any]) -> tuple[TipoCanal | None, str | None]:
    """(tipo de canal, texto do canal) a partir do que o cliente respondeu. Questionário anterior à
    pergunta (v6) devolve (None, None)."""
    escolha = str(respostas.get("como_conheceu") or "").strip()
    if not escolha:
        return None, None
    detalhe = respostas.get("como_conheceu_outros") if escolha == "Outros" else respostas.get("quem_indicou")
    detalhe = str(detalhe or "").strip()
    texto = f"Questionário: {escolha}" + (f" — {detalhe}" if detalhe else "")
    return CANAL_DE_COMO_CONHECEU.get(escolha), texto[:120]


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


def _nova_oportunidade(sessao: Session, q: QuestionarioRecebido, grupo: GrupoEconomico, leitura: Leitura,
                       empresa: Empresa | None = None) -> Oportunidade:
    preenchidos = {k: v for k, v in leitura.volumetria.items() if v is not None}
    oportunidade = Oportunidade(
        grupo_id=grupo.id, empresa_id=empresa.id if empresa else None, nome=(q.nome_fantasia or q.razao_social)[:200], situacao=Situacao.ENVIAR_PROPOSTA,
        data_colocacao=q.recebido_em.date(), origem=Origem.QUESTIONARIO,
        servico_descricao=f"Escopo pedido no questionário: {', '.join(leitura.servicos)}" if leitura.servicos else None,
        servicos_contratados_alem_do_primeiro=leitura.servicos_contratados_alem_do_primeiro,
        tem_consolidacao_de_grupo=leitura.tem_consolidacao_de_grupo, e_auditada=leitura.e_auditada,
        complexidade=leitura.nota_complexidade, risco_tecnico=leitura.nota_risco,
        origem_da_volumetria={k: OrigemDoDado.QUESTIONARIO.value for k in preenchidos},
        **leitura.volumetria,
    )
    oportunidade.tipo_canal, oportunidade.canal = origem_declarada(q.respostas or {})
    sessao.add(oportunidade)
    sessao.flush()
    return oportunidade


def _contato(sessao: Session, q: QuestionarioRecebido, grupo: GrupoEconomico, empresa: Empresa) -> bool:
    """Cria o contato do questionário. Se a pessoa já está na base (mesmo e-mail, em qualquer
    empresa), reaproveita: ganha o vínculo com esta empresa e só os campos vazios são preenchidos
    (base única de contatos, Karine, 01/10/2026). Devolve se criou pessoa nova."""
    email = (q.contato_email or "").strip().lower()
    ja = sessao.scalars(
        sa.select(PessoaContato).where(sa.func.lower(PessoaContato.email) == email).order_by(PessoaContato.id)
    ).first() if email else None
    if ja is not None:
        for campo, valor in (("cargo", q.contato_cargo), ("telefone", q.contato_celular)):
            if valor and not (getattr(ja, campo) or "").strip():
                setattr(ja, campo, valor)
        if empresa is not None and not any(v.empresa_id == empresa.id for v in ja.vinculos):
            ja.vinculos.append(VinculoDeContato(empresa_id=empresa.id))
        return False
    # Contato é ligado só a empresas (`VinculoDeContato`), nunca ao grupo — 01/10/2026.
    sessao.add(PessoaContato(
        nome=q.contato_nome, cargo=q.contato_cargo,
        email=q.contato_email, telefone=q.contato_celular,
        vinculos=[VinculoDeContato(empresa_id=empresa.id)],
    ))
    return True


def _preencher_endereco(empresa: Empresa, buscar_endereco: BuscaDeEndereco | None) -> str:
    """Endereço pelo CNPJ, só nos campos vazios. Devolve a frase para o "o que fez"."""
    campos = ("logradouro", "numero", "complemento", "bairro", "municipio", "uf", "cep")
    if buscar_endereco is None or not empresa.cnpj or all(getattr(empresa, c) for c in ("logradouro", "municipio", "uf", "cep")):
        return ""
    endereco = buscar_endereco(empresa.cnpj)
    if not endereco:
        return " Endereço não encontrado pelo CNPJ: preencha em Contatos."
    preenchidos = 0
    for campo in campos:
        valor = endereco.get(campo)
        if valor and not getattr(empresa, campo):
            setattr(empresa, campo, valor[:2] if campo == "uf" else valor)
            preenchidos += 1
    return " Endereço preenchido pelo CNPJ (cadastro público)." if preenchidos else ""


def _parou_pelo_contato(sessao: Session, q: QuestionarioRecebido) -> bool:
    """Regra D (15/10/2026): antes de criar, procura oportunidade aberta do mesmo contato (e-mail ou celular de quem
    respondeu, ou o lead convertido). Achou: não cria nada e deixa a pessoa escolher entre mesclar e criar nova."""
    from crm.questionario.mescla import par_por_contato  # a mescla usa este módulo: importa aqui para não dar ciclo

    par = par_por_contato(sessao, q)
    if par is None:
        return False
    oportunidade, motivo = par
    q.situacao, q.oportunidade_em_aberto_id = SituacaoDoQuestionario.PRECISA_DE_VOCE, oportunidade.id
    q.o_que_fez = (f'O contato ({motivo}) já está na oportunidade aberta "{oportunidade.nome}" '
                   f"({oportunidade.situacao.value}). Não criei nada, para não duplicar. "
                   "Escolha: mesclar com ela ou criar nova.")
    return True


def _criar_cliente_novo(sessao: Session, q: QuestionarioRecebido, leitura: Leitura,
                        buscar_endereco: BuscaDeEndereco | None) -> Oportunidade:
    """CNPJ que o CRM não conhece: cria grupo, empresa, contato e a oportunidade."""
    nome = q.nome_fantasia or q.razao_social
    homonimo = sessao.scalar(sa.select(GrupoEconomico.nome).where(
        sa.func.lower(GrupoEconomico.nome) == nome.casefold(), GrupoEconomico.fundido_em_id.is_(None),
    ))
    grupo = GrupoEconomico(nome=nome, situacao=SituacaoGrupo.PROSPECT, origem=Origem.QUESTIONARIO)
    sessao.add(grupo)
    sessao.flush()
    empresa = Empresa(
        grupo_id=grupo.id, razao_social=q.razao_social, nome_fantasia=q.nome_fantasia, cnpj=q.cnpj,
        regime_tributario=leitura.regimes[0][:40] if len(leitura.regimes) == 1 else None,
    )
    sessao.add(empresa)
    sessao.flush()
    novo_contato = _contato(sessao, q, grupo, empresa)
    oportunidade = _nova_oportunidade(sessao, q, grupo, leitura, empresa)
    q.cliente_novo, q.grupo_id, q.oportunidade_id = True, grupo.id, oportunidade.id
    q.o_que_fez = ('Criou grupo, empresa, ' + ("contato" if novo_contato else "vinculou o contato que já estava na base")
                   + ' e a oportunidade em "Enviar proposta".' + _preencher_endereco(empresa, buscar_endereco))
    if homonimo:
        q.o_que_fez += (f' Já existe um grupo chamado "{homonimo}" sem este CNPJ: se for o mesmo cliente, '
                        "mescle o questionário com a oportunidade dele.")
    return oportunidade


def importar(sessao: Session, linha: dict[str, Any], buscar_endereco: BuscaDeEndereco | None = None) -> QuestionarioRecebido:
    """Grava o questionário e faz o que dá para fazer sem perguntar. Não faz commit.

    `buscar_endereco` traz o endereço pelo CNPJ (a API passa a BrasilAPI; o teste, uma falsa ou nada)."""
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
        if not _parou_pelo_contato(sessao, q):
            _criar_cliente_novo(sessao, q, leitura, buscar_endereco)
    else:
        grupo = _grupo_vivo(sessao, sessao.get(GrupoEconomico, empresa.grupo_id))
        q.grupo_id = grupo.id
        endereco = _preencher_endereco(empresa, buscar_endereco)
        aberta = sessao.scalars(
            sa.select(Oportunidade).where(Oportunidade.grupo_id == grupo.id, Oportunidade.situacao.in_(EM_ABERTO))
            .order_by(Oportunidade.criado_em.desc(), Oportunidade.id.desc()).limit(1)
        ).first()
        if aberta is not None:
            q.situacao, q.oportunidade_em_aberto_id = SituacaoDoQuestionario.PRECISA_DE_VOCE, aberta.id
            q.o_que_fez = (f'Já existe oportunidade em aberto para este CNPJ ("{aberta.nome}", {aberta.situacao.value}). '
                           "Não criei outra, para não duplicar. Escolha: mesclar com ela ou criar nova." + endereco)
        elif not _parou_pelo_contato(sessao, q):
            novo_contato = _contato(sessao, q, grupo, empresa)
            oportunidade = _nova_oportunidade(sessao, q, grupo, leitura, empresa)
            q.oportunidade_id = oportunidade.id
            q.o_que_fez = (f'Entrou no grupo "{grupo.nome}"; criou a oportunidade'
                           + (" e o contato." if novo_contato else ". O contato já estava cadastrado.") + endereco)
    sessao.add(q)
    sessao.flush()
    return q


def _exigir_pendente(q: QuestionarioRecebido) -> None:
    if q.situacao is not SituacaoDoQuestionario.PRECISA_DE_VOCE:
        raise ValueError("este questionário já foi resolvido")


def anexar(sessao: Session, q: QuestionarioRecebido) -> int:
    """Mescla na oportunidade em aberto que o CRM achou, só preenchendo o vazio. Devolve quantos campos preencheu."""
    from crm.questionario.mescla import mesclar  # a mescla usa este módulo: importa aqui para não dar ciclo

    _exigir_pendente(q)
    return mesclar(sessao, q, sessao.get(Oportunidade, q.oportunidade_em_aberto_id))


def criar_nova(sessao: Session, q: QuestionarioRecebido, buscar_endereco: BuscaDeEndereco | None = None) -> Oportunidade:
    _exigir_pendente(q)
    empresa = sessao.scalar(sa.select(Empresa).where(Empresa.cnpj == q.cnpj))
    if empresa is None:  # a regra D parou antes de criar o cliente: cria agora
        q.situacao, q.oportunidade_em_aberto_id = SituacaoDoQuestionario.IMPORTADO, None
        return _criar_cliente_novo(sessao, q, leitura_de(q), buscar_endereco)
    grupo = _grupo_vivo(sessao, sessao.get(GrupoEconomico, empresa.grupo_id))
    _contato(sessao, q, grupo, empresa)
    oportunidade = _nova_oportunidade(sessao, q, grupo, leitura_de(q), empresa)
    q.situacao, q.oportunidade_id, q.oportunidade_em_aberto_id = SituacaoDoQuestionario.IMPORTADO, oportunidade.id, None
    q.grupo_id = grupo.id
    q.o_que_fez = f'Criou uma oportunidade nova no grupo "{grupo.nome}", ao lado da que já estava em aberto.'
    return oportunidade
