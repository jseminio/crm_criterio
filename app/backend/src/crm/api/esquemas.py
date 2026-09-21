"""O contrato entre a API e a tela.

Separado dos modelos do banco de propósito. A entidade guarda tudo; a tela
recebe o que precisa mostrar, e aceita só o que a pessoa pode mudar. Misturar
os dois faz com que um campo novo no banco vaze para a tela sem ninguém decidir.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from crm.domain.listas import (
    LinhaServico,
    MotivoRecusa,
    Origem,
    Situacao,
    SituacaoGrupo,
    SituacaoLead,
    Temperatura,
    TipoCanal,
    TipoDeOcorrencia,
)

__all__ = [
    "GrupoResumo",
    "OportunidadeResumo",
    "OportunidadeDetalhe",
    "OportunidadeEdicao",
    "LeadResumo",
    "LeadNovo",
    "LeadEdicao",
    "ConversaoDeLead",
    "Fusao",
    "Pagina",
    "ColunaDoFunil",
    "Listas",
    "RecorteResposta",
    "PendenciaResposta",
    "IndicadoresResposta",
    "ExecucaoResumo",
    "ExecucaoDetalhe",
    "OcorrenciaResposta",
    "ResumoPorCampo",
]


class Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GrupoResumo(Base):
    id: int
    nome: str
    situacao: SituacaoGrupo
    origem: Origem
    responsavel_cs: str | None = None
    data_entrada: date | None = None
    fundido_em_id: int | None = None
    quantas_oportunidades: int = 0


class OportunidadeResumo(Base):
    """O que cabe num cartão do funil."""

    id: int
    nome: str
    grupo_id: int
    grupo_nome: str | None = None
    situacao: Situacao
    temperatura: Temperatura | None = None
    servico: str | None = None
    tipo_servico: str | None = None
    captador: str | None = None
    tipo_canal: TipoCanal | None = None
    data_colocacao: date | None = None
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    proxima_acao: str | None = None
    proxima_acao_em: date | None = None


class OportunidadeDetalhe(OportunidadeResumo):
    canal: str | None = None
    linha_servico: LinhaServico | None = None
    data_aceite: date | None = None
    motivo_recusa: MotivoRecusa | None = None
    motivo_recusa_original: str | None = None
    valor_mensalizado: Decimal | None = None
    observacao: str | None = None
    origem: Origem
    linha_planilha: int | None = None


class OportunidadeEdicao(BaseModel):
    """O que a tela pode mudar. Tudo opcional: só o que vier é alterado.

    Preço, serviço e datas de origem **não estão aqui**. Enquanto a planilha
    roda em paralelo, ela é a fonte desses campos — editá-los nos dois lugares
    criaria divergência que ninguém saberia resolver. Entram no E4, quando a
    proposta passar a nascer no CRM.
    """

    situacao: Situacao | None = None
    temperatura: Temperatura | None = None
    motivo_recusa: MotivoRecusa | None = None
    data_aceite: date | None = None
    proxima_acao: str | None = Field(default=None, max_length=200)
    proxima_acao_em: date | None = None
    observacao: str | None = None


class LeadResumo(Base):
    id: int
    nome: str
    empresa_texto: str | None = None
    email: str | None = None
    telefone: str | None = None
    situacao: SituacaoLead
    temperatura: Temperatura | None = None
    tipo_canal: TipoCanal | None = None
    canal: str | None = None
    captador: str | None = None
    interesse: str | None = None
    campanha: str | None = None
    campanha_midia: str | None = None
    proxima_acao: str | None = None
    proxima_acao_em: date | None = None
    observacao: str | None = None
    convertido_em_id: int | None = None


class LeadNovo(BaseModel):
    """O cadastro de lead — a porta de entrada que a planilha nunca teve.

    Só `nome` é obrigatório. Exigir mais faria a pessoa inventar dado para
    conseguir salvar, e dado inventado é pior que campo vazio.
    """

    nome: str = Field(min_length=1, max_length=200)
    empresa_texto: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=200)
    telefone: str | None = Field(default=None, max_length=30)
    tipo_canal: TipoCanal | None = None
    canal: str | None = Field(default=None, max_length=120)
    captador: str | None = Field(default=None, max_length=10)
    interesse: str | None = Field(default=None, max_length=200)
    temperatura: Temperatura | None = None
    campanha: str | None = Field(default=None, max_length=120)
    campanha_midia: str | None = Field(default=None, max_length=120)
    proxima_acao: str | None = Field(default=None, max_length=200)
    proxima_acao_em: date | None = None
    observacao: str | None = None


class LeadEdicao(BaseModel):
    situacao: SituacaoLead | None = None
    temperatura: Temperatura | None = None
    interesse: str | None = Field(default=None, max_length=200)
    proxima_acao: str | None = Field(default=None, max_length=200)
    proxima_acao_em: date | None = None
    observacao: str | None = None


class ConversaoDeLead(BaseModel):
    """Vira oportunidade. O grupo existente é reaproveitado, ou nasce um novo."""

    grupo_id: int | None = None
    nome_do_grupo: str | None = Field(default=None, max_length=200)
    nome: str | None = Field(default=None, max_length=200)
    servico: str | None = Field(default=None, max_length=120)
    tipo_servico: str | None = Field(default=None, max_length=120)


class Fusao(BaseModel):
    absorvido_id: int


class ColunaDoFunil(BaseModel):
    """Uma coluna do kanban, com o que a pessoa precisa ver no topo."""

    situacao: Situacao
    quantas: int
    valor_mensal: Decimal
    valor_anual: Decimal
    oportunidades: list[OportunidadeResumo]


class RecorteResposta(Base):
    quantas: int
    valor_mensal: Decimal
    valor_anual: Decimal
    sem_preco_mensal: int
    com_preco_mensal: int


class PendenciaResposta(Base):
    """Um indicador que existe no desenho mas ainda não pode ser calculado.

    A tela mostra o motivo e o que falta, em vez de um traço ou de um zero: o
    zero pareceria medição, e o traço esconderia que há trabalho a fazer.
    """

    calculavel: bool
    motivo: str
    o_que_falta: str


class IndicadoresResposta(Base):
    em_aberto: RecorteResposta
    aceitas: RecorteResposta
    aceitas_com_data_de_aceite: int
    ciclo_medio: PendenciaResposta
    taxa_de_conversao: PendenciaResposta


class ExecucaoResumo(Base):
    """Uma rodada da carga, com os números que respondem: o que entrou, o que
    pede uma pessoa, o que foi ajustado, o que mudou."""

    id: int
    executada_em: datetime
    arquivo: str
    lidas: int
    de_outro_ano: int
    residuais: int
    importadas: int
    criadas: int
    atualizadas: int
    inalteradas: int
    gravadas: int
    ignoradas_incompletas: int
    ignoradas_duplicatas: int
    grupos_criados: int
    grupos_reaproveitados: int
    pendencias: int = 0
    ajustes: int = 0
    mudancas: int = 0


class ResumoPorCampo(Base):
    tipo: TipoDeOcorrencia
    campo: str | None
    quantas: int


class ExecucaoDetalhe(ExecucaoResumo):
    por_campo: list[ResumoPorCampo]


class OcorrenciaResposta(Base):
    id: int
    tipo: TipoDeOcorrencia
    linha: int | None
    campo: str | None
    texto: str


class Pagina[T](BaseModel):
    total: int
    itens: list[T]


class Listas(BaseModel):
    """As listas controladas, para a tela montar os seletores.

    Vêm do servidor porque `crm.domain.listas` é a única fonte. Duplicá-las no
    React criaria a segunda cópia da mesma regra.
    """

    situacoes: list[str]
    situacoes_de_lead: list[str]
    temperaturas: list[str]
    tipos_de_canal: list[str]
    tipos_de_canal_em_operacao: list[str]
    motivos_de_recusa: list[str]
    linhas_de_servico: list[str]
    situacoes_de_grupo: list[str]
    captadores: list[str]
