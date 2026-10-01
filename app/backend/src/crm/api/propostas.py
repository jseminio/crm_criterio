"""Rotas da proposta em PowerPoint (01/10/2026): a aba "Proposta" da oportunidade, gerar e baixar o
.pptx, marcar como enviada, e Configurações › Propostas (matrizes e numeração). Regras em `crm.proposta`.

A proposta sai em PowerPoint de propósito: Eduardo ou Karine revisam, ajustam à mão se preciso,
salvam como PDF e enviam. O CRM guarda o número, os valores e quem enviou.
"""

from __future__ import annotations

import base64
import re
import unicodedata
from collections.abc import Callable, Iterator
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, defer

from crm.api.classificacao import janela_vigente, parametros_vigentes
from crm.db.base import agora
from crm.db.modelos import (
    ConfiguracaoDeProposta, HistoricoDePreco, MatrizDeProposta, Oportunidade, Proposta,
)
from crm.domain.listas import ORIGEM_DA_MUDANCA_NO_CRM, Situacao, TipoDeMatriz
from crm.proposta import conta, marcadores
from crm.proposta.rascunho import base_da_proposta, porte_da_oportunidade

__all__ = ["roteador_de_propostas", "PADRAO_DA_CONFIGURACAO"]

PADRAO_DA_CONFIGURACAO = {
    # Aprovado por Eduardo em 01/10/2026: a última enviada foi a 153.2026 (NRH).
    "proximo_numero": 154, "revisores": ["Eduardo", "Karine"],
    "plano_bpo": Decimal("5000"), "plano_plus": Decimal("7000"), "plano_cfo": Decimal("9000"),
}
# 200 MB desde 01/10/2026, a pedido de Eduardo: a matriz Contábil oficial, cheia de imagens, não coube em 40 MB.
_LIMITE_DA_MATRIZ = 200 * 1024 * 1024
_TRACO = "—"

Matriz = Literal["Contábil", "Financeiro"]


class Sugestao(BaseModel):
    porte: str
    porte_confirmado: bool
    horas_base: Decimal
    complexidade: int
    complexidade_informada: bool
    risco: int
    risco_informado: bool
    disciplina: int
    atrito: Decimal
    horas: Decimal
    custo_hora: Decimal
    custo: Decimal
    imposto: Decimal
    margem_alvo: Decimal
    origem_da_margem: str
    bruto: Decimal
    liquido: Decimal


class EntradaDaProposta(BaseModel):
    matriz: Matriz
    cliente: str = Field(min_length=1, max_length=200)
    tratamento: str = Field(min_length=1, max_length=200)
    contextualizacao: str = Field(min_length=1, max_length=4000)
    valor_contabil: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    valor_dp: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    horas_contabil: int | None = Field(default=None, ge=0, le=10000)
    horas_dp: int | None = Field(default=None, ge=0, le=10000)
    plano_bpo: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    plano_plus: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    plano_cfo: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class PropostaResumo(BaseModel):
    id: int
    numero: str
    matriz: str
    gerada_em: datetime
    valor_liquido: Decimal | None
    valor_bruto: Decimal | None
    enviada_em: date | None
    enviada_por: str | None
    arquivo: str


class MatrizResumo(BaseModel):
    id: int
    tipo: str
    nome_arquivo: str
    enviada_em: datetime
    enviada_por: str
    encontrados: int
    obrigatorios: int
    faltando: list[str]
    desconhecidos: list[str]
    utilizavel: bool


class AbaDaProposta(BaseModel):
    matriz_sugerida: Matriz
    servicos: list[str]
    tem_dp: bool
    sugestao: Sugestao | None
    sem_sugestao: str | None
    rascunho: EntradaDaProposta
    perfil: dict[str, str]
    imposto: Decimal
    matrizes: dict[str, MatrizResumo | None]
    revisores: list[str]
    proximo_numero: str
    propostas: list[PropostaResumo]


class Envio(BaseModel):
    por: str = Field(min_length=1, max_length=60)
    em: date


class Configuracao(BaseModel):
    proximo_numero: int = Field(ge=1, le=99999)
    revisores: list[str] = Field(min_length=1, max_length=10)
    plano_bpo: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    plano_plus: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    plano_cfo: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class ConfiguracaoResposta(Configuracao):
    imposto: Decimal
    """A alíquota estimada da proposta é o imposto de Carteira › Parâmetros de cálculo: uma fonte só."""
    ultimo_usado: str | None


class MarcadorResposta(BaseModel):
    nome: str
    descricao: str
    obrigatorio_em: list[str]


class Matrizes(BaseModel):
    em_uso: dict[str, MatrizResumo | None]
    marcadores: list[MarcadorResposta]


def _ano_de_hoje() -> int:
    return date.today().year


def _texto_do_numero(numero: int, ano: int) -> str:
    return f"{numero}.{ano}"


def _seguro_para_arquivo(nome: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]+', " ", nome).strip()[:80] or "Cliente"


def _nome_do_arquivo(p: Proposta, tipo: TipoDeMatriz) -> str:
    cliente = _seguro_para_arquivo(p.valores["entrada"]["cliente"])
    servico = "Contabil" if tipo is TipoDeMatriz.CONTABIL else "Financeiro"
    return f"{cliente}_Proposta BPO {servico}_{_texto_do_numero(p.numero, p.ano)}.pptx"


def _disposicao(nome: str) -> str:
    """Nome sem acento ("Serviços" → "Servicos"), como as propostas da Critério já são nomeadas, e só
    em `filename`: com `filename*` em UTF-8 o Chromium testado descartou o nome e salvou "download"."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return f'attachment; filename="{sem_acento.replace(chr(34), "")}"'


def roteador_de_propostas(obter_sessao: Callable[[], Iterator[Session]]) -> APIRouter:
    r = APIRouter(tags=["proposta"])

    def _configuracao(sessao: Session, *, travar: bool = False) -> ConfiguracaoDeProposta:
        consulta = sa.select(ConfiguracaoDeProposta).order_by(ConfiguracaoDeProposta.id).limit(1)
        if travar:
            consulta = consulta.with_for_update()
        c = sessao.scalars(consulta).first()
        if c is None:  # a migração grava a linha; isto cobre banco criado sem ela (testes)
            c = ConfiguracaoDeProposta(**PADRAO_DA_CONFIGURACAO)
            sessao.add(c)
            sessao.flush()
        return c

    def _imposto(sessao: Session) -> Decimal:
        return parametros_vigentes(sessao)[1].imposto

    def _matriz_em_uso(sessao: Session, tipo: TipoDeMatriz) -> MatrizDeProposta | None:
        # O .pptx em base64 pode ter dezenas de MB: só vem do banco quando alguém baixa ou gera o arquivo.
        return sessao.scalars(
            sa.select(MatrizDeProposta).options(defer(MatrizDeProposta.conteudo_base64))
            .where(MatrizDeProposta.tipo == tipo)
            .order_by(MatrizDeProposta.enviada_em.desc(), MatrizDeProposta.id.desc()).limit(1)
        ).first()

    def _matriz_resumo(m: MatrizDeProposta | None) -> MatrizResumo | None:
        if m is None:
            return None
        obrigatorios = marcadores.OBRIGATORIOS[m.tipo]
        return MatrizResumo(
            id=m.id, tipo=m.tipo.value, nome_arquivo=m.nome_arquivo, enviada_em=m.enviada_em, enviada_por=m.enviada_por,
            encontrados=len(obrigatorios) - len(m.faltando), obrigatorios=len(obrigatorios),
            faltando=m.faltando, desconhecidos=m.desconhecidos, utilizavel=not m.faltando and not m.desconhecidos,
        )

    def _em_uso(sessao: Session) -> dict[str, MatrizResumo | None]:
        return {t.value: _matriz_resumo(_matriz_em_uso(sessao, t)) for t in TipoDeMatriz}

    def _resumo(sessao: Session, p: Proposta) -> PropostaResumo:
        tipo = sessao.get(MatrizDeProposta, p.matriz_id).tipo
        return PropostaResumo(
            id=p.id, numero=_texto_do_numero(p.numero, p.ano), matriz=tipo.value, gerada_em=p.gerada_em,
            valor_liquido=p.valor_liquido, valor_bruto=p.valor_bruto, enviada_em=p.enviada_em,
            enviada_por=p.enviada_por, arquivo=_nome_do_arquivo(p, tipo),
        )

    def _oportunidade(sessao: Session, oportunidade_id: int) -> Oportunidade:
        o = sessao.get(Oportunidade, oportunidade_id)
        if o is None:
            raise HTTPException(404, "oportunidade não encontrada")
        return o

    def _propostas(sessao: Session, oportunidade_id: int) -> list[Proposta]:
        return list(sessao.scalars(
            sa.select(Proposta).where(Proposta.oportunidade_id == oportunidade_id)
            .order_by(Proposta.gerada_em.desc(), Proposta.id.desc())
        ))

    def _sugestao(sessao: Session, o: Oportunidade) -> tuple[Sugestao | None, str | None]:
        porte, confirmado = porte_da_oportunidade(o)
        if porte is None:
            return None, "Sem porte: preencha a volumetria na aba \"Volumetria e porte\" para ter o preço sugerido."
        janela = janela_vigente(sessao)
        _, p_rent = parametros_vigentes(sessao)
        s = conta.preco_sugerido(
            porte=porte, complexidade=o.complexidade, risco=o.risco_tecnico,
            margem_minima=janela.margem_minima, margem_alvo=janela.margem_alvo, p=p_rent,
        )
        if s is None:
            return None, f"O porte {porte} não está na matriz de horas dos Parâmetros."
        return Sugestao(**{**s.__dict__, "porte_confirmado": confirmado, "origem_da_margem": janela.origem}), None

    @r.get("/api/oportunidades/{oportunidade_id}/proposta", response_model=AbaDaProposta)
    def aba(oportunidade_id: int, sessao: Session = Depends(obter_sessao)) -> AbaDaProposta:
        o = _oportunidade(sessao, oportunidade_id)
        base = base_da_proposta(sessao, o)
        sugestao, sem = _sugestao(sessao, o)
        config = _configuracao(sessao)
        propostas = _propostas(sessao, o.id)
        if propostas:  # reabrir a aba traz o que foi usado na última, para ajustar e gerar de novo
            rascunho = EntradaDaProposta(**propostas[0].valores["entrada"])
        else:
            rascunho = EntradaDaProposta(
                matriz=base.matriz.value, cliente=base.cliente, tratamento=base.tratamento,
                contextualizacao=base.contextualizacao,
                valor_contabil=conta.arredondar_50(sugestao.liquido) if sugestao and not base.tem_dp else None,
                plano_bpo=config.plano_bpo, plano_plus=config.plano_plus, plano_cfo=config.plano_cfo,
            )
        aberta = propostas[0] if propostas and propostas[0].enviada_em is None else None
        proximo = (_texto_do_numero(aberta.numero, aberta.ano) if aberta
                   else _texto_do_numero(config.proximo_numero, _ano_de_hoje()))
        sessao.commit()  # a configuração pode ter nascido agora
        return AbaDaProposta(
            matriz_sugerida=base.matriz.value, servicos=base.servicos, tem_dp=base.tem_dp,
            sugestao=sugestao, sem_sugestao=sem, rascunho=rascunho, perfil=base.perfil, imposto=_imposto(sessao),
            matrizes=_em_uso(sessao), revisores=list(config.revisores), proximo_numero=proximo,
            propostas=[_resumo(sessao, p) for p in propostas],
        )

    def _valores(entrada: EntradaDaProposta, tipo: TipoDeMatriz, numero: str, perfil: dict[str, str],
                 imposto: Decimal) -> tuple[dict[str, str], Decimal | None, Decimal | None]:
        v = {"numero": numero, "cliente": entrada.cliente.strip(), "tratamento": entrada.tratamento.strip(),
             "contextualizacao": entrada.contextualizacao.strip(), **perfil}
        if tipo is TipoDeMatriz.FINANCEIRO:
            for campo in ("plano_bpo", "plano_plus", "plano_cfo"):
                valor = getattr(entrada, campo)
                if valor is None:
                    raise HTTPException(422, "preencha o preço dos três planos")
                v[campo] = f"R$ {conta.reais_sem_centavos_se_inteiro(valor)}"
            return v, None, None
        if not entrada.valor_contabil:
            raise HTTPException(422, "preencha o honorário de Contábil/Fiscal")
        if entrada.horas_contabil is None:
            raise HTTPException(422, "preencha as horas de consulta por ano de Contábil/Fiscal")
        if entrada.valor_dp and entrada.horas_dp is None:
            raise HTTPException(422, "preencha as horas de consulta por ano de DP")
        liquido = entrada.valor_contabil + (entrada.valor_dp or 0)
        bruto = conta.bruto_de(liquido, imposto)
        v.update({
            "valor_contabil": conta.reais_sem_centavos_se_inteiro(entrada.valor_contabil),
            "valor_dp": conta.reais_sem_centavos_se_inteiro(entrada.valor_dp) if entrada.valor_dp else _TRACO,
            "horas_contabil": str(entrada.horas_contabil),
            "horas_dp": str(entrada.horas_dp) if entrada.valor_dp else _TRACO,
            "horas_total": str(entrada.horas_contabil + ((entrada.horas_dp or 0) if entrada.valor_dp else 0)),
            "valor_liquido": f"R$ {conta.reais(liquido)}", "valor_bruto": f"R$ {conta.reais(bruto)}",
        })
        return v, liquido, bruto

    @r.post("/api/oportunidades/{oportunidade_id}/proposta", response_model=PropostaResumo)
    def gerar(oportunidade_id: int, entrada: EntradaDaProposta, sessao: Session = Depends(obter_sessao)) -> PropostaResumo:
        """Reserva o número e grava os valores. Gerar de novo antes de enviar regrava a mesma proposta
        (mesmo número); depois de enviada, abre número novo. O arquivo sai em `GET /api/propostas/{id}/pptx`."""
        o = _oportunidade(sessao, oportunidade_id)
        tipo = TipoDeMatriz(entrada.matriz)
        matriz = _matriz_em_uso(sessao, tipo)
        if matriz is None:
            raise HTTPException(409, f"Ainda não há matriz {tipo.value}: suba o PowerPoint em Configurações › Propostas.")
        if matriz.faltando or matriz.desconhecidos:
            problema = "; ".join(filter(None, [
                f"faltam {', '.join('{{' + n + '}}' for n in matriz.faltando)}" if matriz.faltando else "",
                f"marcadores desconhecidos {', '.join('{{' + n + '}}' for n in matriz.desconhecidos)}" if matriz.desconhecidos else "",
            ]))
            raise HTTPException(409, f"A matriz {tipo.value} em uso não serve: {problema}. Corrija e suba de novo em Configurações › Propostas.")
        base = base_da_proposta(sessao, o)
        propostas = _propostas(sessao, o.id)
        aberta = propostas[0] if propostas and propostas[0].enviada_em is None else None
        if aberta is not None:
            numero, ano = aberta.numero, aberta.ano
        else:
            config = _configuracao(sessao, travar=True)
            ano = _ano_de_hoje()
            numero = config.proximo_numero
            usados = set(sessao.scalars(sa.select(Proposta.numero).where(Proposta.ano == ano, Proposta.numero >= numero)))
            while numero in usados:  # alguém mudou o próximo número para um já usado: pula, nunca repete
                numero += 1
            config.proximo_numero = numero + 1
        marcas, liquido, bruto = _valores(entrada, tipo, _texto_do_numero(numero, ano), base.perfil, _imposto(sessao))
        valores = {"entrada": entrada.model_dump(mode="json"), "marcadores": marcas}
        if aberta is not None:
            p = aberta
            p.matriz_id, p.valores, p.valor_liquido, p.valor_bruto, p.gerada_em = matriz.id, valores, liquido, bruto, agora()
        else:
            p = Proposta(oportunidade_id=o.id, numero=numero, ano=ano, matriz_id=matriz.id, valores=valores,
                         valor_liquido=liquido, valor_bruto=bruto, gerada_em=agora())
            sessao.add(p)
        sessao.commit()
        return _resumo(sessao, p)

    def _proposta(sessao: Session, proposta_id: int) -> Proposta:
        p = sessao.get(Proposta, proposta_id)
        if p is None:
            raise HTTPException(404, "proposta não encontrada")
        return p

    @r.get("/api/propostas/{proposta_id}/pptx")
    def baixar(proposta_id: int, sessao: Session = Depends(obter_sessao)) -> Response:
        """Sempre com a matriz e os valores gravados: baixar de novo sai igual, mesmo se a matriz mudou."""
        p = _proposta(sessao, proposta_id)
        matriz = sessao.get(MatrizDeProposta, p.matriz_id)
        conteudo = marcadores.preencher(base64.b64decode(matriz.conteudo_base64), p.valores["marcadores"])
        return Response(
            conteudo, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": _disposicao(_nome_do_arquivo(p, matriz.tipo)), "Cache-Control": "no-store"},
        )

    @r.post("/api/propostas/{proposta_id}/enviada", response_model=PropostaResumo)
    def marcar_enviada(proposta_id: int, envio: Envio, sessao: Session = Depends(obter_sessao)) -> PropostaResumo:
        """Quem enviou e quando. A oportunidade em "Enviar proposta" passa a "Em avaliação pela empresa";
        na matriz Contábil, o total líquido vira o preço mensal da oportunidade, com histórico."""
        p = _proposta(sessao, proposta_id)
        config = _configuracao(sessao)
        if envio.por not in config.revisores:
            raise HTTPException(422, f"quem envia é {', '.join(config.revisores)} (Configurações › Propostas)")
        if envio.em > date.today():
            raise HTTPException(422, "a data de envio não pode ser no futuro")
        if p.enviada_em is not None:
            raise HTTPException(409, f"esta proposta já foi marcada como enviada em {p.enviada_em:%d/%m/%Y} por {p.enviada_por}")
        p.enviada_em, p.enviada_por = envio.em, envio.por
        o = sessao.get(Oportunidade, p.oportunidade_id)
        editados = set()
        if o.situacao is Situacao.ENVIAR_PROPOSTA:
            o.situacao = Situacao.EM_AVALIACAO
            editados.add("situacao")
        if p.valor_liquido is not None and o.preco_mensal != p.valor_liquido:
            sessao.add(HistoricoDePreco(
                oportunidade_id=o.id, origem=ORIGEM_DA_MUDANCA_NO_CRM,
                motivo=f"Proposta {_texto_do_numero(p.numero, p.ano)} enviada (valor líquido)",
                preco_mensal_anterior=o.preco_mensal, preco_mensal_novo=p.valor_liquido,
                preco_anual_anterior=o.preco_anual, preco_anual_novo=o.preco_anual,
            ))
            o.preco_mensal = p.valor_liquido
            editados.add("preco_mensal")
        if editados:
            o.campos_do_crm = sorted(set(o.campos_do_crm or []) | editados)
        sessao.commit()
        return _resumo(sessao, p)

    # ------------------------------------------------------------ Configurações › Propostas

    @r.get("/api/propostas/matrizes", response_model=Matrizes)
    def matrizes(sessao: Session = Depends(obter_sessao)) -> Matrizes:
        return Matrizes(
            em_uso=_em_uso(sessao),
            marcadores=[
                MarcadorResposta(nome=n, descricao=d,
                                 obrigatorio_em=[t.value for t in TipoDeMatriz if n in marcadores.OBRIGATORIOS[t]])
                for n, d in marcadores.MARCADORES.items()
            ],
        )

    @r.post("/api/propostas/matrizes/{tipo}", response_model=MatrizResumo)
    async def subir_matriz(
        tipo: Matriz, request: Request, nome_arquivo: str = Query(min_length=1, max_length=200),
        enviada_por: str = Query(min_length=1, max_length=60), sessao: Session = Depends(obter_sessao),
    ) -> MatrizResumo:
        """O corpo é o .pptx. Fica gravada mesmo com marcador faltando, para a tela mostrar o que
        corrigir; nesse caso não é usada para gerar."""
        config = _configuracao(sessao)
        if enviada_por not in config.revisores:
            raise HTTPException(422, f"quem sobe a matriz é {', '.join(config.revisores)}")
        if not nome_arquivo.lower().endswith(".pptx"):
            raise HTTPException(422, "a matriz precisa ser um PowerPoint .pptx")
        dados = await request.body()
        if not dados:
            raise HTTPException(400, "nenhum arquivo enviado")
        if len(dados) > _LIMITE_DA_MATRIZ:
            raise HTTPException(413, f"arquivo grande demais (o limite é {_LIMITE_DA_MATRIZ // (1024 * 1024)} MB)")
        t = TipoDeMatriz(tipo)
        try:
            exame = marcadores.examinar(dados, t)
        except marcadores.MatrizIlegivel as falha:
            raise HTTPException(422, str(falha)) from falha
        m = MatrizDeProposta(
            tipo=t, nome_arquivo=nome_arquivo, conteudo_base64=base64.b64encode(dados).decode(), enviada_em=agora(),
            enviada_por=enviada_por, faltando=exame.faltando, desconhecidos=exame.desconhecidos,
        )
        sessao.add(m)
        sessao.commit()
        return _matriz_resumo(m)

    @r.get("/api/propostas/matrizes/{matriz_id}/pptx")
    def baixar_matriz(matriz_id: int, sessao: Session = Depends(obter_sessao)) -> Response:
        m = sessao.get(MatrizDeProposta, matriz_id)
        if m is None:
            raise HTTPException(404, "matriz não encontrada")
        return Response(
            base64.b64decode(m.conteudo_base64),
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": _disposicao(m.nome_arquivo), "Cache-Control": "no-store"},
        )

    def _configuracao_resposta(sessao: Session, c: ConfiguracaoDeProposta) -> ConfiguracaoResposta:
        ultimo = sessao.execute(
            sa.select(Proposta.numero, Proposta.ano).order_by(Proposta.ano.desc(), Proposta.numero.desc()).limit(1)
        ).first()
        return ConfiguracaoResposta(
            proximo_numero=c.proximo_numero, revisores=list(c.revisores), plano_bpo=c.plano_bpo,
            plano_plus=c.plano_plus, plano_cfo=c.plano_cfo, imposto=_imposto(sessao),
            ultimo_usado=_texto_do_numero(*ultimo) if ultimo else None,
        )

    @r.get("/api/propostas/configuracao", response_model=ConfiguracaoResposta)
    def configuracao(sessao: Session = Depends(obter_sessao)) -> ConfiguracaoResposta:
        c = _configuracao(sessao)
        sessao.commit()
        return _configuracao_resposta(sessao, c)

    @r.put("/api/propostas/configuracao", response_model=ConfiguracaoResposta)
    def editar_configuracao(corpo: Configuracao, sessao: Session = Depends(obter_sessao)) -> ConfiguracaoResposta:
        revisores = [n.strip() for n in corpo.revisores if n.strip()]
        if not revisores or len({n.casefold() for n in revisores}) != len(revisores):
            raise HTTPException(422, "informe quem revisa e envia, sem repetir nomes")
        if any(len(n) > 60 for n in revisores):
            raise HTTPException(422, "nome de quem envia com mais de 60 letras")
        ano = _ano_de_hoje()
        maior = sessao.scalar(sa.select(sa.func.max(Proposta.numero)).where(Proposta.ano == ano))
        if maior is not None and corpo.proximo_numero <= maior:
            raise HTTPException(422, f"o {_texto_do_numero(maior, ano)} já foi usado: o próximo precisa ser maior que {maior}")
        c = _configuracao(sessao, travar=True)
        c.proximo_numero, c.revisores = corpo.proximo_numero, revisores
        c.plano_bpo, c.plano_plus, c.plano_cfo = corpo.plano_bpo, corpo.plano_plus, corpo.plano_cfo
        sessao.commit()
        return _configuracao_resposta(sessao, c)

    return r
