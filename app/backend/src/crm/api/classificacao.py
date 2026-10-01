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
    AnaliseDaCarteira, AvaliacaoEmAndamento, ClassificacaoDoGrupo, Contrato, Empresa, GrupoEconomico, MixDeEquipe,
    PeriodoDeAvaliacao, RevisaoDaCarteira, VersaoDeParametros,
)
from crm.db.base import agora
from crm.domain import avaliacao as regra_de_avaliacao
from crm.domain import classificacao as regra
from crm.domain import parametros as regra_de_parametros
from crm.domain import porte as regras_de_porte
from crm.domain.listas import SituacaoContrato
from crm.domain.rentabilidade import PARAMETROS_DE_RENTABILIDADE
from crm.relatorios.exportacao_da_carteira import (
    EmpresaDaExportacao, LinhaDeHistorico, ParametrosDaPlanilha, gerar_planilha,
)

JANELA_PADRAO = (Decimal("0.6000"), Decimal("0.7000"))
"""Mínima e alvo do primeiro período, antes de alguém definir outras (pedido de 29/09/2026)."""

PORTES_VALIDOS = {p.value for p in regras_de_porte.Porte}

AVISO_DA_PLANILHA = (
    "A nota de rentabilidade vem da planilha de saúde da carteira, sem recálculo: a regra de atrito/disciplina "
    "ainda está pendente de validação (defeito 7.2)."
)

FONTE_DO_CALCULO = "Cálculo da carteira"
"""Começo da `fonte` das leituras gravadas pelo "Calcular carteira": nelas a rentabilidade é a do CRM."""

AVISO_DO_CRM = (
    "{n} grupo(s) com a nota de rentabilidade calculada pelo CRM no \"Calcular carteira\": margem no nível do "
    "grupo (horas pelo porte do grupo, atrito pelas notas), pela régua de margem dos parâmetros (decisão de "
    "29/09/2026). Nas leituras anteriores, vale a nota da planilha."
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
    rentabilidade_planilha: Decimal
    """A nota de rentabilidade tal como veio da planilha/deck de classificação (revisão 1), sem o
    recálculo do defeito 7.2. `rentabilidade` acima é a que entra no Score — pode ser a mesma ou a
    recalculada; esta aqui é sempre a original, para quem quer comparar com o material de fora."""
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
    porte_justificativa: str | None = None


class RespostasDeDisciplina(BaseModel):
    meses_no_prazo: int = Field(ge=0, le=3)
    cobranca_dobrada: bool
    atraso_recorrente: bool


class RespostasDeInadimplencia(BaseModel):
    meses_em_dia: int = Field(ge=0, le=3)
    em_negociacao: bool
    ja_suspenso: bool


class RespostasDaAvaliacao(BaseModel):
    """O que foi marcado no painel Avaliar. Os ids dos itens são os da tela; o que ela não
    reconhecer mais (item renomeado ou retirado) simplesmente não volta marcado."""

    complexidade: list[str] = Field(default_factory=list, max_length=20)
    risco: list[str] = Field(default_factory=list, max_length=20)
    cross_sell: list[str] = Field(default_factory=list, max_length=20)
    disciplina: RespostasDeDisciplina
    inadimplencia: RespostasDeInadimplencia


class AvaliacaoGravada(BaseModel):
    respostas: RespostasDaAvaliacao
    registrado_em: datetime
    atribuido_por: str | None


class RentabilidadeDoGrupoResposta(BaseModel):
    """Margem com o honorário praticado e o honorário que daria a margem alvo do período
    (`crm.domain.avaliacao.rentabilidade_do_grupo`), no nível do grupo."""

    porte: str
    horas: Decimal
    custo_de_servir: Decimal
    honorario_praticado: Decimal
    margem: Decimal | None
    honorario_calculado: Decimal
    defasagem: Decimal | None
    revisao_de_honorarios: bool


class RascunhoResposta(BaseModel):
    respostas: dict
    preenchidas: list[str]
    atualizado_em: datetime
    atualizado_por: str


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
    avaliacao: AvaliacaoGravada | None = None
    """As respostas da avaliação mais recente que as gravou — nem sempre a leitura mostrada,
    porque uma carga ou um recálculo posterior grava leitura nova sem respostas."""
    rascunho: RascunhoResposta | None = None
    """O rascunho do período aberto, se houver."""
    rentabilidade_do_grupo: RentabilidadeDoGrupoResposta | None = None
    """`None` quando o grupo ainda não tem porte confirmado."""
    receita_em_contrato: Decimal | None = None
    """Soma das mensalidades dos contratos ativos e suspensos (30/09/2026). É a receita praticada
    comparada com a calculada; `None` quando o grupo não tem contrato com mensalidade no CRM, e aí
    vale a receita da leitura (a da planilha)."""
    contratos: int = 0
    """Quantos contratos entraram na soma."""


class ClienteNovo(BaseModel):
    """Grupo com contrato ativo ou suspenso, com mensalidade, e sem nenhuma leitura de classificação
    (30/09/2026). Entra na avaliação do período com 7 abas; a primeira leitura nasce no "Calcular carteira"."""
    grupo_id: int
    grupo_nome: str
    desde: date | None
    """Início do contrato mais antigo; `None` se nenhum tem data."""
    receita_em_contrato: Decimal
    contratos: int
    empresas: list[EmpresaDoGrupo] = []
    porte: PorteDoGrupo
    rascunho: RascunhoResposta | None = None
    rentabilidade_do_grupo: RentabilidadeDoGrupoResposta | None = None
    """Com o porte e as notas de complexidade, disciplina e risco do rascunho; `None` enquanto faltar algum."""


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


class PendenciaDoPeriodo(BaseModel):
    grupo_id: int
    grupo_nome: str
    preenchidas: int
    abas: int = len(regra_de_avaliacao.ABAS)
    """Total de abas do grupo: 7 para cliente novo (com a aba Saúde), 6 para os demais."""
    novo: bool = False


class PeriodoResposta(BaseModel):
    id: int
    mes_de_referencia: date
    aberto_em: datetime
    aberto_por: str
    margem_minima: Decimal
    margem_alvo: Decimal
    calculado_em: datetime | None
    calculado_por: str | None
    grupos: int
    completos: int
    abas: int
    pendentes: list[PendenciaDoPeriodo]


class JanelaResposta(BaseModel):
    margem_minima: Decimal
    margem_alvo: Decimal
    origem: str
    """"período aberto", "último período" ou "padrão" (nenhum período ainda)."""


class ClassificacaoDaCarteira(BaseModel):
    referencia: date | None
    versao_dos_parametros: str | None
    isc: IscResposta | None
    retrato: RetratoResposta | None
    por_classe: dict[str, int]
    distribuicao_por_classe: list[FaixaDeClasseResposta]
    itens: list[ItemDaCarteira]
    avisos: list[str]
    periodo: PeriodoResposta | None = None
    janela: JanelaResposta | None = None
    novos: list[ClienteNovo] = []
    """Clientes novos, ainda sem leitura: não entram no ISC, no retrato nem na distribuição por classe."""


def _notas(c: ClassificacaoDoGrupo, rentabilidade_planilha: Decimal | None = None) -> NotasDoGrupo:
    return NotasDoGrupo(
        receita=c.nota_receita, rentabilidade=c.nota_rentabilidade,
        rentabilidade_planilha=rentabilidade_planilha if rentabilidade_planilha is not None else c.nota_rentabilidade,
        complexidade=c.complexidade, disciplina=c.disciplina,
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
        porte_justificativa=g.porte_justificativa,
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
    respostas: RespostasDaAvaliacao | None = None


MES = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$", description="AAAA-MM")


class JanelaEntrada(BaseModel):
    margem_minima: Decimal = Field(gt=0, lt=1)
    margem_alvo: Decimal = Field(gt=0, lt=1)


class AbrirPeriodo(BaseModel):
    autor: str = Field(min_length=2, max_length=120)
    mes: str = MES
    margem_minima: Decimal | None = Field(default=None, gt=0, lt=1)
    margem_alvo: Decimal | None = Field(default=None, gt=0, lt=1)
    """Sem as duas, repete a janela do período anterior (ou 60% e 70% no primeiro)."""


class EdicaoDaJanela(JanelaEntrada):
    autor: str = Field(min_length=2, max_length=120)


class RespostasDePorte(VolumetriaEntrada):
    porte: str = Field(min_length=1, max_length=20)
    justificativa: str | None = Field(default=None, max_length=500)


class RespostasDeSaude(BaseModel):
    """Aba "Saúde" do cliente novo (30/09/2026): quem já está na Carteira herda da leitura anterior."""

    semaforo: int = Field(ge=1, le=3)
    churn: int = Field(ge=1, le=5)


class RascunhoEntrada(BaseModel):
    """Só as abas que vierem mudam; as outras ficam como estavam no rascunho."""

    autor: str = Field(min_length=2, max_length=120)
    complexidade: list[str] | None = Field(default=None, max_length=20)
    risco: list[str] | None = Field(default=None, max_length=20)
    cross_sell: list[str] | None = Field(default=None, max_length=20)
    disciplina: RespostasDeDisciplina | None = None
    inadimplencia: RespostasDeInadimplencia | None = None
    porte: RespostasDePorte | None = None
    saude: RespostasDeSaude | None = None
    """Só para cliente novo."""


class CalcularCarteira(BaseModel):
    autor: str = Field(min_length=2, max_length=120)


class SimulacaoResposta(BaseModel):
    pendentes: list[str]
    """Abas sem rascunho neste período: entram com a nota atual da carteira (cliente novo não tem)."""
    notas_antes: dict[str, Decimal] | None
    """`None` para cliente novo, que não tem leitura anterior."""
    notas_depois: dict[str, Decimal | None]
    """Cliente novo: `None` na nota cuja aba ainda falta."""
    score_antes: Decimal | None
    score_depois: Decimal | None
    """`None` para cliente novo enquanto faltar alguma aba."""
    classe_antes: str | None
    classe_depois: str | None
    rentabilidade: RentabilidadeDoGrupoResposta | None
    novo: bool = False


class ResultadoDoCalculo(BaseModel):
    periodo: PeriodoResposta
    grupos_calculados: int


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


def _q4_janela(v: Decimal) -> Decimal:
    # O mesmo texto ("0.7000") no SQLite dos testes e no PostgreSQL.
    return Decimal(v).quantize(Decimal("0.0001"))


def janela_vigente(sessao: Session) -> JanelaResposta:
    """A margem mínima e a alvo em uso: as do período aberto, senão as do último, senão o padrão.
    Fora do roteador porque a proposta usa a mesma margem alvo para o preço sugerido."""
    aberto = sessao.scalars(sa.select(PeriodoDeAvaliacao).where(PeriodoDeAvaliacao.calculado_em.is_(None))).first()
    if aberto is not None:
        return JanelaResposta(margem_minima=_q4_janela(aberto.margem_minima), margem_alvo=_q4_janela(aberto.margem_alvo), origem="período aberto")
    ultimo = sessao.scalars(
        sa.select(PeriodoDeAvaliacao).order_by(PeriodoDeAvaliacao.mes_de_referencia.desc()).limit(1)
    ).first()
    if ultimo is not None:
        return JanelaResposta(margem_minima=_q4_janela(ultimo.margem_minima), margem_alvo=_q4_janela(ultimo.margem_alvo), origem="último período")
    return JanelaResposta(margem_minima=JANELA_PADRAO[0], margem_alvo=JANELA_PADRAO[1], origem="padrão")


def _versao_de_parametros_vigente(sessao: Session) -> VersaoDeParametros | None:
    return sessao.scalars(
        sa.select(VersaoDeParametros).order_by(VersaoDeParametros.criado_em.desc()).limit(1)
    ).first()


def _linha_de_parametros(v: VersaoDeParametros) -> regra_de_parametros.LinhaDeParametros:
    return regra_de_parametros.LinhaDeParametros(**{c: getattr(v, c) for c in _CAMPOS_DE_LINHA})


def _mix_de(v: VersaoDeParametros) -> list[regra_de_parametros.CelulaDeMix]:
    return [regra_de_parametros.CelulaDeMix(porte=m.porte, cargo=m.cargo, mix_percentual=m.mix_percentual) for m in v.mix]


def parametros_vigentes(sessao: Session) -> tuple[regra.Parametros, regra_de_parametros.ParametrosDeRentabilidade]:
    """A versão mais recente do banco; sem nenhuma gravada ainda, cai nas constantes do código
    (a mesma semente que a migração grava — nunca fica sem parâmetro)."""
    v = _versao_de_parametros_vigente(sessao)
    if v is None:
        return regra.PARAMETROS, PARAMETROS_DE_RENTABILIDADE
    linha = _linha_de_parametros(v)
    versao_str = f"banco-v{v.id}"
    return (
        regra_de_parametros.construir_parametros(linha, versao=versao_str),
        regra_de_parametros.construir_parametros_de_rentabilidade(linha, _mix_de(v), versao=versao_str),
    )


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

    def _leituras(sessao: Session) -> tuple[list, list]:
        """Todas as leituras (da mais recente para a mais antiga) e a mais recente de cada grupo
        não fundido — a carteira."""
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
        return todas, linhas

    def _receita_em_contrato(sessao: Session) -> dict[int, tuple[Decimal, int, date | None]]:
        """Grupo → (soma das mensalidades, contratos somados, início mais antigo), só contratos
        ativos e suspensos com mensalidade — o mesmo critério do MRR (`crm.domain.mrr`)."""
        return {
            g: (v, n, desde) for g, v, n, desde in sessao.execute(
                sa.select(Contrato.grupo_id, sa.func.sum(Contrato.preco_mensal), sa.func.count(Contrato.id),
                          sa.func.min(Contrato.data_inicio))
                .where(Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]),
                       Contrato.preco_mensal > 0)
                .group_by(Contrato.grupo_id)
            )
        }

    def _grupos_novos(sessao: Session, contratos: dict[int, tuple[Decimal, int, date | None]]) -> list[GrupoEconomico]:
        """Com contrato valendo e sem nenhuma leitura: o cliente novo (decisão de 30/09/2026)."""
        if not contratos:
            return []
        com_leitura = sa.select(ClassificacaoDoGrupo.id).where(ClassificacaoDoGrupo.grupo_id == GrupoEconomico.id).exists()
        return list(sessao.scalars(
            sa.select(GrupoEconomico)
            .where(GrupoEconomico.id.in_(contratos), GrupoEconomico.fundido_em_id.is_(None), ~com_leitura)
            .order_by(GrupoEconomico.nome)
        ))

    def _periodo_aberto(sessao: Session) -> PeriodoDeAvaliacao | None:
        return sessao.scalars(
            sa.select(PeriodoDeAvaliacao).where(PeriodoDeAvaliacao.calculado_em.is_(None))
        ).first()

    def _q4(v: Decimal) -> Decimal:
        # O mesmo texto ("0.7000") no SQLite dos testes e no PostgreSQL.
        return Decimal(v).quantize(Decimal("0.0001"))

    _janela = janela_vigente

    def _rascunhos(sessao: Session, periodo: PeriodoDeAvaliacao | None) -> dict[int, AvaliacaoEmAndamento]:
        if periodo is None:
            return {}
        return {a.grupo_id: a for a in sessao.scalars(
            sa.select(AvaliacaoEmAndamento).where(AvaliacaoEmAndamento.periodo_id == periodo.id)
        )}

    def _rascunho_resposta(a: AvaliacaoEmAndamento, *, novo: bool = False) -> RascunhoResposta:
        return RascunhoResposta(
            respostas=a.respostas, preenchidas=regra_de_avaliacao.abas_preenchidas(a.respostas, novo=novo),
            atualizado_em=a.atualizado_em, atualizado_por=a.atualizado_por,
        )

    def _periodo_resposta(
        sessao: Session, periodo: PeriodoDeAvaliacao, linhas: list | None = None,
        novos: list[GrupoEconomico] | None = None,
    ) -> PeriodoResposta:
        if linhas is None:
            _, linhas = _leituras(sessao)
        if novos is None:
            novos = _grupos_novos(sessao, _receita_em_contrato(sessao))
        rascunhos = _rascunhos(sessao, periodo)
        grupos = [(c.grupo_id, nome, False) for c, nome in linhas] + [(g.id, g.nome, True) for g in novos]
        pendentes = []
        for grupo_id, nome, novo in sorted(grupos, key=lambda x: x[1]):
            total = len(regra_de_avaliacao.ABAS_DO_NOVO if novo else regra_de_avaliacao.ABAS)
            feitas = len(regra_de_avaliacao.abas_preenchidas(rascunhos[grupo_id].respostas, novo=novo)) if grupo_id in rascunhos else 0
            if feitas < total:
                pendentes.append(PendenciaDoPeriodo(grupo_id=grupo_id, grupo_nome=nome, preenchidas=feitas, abas=total, novo=novo))
        return PeriodoResposta(
            id=periodo.id, mes_de_referencia=periodo.mes_de_referencia, aberto_em=periodo.aberto_em,
            aberto_por=periodo.aberto_por, margem_minima=_q4(periodo.margem_minima), margem_alvo=_q4(periodo.margem_alvo),
            calculado_em=periodo.calculado_em, calculado_por=periodo.calculado_por,
            grupos=len(grupos), completos=len(grupos) - len(pendentes), abas=len(regra_de_avaliacao.ABAS),
            pendentes=pendentes,
        )

    def _rentabilidade(
        honorario: Decimal, porte: str | None, complexidade: Decimal, disciplina: Decimal, risco: Decimal,
        janela: JanelaResposta, p_rent: regra_de_parametros.ParametrosDeRentabilidade,
    ) -> RentabilidadeDoGrupoResposta | None:
        if not porte or porte not in p_rent.horas_base:
            return None
        res = regra_de_avaliacao.rentabilidade_do_grupo(
            honorario=honorario, porte=porte, complexidade=complexidade, disciplina=disciplina, risco=risco,
            margem_minima=janela.margem_minima, margem_alvo=janela.margem_alvo, p=p_rent,
        )
        return RentabilidadeDoGrupoResposta(
            porte=porte, horas=res.horas, custo_de_servir=res.custo_de_servir, honorario_praticado=honorario,
            margem=res.margem, honorario_calculado=res.honorario_calculado, defasagem=res.defasagem,
            revisao_de_honorarios=res.revisao_de_honorarios,
        )

    def _receita_praticada(c: ClassificacaoDoGrupo, contratos: dict) -> Decimal:
        """O valor em contrato; sem contrato com mensalidade no CRM, a receita da leitura (da planilha)."""
        return contratos[c.grupo_id][0] if c.grupo_id in contratos else c.receita_mensal

    def _notas_do_novo(respostas: dict, porte: str | None) -> dict:
        """As notas que o rascunho de um cliente novo já permite: as das abas e a de Receita pelo porte."""
        notas = dict(regra_de_avaliacao.notas_das_respostas(respostas))
        if porte in regra_de_avaliacao.NOTA_DE_RECEITA_POR_PORTE:
            notas["receita"] = regra_de_avaliacao.NOTA_DE_RECEITA_POR_PORTE[porte]
        return notas

    def _porte_do_rascunho(respostas: dict, grupo: GrupoEconomico) -> str | None:
        return respostas["porte"]["porte"] if "porte" in respostas else grupo.porte

    def _clientes_novos(
        sessao: Session, novos: list[GrupoEconomico], contratos: dict, periodo: PeriodoDeAvaliacao | None,
        janela: JanelaResposta, p_rent: regra_de_parametros.ParametrosDeRentabilidade,
    ) -> list[ClienteNovo]:
        if not novos:
            return []
        rascunhos = _rascunhos(sessao, periodo)
        mensal = _mensalidade_por_empresa(sessao)
        empresas: dict[int, list[EmpresaDoGrupo]] = {}
        for e in sessao.scalars(
            sa.select(Empresa).where(Empresa.grupo_id.in_([g.id for g in novos])).order_by(Empresa.razao_social)
        ):
            empresas.setdefault(e.grupo_id, []).append(
                EmpresaDoGrupo(id=e.id, razao_social=e.razao_social, cnpj=e.cnpj, mensalidade=mensal.get(e.id))
            )
        saida = []
        for g in novos:
            valor, n, desde = contratos[g.id]
            rascunho = rascunhos.get(g.id)
            respostas = rascunho.respostas if rascunho else {}
            porte = _porte_do_rascunho(respostas, g)
            notas = _notas_do_novo(respostas, porte)
            rent = None
            if {"complexidade", "disciplina", "risco"} <= notas.keys():
                rent = _rentabilidade(valor, porte, Decimal(notas["complexidade"]), Decimal(notas["disciplina"]),
                                      Decimal(notas["risco"]), janela, p_rent)
            saida.append(ClienteNovo(
                grupo_id=g.id, grupo_nome=g.nome, desde=desde, receita_em_contrato=valor, contratos=n,
                empresas=empresas.get(g.id, []), porte=_porte(g),
                rascunho=_rascunho_resposta(rascunho, novo=True) if rascunho else None, rentabilidade_do_grupo=rent,
            ))
        return saida

    def _mensalidade_por_empresa(sessao: Session) -> dict[int, Decimal]:
        return {
            e: v for e, v in sessao.execute(
                sa.select(Contrato.empresa_id, sa.func.sum(Contrato.preco_mensal))
                .where(Contrato.empresa_id.is_not(None),
                       Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
                .group_by(Contrato.empresa_id)
            )
        }

    @r.get("/classificacao", response_model=ClassificacaoDaCarteira)
    def classificacao(sessao: Session = Depends(obter_sessao)) -> ClassificacaoDaCarteira:
        todas, linhas = _leituras(sessao)
        vistos = {c.grupo_id for c, _ in linhas}
        periodo = _periodo_aberto(sessao)
        janela = _janela(sessao)
        contratos = _receita_em_contrato(sessao)
        grupos_novos = _grupos_novos(sessao, contratos)
        _, p_rent = _parametros_vigentes(sessao)
        novos = _clientes_novos(sessao, grupos_novos, contratos, periodo, janela, p_rent)
        if not linhas:
            return ClassificacaoDaCarteira(referencia=None, versao_dos_parametros=None, isc=None, retrato=None,
                                           por_classe={}, distribuicao_por_classe=[], itens=[], avisos=[],
                                           periodo=_periodo_resposta(sessao, periodo, linhas, grupos_novos) if periodo else None,
                                           janela=janela, novos=novos)
        ativos = set(sessao.scalars(
            sa.select(Contrato.grupo_id).where(Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
        ))
        mensal = _mensalidade_por_empresa(sessao)
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
        # A rentabilidade "da planilha/deck" é sempre a revisão 1 da mesma referência — mesmo quando
        # a revisão mostrada (a mais recente) já foi recalculada pelo defeito 7.2.
        referencia_por_grupo = {c.grupo_id: c.referencia for c, _ in linhas}
        avaliacao_por_grupo: dict[int, AvaliacaoGravada] = {}
        for c, _ in todas:  # `todas` vem da mais recente para a mais antiga
            if c.respostas_da_avaliacao and c.grupo_id not in avaliacao_por_grupo:
                avaliacao_por_grupo[c.grupo_id] = AvaliacaoGravada(
                    respostas=RespostasDaAvaliacao.model_validate(c.respostas_da_avaliacao),
                    registrado_em=c.registrado_em, atribuido_por=c.atribuido_por,
                )
        rascunhos = _rascunhos(sessao, periodo)
        rentabilidade_por_grupo = {
            c.grupo_id: _rentabilidade(_receita_praticada(c, contratos), grupos_por_id[c.grupo_id].porte, c.complexidade,
                                       c.disciplina, c.risco_tecnico, janela, p_rent)
            for c, _ in linhas
        }
        rentabilidade_planilha_por_grupo = {
            c.grupo_id: c.nota_rentabilidade
            for c, _ in todas
            if c.revisao == 1 and referencia_por_grupo.get(c.grupo_id) == c.referencia
        }
        # Depois do "Calcular carteira", a nota que vale é a do CRM (decisão de 29/09/2026).
        for c, _ in linhas:
            if c.fonte.startswith(FONTE_DO_CALCULO):
                rentabilidade_planilha_por_grupo[c.grupo_id] = c.nota_rentabilidade
        itens = [
            ItemDaCarteira(
                grupo_id=c.grupo_id, grupo_nome=nome, receita_mensal=c.receita_mensal, score=c.score, classe=c.classe,
                classe_efetiva=c.classe_efetiva, alerta_de_churn=c.alerta_de_churn, em_cobranca=c.em_cobranca,
                eixo_de_acao=c.eixo_de_acao, semaforo=c.semaforo, churn=c.churn, sem_contrato_ativo=c.grupo_id not in ativos,
                empresas=empresas.get(c.grupo_id, []),
                notas=_notas(c, rentabilidade_planilha_por_grupo.get(c.grupo_id)),
                porte=_porte(grupos_por_id[c.grupo_id]),
                avaliacao=avaliacao_por_grupo.get(c.grupo_id),
                rascunho=_rascunho_resposta(rascunhos[c.grupo_id]) if c.grupo_id in rascunhos else None,
                rentabilidade_do_grupo=rentabilidade_por_grupo[c.grupo_id],
                receita_em_contrato=contratos[c.grupo_id][0] if c.grupo_id in contratos else None,
                contratos=contratos[c.grupo_id][1] if c.grupo_id in contratos else 0,
            )
            for c, nome in linhas
        ]
        calculado = regra.isc(regra.Unidade(c.receita_mensal, c.classe, c.semaforo, c.churn) for c, _ in linhas)
        retrato = regra.retrato(regra.GrupoDoRetrato(nome, c.receita_mensal, c.em_cobranca) for c, nome in linhas)
        por_classe: dict[str, int] = {}
        for i in itens:
            por_classe[i.classe] = por_classe.get(i.classe, 0) + 1
        do_crm = [c for c, _ in linhas if c.fonte.startswith(FONTE_DO_CALCULO)]
        de_carga = [(c, nome) for c, nome in linhas if not c.fonte.startswith(FONTE_DO_CALCULO)]
        da_planilha = [nome for c, nome in de_carga if c.rentabilidade_da_planilha]
        avisos = []
        if de_carga and len(da_planilha) == len(de_carga):
            avisos.append(AVISO_DA_PLANILHA)
        elif de_carga:
            avisos.append(AVISO_RECALCULADA)
            if da_planilha:
                avisos.append(f"{len(da_planilha)} grupo(s) mantiveram a nota de rentabilidade da planilha, porque os honorários "
                              "das empresas não fecham com a receita oficial: " + ", ".join(da_planilha) + ".")
        if do_crm:
            avisos.append(AVISO_DO_CRM.format(n=len(do_crm)))
        parados = [i.grupo_nome for i in itens if i.sem_contrato_ativo]
        if parados:
            avisos.append(f"{len(parados)} grupo(s) sem contrato ativo hoje continuam no snapshot da referência: "
                          + ", ".join(parados) + ".")
        if novos:
            avisos.append(f"{len(novos)} cliente(s) novo(s), com contrato e sem leitura, entram na Carteira no próximo "
                          "\"Calcular carteira\": " + ", ".join(n.grupo_nome for n in novos) + ".")
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
            periodo=_periodo_resposta(sessao, periodo, linhas, grupos_novos) if periodo else None, janela=janela,
            novos=novos,
        )

    def _ultima(sessao: Session, grupo_id: int) -> ClassificacaoDoGrupo | None:
        return sessao.scalars(
            sa.select(ClassificacaoDoGrupo).where(ClassificacaoDoGrupo.grupo_id == grupo_id)
            .order_by(ClassificacaoDoGrupo.referencia.desc(), ClassificacaoDoGrupo.revisao.desc()).limit(1)
        ).first()

    _versao_vigente = _versao_de_parametros_vigente
    _parametros_vigentes = parametros_vigentes

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

    def _notas_novas(anterior: ClassificacaoDoGrupo, mudou: dict) -> regra.Notas:
        return regra.Notas(
            receita=anterior.nota_receita, rentabilidade=mudou.get("rentabilidade", anterior.nota_rentabilidade),
            complexidade=mudou.get("complexidade", anterior.complexidade), disciplina=mudou.get("disciplina", anterior.disciplina),
            risco=mudou.get("risco", anterior.risco_tecnico), cross_sell=mudou.get("cross_sell", anterior.cross_sell),
            adimplencia=mudou.get("adimplencia", anterior.adimplencia), semaforo=mudou.get("semaforo", anterior.semaforo),
            churn=mudou.get("churn", anterior.churn),
        )

    def _notas_do_calculo(
        anterior: ClassificacaoDoGrupo, respostas: dict, porte: str | None,
        p_rent: regra_de_parametros.ParametrosDeRentabilidade, honorario: Decimal,
    ) -> tuple[dict, regra_de_avaliacao.NotaDeRentabilidadeDoGrupo | None]:
        """As notas das respostas e, com porte e honorário, a nota de Rentabilidade pela margem do CRM.
        Sem porte ou sem honorário, a rentabilidade fica a anterior. O honorário é o valor em contrato
        (ou, sem contrato no CRM, a receita da leitura)."""
        mudou = dict(regra_de_avaliacao.notas_das_respostas(respostas))
        if not porte or porte not in p_rent.horas_base:
            return mudou, None
        parcial = _notas_novas(anterior, mudou)
        rent = regra_de_avaliacao.nota_de_rentabilidade_do_grupo(
            honorario=honorario, porte=porte, complexidade=parcial.complexidade,
            disciplina=parcial.disciplina, risco=parcial.risco, p=p_rent,
        )
        if rent.nota is None:
            return mudou, None
        mudou["rentabilidade"] = rent.nota
        return mudou, rent

    def _nova_leitura(
        sessao: Session, anterior: ClassificacaoDoGrupo, mudou: dict, parametros: regra.Parametros, *,
        fonte: str, autor: str, motivo: str, respostas: dict | None,
        rentabilidade: regra_de_avaliacao.NotaDeRentabilidadeDoGrupo | None = None, receita: Decimal | None = None,
    ) -> ClassificacaoDoGrupo:
        """Leitura nova com as notas de `mudou`; o resto copia da anterior (snapshot imutável).
        `receita`, quando vem, é o valor em contrato e substitui a receita da anterior."""
        novas = _notas_novas(anterior, mudou)
        hoje = date.today()
        revisao = 1 + (sessao.scalar(
            sa.select(sa.func.max(ClassificacaoDoGrupo.revisao)).where(
                ClassificacaoDoGrupo.grupo_id == anterior.grupo_id, ClassificacaoDoGrupo.referencia == hoje)
        ) or 0)
        pontos = regra.score(novas, p=parametros)
        letra = regra.classe(pontos, p=parametros)
        return ClassificacaoDoGrupo(
            grupo_id=anterior.grupo_id, referencia=hoje, revisao=revisao, fonte=fonte,
            versao_dos_parametros=parametros.versao, atribuido_por=autor.strip(), motivo=motivo.strip(),
            receita_mensal=receita if receita is not None else anterior.receita_mensal,
            margem=rentabilidade.margem if rentabilidade else anterior.margem,
            horas_por_mes=rentabilidade.horas if rentabilidade else anterior.horas_por_mes,
            rentabilidade_da_planilha=False if rentabilidade else anterior.rentabilidade_da_planilha,
            nota_receita=novas.receita, nota_rentabilidade=novas.rentabilidade, complexidade=novas.complexidade,
            disciplina=novas.disciplina, risco_tecnico=novas.risco, cross_sell=novas.cross_sell, adimplencia=novas.adimplencia,
            semaforo=novas.semaforo, churn=novas.churn, score=pontos.quantize(Decimal("0.0001")), classe=letra,
            classe_efetiva=regra.classe_efetiva(letra, novas, p=parametros), alerta_de_churn=regra.alerta_de_churn(letra, novas, p=parametros),
            em_cobranca=regra.cobranca(novas, p=parametros), eixo_de_acao=regra.eixo_de_acao(letra, novas, p=parametros),
            respostas_da_avaliacao=respostas,
        )

    def _primeira_leitura(
        grupo_id: int, notas: dict, parametros: regra.Parametros, *, receita: Decimal,
        rentabilidade: regra_de_avaliacao.NotaDeRentabilidadeDoGrupo, fonte: str, autor: str, motivo: str,
        respostas: dict,
    ) -> ClassificacaoDoGrupo:
        """A primeira leitura de um cliente novo: todas as notas vêm do rascunho completo, a de Receita
        pelo porte e a de Rentabilidade pela margem do CRM (decisão de 30/09/2026)."""
        novas = regra.Notas(
            receita=notas["receita"], rentabilidade=rentabilidade.nota, complexidade=notas["complexidade"],
            disciplina=notas["disciplina"], risco=notas["risco"], cross_sell=notas["cross_sell"],
            adimplencia=notas["adimplencia"], semaforo=notas["semaforo"], churn=notas["churn"],
        )
        pontos = regra.score(novas, p=parametros)
        letra = regra.classe(pontos, p=parametros)
        return ClassificacaoDoGrupo(
            grupo_id=grupo_id, referencia=date.today(), revisao=1, fonte=fonte,
            versao_dos_parametros=parametros.versao, atribuido_por=autor.strip(), motivo=motivo.strip(),
            receita_mensal=receita, margem=rentabilidade.margem, horas_por_mes=rentabilidade.horas,
            rentabilidade_da_planilha=False,
            nota_receita=novas.receita, nota_rentabilidade=novas.rentabilidade, complexidade=novas.complexidade,
            disciplina=novas.disciplina, risco_tecnico=novas.risco, cross_sell=novas.cross_sell, adimplencia=novas.adimplencia,
            semaforo=novas.semaforo, churn=novas.churn, score=pontos.quantize(Decimal("0.0001")), classe=letra,
            classe_efetiva=regra.classe_efetiva(letra, novas, p=parametros), alerta_de_churn=regra.alerta_de_churn(letra, novas, p=parametros),
            em_cobranca=regra.cobranca(novas, p=parametros), eixo_de_acao=regra.eixo_de_acao(letra, novas, p=parametros),
            respostas_da_avaliacao=respostas,
        )

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
        mudou = corpo.model_dump(exclude={"autor", "motivo", "respostas"}, exclude_none=True)
        if not mudou:
            raise HTTPException(422, "informe ao menos uma nota para alterar")
        parametros, _ = _parametros_vigentes(sessao)
        sessao.add(_nova_leitura(
            sessao, anterior, mudou, parametros, fonte="Edição manual no CRM", autor=corpo.autor, motivo=corpo.motivo,
            respostas=corpo.respostas.model_dump() if corpo.respostas else None,
        ))
        sessao.commit()
        avisos = []
        if {"complexidade", "disciplina", "risco"} & mudou.keys():
            avisos.append("A nota de rentabilidade não foi recalculada: o CRM ainda não guarda os insumos de porte por empresa.")
        atual = classificacao(sessao)
        item = next(i for i in atual.itens if i.grupo_id == grupo_id)
        return ResultadoDaEdicao(item=item, isc=atual.isc, avisos=avisos)

    def _validar_janela(sessao: Session, minima: Decimal, alvo: Decimal) -> None:
        _, p_rent = _parametros_vigentes(sessao)
        if minima > alvo:
            raise HTTPException(422, "a margem mínima não pode passar da margem alvo")
        if alvo + p_rent.imposto >= 1:
            raise HTTPException(422, f"margem alvo + imposto ({p_rent.imposto:.0%}) precisa ficar abaixo de 100%")

    def _exigir_periodo_aberto(sessao: Session) -> PeriodoDeAvaliacao:
        periodo = _periodo_aberto(sessao)
        if periodo is None:
            raise HTTPException(409, "nenhum período de avaliação aberto: abra um na Carteira")
        return periodo

    def _grupo_da_carteira(
        sessao: Session, grupo_id: int,
    ) -> tuple[GrupoEconomico, ClassificacaoDoGrupo | None, tuple[Decimal, int, date | None] | None]:
        """O grupo, a leitura mais recente (`None` = cliente novo) e o valor em contrato."""
        grupo = sessao.get(GrupoEconomico, grupo_id)
        if grupo is None:
            raise HTTPException(404, "grupo não encontrado")
        if grupo.fundido_em_id is not None:
            raise HTTPException(409, "grupo fundido em outro: avalie o grupo que ficou")
        contrato = _receita_em_contrato(sessao).get(grupo_id)
        anterior = _ultima(sessao, grupo_id)
        if anterior is None and contrato is None:
            raise HTTPException(409, "o grupo ainda não tem classificação carregada nem contrato ativo com mensalidade")
        return grupo, anterior, contrato

    @r.get("/periodo", response_model=PeriodoResposta | None)
    def periodo_aberto(sessao: Session = Depends(obter_sessao)) -> PeriodoResposta | None:
        periodo = _periodo_aberto(sessao)
        return _periodo_resposta(sessao, periodo) if periodo else None

    @r.post("/periodo", response_model=PeriodoResposta, status_code=201)
    def abrir_periodo(corpo: AbrirPeriodo, sessao: Session = Depends(obter_sessao)) -> PeriodoResposta:
        if _periodo_aberto(sessao) is not None:
            raise HTTPException(409, "já há um período aberto: calcule a carteira dele antes de abrir outro")
        ano, mes = (int(x) for x in corpo.mes.split("-"))
        inicio = date(ano, mes, 1)
        if sessao.scalar(sa.select(PeriodoDeAvaliacao.id).where(PeriodoDeAvaliacao.mes_de_referencia == inicio)):
            raise HTTPException(409, f"o período {mes:02d}/{ano} já existe")
        anterior = _janela(sessao)
        minima = corpo.margem_minima if corpo.margem_minima is not None else anterior.margem_minima
        alvo = corpo.margem_alvo if corpo.margem_alvo is not None else anterior.margem_alvo
        _validar_janela(sessao, minima, alvo)
        periodo = PeriodoDeAvaliacao(
            mes_de_referencia=inicio, aberto_por=corpo.autor.strip(), margem_minima=minima, margem_alvo=alvo,
        )
        sessao.add(periodo)
        sessao.commit()
        return _periodo_resposta(sessao, periodo)

    @r.patch("/periodo/janela", response_model=PeriodoResposta)
    def editar_janela(corpo: EdicaoDaJanela, sessao: Session = Depends(obter_sessao)) -> PeriodoResposta:
        periodo = _exigir_periodo_aberto(sessao)
        _validar_janela(sessao, corpo.margem_minima, corpo.margem_alvo)
        periodo.margem_minima, periodo.margem_alvo = corpo.margem_minima, corpo.margem_alvo
        sessao.commit()
        return _periodo_resposta(sessao, periodo)

    @r.put("/periodo/grupos/{grupo_id}/rascunho", response_model=RascunhoResposta)
    def salvar_rascunho(grupo_id: int, corpo: RascunhoEntrada, sessao: Session = Depends(obter_sessao)) -> RascunhoResposta:
        """Grava o que vier, aba por aba, sem mexer no Score. Aba ausente continua como estava."""
        periodo = _exigir_periodo_aberto(sessao)
        _, anterior, _ = _grupo_da_carteira(sessao, grupo_id)
        novas = corpo.model_dump(exclude={"autor"}, exclude_none=True)
        if not novas:
            raise HTTPException(422, "informe ao menos uma aba")
        if "saude" in novas and anterior is not None:
            raise HTTPException(422, "a aba Saúde é só para cliente novo: quem já está na Carteira mantém semáforo e churn da leitura anterior")
        if "porte" in novas:
            porte = novas["porte"]
            if porte["porte"] not in PORTES_VALIDOS:
                raise HTTPException(422, f"porte desconhecido: {porte['porte']}")
            volumetria = {k: v for k, v in porte.items() if k in VolumetriaEntrada.model_fields}
            sugestao = regras_de_porte.sugerir_porte(regras_de_porte.Volumetria(**volumetria))
            difere = sugestao.porte is not None and sugestao.porte.value != porte["porte"]
            if difere and not (porte.get("justificativa") or "").strip():
                raise HTTPException(
                    422, f"justificativa obrigatória: o porte {porte['porte']} difere da sugestão do questionário "
                         f"({sugestao.porte.value})",
                )
            porte["justificativa"] = (porte.get("justificativa") or "").strip() or None
        rascunho = sessao.scalars(sa.select(AvaliacaoEmAndamento).where(
            AvaliacaoEmAndamento.periodo_id == periodo.id, AvaliacaoEmAndamento.grupo_id == grupo_id)).first()
        if rascunho is None:
            rascunho = AvaliacaoEmAndamento(periodo_id=periodo.id, grupo_id=grupo_id, respostas={},
                                            atualizado_por=corpo.autor.strip())
            sessao.add(rascunho)
        rascunho.respostas = {**(rascunho.respostas or {}), **novas}  # dict novo: o JSON só grava se o objeto muda
        rascunho.atualizado_por = corpo.autor.strip()
        rascunho.atualizado_em = agora()
        sessao.commit()
        return _rascunho_resposta(rascunho, novo=anterior is None)

    @r.post("/periodo/grupos/{grupo_id}/simulacao", response_model=SimulacaoResposta)
    def simular(grupo_id: int, sessao: Session = Depends(obter_sessao)) -> SimulacaoResposta:
        """"Calcular este cliente": o resultado de um grupo com o rascunho atual. **Não grava nada**;
        a carteira só muda no "Calcular carteira"."""
        periodo = _exigir_periodo_aberto(sessao)
        grupo, anterior, contrato = _grupo_da_carteira(sessao, grupo_id)
        rascunho = _rascunhos(sessao, periodo).get(grupo_id)
        respostas = rascunho.respostas if rascunho else {}
        parametros, p_rent = _parametros_vigentes(sessao)
        porte = _porte_do_rascunho(respostas, grupo)
        janela = _janela(sessao)
        if anterior is None:
            return _simular_novo(respostas, porte, contrato[0], parametros, p_rent, janela)
        honorario = contrato[0] if contrato else anterior.receita_mensal
        mudou, _ = _notas_do_calculo(anterior, respostas, porte, p_rent, honorario)
        depois = _notas_novas(anterior, mudou)
        pontos = regra.score(depois, p=parametros)
        letra = regra.classe(pontos, p=parametros)
        chaves = ("rentabilidade", "complexidade", "risco", "disciplina", "cross_sell", "adimplencia")
        nome_na_leitura = {"risco": "risco_tecnico", "rentabilidade": "nota_rentabilidade"}
        return SimulacaoResposta(
            pendentes=[a for a in regra_de_avaliacao.ABAS if a not in respostas],
            notas_antes={k: Decimal(getattr(anterior, nome_na_leitura.get(k, k))) for k in chaves},
            notas_depois={k: Decimal(getattr(depois, k)) for k in chaves},
            score_antes=anterior.score, score_depois=pontos.quantize(Decimal("0.0001")),
            classe_antes=anterior.classe_efetiva, classe_depois=regra.classe_efetiva(letra, depois, p=parametros),
            rentabilidade=_rentabilidade(honorario, porte, depois.complexidade, depois.disciplina,
                                         depois.risco, janela, p_rent),
        )

    def _rentabilidade_do_novo(
        notas: dict, porte: str | None, honorario: Decimal, p_rent: regra_de_parametros.ParametrosDeRentabilidade,
    ) -> regra_de_avaliacao.NotaDeRentabilidadeDoGrupo | None:
        if not porte or porte not in p_rent.horas_base or not {"complexidade", "disciplina", "risco"} <= notas.keys():
            return None
        rent = regra_de_avaliacao.nota_de_rentabilidade_do_grupo(
            honorario=honorario, porte=porte, complexidade=Decimal(notas["complexidade"]),
            disciplina=Decimal(notas["disciplina"]), risco=Decimal(notas["risco"]), p=p_rent,
        )
        return rent if rent.nota is not None else None

    def _simular_novo(
        respostas: dict, porte: str | None, honorario: Decimal, parametros: regra.Parametros,
        p_rent: regra_de_parametros.ParametrosDeRentabilidade, janela: JanelaResposta,
    ) -> SimulacaoResposta:
        """Cliente novo: sem "antes"; Score e Classe só com todas as 7 abas."""
        notas = _notas_do_novo(respostas, porte)
        rent = _rentabilidade_do_novo(notas, porte, honorario, p_rent)
        if rent is not None:
            notas["rentabilidade"] = rent.nota
        chaves = ("receita", "rentabilidade", "complexidade", "risco", "disciplina", "cross_sell", "adimplencia",
                  "semaforo", "churn")
        pendentes = [a for a in regra_de_avaliacao.ABAS_DO_NOVO if a not in respostas]
        pontos = letra = None
        if not pendentes and all(k in notas for k in chaves):
            completas = regra.Notas(**{k: notas[k] for k in chaves})
            pontos = regra.score(completas, p=parametros)
            letra = regra.classe_efetiva(regra.classe(pontos, p=parametros), completas, p=parametros)
            pontos = pontos.quantize(Decimal("0.0001"))
        rentabilidade = None
        if {"complexidade", "disciplina", "risco"} <= notas.keys():
            rentabilidade = _rentabilidade(honorario, porte, Decimal(notas["complexidade"]), Decimal(notas["disciplina"]),
                                           Decimal(notas["risco"]), janela, p_rent)
        return SimulacaoResposta(
            pendentes=pendentes, notas_antes=None,
            notas_depois={k: (Decimal(notas[k]) if k in notas else None) for k in chaves},
            score_antes=None, score_depois=pontos, classe_antes=None, classe_depois=letra,
            rentabilidade=rentabilidade, novo=True,
        )

    @r.post("/periodo/calcular", response_model=ResultadoDoCalculo)
    def calcular_carteira(corpo: CalcularCarteira, sessao: Session = Depends(obter_sessao)) -> ResultadoDoCalculo:
        """Aplica os rascunhos de **todos** os grupos de uma vez e fecha o período. Recusa enquanto
        faltar qualquer aba de qualquer grupo (decisão de 29/09/2026). A receita da leitura nova é o
        valor em contrato; o cliente novo ganha a primeira leitura (decisões de 30/09/2026)."""
        periodo = _exigir_periodo_aberto(sessao)
        _, linhas = _leituras(sessao)
        contratos = _receita_em_contrato(sessao)
        novos = _grupos_novos(sessao, contratos)
        situacao = _periodo_resposta(sessao, periodo, linhas, novos)
        if situacao.pendentes:
            nomes = ", ".join(p.grupo_nome for p in situacao.pendentes[:10])
            mais = f" e mais {len(situacao.pendentes) - 10}" if len(situacao.pendentes) > 10 else ""
            raise HTTPException(409, f"faltam {len(situacao.pendentes)} de {situacao.grupos} grupos: {nomes}{mais}")
        rascunhos = _rascunhos(sessao, periodo)
        parametros, p_rent = _parametros_vigentes(sessao)
        rotulo = f"{periodo.mes_de_referencia:%m/%Y}"
        autor = corpo.autor.strip()
        fonte = f"{FONTE_DO_CALCULO}, período {rotulo}"
        motivo = f"Avaliação do período {rotulo}, calculada para a carteira inteira"
        # Primeiro as primeiras leituras: se alguma não fecha, nada é gravado.
        primeiras = []
        for g in novos:
            respostas = rascunhos[g.id].respostas
            porte = respostas["porte"]["porte"]
            notas = _notas_do_novo(respostas, porte)
            rent = _rentabilidade_do_novo(notas, porte, contratos[g.id][0], p_rent)
            if rent is None or "receita" not in notas:
                raise HTTPException(409, f"{g.nome}: sem nota de Receita ou de Rentabilidade para o porte {porte}")
            primeiras.append((g, respostas, porte, notas, rent))
        for c, _nome in linhas:
            respostas = rascunhos[c.grupo_id].respostas
            grupo = sessao.get(GrupoEconomico, c.grupo_id)
            novo_porte = _aplicar_porte(grupo, respostas["porte"], autor)
            receita = contratos[c.grupo_id][0] if c.grupo_id in contratos else None
            mudou, rent = _notas_do_calculo(c, respostas, novo_porte, p_rent, receita if receita is not None else c.receita_mensal)
            sessao.add(_nova_leitura(
                sessao, c, mudou, parametros, fonte=fonte, autor=autor, motivo=motivo,
                respostas={k: v for k, v in respostas.items() if k != "porte"}, rentabilidade=rent, receita=receita,
            ))
        for g, respostas, porte, notas, rent in primeiras:
            _aplicar_porte(g, respostas["porte"], autor)
            sessao.add(_primeira_leitura(
                g.id, notas, parametros, receita=contratos[g.id][0], rentabilidade=rent, fonte=fonte, autor=autor,
                motivo=f"Primeira leitura de cliente novo, período {rotulo}",
                respostas={k: v for k, v in respostas.items() if k != "porte"},
            ))
        periodo.calculado_em, periodo.calculado_por = agora(), autor
        sessao.commit()
        return ResultadoDoCalculo(periodo=_periodo_resposta(sessao, periodo), grupos_calculados=len(linhas) + len(primeiras))

    def _aplicar_porte(grupo: GrupoEconomico, porte: dict, autor: str) -> str:
        """O porte do rascunho vai para o grupo, com a volumetria e a justificativa."""
        novo_porte = porte["porte"]
        grupo.porte_justificativa = porte.get("justificativa")
        for campo in VolumetriaEntrada.model_fields:  # ausente no rascunho = apagado na tela
            setattr(grupo, campo, porte.get(campo))
        if grupo.porte != novo_porte:
            grupo.porte, grupo.porte_definido_por, grupo.porte_definido_em = novo_porte, autor, agora()
        return novo_porte

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
        para Score, Classe, Classe Efetiva, Alerta, $$$ e Eixo de Ação
        (`crm.relatorios.exportacao_da_carteira`)."""
        linhas = sessao.execute(
            sa.select(ClassificacaoDoGrupo, GrupoEconomico.nome)
            .join(GrupoEconomico, GrupoEconomico.id == ClassificacaoDoGrupo.grupo_id)
            .order_by(GrupoEconomico.nome, GrupoEconomico.id, ClassificacaoDoGrupo.referencia,
                      ClassificacaoDoGrupo.revisao)
        ).all()
        de_exportacao = [
            LinhaDeHistorico(
                grupo_id=c.grupo_id, grupo_nome=nome, referencia=c.referencia, revisao=c.revisao, registrado_em=c.registrado_em,
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

        ids_dos_grupos = {c.grupo_id for c, _ in linhas}
        mensal = {
            e: v for e, v in sessao.execute(
                sa.select(Contrato.empresa_id, sa.func.sum(Contrato.preco_mensal))
                .where(Contrato.empresa_id.is_not(None),
                       Contrato.situacao.in_([SituacaoContrato.ATIVO, SituacaoContrato.SUSPENSO]))
                .group_by(Contrato.empresa_id)
            )
        }
        empresas_por_grupo: dict[int, list[EmpresaDaExportacao]] = {}
        for e in sessao.scalars(
            sa.select(Empresa).where(Empresa.grupo_id.in_(ids_dos_grupos)).order_by(Empresa.razao_social)
        ):
            empresas_por_grupo.setdefault(e.grupo_id, []).append(
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
