"""O SDR de IA: registro das conversas com os leads e o painel — 27/09/2026.

Quem chama as rotas de conversa é a integração do canal (WhatsApp ou e-mail),
a cada mensagem que entra ou sai. Decisão de Eduardo em 27/09/2026: o SDR de
IA **envia sozinho**. As travas que antes dependiam da aprovação passam a
valer aqui, no servidor, em cada mensagem:

- nada sai para lead marcado "não contatar" (409);
- mensagem da IA não fala de preço (422);
- conversa encerrada não recebe mensagem da IA (409), salvo o lembrete e o
  agradecimento do questionário.

Questionário de volumetria (06/10/2026): a mensagem com o link marca o envio;
`GET /api/sdr/questionario/pendentes` diz a quem lembrar (2 dias úteis sem
resposta, em horário comercial) ou agradecer (respondeu), e o servidor recusa lembrete ou
agradecimento fora do passo (409). Regras em `crm.domain.questionario_do_lead`.

O painel (`GET /api/sdr/painel`) só lê: é `crm.domain.sdr.calcular_painel`
sobre os leads do mês.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from decimal import Decimal
from typing import Callable, Iterator

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from crm.agente.config import ler_configuracao
from crm.agente.disparo_do_questionario import Canais, disparar
from crm.api import esquemas as e
from crm.api.disparo_do_questionario import ESTADO_DO_DISPARO, canais_reais
from crm.db import leads as regras_do_lead
from crm.db import questionario_do_lead as do_lead
from crm.db.base import agora
from crm.db.modelos import (
    ConversaDoSdr,
    InvestimentoEmMidia,
    Lead,
    MensagemDoSdr,
    ParametrosDoSdr,
)
from crm.domain import questionario_do_lead as questionario
from crm.domain import sdr as regras
from crm.domain.listas import AutorDaMensagem, DesfechoDaConversa, SituacaoLead
from crm.domain.servicos import problema_no_tema

__all__ = ["roteador"]

_SO_DA_IA = ("intencao", "confianca", "termo_nao_reconhecido", "custo_usd", "questionario")


def _situacao(lead: Lead, recebidos: list, momento: datetime) -> e.QuestionarioDoLead:
    atual = do_lead.situacao(lead, recebidos, momento)
    return e.QuestionarioDoLead(
        lead_id=lead.id,
        passo=atual.passo,
        enviado_em=lead.questionario_enviado_em,
        respondido_em=atual.respondido_em,
        lembrado_em=lead.questionario_lembrado_em,
        agradecido_em=lead.questionario_agradecido_em,
        lembrar_a_partir_de=atual.lembrar_a_partir_de,
    )


def roteador(
    obter_sessao: Callable[[], Iterator[Session]],
    canais_do_disparo: Callable[[], Canais | None] = canais_reais,
) -> APIRouter:
    r = APIRouter(prefix="/api/sdr", tags=["sdr"])

    def _conversa(sessao: Session, conversa_id: int) -> ConversaDoSdr:
        conversa = sessao.get(ConversaDoSdr, conversa_id)
        if conversa is None:
            raise HTTPException(404, "conversa não encontrada")
        return conversa

    # --------------------------------------------------------- conversas
    @r.post("/conversas", response_model=e.ConversaResposta, status_code=201)
    def abrir_conversa(corpo: e.ConversaNova, sessao: Session = Depends(obter_sessao, scope="function")):
        lead = sessao.get(Lead, corpo.lead_id)
        if lead is None:
            raise HTTPException(404, "lead não encontrado")
        if lead.nao_contatar:
            raise HTTPException(409, 'o lead pediu para não ser contatado')
        if lead.convertido_em_id is not None:
            raise HTTPException(409, "este lead já virou oportunidade: a conversa agora é da equipe")
        aberta = sessao.scalar(
            sa.select(ConversaDoSdr.id).where(
                ConversaDoSdr.lead_id == lead.id, ConversaDoSdr.desfecho.is_(None)
            )
        )
        if aberta is not None:
            raise HTTPException(409, f"o lead já tem uma conversa em andamento ({aberta})")
        conversa = ConversaDoSdr(lead_id=lead.id, canal=corpo.canal, iniciada_em=agora())
        sessao.add(conversa)
        sessao.flush()
        return e.ConversaResposta.model_validate(conversa)

    @r.get("/leads/{lead_id}/conversas", response_model=list[e.ConversaResposta])
    def conversas_do_lead(lead_id: int, sessao: Session = Depends(obter_sessao, scope="function")):
        if sessao.get(Lead, lead_id) is None:
            raise HTTPException(404, "lead não encontrado")
        conversas = sessao.scalars(
            sa.select(ConversaDoSdr)
            .where(ConversaDoSdr.lead_id == lead_id)
            .options(selectinload(ConversaDoSdr.mensagens))
            .order_by(ConversaDoSdr.id)
        ).all()
        return [e.ConversaResposta.model_validate(c) for c in conversas]

    @r.post(
        "/conversas/{conversa_id}/mensagens", response_model=e.MensagemResposta, status_code=201
    )
    def registrar_mensagem(
        conversa_id: int, corpo: e.MensagemNova, sessao: Session = Depends(obter_sessao, scope="function")
    ):
        conversa = _conversa(sessao, conversa_id)
        lead = conversa.lead
        dados = corpo.model_dump(exclude_unset=True)

        momento = agora()
        if corpo.autor is AutorDaMensagem.IA:
            # Lembrete e agradecimento do questionário saem também depois do encerramento: o
            # lead costuma pedir a proposta no fim da conversa (06/10/2026).
            if conversa.desfecho is not None and corpo.questionario is None:
                raise HTTPException(409, "a conversa está encerrada: a IA não fala mais nela")
            if corpo.questionario is not None:
                passo = _situacao(lead, do_lead.recebidos(sessao), momento).passo
                if passo is not questionario.PASSO_DA_MENSAGEM[corpo.questionario]:
                    raise HTTPException(409, questionario.por_que_nao(passo))
            problema = regras.problema_na_mensagem(corpo.texto)
            if problema:
                raise HTTPException(422, problema)
            if corpo.tom is not None:
                raise HTTPException(422, "o tom só vale para mensagem do lead")
        else:
            usados = [c for c in (*_SO_DA_IA, "fallback") if dados.get(c) not in (None, False)]
            if usados:
                raise HTTPException(422, f"só a mensagem da IA leva: {', '.join(usados)}")
            if corpo.autor is AutorDaMensagem.EQUIPE and corpo.tom is not None:
                raise HTTPException(422, "o tom só vale para mensagem do lead")

        if corpo.autor is not AutorDaMensagem.LEAD and lead.nao_contatar:
            raise HTTPException(409, "o lead pediu para não ser contatado")

        dados.pop("questionario", None)
        mensagem = MensagemDoSdr(conversa_id=conversa.id, enviada_em=momento, **dados)
        sessao.add(mensagem)

        if corpo.questionario is questionario.MensagemDoQuestionario.LEMBRETE:
            lead.questionario_lembrado_em = momento
        elif corpo.questionario is questionario.MensagemDoQuestionario.AGRADECIMENTO:
            lead.questionario_agradecido_em = momento
        if (
            corpo.autor is not AutorDaMensagem.LEAD
            and lead.questionario_enviado_em is None
            and questionario.tem_o_link(corpo.texto, do_lead.links_do_questionario())
        ):
            lead.questionario_enviado_em = momento

        if corpo.autor is AutorDaMensagem.LEAD and lead.situacao is SituacaoLead.NOVO:
            lead.situacao = SituacaoLead.EM_CONTATO
        # A primeira mensagem da equipe depois do transbordo encerra a espera.
        if (
            corpo.autor is AutorDaMensagem.EQUIPE
            and conversa.desfecho is DesfechoDaConversa.TRANSBORDO
            and conversa.atendida_em is None
        ):
            conversa.atendida_em = momento
        sessao.flush()
        return e.MensagemResposta.model_validate(mensagem)

    # ------------------------------------------------------ questionário
    @r.get("/leads/{lead_id}/questionario", response_model=e.QuestionarioDoLead)
    def questionario_do_lead(lead_id: int, sessao: Session = Depends(obter_sessao, scope="function")):
        """Em que passo está o questionário do lead, pelo que o CRM sabe. A integração entrega isto à IA."""
        lead = sessao.get(Lead, lead_id)
        if lead is None:
            raise HTTPException(404, "lead não encontrado")
        return _situacao(lead, do_lead.recebidos(sessao), agora())

    @r.get("/questionario/pendentes", response_model=list[e.PendenciaDoQuestionario])
    def questionario_pendente(sessao: Session = Depends(obter_sessao, scope="function")):
        """A quem a IA deve lembrar ou agradecer agora. Fica fora quem pediu para não ser contatado."""
        return [
            e.PendenciaDoQuestionario(
                lead_id=p.lead.id, nome=p.lead.nome, conversa_id=p.conversa.id, canal=p.conversa.canal,
                passo=p.situacao.passo, enviado_em=p.lead.questionario_enviado_em,
                respondido_em=p.situacao.respondido_em,
            )
            for p in do_lead.pendentes(sessao, agora())
        ]

    @r.get("/questionario/disparo", response_model=e.EstadoDoDisparoResposta)
    def estado_do_disparo():
        """A última rodada do disparo automático: quantos saíram, avisos e erros."""
        return ESTADO_DO_DISPARO.retrato()

    @r.post("/questionario/disparar", response_model=e.EstadoDoDisparoResposta)
    def disparar_agora(sessao: Session = Depends(obter_sessao, scope="function")):
        """Uma rodada agora, sem esperar os 10 minutos. Só com o disparo ligado e em horário comercial."""
        canais = canais_do_disparo()
        if canais is None:
            raise HTTPException(409, "o disparo está desligado: ligue com CRM_DISPARO_DO_QUESTIONARIO=true")
        resultado = disparar(sessao, canais, agora(), ler_configuracao().link_do_questionario)
        ESTADO_DO_DISPARO.registrar(ligado=True, resultado=resultado)
        return ESTADO_DO_DISPARO.retrato()

    @r.post("/conversas/{conversa_id}/encerrar", response_model=e.ConversaResposta)
    def encerrar(conversa_id: int, corpo: e.Encerramento, sessao: Session = Depends(obter_sessao, scope="function")):
        conversa = _conversa(sessao, conversa_id)
        if conversa.desfecho is not None:
            raise HTTPException(409, "a conversa já foi encerrada")
        lead = conversa.lead
        D = DesfechoDaConversa

        if corpo.desfecho is not D.TRANSBORDO and (corpo.motivo_transbordo or corpo.destino_transbordo):
            raise HTTPException(422, "motivo e destino do transbordo só valem para transbordo")
        if corpo.desfecho is not D.FORA_DO_PERFIL and corpo.motivo_descarte:
            raise HTTPException(422, "o motivo de descarte só vale para lead fora do perfil")
        if corpo.desfecho is D.TRANSBORDO and not (corpo.motivo_transbordo and corpo.destino_transbordo):
            raise HTTPException(422, "para passar para a equipe, informe o motivo e o destino")
        # O veredito da IA muda a situação do lead — um lead que já virou
        # oportunidade tem a situação decidida por ela.
        if corpo.desfecho.veredito_da_ia and lead.convertido_em_id is not None:
            raise HTTPException(409, "este lead já virou oportunidade")

        try:
            if corpo.porte_estimado is not None:
                lead.porte_estimado = regras_do_lead.validar_porte(corpo.porte_estimado)
            if corpo.cnpj is not None:
                lead.cnpj = corpo.cnpj
            if corpo.interesse is not None:
                problema = problema_no_tema(corpo.interesse, corpo.interesse_tema, exigir=True)
                if problema:
                    raise regras_do_lead.RegraDoLead(problema)
                lead.interesse = corpo.interesse
                lead.interesse_tema = (corpo.interesse_tema or "").strip() or None
            if corpo.desfecho is D.QUALIFICADO:
                regras_do_lead.qualificar(lead)
            elif corpo.desfecho is D.FORA_DO_PERFIL:
                regras_do_lead.descartar(lead, corpo.motivo_descarte)
        except regras_do_lead.RegraDoLead as problema:
            raise HTTPException(problema.status, str(problema)) from problema

        conversa.desfecho = corpo.desfecho
        conversa.encerrada_em = agora()
        conversa.motivo_transbordo = corpo.motivo_transbordo
        conversa.destino_transbordo = corpo.destino_transbordo
        sessao.flush()
        return e.ConversaResposta.model_validate(conversa)

    @r.post("/conversas/{conversa_id}/nota", response_model=e.ConversaResposta)
    def dar_nota(conversa_id: int, corpo: e.NotaDaConversa, sessao: Session = Depends(obter_sessao, scope="function")):
        conversa = _conversa(sessao, conversa_id)
        if conversa.desfecho is None:
            raise HTTPException(409, "a nota vem depois que a conversa termina")
        if conversa.nota is not None:
            raise HTTPException(409, "esta conversa já tem nota")
        conversa.nota = corpo.nota
        sessao.flush()
        return e.ConversaResposta.model_validate(conversa)

    # ----------------------------------------------------- custos e mídia
    def _parametros(sessao: Session) -> ParametrosDoSdr | None:
        return sessao.scalar(sa.select(ParametrosDoSdr).order_by(ParametrosDoSdr.id).limit(1))

    @r.get("/parametros", response_model=e.ParametrosDoSdrResposta)
    def ler_parametros(sessao: Session = Depends(obter_sessao, scope="function")):
        atual = _parametros(sessao)
        return e.ParametrosDoSdrResposta.model_validate(atual) if atual else e.ParametrosDoSdrResposta()

    @r.put("/parametros", response_model=e.ParametrosDoSdrResposta)
    def gravar_parametros(corpo: e.ParametrosDoSdrEdicao, sessao: Session = Depends(obter_sessao, scope="function")):
        atual = _parametros(sessao)
        if atual is None:
            atual = ParametrosDoSdr()
            sessao.add(atual)
        for campo, valor in corpo.model_dump().items():
            setattr(atual, campo, valor)
        sessao.flush()
        return e.ParametrosDoSdrResposta.model_validate(atual)

    @r.get("/midia", response_model=list[e.InvestimentoResposta])
    def listar_midia(
        mes: str = Query(pattern=regras.MES.pattern), sessao: Session = Depends(obter_sessao, scope="function")
    ):
        itens = sessao.scalars(
            sa.select(InvestimentoEmMidia)
            .where(InvestimentoEmMidia.mes == mes)
            .order_by(InvestimentoEmMidia.canal)
        ).all()
        return [e.InvestimentoResposta.model_validate(i) for i in itens]

    @r.put("/midia", response_model=e.InvestimentoResposta)
    def gravar_midia(corpo: e.InvestimentoEdicao, sessao: Session = Depends(obter_sessao, scope="function")):
        canal = corpo.canal.strip()
        atual = sessao.scalar(
            sa.select(InvestimentoEmMidia).where(
                InvestimentoEmMidia.mes == corpo.mes, InvestimentoEmMidia.canal == canal
            )
        )
        if atual is None:
            atual = InvestimentoEmMidia(mes=corpo.mes, canal=canal, valor=corpo.valor)
            sessao.add(atual)
        else:
            atual.valor = corpo.valor
        sessao.flush()
        return e.InvestimentoResposta.model_validate(atual)

    # ------------------------------------------------------------- painel
    def _calcular(sessao: Session, mes: str, origem: str | None, anterior: regras.Resumo | None):
        inicio, fim = regras.intervalo_do_mes(mes)
        leads = sessao.scalars(
            sa.select(Lead)
            .where(Lead.criado_em >= inicio, Lead.criado_em < fim)
            .options(selectinload(Lead.conversas).selectinload(ConversaDoSdr.mensagens))
        ).all()
        midia = {
            i.canal: Decimal(i.valor)
            for i in sessao.scalars(
                sa.select(InvestimentoEmMidia).where(InvestimentoEmMidia.mes == mes)
            )
        }
        parametros = _parametros(sessao)
        return regras.calcular_painel(
            mes=mes,
            leads=leads,
            midia=midia,
            origem=origem,
            custo_hora_sdr=parametros.custo_hora_sdr if parametros else None,
            minutos_por_conversa=parametros.minutos_por_conversa if parametros else None,
            cotacao_dolar=parametros.cotacao_dolar if parametros else None,
            anterior=anterior,
        )

    @r.get("/painel")
    def painel(
        mes: str = Query(pattern=regras.MES.pattern),
        origem: str | None = Query(
            default=None, pattern=f"^({regras.ORIGEM_TRAFEGO_PAGO}|{regras.ORIGEM_FRIO})$"
        ),
        sessao: Session = Depends(obter_sessao, scope="function"),
    ) -> dict:
        """Os números da coorte do mês e o resumo do mês anterior, para a variação."""
        anterior = regras.resumir(_calcular(sessao, regras.mes_anterior(mes), origem, None))
        return asdict(_calcular(sessao, mes, origem, anterior))

    return r
