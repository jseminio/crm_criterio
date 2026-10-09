"""Configurações › Integrações (amostra aprovada por Eduardo em 07/10/2026).

Chave de IA, WhatsApp, e-mail, questionário e disparo se cadastram, trocam e testam pela tela, sem
nada no painel do servidor. Regras:

- vale primeiro o que está na tela; sem valor na tela, a variável de ambiente antiga; depois o padrão
  (`crm.configuracao`). A origem de cada campo aparece na tela;
- segredo vai cifrado para o banco e **nunca volta**: a tela vê só os 4 últimos caracteres. Campo de
  segredo enviado vazio mantém o que está salvo; para tirar, a tela manda o campo em `apagar`;
- testar não grava nada e não envia mensagem a ninguém; "enviar teste" manda uma mensagem real só para
  o número ou e-mail que a pessoa digitou;
- só quem tem `configuracoes.integracoes` (o Administrador tem tudo).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm import configuracao
from crm.agente.config import ConfiguracaoDoAgente, ler_configuracao
from crm.agente.envio import EnvioFalhou, conferir_credenciais, enviar_email
from crm.agente.whatsapp import conferir_numero, enviar_modelo
from crm.api.acesso import quem_fez
from crm.domain.abordagem import normalizar_destino
from crm.domain.listas import CanalDeAbordagem
from crm.questionario.fonte import BuscaFalhou, FonteDeQuestionarios

__all__ = ["Testadores", "roteador_de_integracoes"]

MODELO_DE_TESTE = "criterio_lembrete_questionario"


class Falhou(RuntimeError):
    """O teste não passou. A mensagem é para a pessoa ler; nunca leva segredo."""


def _testar_ia(config: ConfiguracaoDoAgente) -> str:
    """Uma chamada mínima a cada IA em uso (a principal e a reserva), sem gravar nada."""
    from crm.agente.erros import mensagem_de_falha
    from crm.agente.ia import cliente_de, em_uso

    partes, falhou = [], False
    for nome in em_uso(config):
        try:
            cliente = cliente_de(nome, config)
            cliente.messages.create(model=cliente.modelo, max_tokens=16,
                                    messages=[{"role": "user", "content": "Responda só: ok"}])
            partes.append(f"{nome} respondeu com o modelo {cliente.modelo}")
        except Exception as falha:  # noqa: BLE001 — vira frase para a tela, sem detalhe da requisição
            falhou = True
            partes.append(f"{nome}: {mensagem_de_falha(falha)}")
    texto = ". ".join(partes) + "."
    if falhou:
        raise Falhou(texto)
    return texto


def _falta_no_webhook() -> str:
    """O que falta para receber as respostas do lead (09/10/2026); vazio quando não falta nada."""
    faltam = [r for c, r in (("whatsapp.verificacao", "o token de verificação"),
                             ("whatsapp.chave_do_app", "a chave secreta do app")) if not configuracao.valor(c)]
    return f" Para receber as respostas do lead, falta {' e '.join(faltam)}." if faltam else ""


def _testar_whatsapp(config: ConfiguracaoDoAgente) -> str:
    if config.whatsapp is None:
        raise Falhou("Faltam o token e o ID do número." + _falta_no_webhook())
    try:
        return f"A Meta reconheceu o número {conferir_numero(config.whatsapp)}." + _falta_no_webhook()
    except EnvioFalhou as falha:
        raise Falhou(str(falha) + _falta_no_webhook()) from falha


def _testar_email(config: ConfiguracaoDoAgente) -> str:
    if config.email is None:
        raise Falhou("Faltam o diretório, o aplicativo, o segredo ou a caixa remetente.")
    try:
        conferir_credenciais(config.email)
    except EnvioFalhou as falha:
        raise Falhou(str(falha)) from falha
    return f"O Microsoft 365 aceitou as credenciais. Os e-mails saem de {config.email.remetente}."


def _enviar_whatsapp(config: ConfiguracaoDoAgente, para: str) -> str:
    if config.whatsapp is None:
        raise Falhou("Faltam o token e o ID do número.")
    numero = normalizar_destino(CanalDeAbordagem.WHATSAPP, para)
    if len(numero) not in (12, 13):
        raise Falhou("Digite o celular com DDD, como 21 99999-9999.")
    try:
        enviar_modelo(config.whatsapp, para=numero, modelo=MODELO_DE_TESTE,
                      parametros={"nome": "teste", "servico": "BPO Financeiro"})
    except EnvioFalhou as falha:
        raise Falhou(str(falha)) from falha
    return f"A Meta aceitou o modelo {MODELO_DE_TESTE} para o final {numero[-4:]}. Confira no celular."


def _enviar_email(config: ConfiguracaoDoAgente, para: str) -> str:
    if config.email is None:
        raise Falhou("Faltam o diretório, o aplicativo, o segredo ou a caixa remetente.")
    if "@" not in para:
        raise Falhou("Digite um e-mail válido.")
    try:
        enviar_email(config.email, para=para.strip(), assunto="Teste do CRM Critério",
                     corpo="Este é um e-mail de teste enviado pela tela Configurações › Integrações do CRM.")
    except EnvioFalhou as falha:
        raise Falhou(str(falha)) from falha
    return f"E-mail de teste enviado para {para.strip()}."


@dataclass
class Testadores:
    """Os testes de cada cartão. O teste troca por falsos, sem rede."""

    ia: Callable[[ConfiguracaoDoAgente], str] = _testar_ia
    whatsapp: Callable[[ConfiguracaoDoAgente], str] = _testar_whatsapp
    email: Callable[[ConfiguracaoDoAgente], str] = _testar_email
    enviar: dict[str, Callable[[ConfiguracaoDoAgente, str], str]] = field(
        default_factory=lambda: {"whatsapp": _enviar_whatsapp, "email": _enviar_email}
    )


# ------------------------------------------------------------------ esquemas
class CampoResposta(BaseModel):
    chave: str
    rotulo: str
    segredo: bool
    origem: str
    """"tela", "servidor" (variável de ambiente), "padrão" ou "vazio"."""
    valor: str | None
    """Nunca para segredo."""
    final: str | None
    """Os 4 últimos caracteres do segredo salvo."""
    ilegivel: bool
    padrao: str
    ajuda: str
    exemplo: str
    opcoes: list[str]
    secao: str = ""
    """Subtítulo que a tela mostra antes deste campo."""


class WebhookResposta(BaseModel):
    """O que a tela mostra sobre o webhook do WhatsApp (09/10/2026)."""

    caminho: str
    """A tela monta o endereço completo com o domínio em que está aberta."""
    ultimo_aviso_em: datetime | None
    ultimo_aviso_situacao: str | None


class GrupoResposta(BaseModel):
    chave: str
    titulo: str
    testavel: bool
    envia_teste: bool
    configurado: bool
    """Tem valor (da tela ou do servidor) em todos os campos sem padrão."""
    campos: list[CampoResposta]
    alterado_por: str | None
    alterado_em: datetime | None
    webhook: WebhookResposta | None = None


class IntegracoesResposta(BaseModel):
    grupos: list[GrupoResposta]


class Alteracao(BaseModel):
    valores: dict[str, str] = Field(default_factory=dict)
    """Campo de segredo vazio mantém o salvo; campo comum vazio volta ao servidor ou ao padrão."""
    apagar: list[str] = Field(default_factory=list)
    """Campos para tirar da tela (inclusive segredo): volta a valer o servidor ou o padrão."""


class ResultadoDoTeste(BaseModel):
    ok: bool
    mensagem: str
    segundos: float
    em: datetime


class PedidoDeEnvio(BaseModel):
    para: str = Field(min_length=3, max_length=200)


_VERSAO = re.compile(r"^v\d{1,3}\.\d$")
_CHAVE_DO_APP = re.compile(r"^[0-9a-fA-F]{32}$")


def _problema(campo: configuracao.Campo, valor: str) -> str | None:
    if campo.opcoes and valor not in campo.opcoes:
        return f"{campo.rotulo}: use {' ou '.join(campo.opcoes)}"
    if campo.chave == "whatsapp.versao" and not _VERSAO.match(valor):
        return "Versão da API da Meta: use o formato v24.0"
    if campo.chave in ("questionario.link", "questionario.url") and not valor.startswith("https://"):
        return f"{campo.rotulo}: o endereço começa com https://"
    if campo.chave == "m365.remetente" and "@" not in valor:
        return "Caixa remetente: digite um e-mail"
    if campo.chave == "whatsapp.verificacao" and (len(valor) < 16 or any(c.isspace() for c in valor)):
        return "Token de verificação: no mínimo 16 caracteres, sem espaço"
    if campo.chave == "whatsapp.chave_do_app" and not _CHAVE_DO_APP.match(valor):
        return "Chave secreta do app: cole os 32 caracteres que a Meta mostra"
    return None


def _configurado(grupo: str, linhas: dict[str, configuracao.Linha]) -> bool:
    """IA: basta a chave de quem está em uso (principal e reserva). O resto: todos os campos com valor."""
    if grupo == "ia":
        from crm.agente.ia import NENHUMA

        em_uso = {linhas["ia.principal"].valor, linhas["ia.reserva"].valor} - {NENHUMA, None}
        return all(linhas[f"{n.casefold()}.chave"].origem != "vazio" for n in em_uso)
    return all(l.origem != "vazio" for l in linhas.values() if not l.campo.opcional and
               configuracao.CAMPOS[l.campo.chave] in configuracao.catalogo.grupo(grupo).campos)


def _webhook(sessao: Session) -> WebhookResposta:
    import sqlalchemy as sa

    from crm.api.webhook_whatsapp import CAMINHO
    from crm.db.modelos import EventoDoWhatsapp

    ultimo = sessao.execute(
        sa.select(EventoDoWhatsapp.recebido_em, EventoDoWhatsapp.situacao)
        .order_by(EventoDoWhatsapp.recebido_em.desc(), EventoDoWhatsapp.id.desc()).limit(1)
    ).first()
    return WebhookResposta(caminho=CAMINHO, ultimo_aviso_em=ultimo[0] if ultimo else None,
                           ultimo_aviso_situacao=ultimo[1] if ultimo else None)


def roteador_de_integracoes(
    obter_sessao: Callable[[], Iterator[Session]],
    fonte_de_questionarios: Callable[[], FonteDeQuestionarios | None],
    testadores: Testadores | None = None,
) -> APIRouter:
    r = APIRouter(prefix="/api/configuracoes/integracoes", tags=["configurações"])
    t = testadores or Testadores()

    def _grupo(chave: str) -> configuracao.Grupo:
        g = configuracao.catalogo.grupo(chave)
        if g is None:
            raise HTTPException(404, "integração não encontrada")
        return g

    def _resposta(sessao: Session) -> IntegracoesResposta:
        linhas = configuracao.linhas(sessao)
        grupos = []
        for g in configuracao.GRUPOS:
            do_grupo = [linhas[c.chave] for c in g.campos]
            datas = [(l.alterado_em, l.alterado_por) for l in do_grupo if l.alterado_em]
            ultima = max(datas, key=lambda d: d[0]) if datas else (None, None)
            grupos.append(GrupoResposta(
                chave=g.chave, titulo=g.titulo, testavel=g.testavel, envia_teste=g.chave in t.enviar,
                configurado=_configurado(g.chave, linhas),
                campos=[CampoResposta(
                    chave=l.campo.chave, rotulo=l.campo.rotulo, segredo=l.campo.segredo, origem=l.origem,
                    valor=l.valor, final=l.final, ilegivel=l.ilegivel, padrao=l.campo.padrao,
                    ajuda=l.campo.ajuda, exemplo=l.campo.exemplo, opcoes=list(l.campo.opcoes),
                    secao=l.campo.secao,
                ) for l in do_grupo],
                alterado_em=ultima[0], alterado_por=ultima[1],
                webhook=_webhook(sessao) if g.chave == "whatsapp" else None,
            ))
        return IntegracoesResposta(grupos=grupos)

    @r.get("", response_model=IntegracoesResposta)
    def ler(sessao: Session = Depends(obter_sessao, scope="function")) -> IntegracoesResposta:
        return _resposta(sessao)

    @r.put("/{chave}", response_model=IntegracoesResposta)
    def salvar(chave: str, corpo: Alteracao, sessao: Session = Depends(obter_sessao, scope="function")) -> IntegracoesResposta:
        g = _grupo(chave)
        do_grupo = {c.chave: c for c in g.campos}
        fora = [k for k in (*corpo.valores, *corpo.apagar) if k not in do_grupo]
        if fora:
            raise HTTPException(422, f"campo que não é desta integração: {', '.join(fora)}")
        problemas = [p for k, v in corpo.valores.items() if v.strip() and (p := _problema(do_grupo[k], v.strip()))]
        if problemas:
            raise HTTPException(422, "; ".join(problemas))
        quem = quem_fez("tela de Integrações")
        for campo, valor in corpo.valores.items():
            if do_grupo[campo].segredo and not valor.strip():
                continue  # segredo vazio: mantém o salvo
            configuracao.gravar(sessao, campo, valor, quem)
        for campo in corpo.apagar:
            configuracao.gravar(sessao, campo, None, quem)
        sessao.flush()
        sessao.commit()
        configuracao.invalidar()
        return _resposta(sessao)

    def _cronometrar(executar: Callable[[], str]) -> ResultadoDoTeste:
        from crm.db.base import agora

        inicio = time.monotonic()
        try:
            ok, mensagem = True, executar()
        except (Falhou, BuscaFalhou) as falha:
            ok, mensagem = False, str(falha)
        return ResultadoDoTeste(ok=ok, mensagem=mensagem, segundos=round(time.monotonic() - inicio, 1), em=agora())

    def _questionario() -> str:
        fonte = fonte_de_questionarios()
        if fonte is None:
            raise Falhou("Faltam o endereço e a chave da busca.")
        return f"O site respondeu: {len(fonte.novos())} questionário(s) novo(s) esperando a busca."

    @r.post("/{chave}/testar", response_model=ResultadoDoTeste)
    def testar(chave: str) -> ResultadoDoTeste:
        """Não grava nada e não envia mensagem a ninguém."""
        g = _grupo(chave)
        if not g.testavel:
            raise HTTPException(409, "esta integração não tem teste")
        configuracao.invalidar()
        if g.chave == "questionario":
            return _cronometrar(_questionario)
        testador = {"ia": t.ia, "whatsapp": t.whatsapp, "email": t.email}[g.chave]
        return _cronometrar(lambda: testador(ler_configuracao()))

    @r.post("/{chave}/enviar-teste", response_model=ResultadoDoTeste)
    def enviar_teste(chave: str, corpo: PedidoDeEnvio) -> ResultadoDoTeste:
        """Manda uma mensagem real, só para o número ou o e-mail digitado."""
        _grupo(chave)
        if chave not in t.enviar:
            raise HTTPException(409, "esta integração não envia teste")
        configuracao.invalidar()
        return _cronometrar(lambda: t.enviar[chave](ler_configuracao(), corpo.para))

    return r
