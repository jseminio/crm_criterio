"""Configurações › Integrações (amostra aprovada por Eduardo em 07/10/2026).

Chave de IA, WhatsApp, e-mail, questionário, disparo, Meta Ads (13/10/2026), Google Ads (14/10/2026), Clicksign (18/10/2026) e Granola (23/10/2026) se cadastram, trocam e testam pela tela, sem
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
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm import configuracao
from crm.agente.config import ConfiguracaoDoAgente, ler_configuracao
from crm.agente.envio import EnvioFalhou, conferir_credenciais, enviar_email
from crm.agente.whatsapp import conferir_numero, enviar_modelo
from crm.api.acesso import quem_fez
from crm.api.whatsapp_recebido import situacao_do_recebimento
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


def _testar_whatsapp(config: ConfiguracaoDoAgente) -> str:
    if config.whatsapp is None:
        raise Falhou("Faltam o token e o ID do número.")
    try:
        return f"A Meta reconheceu o número {conferir_numero(config.whatsapp)}."
    except EnvioFalhou as falha:
        raise Falhou(str(falha)) from falha


def _testar_email(config: ConfiguracaoDoAgente) -> str:
    if config.email is None:
        raise Falhou("Faltam o diretório, o aplicativo, o segredo ou a caixa remetente.")
    try:
        conferir_credenciais(config.email)
    except EnvioFalhou as falha:
        raise Falhou(str(falha)) from falha
    return f"O Microsoft 365 aceitou as credenciais. Os e-mails saem de {config.email.remetente}."


def _testar_meta_ads(_: ConfiguracaoDoAgente) -> str:
    """Testa o que estiver ligado no grupo: a leitura do gasto (conta de anúncios) e a entrada dos leads (página)."""
    from crm.anuncios import LeituraFalhou
    from crm.anuncios import leads_do_meta, meta

    leitura, leads = meta.ler_configuracao(), leads_do_meta.ler_configuracao()
    if leitura is None and leads is None:
        raise Falhou("Ligue a leitura (token e conta) ou a entrada dos leads (página e token da página).")
    partes, falhou = [], False
    for executar in ([lambda: meta.conferir_conta(leitura)] if leitura else []) + (
            [lambda: leads_do_meta.conferir_pagina(leads)] if leads else []):
        try:
            partes.append(executar())
        except LeituraFalhou as falha:
            falhou = True
            partes.append(str(falha))
    texto = " ".join(partes)
    if falhou:
        raise Falhou(texto)
    return texto


def _testar_google_ads(_: ConfiguracaoDoAgente) -> str:
    from crm.anuncios import LeituraFalhou, google

    config = google.ler_configuracao() or google.ler_leads()
    if config is None:
        raise Falhou("Ligue a leitura ou a entrada dos leads e preencha o token de desenvolvedor, o cliente OAuth, "
                     "o refresh token e a conta.")
    try:
        return google.conferir_conta(config)
    except LeituraFalhou as falha:
        raise Falhou(str(falha)) from falha


def _testar_clicksign(_: ConfiguracaoDoAgente) -> str:
    from crm.contrato import clicksign

    config = clicksign.ler_configuracao()
    if config is None:
        raise Falhou("Ligue a assinatura e salve o access token.")
    try:
        texto = clicksign.conferir_conta(config)
    except clicksign.FalhaNaClicksign as falha:
        raise Falhou(str(falha)) from falha
    faltas = [n for c, n in (("clicksign.segredo_webhook", "a chave do webhook (sem ela o CRM recusa os avisos)"),
                             ("clicksign.email_criterio", "o e-mail de quem assina pela Critério"))
              if not configuracao.valor(c).strip()]
    return texto + (f" Falta salvar {' e '.join(faltas)}." if faltas else "")


def testar_granola(http: Callable[[], object] | None = None) -> str:
    """A chave abre as pastas e as duas pastas escolhidas existem. Não precisa da busca ligada; não grava nada."""
    from crm.granola import cliente as granola

    config = granola.ler_configuracao(exigir_ligada=False)
    if config is None:
        raise Falhou("Salve a chave da API do Granola.")
    try:
        with (http or granola.novo_http)() as cliente:
            return granola.conferir(cliente, config)
    except granola.FalhaNoGranola as falha:
        raise Falhou(str(falha)) from falha


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
    meta_ads: Callable[[ConfiguracaoDoAgente], str] = _testar_meta_ads
    google_ads: Callable[[ConfiguracaoDoAgente], str] = _testar_google_ads
    clicksign: Callable[[ConfiguracaoDoAgente], str] = _testar_clicksign
    granola: Callable[[ConfiguracaoDoAgente], str] = lambda _: testar_granola()
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


class GrupoResposta(BaseModel):
    chave: str
    titulo: str
    testavel: bool
    envia_teste: bool
    configurado: bool
    """Tem valor (da tela ou do servidor) em todos os campos sem padrão."""
    situacao: str | None = None
    """Uma frase sobre o funcionamento, quando a integração tem (o recebimento do WhatsApp)."""
    campos: list[CampoResposta]
    alterado_por: str | None
    alterado_em: datetime | None


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


def _problema(campo: configuracao.Campo, valor: str) -> str | None:
    if campo.opcoes and valor not in campo.opcoes:
        return f"{campo.rotulo}: use {' ou '.join(campo.opcoes)}"
    if campo.chave in ("whatsapp.versao", "meta_ads.versao") and not _VERSAO.match(valor):
        return "Versão da API da Meta: use o formato v24.0"
    if campo.chave == "google_ads.versao" and not re.match(r"^v\d{2,3}$", valor):
        return "Versão da API do Google Ads: use o formato v25"
    if campo.chave in ("google_ads.conta", "google_ads.conta_admin") and not re.fullmatch(r"\d{3}-?\d{3}-?\d{4}", valor):
        return f"{campo.rotulo}: 10 dígitos, como 123-456-7890"
    if campo.chave in ("meta_ads.conjunto", "meta_ads.pagina", "google_ads.acao_qualificado", "google_ads.acao_reuniao",
                       "google_ads.acao_contrato") and not valor.isdigit():
        return f"{campo.rotulo}: só os números"
    if campo.chave == "meta_ads.conta" and not valor.removeprefix("act_").isdigit():
        return "ID da conta de anúncios: só os números, como 1708029123631617"
    if campo.chave in ("questionario.link", "questionario.url") and not valor.startswith("https://"):
        return f"{campo.rotulo}: o endereço começa com https://"
    if campo.chave == "sdr.teto_por_conversa" and _decimal(valor) is None:
        return f"{campo.rotulo}: um valor em dólar maior que zero, como 0.50"
    if campo.chave == "sdr.maximo_de_respostas" and not (valor.isdigit() and 1 <= int(valor) <= 50):
        return f"{campo.rotulo}: um número de 1 a 50"
    if campo.chave == "sdr.espera_segundos" and not (valor.isdigit() and int(valor) <= 300):
        return f"{campo.rotulo}: um número de 0 a 300"
    if campo.chave in ("sdr.modelo_leve", "sdr.modelo_leve_openai") and not re.fullmatch(r"[a-z0-9][a-z0-9.\-]{2,59}", valor):
        return f"{campo.rotulo}: o nome do modelo, como {campo.exemplo}"
    if campo.chave == "granola.desde":
        from crm.granola.cliente import data_de_texto

        try:
            data_de_texto(valor)
        except ValueError:
            return "Trazer notas a partir de: use o formato 01/10/2026"
    if campo.chave == "m365.remetente" and "@" not in valor:
        return "Caixa remetente: digite um e-mail"
    return None


def _decimal(valor: str) -> Decimal | None:
    try:
        numero = Decimal(valor.replace(",", "."))
    except InvalidOperation:
        return None
    return numero if numero.is_finite() and Decimal(0) < numero <= Decimal(100) else None


def _configurado(grupo: str, linhas: dict[str, configuracao.Linha]) -> bool:
    """IA: basta a chave de quem está em uso (principal e reserva). O resto: todos os campos com valor."""
    if grupo == "ia":
        from crm.agente.ia import NENHUMA

        em_uso = {linhas["ia.principal"].valor, linhas["ia.reserva"].valor} - {NENHUMA, None}
        return all(linhas[f"{n.casefold()}.chave"].origem != "vazio" for n in em_uso)
    opcionais = {"whatsapp.recebimento", "whatsapp.token_verificacao", "whatsapp.app_secret", "google_ads.conta_admin", "meta_ads.conjunto", "meta_ads.pagina", "meta_ads.token_pagina", "google_ads.acao_qualificado",
                 "google_ads.acao_reuniao", "google_ads.acao_contrato", "granola.desde"}
    return all(l.origem != "vazio" for l in linhas.values() if configuracao.CAMPOS[l.campo.chave] in
               configuracao.catalogo.grupo(grupo).campos and l.campo.chave not in opcionais)


def _situacao(grupo: str, sessao: Session) -> str | None:
    if grupo == "whatsapp":
        return situacao_do_recebimento(sessao)
    if grupo == "sdr_respostas":
        from crm.agente.respostas_do_sdr import situacao_das_respostas
        from crm.agente.roteador_do_sdr import ler_configuracao_das_respostas
        from crm.api.respostas_do_sdr import ESTADO_DAS_RESPOSTAS
        from crm.db.base import agora

        return situacao_das_respostas(sessao, agora(), ler_configuracao_das_respostas(), ESTADO_DAS_RESPOSTAS.erro())
    return None


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
                situacao=_situacao(g.chave, sessao),
                campos=[CampoResposta(
                    chave=l.campo.chave, rotulo=l.campo.rotulo, segredo=l.campo.segredo, origem=l.origem,
                    valor=l.valor, final=l.final, ilegivel=l.ilegivel, padrao=l.campo.padrao,
                    ajuda=l.campo.ajuda, exemplo=l.campo.exemplo, opcoes=list(l.campo.opcoes),
                ) for l in do_grupo],
                alterado_em=ultima[0], alterado_por=ultima[1],
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
        testador = {"ia": t.ia, "whatsapp": t.whatsapp, "email": t.email, "meta_ads": t.meta_ads,
                    "google_ads": t.google_ads, "clicksign": t.clicksign, "granola": t.granola}[g.chave]
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
