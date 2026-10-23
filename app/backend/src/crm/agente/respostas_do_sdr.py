"""As respostas do SDR de IA no WhatsApp — fase 1 (amostra aprovada por Eduardo em 23/10/2026).

O laço (`crm.api.respostas_do_sdr`) chama `rodar_uma_vez` a cada poucos segundos. Para cada conversa com
mensagem do lead ainda sem resposta, em três passos, sem segurar o banco enquanto a IA pensa:

1. **Lê** a conversa e confere o que não depende de IA: não contatar e janela fechada (não responde), lead
   que já virou oportunidade (vai para a equipe, em silêncio), máximo de respostas e teto de custo (vai
   para a equipe com a frase de passagem).
2. **Decide** pelo roteador (`crm.agente.roteador_do_sdr`).
3. **Grava e envia**, conferindo antes se nada mudou: se o lead escreveu de novo ou a equipe assumiu no
   meio, a resposta não sai (fica registrada como descartada, com o custo). No modo **supervisionado** a
   resposta vira rascunho, que a equipe envia ou descarta; no **automático**, sai na hora.

E o que a equipe faz na tela: responder ao lead, enviar ou descartar o rascunho, devolver a conversa à IA.
**Nada sai para quem pediu para não ser contatado, nem fora da janela de 24 horas.** Nada de conteúdo no
log: só contagens e o tipo da falha.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session, selectinload

from crm.agente.ensaio_sdr import montar_contexto
from crm.agente.envio import EnvioFalhou
from crm.agente.prompt_do_sdr import PROMPT_DO_ROTEIRO
from crm.agente.recebimento import LIMITE_DO_TEXTO
from crm.agente.roteador_do_sdr import (
    Clientes, ConfiguracaoDasRespostas, Passagem, Pedido, Resposta, cabecalho_do_lead, decidir, formatar_conversa,
    passagem_do_servidor,
)
from crm.agente.sdr import AgenteFalhou
from crm.db import questionario_do_lead as do_lead
from crm.db.modelos import ConversaDoSdr, FichaDaBase, Lead, MensagemDoSdr
from crm.domain import questionario_do_lead as questionario
from crm.domain.abordagem import normalizar_destino
from crm.domain.listas import AutorDaMensagem, CanalDeAbordagem, DesfechoDaConversa
from crm.domain.listas import DestinoDoTransbordo as D
from crm.domain.listas import MotivoDeTransbordo as M
from crm.domain.servicos import servico_do_catalogo

__all__ = [
    "FRASE_DE_PASSAGEM", "JANELA", "NAO_SAIU", "Enviar", "RegraDaResposta", "Rodada", "conversas_pendentes",
    "descartar_rascunho", "devolver_para_a_ia", "enviar_rascunho", "janela_do_lead", "responder_pela_equipe",
    "rodar_uma_vez", "saiu", "situacao_das_respostas",
]

_log = logging.getLogger(__name__)

_BRASILIA = ZoneInfo("America/Sao_Paulo")
JANELA = timedelta(hours=24)
NAO_SAIU = ("rascunho", "descartada", "bloqueada")
"""As respostas da IA que o lead não recebeu. Ficam registradas (com o custo), fora da conversa que a IA lê."""
LOTE = 20
HISTORICO = 40
FRASE_DE_PASSAGEM = "Vou passar a conversa para a nossa equipe, que continua com você por aqui."

Enviar = Callable[[str, str], str]
"""(número só com dígitos, texto) → id da mensagem na Meta. Levanta `EnvioFalhou`."""


class RegraDaResposta(Exception):
    def __init__(self, status: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status


def saiu(m: MensagemDoSdr) -> bool:
    return m.entrega not in NAO_SAIU


def _utc(d: datetime) -> datetime:
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def janela_do_lead(lead: Lead) -> datetime | None:
    """Até quando vale texto livre: 24 horas desde a última mensagem do lead em qualquer conversa do WhatsApp."""
    ultimas = [_utc(c.ultima_do_lead_em) for c in lead.conversas
               if c.canal is CanalDeAbordagem.WHATSAPP and c.ultima_do_lead_em]
    return max(ultimas) + JANELA if ultimas else None


def _ultimo_id(conversa: ConversaDoSdr, do_lead_: bool) -> int:
    return max((m.id for m in conversa.mensagens if (m.autor is AutorDaMensagem.LEAD) == do_lead_), default=0)


def _pendente(conversa: ConversaDoSdr) -> bool:
    """O lead escreveu depois da última mensagem da Critério (enviada, rascunho ou barrada)."""
    return _ultimo_id(conversa, True) > _ultimo_id(conversa, False)


def conversas_pendentes(sessao: Session, momento: datetime, cfg: ConfiguracaoDasRespostas) -> list[int]:
    """As conversas que a IA deve responder agora: WhatsApp, em andamento, com a IA, o lead parado há pelo
    menos a espera e com mensagem sem resposta."""
    conversas = sessao.scalars(
        sa.select(ConversaDoSdr)
        .where(ConversaDoSdr.canal == CanalDeAbordagem.WHATSAPP, ConversaDoSdr.desfecho.is_(None),
               ConversaDoSdr.equipe_desde.is_(None), ConversaDoSdr.ultima_do_lead_em.is_not(None))
        .options(selectinload(ConversaDoSdr.mensagens))
        .order_by(ConversaDoSdr.ultima_do_lead_em, ConversaDoSdr.id)
    ).all()
    # As horas são conferidas aqui, com fuso: o SQLite dos testes guarda a hora sem ele.
    return [c.id for c in conversas
            if momento - JANELA < _utc(c.ultima_do_lead_em) <= momento - cfg.espera and _pendente(c)][:LOTE]


# ------------------------------------------------------------------ 1. ler
@dataclass(frozen=True)
class _Retrato:
    conversa_id: int
    ultimo_id: int
    destino: D
    pedido: Pedido | None = None
    pronta: Resposta | None = None


def _destino_do_servico(lead: Lead) -> D:
    servico = servico_do_catalogo(lead.interesse)
    return servico.transbordo if servico else D.COMERCIAL_C1


def _quando(d: datetime) -> str:
    return _utc(d).astimezone(_BRASILIA).strftime("%d/%m %H:%M")


_QUEM = {AutorDaMensagem.LEAD: "Lead", AutorDaMensagem.IA: "Critério (IA)", AutorDaMensagem.EQUIPE: "Critério (equipe)"}


def _texto_do_pedido(sessao: Session, lead: Lead, mensagens: list[MensagemDoSdr], momento: datetime) -> str:
    passo = do_lead.situacao(lead, do_lead.recebidos(sessao), momento).passo
    cabecalho = cabecalho_do_lead(lead.interesse, lead.interesse_tema,
                                  lead.tipo_canal.value if lead.tipo_canal else None, passo.value)
    return formatar_conversa(cabecalho, [(_quando(m.enviada_em), _QUEM[m.autor], m.texto) for m in mensagens])


def _sistema(sessao: Session, momento: datetime, link: str) -> str:
    fichas = list(sessao.scalars(sa.select(FichaDaBase).order_by(FichaDaBase.id)))
    hoje = _utc(momento).astimezone(_BRASILIA).date()
    return montar_contexto(PROMPT_DO_ROTEIRO, fichas, hoje, link)[0]


def _retratar(sessao: Session, conversa: ConversaDoSdr, momento: datetime, cfg: ConfiguracaoDasRespostas,
              link: str) -> _Retrato | None:
    lead = conversa.lead
    janela = janela_do_lead(lead)
    if lead.nao_contatar or janela is None or janela <= momento or not _pendente(conversa):
        return None
    destino = _destino_do_servico(lead)
    ultimo = max((m.id for m in conversa.mensagens), default=0)

    def pronta(texto: str | None, passagem: Passagem) -> _Retrato:
        return _Retrato(conversa.id, ultimo, destino, pronta=Resposta(rota="regra", texto=texto, passagem=passagem))

    if lead.convertido_em_id is not None:
        return pronta(None, passagem_do_servidor("O lead já virou oportunidade: a conversa é da equipe", None, destino))
    da_ia = [m for m in conversa.mensagens if m.autor is AutorDaMensagem.IA and m.rota]
    if sum(1 for m in da_ia if m.entrega != "descartada") >= cfg.maximo_de_respostas:
        return pronta(FRASE_DE_PASSAGEM, passagem_do_servidor("Chegou ao máximo de respostas da IA", M.OUTRO, destino))
    if sum((m.custo_usd or Decimal(0) for m in da_ia), Decimal(0)) >= cfg.teto_por_conversa:
        return pronta(FRASE_DE_PASSAGEM, passagem_do_servidor("Chegou ao teto de custo da conversa", M.OUTRO, destino))

    todas = sorted((m for c in lead.conversas if c.canal is CanalDeAbordagem.WHATSAPP for m in c.mensagens),
                   key=lambda m: (_utc(m.enviada_em), m.id))
    vistas = [m for m in todas if saiu(m)][-HISTORICO:]
    ultimo_da_criterio = _ultimo_id(conversa, False)
    pendente = "\n".join(m.texto for m in conversa.mensagens
                         if m.autor is AutorDaMensagem.LEAD and m.id > ultimo_da_criterio)
    primeira = not any(m.autor is AutorDaMensagem.IA and saiu(m) and "assistente virtual" in m.texto.casefold()
                       for m in todas)
    pedido = Pedido(
        sistema=_sistema(sessao, momento, link), conversa=_texto_do_pedido(sessao, lead, vistas, momento),
        pendente=pendente, primeira=primeira, links_permitidos=do_lead.links_do_questionario(),
        destino_do_servico=destino,
    )
    return _Retrato(conversa.id, ultimo, destino, pedido=pedido)


# ------------------------------------------------------------------ 3. gravar e enviar
def _passar(conversa: ConversaDoSdr, passagem: Passagem, momento: datetime) -> None:
    conversa.equipe_desde = momento
    conversa.equipe_motivo = passagem.tela[:160]
    conversa.destino_transbordo = passagem.destino
    if passagem.motivo is not None and conversa.desfecho is None:
        conversa.desfecho = DesfechoDaConversa.TRANSBORDO
        conversa.encerrada_em = momento
        conversa.motivo_transbordo = passagem.motivo


def _numero(lead: Lead) -> str:
    numero = normalizar_destino(CanalDeAbordagem.WHATSAPP, lead.telefone) if lead.telefone else ""
    if not numero:
        raise EnvioFalhou("O lead não tem telefone.")
    return numero


def _enviar(enviar: Enviar | None, lead: Lead, texto: str) -> str:
    if enviar is None:
        raise EnvioFalhou("O WhatsApp não está configurado em Configurações › Integrações.")
    return enviar(_numero(lead), texto)


def _marcar_questionario(lead: Lead, texto: str, momento: datetime) -> None:
    if lead.questionario_enviado_em is None and questionario.tem_o_link(texto, do_lead.links_do_questionario()):
        lead.questionario_enviado_em = momento


def _aplicar(sessao: Session, retrato: _Retrato, resposta: Resposta, cfg: ConfiguracaoDasRespostas,
             enviar: Enviar | None, momento: datetime, rodada: "Rodada") -> None:
    conversa = sessao.get(ConversaDoSdr, retrato.conversa_id, with_for_update=True, populate_existing=True)
    if conversa is None:
        return
    lead = conversa.lead
    ultimo = max((m.id for m in conversa.mensagens), default=0)

    def registrar(**campos) -> MensagemDoSdr:
        m = MensagemDoSdr(conversa_id=conversa.id, autor=AutorDaMensagem.IA, enviada_em=momento, **campos)
        sessao.add(m)
        return m

    if conversa.equipe_desde is not None or conversa.desfecho is not None or lead.nao_contatar or ultimo != retrato.ultimo_id:
        if resposta.custo_usd:
            registrar(texto=resposta.bloqueada or resposta.texto or "(sem texto)", entrega="descartada",
                      rota=resposta.rota, modelo=resposta.modelo, custo_usd=resposta.custo_usd,
                      observacao="Não saiu: o lead escreveu de novo ou a equipe assumiu antes")
        return

    for m in conversa.mensagens:
        if m.autor is AutorDaMensagem.IA and m.entrega == "rascunho":
            m.entrega, m.observacao = "descartada", "Substituído por uma resposta nova"
    custo = resposta.custo_usd
    passagem = resposta.passagem
    if resposta.bloqueada:
        registrar(texto=resposta.bloqueada[:LIMITE_DO_TEXTO], entrega="bloqueada", rota=resposta.rota,
                  modelo=resposta.modelo, custo_usd=custo, intencao=resposta.intencao,
                  observacao=(resposta.motivo_do_bloqueio or "")[:300])
        custo = None
    if resposta.texto:
        m = registrar(texto=resposta.texto[:LIMITE_DO_TEXTO], rota="trava" if resposta.bloqueada else resposta.rota,
                      modelo=None if resposta.bloqueada else resposta.modelo, custo_usd=custo,
                      intencao=resposta.intencao)
        if cfg.supervisionado:
            m.entrega = "rascunho"
            rodada.rascunhos += 1
        else:
            sessao.flush()  # grava antes de enviar: se a gravação falhar, nada sai (e nada sai duas vezes)
            try:
                m.externo_id = _enviar(enviar, lead, m.texto)[:128] or None
                m.entrega = "enviada"
                _marcar_questionario(lead, m.texto, momento)
                rodada.respondidas += 1
            except EnvioFalhou as falha:
                m.entrega, m.observacao = "falhou", str(falha)[:300]
                passagem = passagem_do_servidor("O WhatsApp não enviou a resposta da IA", M.SISTEMA_FORA,
                                                retrato.destino)
    if passagem is not None:
        _passar(conversa, passagem, momento)
        rodada.para_a_equipe += 1
    sessao.flush()


# ------------------------------------------------------------------ a rodada
@dataclass
class Rodada:
    respondidas: int = 0
    rascunhos: int = 0
    para_a_equipe: int = 0
    erros: list[str] = field(default_factory=list)


def _responder(fabrica: Callable[[], Session], conversa_id: int, cfg: ConfiguracaoDasRespostas,
               clientes: Callable[[], Clientes], enviar: Enviar | None, agora: Callable[[], datetime], link: str,
               rodada: Rodada) -> None:
    with fabrica() as sessao:
        conversa = sessao.get(ConversaDoSdr, conversa_id)
        retrato = _retratar(sessao, conversa, agora(), cfg, link) if conversa else None
    if retrato is None:
        return
    resposta = retrato.pronta
    if resposta is None:
        try:
            resposta = decidir(retrato.pedido, clientes())
        except AgenteFalhou as falha:  # sem chave, ou nenhum modelo respondeu
            rodada.erros.append(f"A IA não respondeu: {falha}"[:300])
            resposta = Resposta(rota="regra", texto=None, passagem=passagem_do_servidor(
                "A IA não respondeu: a conversa ficou com a equipe", M.SISTEMA_FORA, retrato.destino))
    with fabrica() as sessao:
        _aplicar(sessao, retrato, resposta, cfg, enviar, agora(), rodada)
        sessao.commit()


def rodar_uma_vez(fabrica: Callable[[], Session], cfg: ConfiguracaoDasRespostas, clientes: Callable[[], Clientes],
                  enviar: Enviar | None, link: str, agora: Callable[[], datetime]) -> Rodada:
    """Uma rodada: responde as conversas pendentes. Uma conversa que falha não impede as outras."""
    rodada = Rodada()
    if not cfg.ligado:
        return rodada
    with fabrica() as sessao:
        ids = conversas_pendentes(sessao, agora(), cfg)
    for conversa_id in ids:
        try:
            _responder(fabrica, conversa_id, cfg, clientes, enviar, agora, link, rodada)
        except Exception as falha:  # noqa: BLE001 — a próxima conversa segue; só o tipo vai para o log
            _log.warning("SDR de IA: a resposta de uma conversa falhou (%s)", type(falha).__name__)
            rodada.erros.append(f"Falha inesperada ao responder ({type(falha).__name__}).")
    if ids:
        _log.info("SDR de IA: %d conversas, %d respostas enviadas, %d rascunhos, %d para a equipe, %d erros",
                  len(ids), rodada.respondidas, rodada.rascunhos, rodada.para_a_equipe, len(rodada.erros))
    return rodada


# ------------------------------------------------------------------ o que a equipe faz
def _conferir_envio(lead: Lead, momento: datetime) -> None:
    if lead.nao_contatar:
        raise RegraDaResposta(409, "o lead pediu para não ser contatado")
    janela = janela_do_lead(lead)
    if janela is None or janela <= momento:
        raise RegraDaResposta(409, "a janela de 24 horas do WhatsApp está fechada: para escrever ao lead, só modelo aprovado")


def _descartar_rascunhos(conversa: ConversaDoSdr, motivo: str) -> None:
    for m in conversa.mensagens:
        if m.autor is AutorDaMensagem.IA and m.entrega == "rascunho":
            m.entrega, m.observacao = "descartada", motivo[:300]


def responder_pela_equipe(sessao: Session, conversa: ConversaDoSdr, texto: str, quem: str | None,
                          enviar: Enviar | None, momento: datetime) -> MensagemDoSdr:
    """A equipe escreve ao lead pelo CRM. A IA para de responder nesta conversa até alguém devolvê-la."""
    texto = (texto or "").strip()
    if not texto:
        raise RegraDaResposta(422, "escreva a mensagem")
    if len(texto) > LIMITE_DO_TEXTO:
        raise RegraDaResposta(422, f"o WhatsApp aceita até {LIMITE_DO_TEXTO} caracteres")
    if conversa.canal is not CanalDeAbordagem.WHATSAPP:
        raise RegraDaResposta(409, "só a conversa do WhatsApp é respondida pelo CRM")
    lead = conversa.lead
    _conferir_envio(lead, momento)
    mensagem = MensagemDoSdr(conversa_id=conversa.id, autor=AutorDaMensagem.EQUIPE, enviada_em=momento, texto=texto,
                             entrega="enviada")
    sessao.add(mensagem)
    sessao.flush()  # grava antes de enviar; se o envio falhar, o pedido inteiro é desfeito
    try:
        mensagem.externo_id = _enviar(enviar, lead, texto)[:128] or None
    except EnvioFalhou as falha:
        raise RegraDaResposta(502, str(falha)) from falha
    _descartar_rascunhos(conversa, "A equipe respondeu no lugar")
    if conversa.equipe_desde is None:
        conversa.equipe_desde, conversa.equipe_motivo = momento, "A equipe assumiu a conversa"
    if conversa.atendida_em is None:
        conversa.atendida_em, conversa.atendida_por = momento, (quem or "")[:200] or None
    _marcar_questionario(lead, texto, momento)
    sessao.flush()
    return mensagem


def _rascunho(mensagem: MensagemDoSdr) -> None:
    if mensagem.autor is not AutorDaMensagem.IA or mensagem.entrega != "rascunho":
        raise RegraDaResposta(409, "esta mensagem não é um rascunho da IA esperando envio")


def enviar_rascunho(sessao: Session, mensagem: MensagemDoSdr, texto: str | None, quem: str | None,
                    enviar: Enviar | None, momento: datetime) -> MensagemDoSdr:
    """A equipe envia o rascunho da IA, como está ou com ajuste."""
    _rascunho(mensagem)
    lead = mensagem.conversa.lead
    _conferir_envio(lead, momento)
    novo = (texto or "").strip()
    editada = bool(novo) and novo != mensagem.texto
    if editada and len(novo) > LIMITE_DO_TEXTO:
        raise RegraDaResposta(422, f"o WhatsApp aceita até {LIMITE_DO_TEXTO} caracteres")
    final = novo if editada else mensagem.texto
    try:
        externo = _enviar(enviar, lead, final)
    except EnvioFalhou as falha:
        raise RegraDaResposta(502, str(falha)) from falha
    mensagem.texto, mensagem.enviada_em, mensagem.entrega = final, momento, "enviada"
    mensagem.externo_id = externo[:128] or None
    nota = "Ajustada e enviada" if editada else "Enviada"
    mensagem.observacao = f"{nota} por {quem}"[:300] if quem else f"{nota} pela equipe"
    _marcar_questionario(lead, final, momento)
    sessao.flush()
    return mensagem


def descartar_rascunho(sessao: Session, mensagem: MensagemDoSdr, quem: str | None, momento: datetime) -> MensagemDoSdr:
    """A equipe descarta o rascunho e assume a conversa."""
    _rascunho(mensagem)
    mensagem.entrega = "descartada"
    mensagem.observacao = (f"Descartada por {quem}" if quem else "Descartada pela equipe")[:300]
    conversa = mensagem.conversa
    if conversa.equipe_desde is None:
        _passar(conversa, Passagem(tela="A equipe descartou o rascunho da IA", destino=_destino_do_servico(conversa.lead)),
                momento)
    sessao.flush()
    return mensagem


def devolver_para_a_ia(sessao: Session, conversa: ConversaDoSdr, momento: datetime) -> ConversaDoSdr:
    """A conversa volta para a IA. Se ela já tinha sido encerrada pela passagem, abre uma conversa nova, onde
    entram as próximas mensagens do lead; a IA lê as anteriores como histórico."""
    if conversa.equipe_desde is None:
        raise RegraDaResposta(409, "a conversa já está com a IA")
    if conversa.lead.convertido_em_id is not None:
        raise RegraDaResposta(409, "este lead já virou oportunidade: a conversa é da equipe")
    if conversa.lead.nao_contatar:
        raise RegraDaResposta(409, "o lead pediu para não ser contatado")
    conversa.equipe_desde, conversa.equipe_motivo = None, None
    if conversa.desfecho is None:
        sessao.flush()
        return conversa
    nova = ConversaDoSdr(lead_id=conversa.lead_id, canal=conversa.canal, iniciada_em=momento)
    sessao.add(nova)
    sessao.flush()
    return nova


# ------------------------------------------------------------------ a situação na tela
def _dolar(valor: Decimal) -> str:
    casas = 2 if valor >= Decimal("0.01") or valor == 0 else 3
    return f"US$ {valor:.{casas}f}".replace(".", ",")


def situacao_das_respostas(sessao: Session, momento: datetime, cfg: ConfiguracaoDasRespostas,
                           erro: str | None = None) -> str:
    """A frase da aba Respostas do SDR: o que a IA fez nos últimos 30 dias, quanto custou e a última falha."""
    inicio = momento - timedelta(days=30)
    mensagens = sessao.scalars(
        sa.select(MensagemDoSdr).where(MensagemDoSdr.autor == AutorDaMensagem.IA, MensagemDoSdr.rota.is_not(None),
                                       MensagemDoSdr.enviada_em >= inicio)
    ).all()
    passadas = sessao.scalar(sa.select(sa.func.count()).select_from(ConversaDoSdr).where(sa.or_(
        ConversaDoSdr.equipe_desde >= inicio,  # inclui a reunião aceita e a conversa que a equipe assumiu
        sa.and_(ConversaDoSdr.desfecho == DesfechoDaConversa.TRANSBORDO, ConversaDoSdr.encerrada_em >= inicio),
    ))) or 0  # o transbordo conta mesmo depois de devolvido à IA
    modo = {"Desligado": "Respostas desligadas: a IA não responde a ninguém.",
            "Supervisionado": "Modo supervisionado: a IA rascunha e a equipe envia.",
            "Automático": "Modo automático: a IA envia sozinha."}[cfg.modo]
    if not mensagens:
        frase = f"{modo} Nenhuma resposta da IA nos últimos 30 dias."
    else:
        def conta(rota: str) -> int:
            return sum(1 for m in mensagens if m.rota == rota and m.entrega != "bloqueada")

        barradas = sum(1 for m in mensagens if m.entrega == "bloqueada")
        conversas = len({m.conversa_id for m in mensagens})
        custo = sum((m.custo_usd or Decimal(0) for m in mensagens), Decimal(0))
        frase = (f"{modo} Últimos 30 dias: {conversas} conversa{'s' if conversas != 1 else ''} · "
                 f"respostas da IA: {conta('leve')} no modelo leve, {conta('principal')} no principal, "
                 f"{conta('regra')} pela regra, {barradas} barrada{'s' if barradas != 1 else ''} pela trava · "
                 f"{passadas} passada{'s' if passadas != 1 else ''} para a equipe · custo {_dolar(custo)} "
                 f"({_dolar(custo / conversas)} por conversa).")
    return f"{frase} ⚠ Última falha: {erro}" if erro else frase
