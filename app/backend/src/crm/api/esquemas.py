"""O contrato entre a API e a tela.

Separado dos modelos do banco de propósito. A entidade guarda tudo; a tela
recebe o que precisa mostrar, e aceita só o que a pessoa pode mudar. Misturar
os dois faz com que um campo novo no banco vaze para a tela sem ninguém decidir.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from crm.domain.listas import (
    AderenciaDaPromessa,
    AutorDaMensagem,
    CanalDeAbordagem,
    DesfechoDaConversa,
    DestinoDoTransbordo,
    IndiceDeReajuste,
    MotivoDeDescarte,
    MotivoDeTransbordo,
    Tom,
    LinhaServico,
    MotivoRecusa,
    Origem,
    OrigemDoDado,
    Situacao,
    SituacaoAbordagem,
    SituacaoContrato,
    SituacaoGrupo,
    SituacaoLead,
    TemaDaExpectativa,
    Temperatura,
    TipoCanal,
    IniciativaDoEncerramento,
    MotivoDeEncerramento,
    TipoDeEventoDeContrato,
    TipoDeOcorrencia,
    SituacaoDaAprovacao,
)
from crm.domain.questionario_do_lead import MensagemDoQuestionario, PassoDoQuestionario

__all__ = [
    "GrupoResumo",
    "OportunidadeResumo",
    "OportunidadeDetalhe",
    "OportunidadeEdicao",
    "OportunidadeNova",
    "SugestaoDePorteResposta",
    "LeadResumo",
    "LeadNovo",
    "LeadEdicao",
    "ConversaoDeLead",
    "ConversaNova",
    "ConversaResposta",
    "MensagemNova",
    "MensagemResposta",
    "Encerramento",
    "QuestionarioDoLead",
    "PendenciaDoQuestionario",
    "EstadoDoDisparoResposta",
    "NotaDaConversa",
    "ParametrosDoSdrResposta",
    "ParametrosDoSdrEdicao",
    "InvestimentoResposta",
    "InvestimentoEdicao",
    "ContratoResumo",
    "ContratoDetalhe",
    "AbordagemResumo",
    "AbordagemDetalhe",
    "AbordagemNova",
    "AbordagemEdicao",
    "PedidoDeVersao",
    "Aprovacao",
    "ResumoDasAbordagens",
    "ContratoEdicao",
    "ConversaoEmContrato",
    "Fusao",
    "Pagina",
    "ColunaDoFunil",
    "Listas",
    "RecorteResposta",
    "CicloMedioDeVendasResposta",
    "CoberturaResposta",
    "DependenciaDeCanalResposta",
    "TaxaDeConversaoResposta",
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
    observacao: str | None = None
    data_entrada: date | None = None
    fundido_em_id: int | None = None
    quantas_oportunidades: int = 0


class GrupoEdicao(BaseModel):
    """Correção dos dados cadastrais do grupo. Só o que vier muda; o resto continua como estava.

    **Situação fica de fora de propósito:** hoje ela muda sozinha (proposta aceita vira Cliente) —
    editar à mão aqui abriria brecha pra destoar dessa regra sem ninguém perceber."""

    nome: str | None = Field(default=None, min_length=1, max_length=200)
    responsavel_cs: str | None = Field(default=None, max_length=10)
    observacao: str | None = None


class MrrAtualResposta(Base):
    valor: Decimal
    contratos: int
    suspenso_valor: Decimal
    suspenso_contratos: int
    sem_preco_mensal: int
    grupos: int = 0
    ticket_por_grupo: Decimal | None = None
    mediana_por_grupo: Decimal | None = None


class MovimentoDeMrrResposta(Base):
    de: date
    ate: date
    mrr_inicio: Decimal
    novo: Decimal
    expansao: Decimal
    reajuste: Decimal
    contracao: Decimal
    churn_cliente: Decimal
    churn_criterio: Decimal
    churn: Decimal
    mrr_fim: Decimal
    variacao: Decimal
    nrr: Decimal | None
    grr: Decimal | None


class MrrResposta(Base):
    """O MRR dos **contratos registrados no CRM** — parcial enquanto a carteira anterior
    não estiver carregada (`cobertura_completa` falso: não se compara com a meta). Com
    ela, vem a comparação com a meta e o alerta oficiais."""

    atual: MrrAtualResposta
    movimento: MovimentoDeMrrResposta
    contratos_registrados: int
    contratos_da_carteira_anterior: int
    """Quantos vieram da carga da planilha de saúde da carteira (sem data de assinatura)."""
    cobertura_completa: bool
    aviso: str
    meta: Decimal
    alerta: Decimal
    contra_a_meta: str | None = None
    """"abaixo_do_alerta", "entre" ou "na_meta"; `None` com o MRR parcial (não se compara)."""
    falta_para_a_meta: Decimal | None = None
    """Quanto falta para R$ 400 mil (zero se já atingiu); `None` com o MRR parcial."""
    imposto: Decimal = Decimal("0")
    """A alíquota (Parâmetros de cálculo) que levou os contratos líquidos para bruto."""
    contratos_liquidos: int = 0
    """Ativos e suspensos com preço marcados como líquidos: entraram no MRR com o imposto."""
    contratos_sem_base: int = 0
    """Ativos e suspensos com preço sem bruto/líquido informado: somados como estão."""


class ItemDaAgendaResposta(Base):
    tipo: str
    id: int
    titulo: str
    subtitulo: str | None = None
    situacao: str
    temperatura: str | None = None
    captador: str | None = None
    valor_anual: Decimal | None = None
    proxima_acao: str | None = None
    proxima_acao_em: date | None = None
    balde: str
    dias_de_atraso: int
    dias_desde_o_envio: int | None = None
    oportunidade_id: int | None = None


class AgendaResposta(Base):
    """A fila de follow-up. `contagens` traz todos os baldes, mesmo os vazios."""

    hoje: date
    contagens: dict[str, int]
    itens: list[ItemDaAgendaResposta]


class FusaoFeita(Base):
    """Uma fusão que foi feita, com o que ela moveu, para poder ser desfeita."""

    id: int
    principal_id: int
    principal_nome: str
    absorvido_id: int
    absorvido_nome: str
    feita_em: datetime
    desfeita_em: datetime | None = None
    reconstruida: bool = False
    """Registro refeito a partir de um backup (a fusão é anterior ao registro)."""
    empresas: int
    oportunidades: int
    contatos: int
    contratos: int
    pode_desfazer: bool


class SugestaoDeFusao(Base):
    """Um bloco de grupos que parecem ser o mesmo cliente. Só sugestão."""

    confianca: str
    motivo: str
    principal_id: int
    grupos: list[GrupoResumo]


class OportunidadeResumo(Base):
    """O que cabe num cartão do funil."""

    id: int
    nome: str
    grupo_id: int
    grupo_nome: str | None = None
    empresa_id: int | None = None
    """A empresa (CNPJ) da oportunidade; o grupo vem dela (01/10/2026)."""
    empresa_razao_social: str | None = None
    empresa_cnpj: str | None = None
    situacao: Situacao
    temperatura: Temperatura | None = None
    servico: str | None = None
    tipo_servico: str | None = None
    captador: str | None = None
    tipo_canal: TipoCanal | None = None
    data_colocacao: date | None = None
    data_envio_proposta: date | None = None
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    quantidade_parcelas: int | None = None
    reajuste: IndiceDeReajuste | None = None
    proxima_acao: str | None = None
    proxima_acao_em: date | None = None


class SugestaoDePorteResposta(Base):
    """O que a régua sugere — nunca o que decide. Ver `crm.domain.porte`."""

    calculavel: bool
    pontuacao: Decimal | None = None
    porte: str | None = None
    horas_base: int | None = None
    direcionadores_aplicados: int


class MudancaDePreco(Base):
    """Uma linha do histórico de preço: o valor antes, o valor depois, quando e por quê."""

    id: int
    registrado_em: datetime
    origem: str
    motivo: str | None = None
    preco_mensal_anterior: Decimal | None = None
    preco_mensal_novo: Decimal | None = None
    preco_anual_anterior: Decimal | None = None
    preco_anual_novo: Decimal | None = None


class OportunidadeDetalhe(OportunidadeResumo):
    tem_contrato: bool = False
    """Já virou contrato: a empresa não troca mais por aqui."""
    canal: str | None = None
    linha_servico: LinhaServico | None = None
    servico_descricao: str | None = None
    servico_tema: str | None = None
    data_aceite: date | None = None
    motivo_recusa: MotivoRecusa | None = None
    motivo_recusa_original: str | None = None
    valor_mensalizado: Decimal | None = None
    observacao: str | None = None
    origem: Origem
    linha_planilha: int | None = None

    complexidade: int | None = None
    risco_tecnico: int | None = None

    documentos_fiscais_mes: int | None = None
    lancamentos_contabeis_mes: int | None = None
    pagamentos_mes: int | None = None
    contas_bancarias: int | None = None
    conciliacoes_cartao_mes: int | None = None
    empregados_clt: int | None = None
    admissoes_desligamentos_mes: int | None = None
    cnpjs_no_escopo: int | None = None
    tomadores_de_servico: int | None = None
    servicos_contratados_alem_do_primeiro: int = 0
    tem_consolidacao_de_grupo: bool = False
    e_auditada: bool = False

    origem_da_volumetria: dict[str, str] = {}
    """`{campo: "Entrevista" | "Questionário"}`, só para campos preenchidos."""
    historico_de_preco: list[MudancaDePreco] = []
    """Mais recente primeiro. Só cresce: reajustar não apaga o preço anterior."""

    porte: str | None = None
    porte_definido_por: str | None = None
    porte_definido_em: datetime | None = None
    sugestao_de_porte: SugestaoDePorteResposta | None = None
    """Calculada a cada leitura, nunca gravada — muda se a régua mudar."""


class OportunidadeEdicao(BaseModel):
    """O que a tela pode mudar. Tudo opcional: só o que vier é alterado.

    Nome e empresa entraram em 01/10/2026 (Karine): trocar a empresa leva o grupo
    junto, e a oportunidade que já virou contrato não troca de empresa.

    Preço, serviço e data de originação entraram em 22/09/2026 (E4): a
    proposta já pode nascer e ser ajustada direto no CRM, não só na planilha.
    O campo mudado aqui entra em `campos_do_crm` (mesmo mecanismo que já
    protegia situação/temperatura) — a recarga da planilha não sobrescreve de
    volta.
    """

    nome: str | None = Field(default=None, min_length=1, max_length=200)
    empresa_id: int | None = None

    situacao: Situacao | None = None
    temperatura: Temperatura | None = None
    captador: str | None = Field(default=None, max_length=10)
    tipo_canal: TipoCanal | None = None
    canal: str | None = Field(default=None, max_length=120)
    """Captador e origem (tipo de canal e canal) editáveis no painel — Karine, 07/10/2026. Como os
    outros campos da carga, o que mudar aqui entra em `campos_do_crm` e a recarga não desfaz."""
    motivo_recusa: MotivoRecusa | None = None
    data_aceite: date | None = None
    proxima_acao: str | None = Field(default=None, max_length=200)
    proxima_acao_em: date | None = None
    observacao: str | None = None
    servico: str | None = Field(default=None, max_length=120)
    tipo_servico: str | None = Field(default=None, max_length=120)
    servico_descricao: str | None = Field(default=None, max_length=2000)
    servico_tema: str | None = Field(default=None, max_length=80)
    data_colocacao: date | None = None
    data_envio_proposta: date | None = None
    """Pedida ao mover de Enviar proposta para Em avaliação (10/10/2026)."""
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None

    complexidade: int | None = Field(default=None, ge=1, le=5)
    risco_tecnico: int | None = Field(default=None, ge=1, le=5)

    documentos_fiscais_mes: int | None = Field(default=None, ge=0)
    lancamentos_contabeis_mes: int | None = Field(default=None, ge=0)
    pagamentos_mes: int | None = Field(default=None, ge=0)
    contas_bancarias: int | None = Field(default=None, ge=0)
    conciliacoes_cartao_mes: int | None = Field(default=None, ge=0)
    empregados_clt: int | None = Field(default=None, ge=0)
    admissoes_desligamentos_mes: int | None = Field(default=None, ge=0)
    cnpjs_no_escopo: int | None = Field(default=None, ge=0)
    tomadores_de_servico: int | None = Field(default=None, ge=0)
    servicos_contratados_alem_do_primeiro: int | None = Field(default=None, ge=0)
    tem_consolidacao_de_grupo: bool | None = None
    e_auditada: bool | None = None

    origem_da_volumetria: dict[str, OrigemDoDado] | None = None
    """Substitui o mapa inteiro. As chaves precisam ser direcionadores da volumetria."""
    motivo_do_preco: str | None = Field(default=None, max_length=200)
    """Por que o preço mudou ("reajuste anual"). Só é lido quando o preço muda de fato;
    não é gravado na oportunidade, e sim na linha do histórico."""

    porte: str | None = Field(default=None, max_length=20)
    porte_definido_por: str | None = Field(default=None, max_length=10)
    """Confirma ou sobrepõe a sugestão da régua. Quando `porte` vier
    preenchido, o servidor grava `porte_definido_em` com o instante da
    gravação — não dá pra confiar em relógio de navegador para o registro que
    vai recalibrar a régua depois."""


class OportunidadeNova(BaseModel):
    """Uma proposta nascida no CRM — sem passar pela planilha nem por um lead.

    O grupo existente é reaproveitado pelo nome; se não houver, nasce um novo
    — mesmo padrão de `ConversaoDeLead`.
    """

    nome: str = Field(min_length=1, max_length=200)
    empresa_id: int | None = None
    """A empresa escolhida na base de empresas; quando vem, o grupo é o dela e
    `grupo_id`/`nome_do_grupo` são ignorados. A tela exige (Karine, 01/10/2026)."""
    grupo_id: int | None = None
    nome_do_grupo: str | None = Field(default=None, max_length=200)
    servico: str | None = Field(default=None, max_length=120)
    tipo_servico: str | None = Field(default=None, max_length=120)
    servico_descricao: str | None = Field(default=None, max_length=2000)
    servico_tema: str | None = Field(default=None, max_length=80)
    data_colocacao: date | None = None
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    quantidade_parcelas: int | None = Field(default=None, ge=1, le=120)
    """Só vale em serviço recorrente (C1): lá o preço anual é mensal × parcelas."""
    reajuste: IndiceDeReajuste | None = None
    captador: str | None = Field(default=None, max_length=10)
    temperatura: Temperatura | None = None
    tipo_canal: TipoCanal | None = None
    canal: str | None = Field(default=None, max_length=120)


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
    interesse_descricao: str | None = None
    interesse_tema: str | None = None
    campanha: str | None = None
    campanha_midia: str | None = None
    proxima_acao: str | None = None
    proxima_acao_em: date | None = None
    observacao: str | None = None
    convertido_em_id: int | None = None
    cnpj: str | None = None
    porte_estimado: str | None = None
    qualificado_em: datetime | None = None
    descartado_em: datetime | None = None
    motivo_descarte: MotivoDeDescarte | None = None
    reuniao_marcada_para: datetime | None = None
    nao_contatar: bool = False
    criado_em: datetime | None = None
    primeiro_contato_em: datetime | None = None
    primeiro_contato_pelo_sdr: datetime | None = None
    """A primeira mensagem do SDR: a tela sugere esta data enquanto o primeiro contato não foi gravado."""
    aderencia: AderenciaDaPromessa | None = None
    aderencia_sobre: list[TemaDaExpectativa] | None = None
    aderencia_esperava: str | None = None


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
    interesse_descricao: str | None = Field(default=None, max_length=2000)
    interesse_tema: str | None = Field(default=None, max_length=80)
    temperatura: Temperatura | None = None
    campanha: str | None = Field(default=None, max_length=120)
    campanha_midia: str | None = Field(default=None, max_length=120)
    proxima_acao: str | None = Field(default=None, max_length=200)
    proxima_acao_em: date | None = None
    observacao: str | None = None
    cnpj: str | None = Field(default=None, max_length=18)


class LeadEdicao(BaseModel):
    """Qualificado exige porte estimado; descartado exige o motivo. O servidor
    carimba `qualificado_em` e `descartado_em`."""

    situacao: SituacaoLead | None = None
    temperatura: Temperatura | None = None
    interesse: str | None = Field(default=None, max_length=200)
    interesse_descricao: str | None = Field(default=None, max_length=2000)
    interesse_tema: str | None = Field(default=None, max_length=80)
    proxima_acao: str | None = Field(default=None, max_length=200)
    proxima_acao_em: date | None = None
    observacao: str | None = None
    cnpj: str | None = Field(default=None, max_length=18)
    porte_estimado: str | None = Field(default=None, max_length=20)
    motivo_descarte: MotivoDeDescarte | None = None
    reuniao_marcada_para: datetime | None = None
    nao_contatar: bool | None = None
    primeiro_contato_em: datetime | None = None
    aderencia: AderenciaDaPromessa | None = None
    """"Bate" limpa o "sobre o quê" e o "o que esperava": só fazem sentido quando não bate."""
    aderencia_sobre: list[TemaDaExpectativa] | None = Field(default=None, max_length=5)
    aderencia_esperava: str | None = Field(default=None, max_length=300)


class ConversaoDeLead(BaseModel):
    """Vira oportunidade. O grupo existente é reaproveitado, ou nasce um novo."""

    grupo_id: int | None = None
    nome_do_grupo: str | None = Field(default=None, max_length=200)
    nome: str | None = Field(default=None, max_length=200)
    servico: str | None = Field(default=None, max_length=120)
    tipo_servico: str | None = Field(default=None, max_length=120)
    servico_descricao: str | None = Field(default=None, max_length=2000)
    servico_tema: str | None = Field(default=None, max_length=80)


class ContratoResumo(Base):
    """O que cabe numa linha da lista de contratos."""

    id: int
    grupo_id: int
    grupo_nome: str | None = None
    oportunidade_id: int | None = None
    empresa_id: int | None = None
    anterior_ao_crm: bool = False
    """Da carteira que já existia antes do CRM: sem data de assinatura conhecida."""
    escopo: str | None = None
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    base_do_valor: Literal["bruto", "liquido"] | None = None
    """Se o preço já inclui o imposto. Vazio = não informado."""
    data_inicio: date | None = None
    data_fim: date | None = None
    situacao: SituacaoContrato
    signatario: str | None = None
    saida_em: date | None = None
    """Saída efetiva anunciada (10/10/2026): com o contrato Ativo, ele está em aviso de saída até esta data."""


class EventoDeContratoResposta(Base):
    """Um fato do contrato, guardado com o antes e o depois. Só cresce."""

    id: int
    tipo: TipoDeEventoDeContrato
    data_do_evento: date
    registrado_em: datetime
    descricao: str | None = None
    motivo_categoria: MotivoDeEncerramento | None = None
    iniciativa: IniciativaDoEncerramento | None = None
    preco_mensal_anterior: Decimal | None = None
    preco_mensal_novo: Decimal | None = None
    preco_anual_anterior: Decimal | None = None
    preco_anual_novo: Decimal | None = None
    escopo_anterior: str | None = None
    escopo_novo: str | None = None
    data_fim_anterior: date | None = None
    data_fim_nova: date | None = None
    data_da_saida: date | None = None
    """Só no Encerramento: a saída efetiva; `data_do_evento` é o anúncio."""


class AprovacaoResposta(Base):
    """Um evento acima da alçada, esperando ou já decidido (02/10/2026)."""

    id: int
    contrato_id: int
    grupo_nome: str | None = None
    tipo: TipoDeEventoDeContrato
    data_do_evento: date
    descricao: str | None = None
    preco_mensal_anterior: Decimal | None = None
    preco_mensal_novo: Decimal | None = None
    preco_anual_anterior: Decimal | None = None
    preco_anual_novo: Decimal | None = None
    escopo_anterior: str | None = None
    escopo_novo: str | None = None
    motivo: str
    pedido_por: str
    pedido_em: datetime
    situacao: SituacaoDaAprovacao
    decidido_por: str | None = None
    decidido_em: datetime | None = None
    motivo_da_recusa: str | None = None


class Recusa(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


class ContratoDetalhe(ContratoResumo):
    documento_assinado: str | None = None
    observacao: str | None = None
    eventos: list[EventoDeContratoResposta] = []
    """Mais recente primeiro."""
    aprovacao_pendente: AprovacaoResposta | None = None
    """Evento acima da alçada esperando quem aprova: o contrato não recebe outro até a decisão."""


class EventoDeContratoNovo(BaseModel):
    """Registra um evento. O que cada tipo exige está em `crm.domain.eventos_de_contrato`."""

    tipo: TipoDeEventoDeContrato
    data_do_evento: date | None = None
    """Sem data, vale hoje (data do servidor)."""
    descricao: str | None = Field(default=None, max_length=500)
    motivo_categoria: MotivoDeEncerramento | None = None
    """Só vale no Encerramento; nos outros tipos é recusado."""
    iniciativa: IniciativaDoEncerramento | None = None
    """Quem decidiu encerrar. Só vale no Encerramento, onde é obrigatória."""
    escopo_novo: str | None = Field(default=None, max_length=200)
    preco_mensal_novo: Decimal | None = None
    preco_anual_novo: Decimal | None = None
    data_fim_nova: date | None = None
    data_da_saida: date | None = None
    """Só no Encerramento: a saída efetiva (vazia = a data do anúncio). Até ela o contrato segue Ativo."""


class ContratoEdicao(BaseModel):
    """O que a tela pode mudar. Tudo opcional: só o que vier é alterado."""

    escopo: str | None = Field(default=None, max_length=200)
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    base_do_valor: Literal["bruto", "liquido"] | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    situacao: SituacaoContrato | None = None
    documento_assinado: str | None = Field(default=None, max_length=400)
    signatario: str | None = Field(default=None, max_length=200)
    observacao: str | None = None


class ExclusaoDaOportunidade(BaseModel):
    """O que sai e o que fica se a oportunidade for excluída (04/10/2026). `recusa` preenchida: não sai."""

    recusa: str | None
    propostas: int
    pendencias: int
    precos: int
    questionarios: int
    leads: int
    vendas_da_reuniao: int
    sai_da_conversao: bool


class PedidoDeExclusao(BaseModel):
    motivo: str = Field(min_length=1, max_length=1000)


class ConversaoEmContrato(BaseModel):
    """Vira contrato. Escopo e preço partem da oportunidade aceita, mas podem
    ser ajustados aqui — o que foi aceito na proposta nem sempre é exatamente
    o que vai assinado no papel."""

    escopo: str | None = Field(default=None, max_length=200)
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    data_inicio: date | None = None
    signatario: str | None = Field(default=None, max_length=200)


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


class CicloMedioDeVendasResposta(Base):
    """Originação → aceite — decisão de Eduardo em 23/09/2026.

    Só entra aceita com as duas datas. `aceitas_sem_as_duas_datas` diz quantas
    ficaram de fora, para a tela não fingir que a amostra é o total.
    """

    dias: Decimal | None
    amostra: int
    dias_ate_o_envio: Decimal | None = None
    """Originação → envio da proposta (10/10/2026): o tempo de preparar e enviar."""
    amostra_ate_o_envio: int = 0
    dias_do_envio_ao_aceite: Decimal | None = None
    """Envio → aceite: o tempo de decisão do cliente."""
    amostra_do_envio_ao_aceite: int = 0
    aceitas_sem_as_duas_datas: int
    calculavel: bool


class CoberturaResposta(Base):
    """"Aumentar os pontos de contato" virando número — documento-de-negocio.md,
    seção 12.5."""

    em_aberto_com_proxima_acao: int
    em_aberto_total: int
    com_volumetria_completa: int
    total: int
    percentual_com_proxima_acao: Decimal | None
    percentual_com_volumetria_completa: Decimal | None


class DependenciaDeCanalResposta(Base):
    """Quanto do funil nasce da rede dos sócios."""

    da_rede_de_socios: int
    total: int
    percentual: Decimal | None


class TaxaDeConversaoResposta(Base):
    """Aceitas ÷ decididas — decisão de Eduardo em 22/09/2026.

    Em aberto não entra no denominador: ainda pode fechar. `abaixo_do_alerta`
    e `atingiu_a_meta` vêm em `None` só quando não há decidida nenhuma — não
    calculável é diferente de "abaixo do alerta".
    """

    aceitas: int
    decididas: int
    percentual: Decimal | None
    calculavel: bool
    abaixo_do_alerta: bool | None
    atingiu_a_meta: bool | None
    meta: Decimal
    alerta: Decimal
    """Em %, de Configurações › Metas (padrão: meta 50, alerta 30)."""


class TicketRecorrenteResposta(Base):
    """Ticket das propostas aceitas com preço mensal > 0, com a mediana ao lado.

    Não é o ticket médio da carteira. `participacao_do_maior` mostra quanto o
    maior contrato pesa no total — a média sozinha esconde isso.
    """

    quantas: int
    clientes: int
    valor_mensal: Decimal
    ticket_medio: Decimal | None
    mediana: Decimal | None
    maior_valor: Decimal | None
    participacao_do_maior: Decimal | None
    calculavel: bool


class LinhaDeRecorteResposta(Base):
    chave: str
    propostas: int
    em_aberto: int
    aceitas: int
    decididas: int
    conversao: Decimal | None
    recorrentes: int
    valor_mensal: Decimal
    ticket_medio: Decimal | None
    mediana: Decimal | None


class CenariosDeTicketResposta(Base):
    """Hipóteses de trabalho, não meta. Ver `crm.domain.recortes`."""

    contratos: int
    atipicos: int
    limite_do_atipico: Decimal
    conservador: Decimal
    base: Decimal
    otimista: Decimal
    atipico_minimo: Decimal | None
    atipico_medio: Decimal | None
    atipico_maximo: Decimal | None


class IndicadoresResposta(Base):
    em_aberto: RecorteResposta
    aceitas: RecorteResposta
    aceitas_com_data_de_aceite: int
    ciclo_medio: CicloMedioDeVendasResposta
    taxa_de_conversao: TaxaDeConversaoResposta
    cobertura: CoberturaResposta
    dependencia_de_canal: DependenciaDeCanalResposta
    ticket_recorrente: TicketRecorrenteResposta


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
    oportunidade_id: int | None = None
    """A oportunidade que está nesta linha da planilha (30/09/2026). Só na rodada mais recente:
    `linha_planilha` guarda a posição da última carga, e em rodada antiga a linha pode ter mudado."""
    oportunidade_nome: str | None = None
    grupo_nome: str | None = None
    data_aceite: date | None = None
    """A data de aceite como está no CRM agora, não como veio da planilha."""


class Pagina[T](BaseModel):
    total: int
    itens: list[T]


class PerguntaDoCatalogo(BaseModel):
    texto: str
    direcionador: str | None = None


class PedidoDeServicoNovo(BaseModel):
    """Um "Outro" registrado: o que o lead pediu fora do catálogo."""

    onde: str
    """"Oportunidade" ou "Lead"."""
    id: int
    nome: str
    descricao: str
    registrado_em: datetime


class TemaDoCatalogo(BaseModel):
    nome: str
    perguntas: list[PerguntaDoCatalogo]


class ServicoDoCatalogo(BaseModel):
    """Um serviço do catálogo (`crm.domain.servicos`). Não tem preço de propósito."""

    nome: str
    nome_por_extenso: str | None = None
    linha: LinhaServico
    recorrente: bool
    meses_no_ano: int | None = None
    """13 (contábil, DP) ou 12 (financeiro): o preço anual é mensal × isso."""
    para_quem: str
    perguntas: list[PerguntaDoCatalogo]
    fora_do_perfil: list[str]
    transbordo: DestinoDoTransbordo
    nomes_antigos: list[str] = []
    rascunho: bool = True
    temas: list[TemaDoCatalogo] = []
    """Quando há temas, escolher um é obrigatório."""


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
    motivos_de_encerramento: list[str]
    iniciativas_de_encerramento: list[str]
    papeis_de_contato: list[str]
    linhas_de_servico: list[str]
    situacoes_de_grupo: list[str]
    captadores: list[str]
    portes: list[str]
    servicos: list[str]
    motivos_de_descarte: list[str] = []
    aderencias: list[str] = []
    temas_de_expectativa: list[str] = []
    indices_de_reajuste: list[str] = []


# ---------------------------------------------------------------- abordagens
class ConferenciaResposta(BaseModel):
    regra: str
    ok: bool
    texto: str


class FatoResposta(BaseModel):
    fato: str
    fonte: str


class FichaResposta(Base):
    historico: str
    pesquisa: list[FatoResposta]
    quem_decide: str | None = None
    modelo: str
    criado_em: datetime


class AbordagemResumo(BaseModel):
    """O que cabe numa linha da fila de abordagens."""

    id: int
    grupo_id: int
    grupo_nome: str
    mes: str
    quem_apresenta: str | None = None
    canal: CanalDeAbordagem
    situacao: SituacaoAbordagem
    """Já com "Bloqueada" calculada — ver `crm.domain.abordagem.situacao_exibida`."""
    proximo_passo: str
    atualizado_em: datetime


class AbordagemDetalhe(AbordagemResumo):
    contexto: str | None = None
    destinatario: str | None = None
    assunto: str | None = None
    mensagem: str | None = None
    versao: int
    erro: str | None = None
    ficha: FichaResposta | None = None
    conferencias: list[ConferenciaResposta]
    pode_aprovar: bool
    aprovada_por: str | None = None
    aprovada_em: datetime | None = None
    enviada_em: datetime | None = None
    diagnostico_agendado_em: date | None = None
    link_whatsapp: str | None = None
    """Abre a conversa com o texto pronto. O envio no WhatsApp é da pessoa."""


class AbordagemNova(BaseModel):
    """Uma conta entra na fila. Pelo grupo que já existe, ou pelo nome — aí o
    grupo nasce como prospect, como na conversão de lead."""

    grupo_id: int | None = None
    grupo_nome: str | None = Field(default=None, max_length=200)
    mes: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    quem_apresenta: str | None = Field(default=None, max_length=120)
    canal: CanalDeAbordagem = CanalDeAbordagem.EMAIL
    destinatario: str | None = Field(default=None, max_length=200)
    contexto: str | None = None


class AbordagemEdicao(BaseModel):
    """O que a tela pode mudar. Tudo opcional: só o que vier é alterado."""

    quem_apresenta: str | None = Field(default=None, max_length=120)
    canal: CanalDeAbordagem | None = None
    destinatario: str | None = Field(default=None, max_length=200)
    assunto: str | None = Field(default=None, max_length=300)
    mensagem: str | None = None
    contexto: str | None = None
    diagnostico_agendado_em: date | None = None


class PedidoDeVersao(BaseModel):
    instrucao: str = Field(min_length=3, max_length=1000)


class Aprovacao(BaseModel):
    aprovador: str = Field(default="EL", max_length=10)
    """Sem login até o E1: quem aprova é quem está na máquina — Eduardo."""


class ResumoDasAbordagens(BaseModel):
    mes: str
    na_fila: int
    abordadas: int
    diagnosticos: int
    aguardando_aprovacao: int
    custo_usd: Decimal | None = None
    """Soma do custo estimado das execuções do agente para as contas do mês.
    Nulo quando nenhuma execução tem custo conhecido."""
    custo_parcial: bool = False
    """Há execução de modelo sem preço na tabela: a soma está incompleta."""


# ------------------------------------------------------------ SDR de IA
class ConversaNova(BaseModel):
    lead_id: int
    canal: CanalDeAbordagem


class MensagemNova(BaseModel):
    """O horário é do servidor, no instante do registro — nunca do cliente.

    Os campos de leitura da IA (intenção, confiança, falha, termo, custo) só
    valem para mensagem da IA; o tom, só para mensagem do lead.
    """

    autor: AutorDaMensagem
    texto: str = Field(min_length=1)
    intencao: str | None = Field(default=None, max_length=120)
    confianca: Decimal | None = Field(default=None, ge=0, le=1)
    fallback: bool = False
    termo_nao_reconhecido: str | None = Field(default=None, max_length=120)
    custo_usd: Decimal | None = Field(default=None, ge=0)
    tom: Tom | None = None
    questionario: MensagemDoQuestionario | None = None
    """Só na mensagem da IA: o lembrete ou o agradecimento do questionário (06/10/2026). Só
    estas duas a IA pode mandar em conversa já encerrada."""


class MensagemResposta(Base):
    id: int
    autor: AutorDaMensagem
    enviada_em: datetime
    texto: str
    intencao: str | None = None
    confianca: Decimal | None = None
    fallback: bool = False
    termo_nao_reconhecido: str | None = None
    tom: Tom | None = None


class ConversaResposta(Base):
    id: int
    lead_id: int
    canal: CanalDeAbordagem
    iniciada_em: datetime
    encerrada_em: datetime | None = None
    desfecho: DesfechoDaConversa | None = None
    motivo_transbordo: MotivoDeTransbordo | None = None
    destino_transbordo: DestinoDoTransbordo | None = None
    atendida_em: datetime | None = None
    nota: int | None = None
    mensagens: list[MensagemResposta] = []


class QuestionarioDoLead(BaseModel):
    """Em que passo está o questionário de um lead — a integração do canal entrega isto à IA."""

    lead_id: int
    passo: PassoDoQuestionario
    enviado_em: datetime | None = None
    respondido_em: datetime | None = None
    lembrado_em: datetime | None = None
    agradecido_em: datetime | None = None
    lembrar_a_partir_de: datetime | None = None


class PendenciaDoQuestionario(BaseModel):
    """Um lead à espera de lembrete ou de agradecimento, na conversa mais recente dele."""

    lead_id: int
    nome: str
    conversa_id: int
    canal: CanalDeAbordagem
    passo: PassoDoQuestionario
    enviado_em: datetime
    respondido_em: datetime | None = None


class EstadoDoDisparoResposta(BaseModel):
    """A última rodada do disparo do lembrete e do agradecimento do questionário."""

    automatico: bool
    """Falso quando o CRM roda sem o laço (no teste)."""
    ligado: bool
    """`CRM_DISPARO_DO_QUESTIONARIO=true` na última rodada."""
    intervalo_minutos: int
    ultima_em: datetime | None
    enviados: int
    avisos: list[str]
    erros: list[str]
    proxima_em: datetime | None


class Encerramento(BaseModel):
    """Qualificado exige porte estimado; fora do perfil exige o motivo;
    transbordo exige motivo e destino."""

    desfecho: DesfechoDaConversa
    porte_estimado: str | None = Field(default=None, max_length=20)
    cnpj: str | None = Field(default=None, max_length=18)
    interesse: str | None = Field(default=None, max_length=200)
    interesse_tema: str | None = Field(default=None, max_length=80)
    motivo_descarte: MotivoDeDescarte | None = None
    motivo_transbordo: MotivoDeTransbordo | None = None
    destino_transbordo: DestinoDoTransbordo | None = None


class NotaDaConversa(BaseModel):
    nota: int = Field(ge=1, le=5)


class ParametrosDoSdrResposta(Base):
    custo_hora_sdr: Decimal | None = None
    minutos_por_conversa: int | None = None
    cotacao_dolar: Decimal | None = None
    atualizado_por: str | None = None
    atualizado_em: datetime | None = None


class ParametrosDoSdrEdicao(BaseModel):
    custo_hora_sdr: Decimal | None = Field(default=None, ge=0)
    minutos_por_conversa: int | None = Field(default=None, ge=1, le=600)
    cotacao_dolar: Decimal | None = Field(default=None, gt=0)
    atualizado_por: str | None = Field(default=None, max_length=10)


class InvestimentoResposta(Base):
    id: int
    mes: str
    canal: str
    valor: Decimal


class InvestimentoEdicao(BaseModel):
    mes: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    canal: str = Field(min_length=1, max_length=120)
    valor: Decimal = Field(ge=0)



class ItemDaComposicaoResposta(Base):
    """Uma oportunidade na lista de um número do funil (10/10/2026)."""

    id: int
    nome: str
    grupo: str
    servico: str | None = None
    situacao: str
    captador: str | None = None
    tipo_canal: str | None = None
    data_colocacao: date | None = None
    data_aceite: date | None = None
    data_envio_proposta: date | None = None
    proxima_acao: str | None = None
    entra: bool
    """Conta no numerador (aceita, com próxima ação, da rede dos sócios); nas somas, sempre."""
    parte: str
    valor: Decimal | None = None
    """Preço mensal, MRR (ticket) ou dias (ciclo médio), conforme o indicador."""
    anual: Decimal | None = None
    falta: list[str] = []


class ComposicaoDoFunilResposta(Base):
    indicador: str
    itens: list[ItemDaComposicaoResposta]
