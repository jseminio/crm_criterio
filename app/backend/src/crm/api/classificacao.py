"""API da classificação da carteira (Etapa 3): classe, Score, alertas e eixo de ação por grupo, mais o ISC.

Somente leitura. Lê o **snapshot mais recente** de cada grupo; o ISC é recalculado aqui com a mesma regra
da carga (`crm.domain.classificacao`), nunca copiado da planilha. A nota de rentabilidade vem da planilha
(defeito 7.2 pendente) e a resposta avisa disso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Callable, Iterator

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from crm.agente.analise_da_carteira import (
    MODELO_PADRAO,
    ClienteDaApi,
    DadosDaCarteira,
    GrupoTravado,
    escrever_analise,
)
from crm.agente.config import ler_configuracao
from crm.agente.erros import mensagem_de_falha
from crm.agente.sdr import AgenteFalhou, Uso
from crm.db.modelos import (
    AnaliseDaCarteira, ClassificacaoDoGrupo, Contrato, Empresa, GrupoEconomico, MixDeEquipe,
    RevisaoDaCarteira, VersaoDeParametros,
)
from crm.db.base import agora
from crm.domain import classificacao as regra
from crm.domain import parametros as regra_de_parametros
from crm.domain import porte as regras_de_porte
from crm.domain.listas import SituacaoContrato
from crm.domain.rentabilidade import PARAMETROS_DE_RENTABILIDADE
from crm.relatorios.exportacao_da_carteira import (
    EmpresaDaExportacao, LinhaDeHistorico, ParametrosDaPlanilha, gerar_planilha,
)

AVISO_DA_PLANILHA = (
    "A nota de rentabilidade vem da planilha de saúde da carteira, sem recálculo: a regra de atrito/disciplina "
    "ainda está pendente de validação (defeito 7.2)."
)

AVISO_RECALCULADA = (
    "A rentabilidade foi recalculada no CRM com a disciplina invertida (6 − disciplina), corrigindo o defeito 7.2 "
    "da planilha (decisão de 26/09/2026). As demais notas vêm da planilha de saúde da carteira."
)


class EmpresaDoGrupo(BaseModel):
    id: int
    razao_social: str
    cnpj: str | None
    mensalidade: Decimal | None
    """Preço mensal dos contratos ativos e suspensos da empresa; `None` se não há contrato ligado a ela."""


class NotasDoGrupo(BaseModel):
    receita: Decimal
    rentabilidade: Decimal
    complexidade: Decimal
    disciplina: Decimal
    risco: Decimal
    cross_sell: Decimal
    adimplencia: Decimal
    semaforo: int
    churn: int | None
    rentabilidade_da_planilha: bool
    atribuido_por: str | None
    motivo: str | None
    registrado_em: datetime


class VolumetriaEntrada(BaseModel):
    """Os nove direcionadores da régua de porte, mais os três ajustes. Mesmos campos de
    `crm.domain.porte.Volumetria` — ver lá para o que cada um significa."""

    documentos_fiscais_mes: int | None = Field(default=None, ge=0)
    lancamentos_contabeis_mes: int | None = Field(default=None, ge=0)
    pagamentos_mes: int | None = Field(default=None, ge=0)
    contas_bancarias: int | None = Field(default=None, ge=0)
    conciliacoes_cartao_mes: int | None = Field(default=None, ge=0)
    empregados_clt: int | None = Field(default=None, ge=0)
    admissoes_desligamentos_mes: int | None = Field(default=None, ge=0)
    cnpjs_no_escopo: int | None = Field(default=None, ge=0)
    tomadores_de_servico: int | None = Field(default=None, ge=0)
    servicos_contratados_alem_do_primeiro: int = Field(default=0, ge=0)
    tem_consolidacao_de_grupo: bool = False
    e_auditada: bool = False


class SugestaoDePorteResposta(BaseModel):
    """O que a régua sugere — nunca o que decide. Ver `crm.domain.porte`."""

    calculavel: bool
    pontuacao: Decimal | None
    porte: str | None
    horas_base: int | None
    direcionadores_aplicados: int


class EdicaoDePorte(VolumetriaEntrada):
    autor: str = Field(min_length=2, max_length=120)
    porte: str | None = Field(default=None, max_length=20)
    """Confirma ou sobrepõe a sugestão da régua. Quando vier preenchido e diferente do porte
    atual, o servidor carimba `porte_definido_por`/`porte_definido_em` — instante do servidor,
    não do navegador, porque é este par que vira material pra recalibrar a régua depois."""


class PorteDoGrupo(VolumetriaEntrada):
    porte: str | None
    porte_definido_por: str | None
    porte_definido_em: datetime | None


class ItemDaCarteira(BaseModel):
    grupo_id: int
    grupo_nome: str
    receita_mensal: Decimal
    score: Decimal
    classe: str
    classe_efetiva: str
    alerta_de_churn: str | None
    em_cobranca: bool
    eixo_de_acao: str
    semaforo: int
    churn: int | None
    sem_contrato_ativo: bool
    """O grupo não tem contrato ativo hoje (ex.: baixado depois da referência)."""
    empresas: list[EmpresaDoGrupo] = []
    notas: NotasDoGrupo
    porte: PorteDoGrupo


class IscResposta(BaseModel):
    valor: Decimal
    zona: str
    componente_classe: Decimal
    componente_semaforo: Decimal
    componente_churn: Decimal
    receita_total: Decimal
    grupos: int
    fora_do_isc: int


class RetratoResposta(BaseModel):
    unidades: int
    receita_total: Decimal
    grupos_travados: int
    receita_travada: Decimal
    percentual_travado: Decimal


class FaixaDeClasseResposta(BaseModel):
    classe: str
    minimo: int
    maximo: int
    unidades: int
    percentual: Decimal
    dentro_da_meta: bool


class ClassificacaoDaCarteira(BaseModel):
    referencia: date | None
    versao_dos_parametros: str | None
    isc: IscResposta | None
    retrato: RetratoResposta | None
    por_classe: dict[str, int]
    distribuicao_por_classe: list[FaixaDeClasseResposta]
    itens: list[ItemDaCarteira]
    avisos: list[str]


def _notas(c: ClassificacaoDoGrupo) -> NotasDoGrupo:
    return NotasDoGrupo(
        receita=c.nota_receita, rentabilidade=c.nota_rentabilidade, complexidade=c.complexidade, disciplina=c.disciplina,
        risco=c.risco_tecnico, cross_sell=c.cross_sell, adimplencia=c.adimplencia, semaforo=c.semaforo, churn=c.churn,
        rentabilidade_da_planilha=c.rentabilidade_da_planilha, atribuido_por=c.atribuido_por, motivo=c.motivo,
        registrado_em=c.registrado_em,
    )


def _porte(g: GrupoEconomico) -> PorteDoGrupo:
    return PorteDoGrupo(
        documentos_fiscais_mes=g.documentos_fiscais_mes, lancamentos_contabeis_mes=g.lancamentos_contabeis_mes,
        pagamentos_mes=g.pagamentos_mes, contas_bancarias=g.contas_bancarias,
        conciliacoes_cartao_mes=g.conciliacoes_cartao_mes, empregados_clt=g.empregados_clt,
        admissoes_desligamentos_mes=g.admissoes_desligamentos_mes, cnpjs_no_escopo=g.cnpjs_no_escopo,
        tomadores_de_servico=g.tomadores_de_servico,
        servicos_contratados_alem_do_primeiro=g.servicos_contratados_alem_do_primeiro,
        tem_consolidacao_de_grupo=g.tem_consolidacao_de_grupo, e_auditada=g.e_auditada,
        porte=g.porte, porte_definido_por=g.porte_definido_por, porte_definido_em=g.porte_definido_em,
    )


def _sugestao_de_porte(volumetria: regras_de_porte.Volumetria) -> SugestaoDePorteResposta:
    sugestao = regras_de_porte.sugerir_porte(volumetria)
    return SugestaoDePorteResposta(
        calculavel=sugestao.calculavel, pontuacao=sugestao.pontuacao,
        porte=sugestao.porte.value if sugestao.porte else None,
        horas_base=sugestao.horas_base, direcionadores_aplicados=sugestao.direcionadores_aplicados,
    )


Nota = Decimal


class EdicaoDeNotas(BaseModel):
    """As notas humanas de um grupo. Só o que vier preenchido muda; o resto copia da leitura anterior."""

    autor: str = Field(min_length=2, max_length=120)
    motivo: str = Field(min_length=3, max_length=500)
    complexidade: Decimal | None = Field(default=None, ge=1, le=5)
    disciplina: Decimal | None = Field(default=None, ge=1, le=5)
    risco: Decimal | None = Field(default=None, ge=1, le=5)
    cross_sell: Decimal | None = Field(default=None, ge=1, le=5)
    adimplencia: Decimal | None = Field(default=None, ge=1, le=5)
    semaforo: int | None = Field(default=None, ge=1, le=3)
    churn: int | None = Field(default=None, ge=1, le=5)


class ResultadoDaEdicao(BaseModel):
    item: ItemDaCarteira
    isc: IscResposta | None
    avisos: list[str]


class AnaliseResposta(BaseModel):
    texto: str
    gerada_em: datetime
    gerada_por: str
    modelo: str
    custo_usd: Decimal | None


class GerarAnalise(BaseModel):
    autor: str = Field(min_length=2, max_length=120)


@dataclass
class ServicosDeAnalise:
    """O que a rota de análise usa de fora do banco — o teste troca por um cliente falso."""

    cliente: Callable[[], ClienteDaApi]
    modelo: str = MODELO_PADRAO


def servicos_de_analise_reais() -> ServicosDeAnalise:
    """Lidos do `.env` a cada uso, como o agente SDR. O modelo é sempre o Sonnet (mais barato):
    a análise só descreve números já calculados, não pesquisa nem precisa do modelo do SDR."""
    config = ler_configuracao()

    def cliente() -> ClienteDaApi:
        if not config.chave:
            raise AgenteFalhou(
                "A chave da API da Anthropic não está no .env (ANTHROPIC_API_KEY). "
                "Coloque a chave e tente de novo; nada foi gerado."
            )
        import anthropic

        return anthropic.Anthropic(api_key=config.chave)

    return ServicosDeAnalise(cliente=cliente)


class RegistrarRevisao(BaseModel):
    autor: str = Field(min_length=2, max_length=120)


class EditarMesDaRevisao(BaseModel):
    mes: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="AAAA-MM")


class RevisaoResposta(BaseModel):
    id: int
    mes_de_referencia: date
    registrada_em: datetime
    registrada_por: str
    isc_valor: Decimal
    isc_zona: str
    componente_classe: Decimal
    componente_semaforo: Decimal
    componente_churn: Decimal
    grupos: int
    receita_total: Decimal
    grupos_travados: int
    receita_travada: Decimal
    percentual_travado: Decimal
    baseado_em_referencia: date


class LeituraDoHistorico(BaseModel):
    id: int
    referencia: date
    revisao: int
    registrado_em: datetime
    fonte: str
    atribuido_por: str | None
    motivo: str | None
    score: Decimal
    classe_efetiva: str
    eixo_de_acao: str
    notas: NotasDoGrupo


class CelulaDeMixEntrada(BaseModel):
    porte: str
    cargo: str
    mix_percentual: Decimal = Field(ge=0, le=1)


class CelulaDeMixResposta(BaseModel):
    porte: str
    cargo: str
    mix_percentual: Decimal


_CAMPOS_DE_LINHA = tuple(regra_de_parametros.LinhaDeParametros.__dataclass_fields__)


class EdicaoDeParametros(BaseModel):
    """Uma edição vira **versão nova**, nunca sobrescreve a vigente (mesmo princípio de `EdicaoDeNotas`)."""

    autor: str = Field(min_length=2, max_length=120)
    motivo: str = Field(min_length=3, max_length=500)
    peso_receita: Decimal = Field(ge=0, le=1)
    peso_rentabilidade: Decimal = Field(ge=0, le=1)
    peso_cross_sell: Decimal = Field(ge=0, le=1)
    peso_complexidade: Decimal = Field(ge=0, le=1)
    peso_disciplina: Decimal = Field(ge=0, le=1)
    peso_risco: Decimal = Field(ge=0, le=1)
    peso_adimplencia: Decimal = Field(ge=0, le=1)
    corte_a: Decimal = Field(gt=0, le=5)
    corte_b: Decimal = Field(gt=0, le=5)
    trava_de_adimplencia: int = Field(ge=1, le=5)
    churn_alto: int = Field(ge=1, le=5)
    imposto: Decimal = Field(ge=0, le=1)
    teto_de_atrito: Decimal = Field(ge=0)
    atrito_nota_1: Decimal = Field(ge=0)
    atrito_nota_2: Decimal = Field(ge=0)
    atrito_nota_3: Decimal = Field(ge=0)
    atrito_nota_4: Decimal = Field(ge=0)
    atrito_nota_5: Decimal = Field(ge=0)
    corte_margem_2: Decimal = Field(ge=0, le=1)
    corte_margem_3: Decimal = Field(ge=0, le=1)
    corte_margem_4: Decimal = Field(ge=0, le=1)
    corte_margem_5: Decimal = Field(ge=0, le=1)
    horas_micro: int = Field(gt=0)
    horas_pequeno: int = Field(gt=0)
    horas_medio: int = Field(gt=0)
    horas_grande: int = Field(gt=0)
    horas_extra_grande: int = Field(gt=0)
    taxa_socio_senior: Decimal = Field(ge=0)
    taxa_socio_junior: Decimal = Field(ge=0)
    taxa_supervisor: Decimal = Field(ge=0)
    taxa_analista_senior: Decimal = Field(ge=0)
    taxa_analista_pleno: Decimal = Field(ge=0)
    taxa_analista_junior: Decimal = Field(ge=0)
    mix: list[CelulaDeMixEntrada]


class ParametrosResposta(BaseModel):
    id: int
    criado_em: datetime
    autor: str
    motivo: str
    peso_receita: Decimal
    peso_rentabilidade: Decimal
    peso_cross_sell: Decimal
    peso_complexidade: Decimal
    peso_disciplina: Decimal
    peso_risco: Decimal
    peso_adimplencia: Decimal
    corte_a: Decimal
    corte_b: Decimal
    trava_de_adimplencia: int
    churn_alto: int
    imposto: Decimal
    teto_de_atrito: Decimal
    atrito_nota_1: Decimal
    atrito_nota_2: Decimal
    atrito_nota_3: Decimal
    atrito_nota_4: Decimal
    atrito_nota_5: Decimal
    corte_margem_2: Decimal
    corte_margem_3: Decimal
    corte_margem_4: Decimal
    corte_margem_5: Decimal
    horas_micro: int
    horas_pequeno: int
    horas_medio: int
    horas_grande: int
    horas_extra_grande: int
    taxa_socio_senior: Decimal
    taxa_socio_junior: Decimal
    taxa_supervisor: Decimal
    taxa_analista_senior: Decimal
    taxa_analista_pleno: Decimal
    taxa_analista_junior: Decimal
    mix: list[CelulaDeMixResposta]
    custo_hora: dict[str, Decimal]
    """Calculado (taxa × mix, somado por Porte) — nunca digitado solto, pra nunca destoar da matriz."""


def roteador(
    obter_sessao: Callable[[], Iterator[Session]],
    servicos_de_analise: Callable[[], ServicosDeAnalise] = servicos_de_analise_reais,
) -> APIRouter:
    r = APIRouter(prefix="/api/carteira", tags=["carteira"])

    @r.get("/classificacao", response_model=ClassificacaoDaCarteira)
    def classificacao(sessao: Session = Depends(obter_sessao)) -> ClassificacaoDaCarteira:
        todas = sessao.execute(
            sa.select(ClassificacaoDoGrupo, GrupoEconomico.nome)
            .join(GrupoEconomico, GrupoEconomico.id == ClassificacaoDoGrupo.grupo_id)
            .where(GrupoEconomico.fundido_em_id.is_(None))
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc())
        ).all()
        vistos: set[int] = set()
        linhas = []
        for c, nome in todas:  # a leitura mais recente de cada grupo: referência maior, depois revisão maior
            if c.grupo_id not in vistos:
                vistos.add(c.grupo_id)
                linhas.append((c, nome))
        linhas.sort(key=lambda x: x[0].receita_mensal, reverse=True)
        if not linhas:
            return ClassificacaoDaCarteira(referencia=None, versao_dos_parametros=None, isc=None, retrato=None,
                                           por_classe={}, distribuicao_por_classe=[], itens=[], avisos=[])
        ativos = set(sessao.scalars(
            sa.select(Contrato.grupo_id).where(Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
        ))
        mensal = {
            e: v for e, v in sessao.execute(
                sa.select(Contrato.empresa_id, sa.func.sum(Contrato.preco_mensal))
                .where(Contrato.empresa_id.is_not(None),
                       Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
                .group_by(Contrato.empresa_id)
            )
        }
        empresas: dict[int, list[EmpresaDoGrupo]] = {}
        for e in sessao.scalars(
            sa.select(Empresa).where(Empresa.grupo_id.in_(vistos)).order_by(Empresa.razao_social)
        ):
            empresas.setdefault(e.grupo_id, []).append(
                EmpresaDoGrupo(id=e.id, razao_social=e.razao_social, cnpj=e.cnpj, mensalidade=mensal.get(e.id))
            )
        # Porte não é parte da classificação (não entra no Score, mora no grupo — ver `_porte`),
        # mas a tela de avaliação precisa do que já está salvo pra não sobrescrever com branco.
        grupos_por_id = {g.id: g for g in sessao.scalars(sa.select(GrupoEconomico).where(GrupoEconomico.id.in_(vistos)))}
        itens = [
            ItemDaCarteira(
                grupo_id=c.grupo_id, grupo_nome=nome, receita_mensal=c.receita_mensal, score=c.score, classe=c.classe,
                classe_efetiva=c.classe_efetiva, alerta_de_churn=c.alerta_de_churn, em_cobranca=c.em_cobranca,
                eixo_de_acao=c.eixo_de_acao, semaforo=c.semaforo, churn=c.churn, sem_contrato_ativo=c.grupo_id not in ativos,
                empresas=empresas.get(c.grupo_id, []), notas=_notas(c), porte=_porte(grupos_por_id[c.grupo_id]),
            )
            for c, nome in linhas
        ]
        calculado = regra.isc(regra.Unidade(c.receita_mensal, c.classe, c.semaforo, c.churn) for c, _ in linhas)
        retrato = regra.retrato(regra.GrupoDoRetrato(nome, c.receita_mensal, c.em_cobranca) for c, nome in linhas)
        por_classe: dict[str, int] = {}
        for i in itens:
            por_classe[i.classe] = por_classe.get(i.classe, 0) + 1
        da_planilha = [nome for c, nome in linhas if c.rentabilidade_da_planilha]
        if len(da_planilha) == len(linhas):
            avisos = [AVISO_DA_PLANILHA]
        else:
            avisos = [AVISO_RECALCULADA]
            if da_planilha:
                avisos.append(f"{len(da_planilha)} grupo(s) mantiveram a nota de rentabilidade da planilha, porque os honorários "
                              "das empresas não fecham com a receita oficial: " + ", ".join(da_planilha) + ".")
        parados = [i.grupo_nome for i in itens if i.sem_contrato_ativo]
        if parados:
            avisos.append(f"{len(parados)} grupo(s) sem contrato ativo hoje continuam no snapshot da referência: "
                          + ", ".join(parados) + ".")
        editados = [nome for c, nome in linhas if c.atribuido_por]
        if editados:
            avisos.append(f"{len(editados)} grupo(s) com nota editada à mão depois da carga: " + ", ".join(editados) + ".")
        if calculado and calculado.fora_do_isc:
            avisos.append(f"{calculado.fora_do_isc} grupo(s) sem nota de churn ficaram fora do ISC.")
        primeira = linhas[0][0]
        distribuicao = [
            FaixaDeClasseResposta(**{k: getattr(f, k) for k in FaixaDeClasseResposta.model_fields})
            for f in regra.distribuicao_por_classe(por_classe)
        ]
        return ClassificacaoDaCarteira(
            referencia=max(c.referencia for c, _ in linhas), versao_dos_parametros=primeira.versao_dos_parametros,
            isc=IscResposta(**{k: getattr(calculado, k) for k in IscResposta.model_fields}) if calculado else None,
            retrato=RetratoResposta(**{k: getattr(retrato, k) for k in RetratoResposta.model_fields}) if retrato else None,
            por_classe=dict(sorted(por_classe.items())), distribuicao_por_classe=distribuicao, itens=itens, avisos=avisos,
        )

    def _ultima(sessao: Session, grupo_id: int) -> ClassificacaoDoGrupo | None:
        return sessao.scalars(
            sa.select(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == grupo_id)
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc()).limit(1)
        ).first()

    def _versao_vigente(sessao: Session) -> VersaoDeParametros | None:
        return sessao.scalars(
            sa.select(VersaoDeParametros).order_by(VersaoDeParametros.criado_em.desc()).limit(1)
        ).first()

    def _linha_de_parametros(v: VersaoDeParametros) -> regra_de_parametros.LinhaDeParametros:
        return regra_de_parametros.LinhaDeParametros(**{c: getattr(v, c) for c in _CAMPOS_DE_LINHA})

    def _mix_de(v: VersaoDeParametros) -> list[regra_de_parametros.CelulaDeMix]:
        return [regra_de_parametros.CelulaDeMix(porte=m.porte, cargo=m.cargo, mix_percentual=m.mix_percentual) for m in v.mix]

    def _parametros_vigentes(sessao: Session) -> tuple[regra.Parametros, regra_de_parametros.ParametrosDeRentabilidade]:
        """A versão mais recente do banco; sem nenhuma gravada ainda, cai nas constantes do código
        (a mesma semente que a migração grava — nunca fica sem parâmetro)."""
        v = _versao_vigente(sessao)
        if v is None:
            return regra.PARAMETROS, PARAMETROS_DE_RENTABILIDADE
        linha = _linha_de_parametros(v)
        versao_str = f"banco-v{v.id}"
        return (
            regra_de_parametros.construir_parametros(linha, versao=versao_str),
            regra_de_parametros.construir_parametros_de_rentabilidade(linha, _mix_de(v), versao=versao_str),
        )

    def _parametros_resposta(v: VersaoDeParametros) -> ParametrosResposta:
        linha = _linha_de_parametros(v)
        mix = _mix_de(v)
        campos = {c: getattr(v, c) for c in _CAMPOS_DE_LINHA}
        return ParametrosResposta(
            id=v.id, criado_em=v.criado_em, autor=v.autor, motivo=v.motivo, **campos,
            mix=[CelulaDeMixResposta(porte=c.porte, cargo=c.cargo, mix_percentual=c.mix_percentual) for c in mix],
            custo_hora=regra_de_parametros.custo_hora_por_porte(linha, mix),
        )

    @r.get("/parametros", response_model=ParametrosResposta)
    def parametros_atuais(sessao: Session = Depends(obter_sessao)) -> ParametrosResposta:
        v = _versao_vigente(sessao)
        if v is None:
            raise HTTPException(409, "ainda não há parâmetros gravados no banco — rode a migração pendente (alembic upgrade head)")
        return _parametros_resposta(v)

    @r.post("/parametros", response_model=ParametrosResposta, status_code=201)
    def editar_parametros(corpo: EdicaoDeParametros, sessao: Session = Depends(obter_sessao)) -> ParametrosResposta:
        """Grava uma **versão nova**; a vigente até aqui não é tocada (mesmo princípio das notas).

        Pesos do Score e o mix de cada Porte precisam fechar 100% — senão a edição é recusada, com
        o motivo exato (`crm.domain.parametros.erros_de_pesos`/`erros_de_mix`).
        """
        linha = regra_de_parametros.LinhaDeParametros(**corpo.model_dump(exclude={"autor", "motivo", "mix"}))
        mix = [regra_de_parametros.CelulaDeMix(porte=c.porte, cargo=c.cargo, mix_percentual=c.mix_percentual) for c in corpo.mix]
        erros = regra_de_parametros.erros_de_pesos(linha) + regra_de_parametros.erros_de_mix(mix)
        if erros:
            raise HTTPException(422, "; ".join(erros))
        nova = VersaoDeParametros(
            autor=corpo.autor.strip(), motivo=corpo.motivo.strip(),
            **{c: getattr(linha, c) for c in _CAMPOS_DE_LINHA},
        )
        sessao.add(nova)
        sessao.flush()
        for c in corpo.mix:
            sessao.add(MixDeEquipe(versao_id=nova.id, porte=c.porte, cargo=c.cargo, mix_percentual=c.mix_percentual))
        sessao.commit()
        sessao.refresh(nova)
        return _parametros_resposta(nova)

    @r.post("/grupos/{grupo_id}/notas", response_model=ResultadoDaEdicao, status_code=201)
    def editar_notas(grupo_id: int, corpo: EdicaoDeNotas, sessao: Session = Depends(obter_sessao)) -> ResultadoDaEdicao:
        """Grava uma **nova leitura** com as notas alteradas; a anterior não é tocada (snapshot imutável).

        Score, classe, alerta e eixo são recalculados. **A nota de rentabilidade não muda**: o CRM não guarda porte
        nem insumos por empresa para refazer a margem, e a resposta avisa quando complexidade, disciplina ou risco mudam.
        """
        grupo = sessao.get(GrupoEconomico, grupo_id)
        if grupo is None:
            raise HTTPException(404, "grupo não encontrado")
        if grupo.fundido_em_id is not None:
            raise HTTPException(409, "grupo fundido em outro: edite o grupo que ficou")
        anterior = _ultima(sessao, grupo_id)
        if anterior is None:
            raise HTTPException(409, "o grupo ainda não tem classificação carregada")
        mudou = corpo.model_dump(exclude={"autor", "motivo"}, exclude_none=True)
        if not mudou:
            raise HTTPException(422, "informe ao menos uma nota para alterar")
        novas = regra.Notas(
            receita=anterior.nota_receita, rentabilidade=anterior.nota_rentabilidade,
            complexidade=mudou.get("complexidade", anterior.complexidade), disciplina=mudou.get("disciplina", anterior.disciplina),
            risco=mudou.get("risco", anterior.risco_tecnico), cross_sell=mudou.get("cross_sell", anterior.cross_sell),
            adimplencia=mudou.get("adimplencia", anterior.adimplencia), semaforo=mudou.get("semaforo", anterior.semaforo),
            churn=mudou.get("churn", anterior.churn),
        )
        hoje = date.today()
        revisao = 1 + (sessao.scalar(
            sa.select(sa.func.max(ClassificacaoDoGrupo.revisao)).where(
                ClassificacaoDoGrupo.grupo_id == grupo_id, ClassificacaoDoGrupo.referencia == hoje)
        ) or 0)
        parametros, _ = _parametros_vigentes(sessao)
        pontos = regra.score(novas, p=parametros)
        letra = regra.classe(pontos, p=parametros)
        nova = ClassificacaoDoGrupo(
            grupo_id=grupo_id, referencia=hoje, revisao=revisao, fonte="Edição manual no CRM",
            versao_dos_parametros=parametros.versao, atribuido_por=corpo.autor.strip(), motivo=corpo.motivo.strip(),
            receita_mensal=anterior.receita_mensal, margem=anterior.margem, horas_por_mes=anterior.horas_por_mes,
            rentabilidade_da_planilha=anterior.rentabilidade_da_planilha,
            nota_receita=novas.receita, nota_rentabilidade=novas.rentabilidade, complexidade=novas.complexidade,
            disciplina=novas.disciplina, risco_tecnico=novas.risco, cross_sell=novas.cross_sell, adimplencia=novas.adimplencia,
            semaforo=novas.semaforo, churn=novas.churn, score=pontos.quantize(Decimal("0.0001")), classe=letra,
            classe_efetiva=regra.classe_efetiva(letra, novas, p=parametros), alerta_de_churn=regra.alerta_de_churn(letra, novas, p=parametros),
            em_cobranca=regra.cobranca(novas, p=parametros), eixo_de_acao=regra.eixo_de_acao(letra, novas, p=parametros),
        )
        sessao.add(nova)
        sessao.commit()
        avisos = []
        if {"complexidade", "disciplina", "risco"} & mudou.keys():
            avisos.append("A nota de rentabilidade não foi recalculada: o CRM ainda não guarda os insumos de porte por empresa.")
        atual = classificacao(sessao)
        item = next(i for i in atual.itens if i.grupo_id == grupo_id)
        return ResultadoDaEdicao(item=item, isc=atual.isc, avisos=avisos)

    @r.post("/porte/sugestao", response_model=SugestaoDePorteResposta)
    def sugestao_de_porte(corpo: VolumetriaEntrada) -> SugestaoDePorteResposta:
        """Calcula sem gravar nada — a mesma régua que já roda pra oportunidade
        (`crm.domain.porte`), agora servindo a carteira também."""
        return _sugestao_de_porte(regras_de_porte.Volumetria(**corpo.model_dump()))

    @r.post("/grupos/{grupo_id}/porte", response_model=PorteDoGrupo)
    def editar_porte(grupo_id: int, corpo: EdicaoDePorte, sessao: Session = Depends(obter_sessao)) -> PorteDoGrupo:
        """Grava a volumetria e o porte confirmado **no grupo**, não numa nova revisão da
        classificação: porte não entra no Score, então não há por que duplicá-lo a cada revisão
        mensal (ver `crm.db.modelos.GrupoEconomico.porte`).

        Só o que **vier no corpo** muda — direcionador ausente preserva o valor já salvo, não vira
        `None`. Sem isso, reavaliar só um direcionador (ex.: recontar CNPJs no aniversário do
        contrato) apagaria os outros oito silenciosamente."""
        grupo = sessao.get(GrupoEconomico, grupo_id)
        if grupo is None:
            raise HTTPException(404, "grupo não encontrado")
        if grupo.fundido_em_id is not None:
            raise HTTPException(409, "grupo fundido em outro: edite o grupo que ficou")
        porte_mudou = corpo.porte is not None and grupo.porte != corpo.porte
        for campo, valor in corpo.model_dump(exclude={"autor", "porte"}, exclude_unset=True).items():
            setattr(grupo, campo, valor)
        if corpo.porte is not None:
            grupo.porte = corpo.porte
        if porte_mudou:
            grupo.porte_definido_por = corpo.autor.strip()
            grupo.porte_definido_em = agora()
        sessao.commit()
        return _porte(grupo)

    @r.get("/grupos/{grupo_id}/historico", response_model=list[LeituraDoHistorico])
    def historico(grupo_id: int, sessao: Session = Depends(obter_sessao)) -> list[LeituraDoHistorico]:
        linhas = sessao.scalars(
            sa.select(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == grupo_id)
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc())
        ).all()
        return [
            LeituraDoHistorico(
                id=c.id, referencia=c.referencia, revisao=c.revisao, registrado_em=c.registrado_em, fonte=c.fonte,
                atribuido_por=c.atribuido_por, motivo=c.motivo, score=c.score, classe_efetiva=c.classe_efetiva,
                eixo_de_acao=c.eixo_de_acao, notas=_notas(c),
            )
            for c in linhas
        ]

    @r.get("/exportar")
    def exportar(sessao: Session = Depends(obter_sessao)) -> Response:
        """O histórico completo — todas as leituras de todos os grupos, não só o snapshot atual —
        na visão Grupo → Empresa do modelo `Classificacao_Grupo_COMPLETO.xlsx`, com fórmula viva
        para Score, Rentabilidade, Classe, Classe Efetiva, Alerta, $$$ e Eixo de Ação
        (`crm.relatorios.exportacao_da_carteira`)."""
        linhas = sessao.execute(
            sa.select(ClassificacaoDoGrupo, GrupoEconomico.nome)
            .join(GrupoEconomico, GrupoEconomico.id == ClassificacaoDoGrupo.grupo_id)
            .order_by(GrupoEconomico.nome, ClassificacaoDoGrupo.referencia, ClassificacaoDoGrupo.revisao)
        ).all()
        de_exportacao = [
            LinhaDeHistorico(
                grupo_nome=nome, referencia=c.referencia, revisao=c.revisao, registrado_em=c.registrado_em,
                fonte=c.fonte, atribuido_por=c.atribuido_por, motivo=c.motivo, receita_mensal=c.receita_mensal,
                margem=c.margem, horas_por_mes=c.horas_por_mes,
                nota_receita=c.nota_receita, nota_rentabilidade=c.nota_rentabilidade, complexidade=c.complexidade,
                disciplina=c.disciplina, risco_tecnico=c.risco_tecnico, cross_sell=c.cross_sell,
                adimplencia=c.adimplencia, semaforo=c.semaforo, churn=c.churn, score=c.score, classe=c.classe,
                classe_efetiva=c.classe_efetiva, alerta_de_churn=c.alerta_de_churn, em_cobranca=c.em_cobranca,
                eixo_de_acao=c.eixo_de_acao,
            )
            for c, nome in linhas
        ]

        nomes_dos_grupos = {nome for _, nome in linhas}
        mensal = {
            e: v for e, v in sessao.execute(
                sa.select(Contrato.empresa_id, sa.func.sum(Contrato.preco_mensal))
                .where(Contrato.empresa_id.is_not(None),
                       Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
                .group_by(Contrato.empresa_id)
            )
        }
        empresas_por_grupo: dict[str, list[EmpresaDaExportacao]] = {}
        for e, grupo_nome in sessao.execute(
            sa.select(Empresa, GrupoEconomico.nome).join(GrupoEconomico, GrupoEconomico.id == Empresa.grupo_id)
            .where(GrupoEconomico.nome.in_(nomes_dos_grupos)).order_by(GrupoEconomico.nome, Empresa.razao_social)
        ):
            empresas_por_grupo.setdefault(grupo_nome, []).append(
                EmpresaDaExportacao(razao_social=e.razao_social, cnpj=e.cnpj, mensalidade=mensal.get(e.id))
            )

        parametros_atuais, _ = _parametros_vigentes(sessao)
        parametros_da_planilha = ParametrosDaPlanilha(
            corte_a=parametros_atuais.corte_a, corte_b=parametros_atuais.corte_b,
            trava_de_adimplencia=parametros_atuais.trava_de_adimplencia, churn_alto=parametros_atuais.churn_alto,
            peso_receita=parametros_atuais.peso_receita, peso_rentabilidade=parametros_atuais.peso_rentabilidade,
            peso_adimplencia=parametros_atuais.peso_adimplencia, peso_complexidade=parametros_atuais.peso_complexidade,
            peso_cross_sell=parametros_atuais.peso_cross_sell, peso_disciplina=parametros_atuais.peso_disciplina,
            peso_risco=parametros_atuais.peso_risco,
        )
        conteudo = gerar_planilha(de_exportacao, parametros_da_planilha, empresas_por_grupo)
        nome = f"carteira-historico-{date.today():%Y%m%d}.xlsx"
        return Response(
            conteudo, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{nome}"'},
        )

    def _analise_resposta(a: AnaliseDaCarteira) -> AnaliseResposta:
        return AnaliseResposta(texto=a.texto, gerada_em=a.gerada_em, gerada_por=a.gerada_por, modelo=a.modelo,
                               custo_usd=a.custo_usd)

    @r.get("/analise", response_model=AnaliseResposta | None)
    def analise(sessao: Session = Depends(obter_sessao)) -> AnaliseResposta | None:
        a = sessao.scalars(
            sa.select(AnaliseDaCarteira).order_by(AnaliseDaCarteira.gerada_em.desc()).limit(1)
        ).first()
        return _analise_resposta(a) if a else None

    @r.post("/analise", response_model=AnaliseResposta, status_code=201)
    def gerar_analise(corpo: GerarAnalise, sessao: Session = Depends(obter_sessao)) -> AnaliseResposta:
        """Escreve uma leitura nova da carteira com a IA. Nunca decide nada — só descreve os números
        já calculados. Cada chamada custa uma fração de centavo (Sonnet, sem busca na web)."""
        atual = classificacao(sessao)
        if atual.isc is None or atual.retrato is None:
            raise HTTPException(409, "ainda não há classificação carregada para descrever")
        dados = DadosDaCarteira(
            isc_valor=atual.isc.valor, isc_zona=atual.isc.zona, componente_classe=atual.isc.componente_classe,
            componente_semaforo=atual.isc.componente_semaforo, componente_churn=atual.isc.componente_churn,
            unidades=atual.retrato.unidades, receita_total=atual.retrato.receita_total,
            grupos_travados=[GrupoTravado(i.grupo_nome, i.receita_mensal) for i in atual.itens if i.em_cobranca],
            receita_travada=atual.retrato.receita_travada, percentual_travado=atual.retrato.percentual_travado,
            por_classe=atual.por_classe,
        )
        servicos = servicos_de_analise()
        uso = Uso(servicos.modelo)
        try:
            texto = escrever_analise(servicos.cliente(), servicos.modelo, dados, uso)
        except Exception as falha:
            raise HTTPException(502, mensagem_de_falha(falha)) from falha
        linha = AnaliseDaCarteira(
            gerada_por=corpo.autor.strip(), texto=texto, modelo=servicos.modelo,
            tokens_entrada=uso.tokens_entrada, tokens_saida=uso.tokens_saida, custo_usd=uso.custo_usd,
        )
        sessao.add(linha)
        sessao.commit()
        return _analise_resposta(linha)

    def _revisao_resposta(v: RevisaoDaCarteira) -> RevisaoResposta:
        return RevisaoResposta(
            id=v.id, mes_de_referencia=v.mes_de_referencia, registrada_em=v.registrada_em,
            registrada_por=v.registrada_por, isc_valor=v.isc_valor, isc_zona=v.isc_zona,
            componente_classe=v.componente_classe, componente_semaforo=v.componente_semaforo,
            componente_churn=v.componente_churn, grupos=v.grupos, receita_total=v.receita_total,
            grupos_travados=v.grupos_travados, receita_travada=v.receita_travada,
            percentual_travado=v.percentual_travado, baseado_em_referencia=v.baseado_em_referencia,
        )

    @r.get("/revisoes", response_model=list[RevisaoResposta])
    def revisoes(sessao: Session = Depends(obter_sessao)) -> list[RevisaoResposta]:
        linhas = sessao.scalars(
            sa.select(RevisaoDaCarteira).order_by(RevisaoDaCarteira.mes_de_referencia)
        ).all()
        return [_revisao_resposta(v) for v in linhas]

    @r.post("/revisoes", response_model=RevisaoResposta, status_code=201)
    def registrar_revisao(corpo: RegistrarRevisao, sessao: Session = Depends(obter_sessao)) -> RevisaoResposta:
        """Congela o ISC e o retrato de agora como a revisão do mês civil corrente.

        Uma por mês: já existindo uma para este mês, recusa (o mês certo a editar é a data dela,
        não uma segunda linha). Não recalcula nada — é o placar de hoje, depois de quem revisa
        atualizar as notas que precisar."""
        atual = classificacao(sessao)
        if atual.isc is None or atual.retrato is None:
            raise HTTPException(409, "ainda não há classificação carregada para revisar")
        mes = date(agora().year, agora().month, 1)
        existente = sessao.scalar(sa.select(RevisaoDaCarteira).where(RevisaoDaCarteira.mes_de_referencia == mes))
        if existente is not None:
            raise HTTPException(
                409, f"já existe uma revisão para {mes.strftime('%m/%Y')}, registrada por "
                     f"{existente.registrada_por}. Para corrigir o mês de uma revisão, edite a data dela."
            )
        linha = RevisaoDaCarteira(
            mes_de_referencia=mes, registrada_por=corpo.autor.strip(), isc_valor=atual.isc.valor,
            isc_zona=atual.isc.zona, componente_classe=atual.isc.componente_classe,
            componente_semaforo=atual.isc.componente_semaforo, componente_churn=atual.isc.componente_churn,
            grupos=atual.retrato.unidades, receita_total=atual.retrato.receita_total,
            grupos_travados=atual.retrato.grupos_travados, receita_travada=atual.retrato.receita_travada,
            percentual_travado=atual.retrato.percentual_travado, baseado_em_referencia=atual.referencia,
        )
        sessao.add(linha)
        sessao.commit()
        return _revisao_resposta(linha)

    @r.patch("/revisoes/{revisao_id}/mes", response_model=RevisaoResposta)
    def editar_mes_da_revisao(
        revisao_id: int, corpo: EditarMesDaRevisao, sessao: Session = Depends(obter_sessao)
    ) -> RevisaoResposta:
        """Corrige só o rótulo (o mês a que a revisão se refere) — os números congelados não mudam."""
        linha = sessao.get(RevisaoDaCarteira, revisao_id)
        if linha is None:
            raise HTTPException(404, "revisão não encontrada")
        ano, mes_num = (int(x) for x in corpo.mes.split("-"))
        novo_mes = date(ano, mes_num, 1)
        conflito = sessao.scalar(
            sa.select(RevisaoDaCarteira).where(
                RevisaoDaCarteira.mes_de_referencia == novo_mes, RevisaoDaCarteira.id != revisao_id
            )
        )
        if conflito is not None:
            raise HTTPException(409, f"já existe uma revisão para {novo_mes.strftime('%m/%Y')}")
        linha.mes_de_referencia = novo_mes
        sessao.commit()
        return _revisao_resposta(linha)

    return r
