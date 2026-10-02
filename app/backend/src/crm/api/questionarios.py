"""Rotas do questionário para proposta: buscar no site, ver o que entrou, resolver o que precisa de
alguém e abrir o PDF (pedido de Eduardo, 01/10/2026). Regras em `crm.questionario`."""

from __future__ import annotations

import base64
import binascii
import threading
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from crm.db.base import agora
from crm.db.modelos import GrupoEconomico, Oportunidade, Proposta, QuestionarioRecebido
from crm.domain.listas import Situacao, SituacaoDoQuestionario
from crm.proposta import ficha as regras_da_ficha
from crm.questionario import importacao
from crm.questionario.endereco import BuscaDeEndereco
from crm.questionario.fonte import (
    VARIAVEIS, BuscaFalhou, FonteDaFuncao, FonteDeQuestionarios, FonteSupabase, e_funcao, ler_configuracao,
)
from crm.questionario.leitura import ROTULOS_COMPLEXIDADE, ROTULOS_RISCO, inteiro_ou_nada

__all__ = [
    "ESTADO_DA_BUSCA", "INTERVALO_DA_BUSCA", "BuscaNaoConfigurada", "executar_busca", "fonte_real", "roteador_de_questionarios",
]


def fonte_real() -> FonteDeQuestionarios | None:
    config = ler_configuracao()
    if config is None:
        return None
    return FonteDaFuncao(config) if e_funcao(config) else FonteSupabase(config)


class QuestionarioResumo(BaseModel):
    id: int
    recebido_em: datetime
    razao_social: str
    nome_fantasia: str | None
    cnpj: str
    contato_nome: str
    contato_cargo: str | None
    situacao: str
    cliente_novo: bool
    o_que_fez: str
    grupo_id: int | None
    grupo_nome: str | None
    oportunidade_id: int | None
    oportunidade_em_aberto_id: int | None
    porte_crm: str | None
    porte_site: str | None
    tem_pdf: bool


class ResultadoDaBusca(BaseModel):
    buscado_em: datetime
    novos: list[QuestionarioResumo]
    avisos: list[str]


class Resolucao(BaseModel):
    acao: Literal["anexar", "criar"]


class FatorDoQuestionario(BaseModel):
    id: str
    rotulo: str


class QuestionarioDaOportunidade(BaseModel):
    id: int
    recebido_em: datetime
    versao: str
    contato_nome: str
    contato_cargo: str | None
    contato_email: str | None
    contato_celular: str | None
    servicos: list[str]
    porte_crm: str | None
    porte_site: str | None
    pontuacao: str | None
    horas_base: int | None
    nota_complexidade: int
    fatores_complexidade: list[FatorDoQuestionario]
    nota_risco: int
    fatores_risco: list[FatorDoQuestionario]
    pontos_de_atencao: list[tuple[str, str]]
    notas_emitidas: int | None
    notas_recebidas: int | None
    tem_pdf: bool


_FUSO = ZoneInfo("America/Sao_Paulo")
SITUACOES_DO_PAINEL = ("precisa_de_voce", "aguardando_proposta", "proposta_enviada", "em_espera", "aceita", "perdida")
DIAS_UTEIS_DE_ESPERA = 5
"""Aguardando proposta há mais que isto aparece destacado no painel."""


class LinhaDoPainel(QuestionarioResumo):
    servicos: list[str]
    situacao_do_painel: str
    """Uma de `SITUACOES_DO_PAINEL`, tirada da oportunidade: nada se digita duas vezes."""
    proposta_numero: str | None
    proposta_enviada_em: date | None
    """A primeira proposta enviada desta oportunidade."""
    motivo_da_perda: str | None
    dias_uteis_aguardando: int | None


class NumerosDoPainel(BaseModel):
    recebidos: int
    recebidos_antes: int | None
    """O mesmo número de dias logo antes do período; sem período, não há com o que comparar."""
    aguardando: int
    aguardando_atrasados: int
    enviados: int
    media_de_dias_ate_a_proposta: Decimal | None
    precisam_de_voce: int


class PainelDeQuestionarios(BaseModel):
    numeros: NumerosDoPainel
    itens: list[LinhaDoPainel]


class RespostaDaSecao(BaseModel):
    rotulo: str
    valor: str


class SecaoDeRespostas(BaseModel):
    numero: int
    titulo: str
    respostas: list[RespostaDaSecao]


class BuscaNaoConfigurada(RuntimeError):
    """Sem URL e chave do questionário no .env."""


def executar_busca(
    sessao: Session, origem: FonteDeQuestionarios | None, buscar_endereco: BuscaDeEndereco | None,
) -> tuple[list[QuestionarioRecebido], list[str]]:
    """Traz do site o que ainda não foi importado e faz cada um virar oportunidade (ou "precisa de
    você"). Cada questionário é gravado aqui **antes** de ser marcado lá: se a marca falhar, ele volta
    na próxima busca e só a marca é refeita. Usada pelo botão e pela busca automática."""
    if origem is None:
        raise BuscaNaoConfigurada(
            f"Falta configurar a busca: preencha {VARIAVEIS['url']} e {VARIAVEIS['chave']} no backend/.env "
            "e reinicie o CRM."
        )
    with _UMA_BUSCA_POR_VEZ:  # o botão e a busca automática nunca importam o mesmo questionário juntos
        return _buscar(sessao, origem, buscar_endereco)


_UMA_BUSCA_POR_VEZ = threading.Lock()


def _buscar(
    sessao: Session, origem: FonteDeQuestionarios, buscar_endereco: BuscaDeEndereco | None,
) -> tuple[list[QuestionarioRecebido], list[str]]:
    linhas = origem.novos()
    novos: list[QuestionarioRecebido] = []
    avisos: list[str] = []
    for linha in linhas:
        externo = str(linha.get("id", ""))
        q = sessao.scalar(sa.select(QuestionarioRecebido).where(QuestionarioRecebido.externo_id == externo))
        if q is None:
            try:
                q = importacao.importar(sessao, linha, buscar_endereco)
            except (importacao.LinhaInvalida, KeyError, ValueError) as falha:
                sessao.rollback()  # só esta linha: as anteriores já foram gravadas
                avisos.append(f"Questionário {externo or 'sem id'} ficou de fora: {falha}. Ele continua no site.")
                continue
            sessao.commit()
            novos.append(q)
        try:
            origem.marcar_importado(externo, agora())
            q.marcado_na_origem_em = agora()
            sessao.commit()
        except BuscaFalhou as falha:
            avisos.append(f"{q.razao_social}: entrou no CRM, mas {falha} Na próxima busca o CRM só tenta marcar de novo.")
    return novos, avisos


INTERVALO_DA_BUSCA = timedelta(minutes=10)
"""De quanto em quanto tempo o CRM busca sozinho (aprovado por Eduardo em 02/10/2026)."""


class EstadoDaBusca:
    """A última busca e a próxima, em memória: some ao reiniciar o CRM, que busca logo ao subir."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._ultima_em: datetime | None = None
        self._manual = False
        self._novos = 0
        self._erro: str | None = None
        self._avisos: list[str] = []
        self._proxima_em: datetime | None = None
        self._automatica = False

    def ligar(self, proxima_em: datetime) -> None:
        with self._trava:
            self._automatica, self._proxima_em = True, proxima_em

    def desligar(self) -> None:
        with self._trava:
            self._automatica, self._proxima_em = False, None

    def agendar(self, proxima_em: datetime) -> None:
        with self._trava:
            self._proxima_em = proxima_em

    def registrar(self, *, manual: bool, novos: int, erro: str | None, avisos: list[str] | None = None) -> None:
        with self._trava:
            self._ultima_em, self._manual, self._novos, self._erro = agora(), manual, novos, erro
            self._avisos = list(avisos or [])

    def retrato(self) -> dict:
        with self._trava:
            return {
                "automatica": self._automatica, "intervalo_minutos": int(INTERVALO_DA_BUSCA.total_seconds() // 60),
                "ultima_em": self._ultima_em, "ultima_manual": self._manual, "novos": self._novos,
                "erro": self._erro, "avisos": self._avisos, "proxima_em": self._proxima_em,
            }


ESTADO_DA_BUSCA = EstadoDaBusca()


class EstadoDaBuscaResposta(BaseModel):
    automatica: bool
    """Falso quando o CRM roda sem a busca automática (no teste, ou sem configuração)."""
    intervalo_minutos: int
    ultima_em: datetime | None
    ultima_manual: bool
    novos: int
    erro: str | None
    avisos: list[str]
    proxima_em: datetime | None


def _dia(momento: datetime) -> date:
    return (momento if momento.tzinfo else momento.replace(tzinfo=ZoneInfo("UTC"))).astimezone(_FUSO).date()


def dias_uteis_entre(inicio: date, fim: date) -> int:
    """Dias de segunda a sexta depois de `inicio`, até `fim` inclusive (feriado conta como útil)."""
    return sum(1 for n in range(1, (fim - inicio).days + 1) if (inicio + timedelta(days=n)).weekday() < 5)


def roteador_de_questionarios(
    obter_sessao: Callable[[], Iterator[Session]],
    fonte: Callable[[], FonteDeQuestionarios | None] = fonte_real,
    buscar_endereco: BuscaDeEndereco | None = None,
) -> APIRouter:
    """`buscar_endereco`: endereço pelo CNPJ ao importar (Karine, 01/10/2026). None = não busca."""
    r = APIRouter(tags=["questionário"])

    def _resumo(sessao: Session, q: QuestionarioRecebido) -> QuestionarioResumo:
        grupo = sessao.get(GrupoEconomico, q.grupo_id) if q.grupo_id else None
        return QuestionarioResumo(
            id=q.id, recebido_em=q.recebido_em, razao_social=q.razao_social, nome_fantasia=q.nome_fantasia,
            cnpj=q.cnpj, contato_nome=q.contato_nome, contato_cargo=q.contato_cargo, situacao=q.situacao.value,
            cliente_novo=q.cliente_novo, o_que_fez=q.o_que_fez, grupo_id=q.grupo_id,
            grupo_nome=grupo.nome if grupo else None, oportunidade_id=q.oportunidade_id,
            oportunidade_em_aberto_id=q.oportunidade_em_aberto_id, porte_crm=q.porte_crm, porte_site=q.porte_site,
            tem_pdf=bool(q.pdf_base64),
        )

    @r.post("/api/questionarios/buscar", response_model=ResultadoDaBusca)
    def buscar(sessao: Session = Depends(obter_sessao)) -> ResultadoDaBusca:
        """A busca na hora ("Buscar agora"). A mesma que o CRM faz sozinho a cada 10 minutos."""
        try:
            novos, avisos = executar_busca(sessao, fonte(), buscar_endereco)
        except BuscaNaoConfigurada as falha:
            ESTADO_DA_BUSCA.registrar(manual=True, novos=0, erro=str(falha))
            raise HTTPException(409, str(falha)) from falha
        except BuscaFalhou as falha:
            ESTADO_DA_BUSCA.registrar(manual=True, novos=0, erro=str(falha))
            raise HTTPException(502, str(falha)) from falha
        ESTADO_DA_BUSCA.registrar(manual=True, novos=len(novos), erro=None, avisos=avisos)
        return ResultadoDaBusca(buscado_em=agora(), novos=[_resumo(sessao, q) for q in novos], avisos=avisos)

    @r.get("/api/questionarios/busca", response_model=EstadoDaBuscaResposta)
    def estado_da_busca() -> EstadoDaBuscaResposta:
        """Quando foi a última busca (automática ou na hora), quantos vieram, se deu erro e quando é a próxima."""
        return EstadoDaBuscaResposta(**ESTADO_DA_BUSCA.retrato())

    @r.get("/api/questionarios", response_model=list[QuestionarioResumo])
    def listar(sessao: Session = Depends(obter_sessao), limite: int = Query(default=30, le=200)) -> list[QuestionarioResumo]:
        """Os mais recentes primeiro; os que precisam de alguém vêm antes de todos."""
        itens = sessao.scalars(
            sa.select(QuestionarioRecebido).order_by(
                (QuestionarioRecebido.situacao == SituacaoDoQuestionario.PRECISA_DE_VOCE).desc(),
                QuestionarioRecebido.recebido_em.desc(), QuestionarioRecebido.id.desc(),
            ).limit(limite)
        ).all()
        return [_resumo(sessao, q) for q in itens]

    def _questionario(sessao: Session, questionario_id: int) -> QuestionarioRecebido:
        q = sessao.get(QuestionarioRecebido, questionario_id)
        if q is None:
            raise HTTPException(404, "questionário não encontrado")
        return q

    def _linha_do_painel(sessao: Session, q: QuestionarioRecebido, hoje: date) -> LinhaDoPainel:
        base = _resumo(sessao, q).model_dump()
        servicos = importacao.leitura_de(q).servicos
        o = sessao.get(Oportunidade, q.oportunidade_id) if q.oportunidade_id else None
        propostas = sessao.scalars(
            sa.select(Proposta).where(Proposta.oportunidade_id == o.id).order_by(Proposta.gerada_em.desc())
        ).all() if o else []
        enviadas = [x.enviada_em for x in propostas if x.enviada_em is not None]
        ultima = propostas[0] if propostas else None
        motivo = None
        dias = None
        if q.situacao is SituacaoDoQuestionario.PRECISA_DE_VOCE:
            situacao = "precisa_de_voce"
        elif o is None or o.situacao is Situacao.ENVIAR_PROPOSTA and not enviadas:
            situacao = "aguardando_proposta"
            dias = dias_uteis_entre(_dia(q.recebido_em), hoje)
        elif o.situacao is Situacao.ACEITA:
            situacao = "aceita"
        elif o.situacao in (Situacao.RECUSADA, Situacao.PERDIDO):
            situacao = "perdida"
            motivo = o.motivo_recusa.value if o.motivo_recusa else None
        elif o.situacao is Situacao.ON_HOLD:
            situacao = "em_espera"
        else:
            situacao = "proposta_enviada"
        return LinhaDoPainel(
            **base, servicos=servicos, situacao_do_painel=situacao,
            proposta_numero=f"{ultima.numero}.{ultima.ano}" if ultima else None,
            proposta_enviada_em=min(enviadas) if enviadas else None,
            motivo_da_perda=motivo, dias_uteis_aguardando=dias,
        )

    @r.get("/api/questionarios/painel", response_model=PainelDeQuestionarios)
    def painel(
        sessao: Session = Depends(obter_sessao),
        dias: int = Query(default=30, ge=0, le=3660),
        servico: str | None = None,
        porte: str | None = None,
        situacao: str | None = None,
    ) -> PainelDeQuestionarios:
        """Todos os questionários dos últimos `dias` (0 = desde o primeiro), com a situação tirada da
        oportunidade e os números do topo, que seguem os mesmos filtros (amostra aprovada em 02/10/2026)."""
        if situacao is not None and situacao not in SITUACOES_DO_PAINEL:
            raise HTTPException(422, f"situação desconhecida: use uma de {', '.join(SITUACOES_DO_PAINEL)}")
        hoje = datetime.now(_FUSO).date()
        inicio = hoje - timedelta(days=dias - 1) if dias else None

        def no_filtro(linha: LinhaDoPainel) -> bool:
            return (servico is None or servico in linha.servicos) and (porte is None or linha.porte_crm == porte)

        todos = sessao.scalars(sa.select(QuestionarioRecebido).order_by(
            QuestionarioRecebido.recebido_em.desc(), QuestionarioRecebido.id.desc())).all()
        linhas = [(_dia(q.recebido_em), q) for q in todos]
        periodo = [_linha_do_painel(sessao, q, hoje) for d, q in linhas if inicio is None or d >= inicio]
        periodo = [x for x in periodo if no_filtro(x)]
        antes = None
        if inicio is not None:
            anterior = inicio - timedelta(days=dias)
            antes = sum(1 for d, q in linhas if anterior <= d < inicio and no_filtro(_linha_do_painel(sessao, q, hoje)))

        enviados = [x for x in periodo if x.proposta_enviada_em is not None or x.situacao_do_painel in ("proposta_enviada", "aceita")]
        prazos = [(x.proposta_enviada_em - _dia(x.recebido_em)).days for x in enviados if x.proposta_enviada_em is not None]
        media = (Decimal(sum(prazos)) / len(prazos)).quantize(Decimal("0.1"), ROUND_HALF_UP) if prazos else None
        aguardando = [x for x in periodo if x.situacao_do_painel == "aguardando_proposta"]
        numeros = NumerosDoPainel(
            recebidos=len(periodo), recebidos_antes=antes, aguardando=len(aguardando),
            aguardando_atrasados=sum(1 for x in aguardando if (x.dias_uteis_aguardando or 0) > DIAS_UTEIS_DE_ESPERA),
            enviados=len(enviados), media_de_dias_ate_a_proposta=media,
            precisam_de_voce=sum(1 for x in periodo if x.situacao_do_painel == "precisa_de_voce"),
        )
        itens = [x for x in periodo if situacao is None or x.situacao_do_painel == situacao]
        return PainelDeQuestionarios(numeros=numeros, itens=itens)

    @r.get("/api/questionarios/{questionario_id}/respostas", response_model=list[SecaoDeRespostas])
    def respostas(questionario_id: int, sessao: Session = Depends(obter_sessao)) -> list[SecaoDeRespostas]:
        """O que o cliente respondeu, por seção, só as perguntas respondidas e as seções do escopo pedido.
        É a resposta original: as correções da entrevista ficam na ficha da oportunidade."""
        q = _questionario(sessao, questionario_id)
        secoes = []
        for s in regras_da_ficha.montar(q.respostas, None, q.recebido_em).secoes:
            if not s.no_escopo:
                continue
            itens = [
                RespostaDaSecao(rotulo=c.campo.rotulo, valor=", ".join(map(str, c.valor)) if isinstance(c.valor, list) else str(c.valor))
                for c in s.campos if c.respondida
            ]
            if itens:
                secoes.append(SecaoDeRespostas(numero=s.numero, titulo=s.titulo, respostas=itens))
        return secoes

    @r.post("/api/questionarios/{questionario_id}/resolver", response_model=QuestionarioResumo)
    def resolver(questionario_id: int, corpo: Resolucao, sessao: Session = Depends(obter_sessao)) -> QuestionarioResumo:
        q = _questionario(sessao, questionario_id)
        try:
            if corpo.acao == "anexar":
                importacao.anexar(sessao, q)
            else:
                importacao.criar_nova(sessao, q)
        except ValueError as falha:
            raise HTTPException(409, str(falha)) from falha
        sessao.commit()
        return _resumo(sessao, q)

    @r.get("/api/questionarios/{questionario_id}/pdf")
    def pdf(questionario_id: int, sessao: Session = Depends(obter_sessao)) -> Response:
        q = _questionario(sessao, questionario_id)
        if not q.pdf_base64:
            raise HTTPException(404, "este questionário chegou sem PDF")
        try:
            conteudo = base64.b64decode(q.pdf_base64, validate=True)
        except (binascii.Error, ValueError) as falha:
            raise HTTPException(422, "o PDF deste questionário chegou corrompido") from falha
        return Response(
            conteudo, media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="questionario-{q.cnpj}.pdf"'},
        )

    @r.get("/api/oportunidades/{oportunidade_id}/questionario", response_model=QuestionarioDaOportunidade | None)
    def da_oportunidade(oportunidade_id: int, sessao: Session = Depends(obter_sessao)) -> QuestionarioDaOportunidade | None:
        """O questionário mais recente que criou ou foi anexado a esta oportunidade, se houver."""
        if sessao.get(Oportunidade, oportunidade_id) is None:
            raise HTTPException(404, "oportunidade não encontrada")
        q = sessao.scalars(
            sa.select(QuestionarioRecebido).where(QuestionarioRecebido.oportunidade_id == oportunidade_id)
            .order_by(QuestionarioRecebido.recebido_em.desc()).limit(1)
        ).first()
        if q is None:
            return None
        leitura = importacao.leitura_de(q)
        vol = q.respostas.get("vol") or {}
        inteiro = lambda k: inteiro_ou_nada(vol.get(k))  # noqa: E731
        return QuestionarioDaOportunidade(
            id=q.id, recebido_em=q.recebido_em, versao=q.versao, contato_nome=q.contato_nome,
            contato_cargo=q.contato_cargo, contato_email=q.contato_email, contato_celular=q.contato_celular,
            servicos=leitura.servicos, porte_crm=leitura.porte, porte_site=q.porte_site, pontuacao=leitura.pontuacao,
            horas_base=leitura.horas_base, nota_complexidade=leitura.nota_complexidade,
            fatores_complexidade=[FatorDoQuestionario(id=f, rotulo=ROTULOS_COMPLEXIDADE[f]) for f in leitura.fatores_complexidade],
            nota_risco=leitura.nota_risco,
            fatores_risco=[FatorDoQuestionario(id=f, rotulo=ROTULOS_RISCO[f]) for f in leitura.fatores_risco],
            pontos_de_atencao=leitura.pontos_de_atencao,
            notas_emitidas=inteiro("notas_emitidas"), notas_recebidas=inteiro("notas_recebidas"),
            tem_pdf=bool(q.pdf_base64),
        )

    return r
