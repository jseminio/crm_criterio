"""A fila de abordagens das contas âncora — o agente SDR (26/09/2026).

O agente prepara ficha e rascunho em segundo plano; a pessoa revisa e aprova.
**Só a rota de aprovação envia**, e só quando todas as conferências de
`crm.domain.abordagem` estão ok. O agente não tem como enviar nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator

import sqlalchemy as sa
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session, sessionmaker

from crm.agente.config import ler_configuracao
from crm.agente.envio import EnvioFalhou, enviar_email
from crm.agente.sdr import AgenteFalhou, AgenteSDR, ContextoDaConta, Uso
from crm.api import esquemas as e
from crm.db.abordagens import ContaNaoInformada, GrupoNaoEncontrado, JaNaFila, enfileirar
from crm.db.base import agora
from crm.db.modelos import (
    Abordagem,
    Empresa,
    ExecucaoDoAgente,
    FichaDeConta,
    GrupoEconomico,
    Oportunidade,
    PessoaContato,
)
from crm.db.sessao import sessao as sessao_de
from crm.domain import abordagem as regras
from crm.domain.listas import CanalDeAbordagem, SituacaoAbordagem

__all__ = ["Servicos", "servicos_reais", "roteador_de_abordagens"]

S = SituacaoAbordagem


@dataclass
class Servicos:
    """O que as rotas usam de fora: o agente e o envio. O teste troca os dois."""

    agente: Callable[[], AgenteSDR]
    """Levanta `AgenteFalhou` com a explicação quando não dá para criar."""
    enviar_email: Callable[..., None] | None
    """`None` quando o envio por e-mail não está configurado no `.env`."""


def servicos_reais() -> Servicos:
    """Lidos do `.env` a cada uso: mudar a chave não exige reiniciar a API."""
    config = ler_configuracao()

    def agente() -> AgenteSDR:
        if not config.chave:
            raise AgenteFalhou(
                "A chave da API da Anthropic não está no .env (ANTHROPIC_API_KEY). "
                "Coloque a chave e tente de novo; nada foi enviado."
            )
        import anthropic

        return AgenteSDR(anthropic.Anthropic(api_key=config.chave), config.modelo)

    envio = None
    if config.email is not None:
        email = config.email

        def envio(**campos) -> None:
            enviar_email(email, **campos)

    return Servicos(agente=agente, enviar_email=envio)


def _mensagem_de_falha(falha: Exception) -> str:
    """Explica a falha da API sem expor chave, corpo de requisição ou dado."""
    if isinstance(falha, AgenteFalhou):
        return str(falha)
    try:
        import anthropic
    except ImportError:  # pragma: no cover — o pacote é dependência
        return f"Falha inesperada no agente ({type(falha).__name__})."
    if isinstance(falha, anthropic.AuthenticationError):
        return "A Anthropic recusou a chave da API. Confira ANTHROPIC_API_KEY no .env."
    if isinstance(falha, anthropic.RateLimitError):
        return "O limite de uso da API foi atingido. Tente de novo em alguns minutos."
    if isinstance(falha, anthropic.APIConnectionError):
        return "Não consegui falar com a Anthropic. A máquina está na internet?"
    if isinstance(falha, anthropic.APIStatusError):
        return f"A API da Anthropic respondeu com erro {falha.status_code}. Tente de novo."
    return f"Falha inesperada no agente ({type(falha).__name__})."


def _bloqueados(sessao: Session) -> set[str]:
    """Destinos de contatos marcados "não contatar", em qualquer grupo."""
    contatos = sessao.scalars(
        sa.select(PessoaContato).where(PessoaContato.nao_contatar.is_(True))
    ).all()
    destinos: set[str] = set()
    for contato in contatos:
        destinos.add(regras.normalizar_destino(CanalDeAbordagem.EMAIL, contato.email))
        destinos.add(regras.normalizar_destino(CanalDeAbordagem.WHATSAPP, contato.telefone))
    destinos.discard("")
    return destinos


def _conferencias(sessao: Session, abordagem: Abordagem) -> list[regras.Conferencia]:
    return regras.conferir(
        canal=abordagem.canal,
        destinatario=abordagem.destinatario,
        assunto=abordagem.assunto,
        mensagem=abordagem.mensagem,
        quem_apresenta=abordagem.quem_apresenta,
        pesquisa=abordagem.ficha.pesquisa if abordagem.ficha else [],
        bloqueados=_bloqueados(sessao),
    )


def _resumo(abordagem: Abordagem) -> e.AbordagemResumo:
    situacao = regras.situacao_exibida(abordagem.situacao, abordagem.quem_apresenta)
    return e.AbordagemResumo(
        id=abordagem.id,
        grupo_id=abordagem.grupo_id,
        grupo_nome=abordagem.grupo.nome,
        mes=abordagem.mes,
        quem_apresenta=abordagem.quem_apresenta,
        canal=abordagem.canal,
        situacao=situacao,
        proximo_passo=regras.proximo_passo(
            situacao, abordagem.diagnostico_agendado_em is not None
        ),
        atualizado_em=abordagem.atualizado_em,
    )


def _detalhe(sessao: Session, abordagem: Abordagem) -> e.AbordagemDetalhe:
    conferencias = _conferencias(sessao, abordagem)
    return e.AbordagemDetalhe(
        **_resumo(abordagem).model_dump(),
        contexto=abordagem.contexto,
        destinatario=abordagem.destinatario,
        assunto=abordagem.assunto,
        mensagem=abordagem.mensagem,
        versao=abordagem.versao,
        erro=abordagem.erro,
        ficha=e.FichaResposta.model_validate(abordagem.ficha) if abordagem.ficha else None,
        conferencias=[e.ConferenciaResposta(**vars(c)) for c in conferencias],
        pode_aprovar=(
            abordagem.situacao is S.AGUARDANDO_APROVACAO and regras.pode_aprovar(conferencias)
        ),
        aprovada_por=abordagem.aprovada_por,
        aprovada_em=abordagem.aprovada_em,
        enviada_em=abordagem.enviada_em,
        diagnostico_agendado_em=abordagem.diagnostico_agendado_em,
        link_whatsapp=(
            regras.link_whatsapp(abordagem.destinatario, abordagem.mensagem)
            if abordagem.canal is CanalDeAbordagem.WHATSAPP
            else None
        ),
    )


def _historico_do_crm(sessao: Session, grupo_id: int) -> list[str]:
    oportunidades = sessao.scalars(
        sa.select(Oportunidade)
        .where(Oportunidade.grupo_id == grupo_id)
        .order_by(Oportunidade.data_colocacao.nulls_last(), Oportunidade.id)
    ).all()
    linhas = []
    for o in oportunidades:
        partes = [
            o.data_colocacao.strftime("%m/%Y") if o.data_colocacao else "sem data",
            " – ".join(p for p in (o.servico or o.nome, o.tipo_servico) if p),
            o.situacao.value,
        ]
        if o.preco_mensal:
            partes.append(f"R$ {o.preco_mensal}/mês")
        if o.motivo_recusa_original:
            partes.append(f"motivo: {o.motivo_recusa_original}")
        linhas.append(" · ".join(partes))
    return linhas


def _contatos(sessao: Session, grupo_id: int) -> list[str]:
    # Ligado ao grupo ou a uma empresa dele — mesma regra da área de Contatos.
    contatos = sessao.scalars(
        sa.select(PessoaContato)
        .outerjoin(Empresa, PessoaContato.empresa_id == Empresa.id)
        .where(sa.func.coalesce(PessoaContato.grupo_id, Empresa.grupo_id) == grupo_id)
        .order_by(PessoaContato.id)
    ).all()
    return [
        f"{c.nome}{' — ' + c.cargo if c.cargo else ''}{' (não contatar)' if c.nao_contatar else ''}"
        for c in contatos
    ]


def _confirmar_antes_de_agendar(sessao: Session) -> None:
    """Grava "Pesquisando" antes de a tarefa em segundo plano começar.

    A tarefa abre outra sessão; sem este commit ela pode rodar antes do da
    requisição, não enxergar "Pesquisando" e sair sem fazer nada — a conta
    ficava presa. Aconteceu no PostgreSQL em 26/09/2026. O SQLite dos testes
    não mostra, porque lá as duas sessões dividem a mesma conexão. Também
    solta a trava `FOR UPDATE`, que a tarefa precisa para gravar o resultado.
    """
    sessao.commit()


def roteador_de_abordagens(
    obter_sessao: Callable[[], Iterator[Session]],
    fabrica: Callable[[], sessionmaker[Session]],
    servicos: Callable[[], Servicos],
) -> APIRouter:
    rota = APIRouter(prefix="/api/abordagens", tags=["abordagens"])

    def _buscar(sessao: Session, abordagem_id: int, *, travar: bool = False) -> Abordagem:
        consulta = sa.select(Abordagem).where(Abordagem.id == abordagem_id)
        if travar:
            # Dois cliques em "Aprovar" não podem enviar duas vezes.
            consulta = consulta.with_for_update()
        abordagem = sessao.scalar(consulta)
        if abordagem is None:
            raise HTTPException(404, "abordagem não encontrada")
        return abordagem

    def _executar_preparo(abordagem_id: int, instrucao: str | None) -> None:
        """Roda depois da resposta: o agente pode levar minutos."""
        fab = fabrica()
        with sessao_de(fab) as s:
            abordagem = s.get(Abordagem, abordagem_id)
            if abordagem is None or abordagem.situacao is not S.PESQUISANDO:
                return
            contexto = ContextoDaConta(
                nome=abordagem.grupo.nome,
                mes=abordagem.mes,
                canal=abordagem.canal,
                quem_apresenta=abordagem.quem_apresenta or "",
                historico_crm=_historico_do_crm(s, abordagem.grupo_id),
                contexto_informado=abordagem.contexto,
                contatos=_contatos(s, abordagem.grupo_id),
            )
            anterior = abordagem.mensagem if instrucao else None

        iniciada_em = agora()
        uso: Uso | None = None
        preparo = None
        erro = None
        try:
            agente = servicos().agente()
            uso = Uso(agente.modelo)
            preparo = agente.preparar(
                contexto, instrucao=instrucao, rascunho_anterior=anterior, uso=uso
            )
        except Exception as falha:  # noqa: BLE001 — toda falha vira situação "Erro" na tela
            erro = _mensagem_de_falha(falha)

        with sessao_de(fab) as s:
            abordagem = s.get(Abordagem, abordagem_id)
            if uso is not None:
                s.add(
                    ExecucaoDoAgente(
                        abordagem_id=abordagem_id,
                        iniciada_em=iniciada_em,
                        terminada_em=agora(),
                        modelo=uso.modelo,
                        tokens_entrada=uso.tokens_entrada,
                        tokens_saida=uso.tokens_saida,
                        buscas_web=uso.buscas_web,
                        custo_usd=uso.custo_usd,
                        deu_certo=erro is None,
                        erro=erro,
                    )
                )
            if abordagem is None or abordagem.situacao is not S.PESQUISANDO:
                return  # descartada enquanto o agente trabalhava
            if erro is not None or preparo is None:
                abordagem.situacao = S.ERRO
                abordagem.erro = erro or "O agente não devolveu a ficha."
                return
            ficha = FichaDeConta(
                grupo_id=abordagem.grupo_id,
                historico=preparo.historico,
                pesquisa=preparo.pesquisa,
                quem_decide=preparo.quem_decide,
                modelo=uso.modelo if uso else "",
            )
            s.add(ficha)
            s.flush()
            abordagem.ficha_id = ficha.id
            abordagem.assunto = (
                (preparo.assunto or None) if abordagem.canal is CanalDeAbordagem.EMAIL else None
            )
            abordagem.mensagem = preparo.mensagem
            abordagem.versao += 1
            abordagem.erro = None
            abordagem.situacao = S.AGUARDANDO_APROVACAO

    @rota.get("", response_model=e.Pagina[e.AbordagemResumo])
    def listar(
        sessao: Session = Depends(obter_sessao),
        mes: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
        situacao: list[SituacaoAbordagem] | None = Query(default=None),
    ) -> e.Pagina[e.AbordagemResumo]:
        consulta = sa.select(Abordagem).join(GrupoEconomico)
        if mes:
            consulta = consulta.where(Abordagem.mes == mes)
        abordagens = sessao.scalars(consulta.order_by(Abordagem.mes, Abordagem.id)).all()
        itens = [_resumo(a) for a in abordagens]
        if situacao:
            # Filtra depois de calcular: "Bloqueada" não existe no banco.
            itens = [i for i in itens if i.situacao in situacao]
        return e.Pagina(total=len(itens), itens=itens)

    @rota.get("/resumo", response_model=e.ResumoDasAbordagens)
    def resumo(
        mes: str = Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
        sessao: Session = Depends(obter_sessao),
    ) -> e.ResumoDasAbordagens:
        abordagens = sessao.scalars(sa.select(Abordagem).where(Abordagem.mes == mes)).all()
        ativas = [a for a in abordagens if a.situacao is not S.DESCARTADA]
        custos = sessao.scalars(
            sa.select(ExecucaoDoAgente.custo_usd)
            .join(Abordagem, ExecucaoDoAgente.abordagem_id == Abordagem.id)
            .where(Abordagem.mes == mes)
        ).all()
        conhecidos = [c for c in custos if c is not None]
        return e.ResumoDasAbordagens(
            mes=mes,
            na_fila=len(ativas),
            abordadas=sum(1 for a in ativas if a.situacao is S.ENVIADA),
            diagnosticos=sum(1 for a in ativas if a.diagnostico_agendado_em is not None),
            aguardando_aprovacao=sum(1 for a in ativas if a.situacao is S.AGUARDANDO_APROVACAO),
            custo_usd=sum(conhecidos) if conhecidos else None,
            custo_parcial=len(conhecidos) < len(custos),
        )

    @rota.post("", response_model=e.AbordagemDetalhe, status_code=201)
    def criar(
        corpo: e.AbordagemNova, sessao: Session = Depends(obter_sessao)
    ) -> e.AbordagemDetalhe:
        try:
            abordagem = enfileirar(sessao, **corpo.model_dump())
        except GrupoNaoEncontrado as falha:
            raise HTTPException(404, str(falha)) from falha
        except ContaNaoInformada as falha:
            raise HTTPException(422, str(falha)) from falha
        except JaNaFila as falha:
            raise HTTPException(409, str(falha)) from falha
        sessao.refresh(abordagem)
        return _detalhe(sessao, abordagem)

    @rota.get("/{abordagem_id}", response_model=e.AbordagemDetalhe)
    def ver(abordagem_id: int, sessao: Session = Depends(obter_sessao)) -> e.AbordagemDetalhe:
        return _detalhe(sessao, _buscar(sessao, abordagem_id))

    @rota.patch("/{abordagem_id}", response_model=e.AbordagemDetalhe)
    def editar(
        abordagem_id: int,
        corpo: e.AbordagemEdicao,
        sessao: Session = Depends(obter_sessao),
    ) -> e.AbordagemDetalhe:
        abordagem = _buscar(sessao, abordagem_id)
        mudancas = corpo.model_dump(exclude_unset=True)
        agendamento = mudancas.pop("diagnostico_agendado_em", None)
        texto_do_envio = {"canal", "destinatario", "assunto", "mensagem"} & mudancas.keys()

        if abordagem.situacao in (S.PESQUISANDO,) and mudancas:
            raise HTTPException(409, "o agente está preparando esta conta; espere terminar")
        if abordagem.situacao in (S.ENVIADA, S.DESCARTADA, S.APROVADA) and texto_do_envio:
            raise HTTPException(409, "a mensagem já foi aprovada; não dá para mudar o texto")
        if "diagnostico_agendado_em" in corpo.model_fields_set:
            if abordagem.situacao is not S.ENVIADA:
                raise HTTPException(422, "diagnóstico só se agenda depois do envio")
            abordagem.diagnostico_agendado_em = agendamento

        for campo, valor in mudancas.items():
            if isinstance(valor, str):
                valor = valor.strip() or None
            setattr(abordagem, campo, valor)
        sessao.flush()
        return _detalhe(sessao, abordagem)

    @rota.post("/{abordagem_id}/preparar", response_model=e.AbordagemDetalhe, status_code=202)
    def preparar(
        abordagem_id: int,
        tarefas: BackgroundTasks,
        sessao: Session = Depends(obter_sessao),
    ) -> e.AbordagemDetalhe:
        abordagem = _buscar(sessao, abordagem_id, travar=True)
        if abordagem.situacao not in (S.A_PREPARAR, S.ERRO):
            raise HTTPException(409, "esta conta não está a preparar")
        if not (abordagem.quem_apresenta or "").strip():
            raise HTTPException(422, "defina quem apresenta a conta antes de preparar")
        abordagem.situacao = S.PESQUISANDO
        abordagem.erro = None
        _confirmar_antes_de_agendar(sessao)
        tarefas.add_task(_executar_preparo, abordagem.id, None)
        return _detalhe(sessao, abordagem)

    @rota.post("/{abordagem_id}/nova-versao", response_model=e.AbordagemDetalhe, status_code=202)
    def nova_versao(
        abordagem_id: int,
        corpo: e.PedidoDeVersao,
        tarefas: BackgroundTasks,
        sessao: Session = Depends(obter_sessao),
    ) -> e.AbordagemDetalhe:
        abordagem = _buscar(sessao, abordagem_id, travar=True)
        if abordagem.situacao is not S.AGUARDANDO_APROVACAO:
            raise HTTPException(409, "só se pede outra versão de um rascunho aguardando aprovação")
        abordagem.situacao = S.PESQUISANDO
        _confirmar_antes_de_agendar(sessao)
        tarefas.add_task(_executar_preparo, abordagem.id, corpo.instrucao)
        return _detalhe(sessao, abordagem)

    @rota.post("/{abordagem_id}/aprovar", response_model=e.AbordagemDetalhe)
    def aprovar(
        abordagem_id: int,
        corpo: e.Aprovacao,
        sessao: Session = Depends(obter_sessao),
    ) -> e.AbordagemDetalhe:
        """A única rota que envia. E-mail sai na hora; WhatsApp fica aprovado
        e a pessoa envia pelo aplicativo com o link pronto."""
        abordagem = _buscar(sessao, abordagem_id, travar=True)
        if abordagem.situacao is not S.AGUARDANDO_APROVACAO:
            raise HTTPException(409, "só se aprova um rascunho aguardando aprovação")
        conferencias = _conferencias(sessao, abordagem)
        if not regras.pode_aprovar(conferencias):
            pendentes = "; ".join(c.texto for c in conferencias if not c.ok)
            raise HTTPException(422, f"ainda há o que resolver antes de aprovar: {pendentes}")

        if abordagem.canal is CanalDeAbordagem.EMAIL:
            envio = servicos().enviar_email
            if envio is None:
                raise HTTPException(
                    409,
                    "o envio por e-mail não está configurado: preencha CRM_M365_* no .env",
                )
            try:
                envio(
                    para=abordagem.destinatario,
                    assunto=abordagem.assunto or "",
                    corpo=abordagem.mensagem or "",
                )
            except EnvioFalhou as falha:
                raise HTTPException(502, str(falha)) from falha

        momento = agora()
        abordagem.aprovada_por = corpo.aprovador
        abordagem.aprovada_em = momento
        if abordagem.canal is CanalDeAbordagem.EMAIL:
            abordagem.situacao = S.ENVIADA
            abordagem.enviada_em = momento
        else:
            abordagem.situacao = S.APROVADA
        sessao.flush()
        return _detalhe(sessao, abordagem)

    @rota.post("/{abordagem_id}/marcar-enviada", response_model=e.AbordagemDetalhe)
    def marcar_enviada(
        abordagem_id: int, sessao: Session = Depends(obter_sessao)
    ) -> e.AbordagemDetalhe:
        abordagem = _buscar(sessao, abordagem_id, travar=True)
        if abordagem.situacao is not S.APROVADA:
            raise HTTPException(409, "só se marca como enviada uma mensagem aprovada no WhatsApp")
        abordagem.situacao = S.ENVIADA
        abordagem.enviada_em = agora()
        sessao.flush()
        return _detalhe(sessao, abordagem)

    @rota.post("/{abordagem_id}/descartar", response_model=e.AbordagemDetalhe)
    def descartar(
        abordagem_id: int, sessao: Session = Depends(obter_sessao)
    ) -> e.AbordagemDetalhe:
        abordagem = _buscar(sessao, abordagem_id, travar=True)
        if abordagem.situacao in (S.ENVIADA, S.DESCARTADA):
            raise HTTPException(409, "esta abordagem já foi enviada ou descartada")
        abordagem.situacao = S.DESCARTADA
        sessao.flush()
        return _detalhe(sessao, abordagem)

    return rota
