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
    CanalDeAbordagem,
    LinhaServico,
    MotivoRecusa,
    Origem,
    OrigemDoDado,
    Situacao,
    SituacaoAbordagem,
    SituacaoContrato,
    SituacaoGrupo,
    SituacaoLead,
    Temperatura,
    TipoCanal,
    IniciativaDoEncerramento,
    MotivoDeEncerramento,
    TipoDeEventoDeContrato,
    TipoDeOcorrencia,
)

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
    data_entrada: date | None = None
    fundido_em_id: int | None = None
    quantas_oportunidades: int = 0


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
    não estiver carregada. `cobertura_completa` fica sempre `False` por enquanto: é o
    aviso de que este número não se compara com a meta de R$ 400 mil."""

    atual: MrrAtualResposta
    movimento: MovimentoDeMrrResposta
    contratos_registrados: int
    contratos_da_carteira_anterior: int
    """Quantos vieram da carga da planilha de saúde da carteira (sem data de assinatura)."""
    cobertura_completa: bool
    aviso: str


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


class AgendaResposta(Base):
    """A fila de follow-up. `contagens` traz todos os baldes, mesmo os vazios."""

    hoje: date
    contagens: dict[str, int]
    itens: list[ItemDaAgendaResposta]


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
    canal: str | None = None
    linha_servico: LinhaServico | None = None
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

    Preço, serviço e data de originação entraram em 22/09/2026 (E4): a
    proposta já pode nascer e ser ajustada direto no CRM, não só na planilha.
    O campo mudado aqui entra em `campos_do_crm` (mesmo mecanismo que já
    protegia situação/temperatura) — a recarga da planilha não sobrescreve de
    volta.
    """

    situacao: Situacao | None = None
    temperatura: Temperatura | None = None
    motivo_recusa: MotivoRecusa | None = None
    data_aceite: date | None = None
    proxima_acao: str | None = Field(default=None, max_length=200)
    proxima_acao_em: date | None = None
    observacao: str | None = None
    servico: str | None = Field(default=None, max_length=120)
    tipo_servico: str | None = Field(default=None, max_length=120)
    data_colocacao: date | None = None
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
    grupo_id: int | None = None
    nome_do_grupo: str | None = Field(default=None, max_length=200)
    servico: str | None = Field(default=None, max_length=120)
    tipo_servico: str | None = Field(default=None, max_length=120)
    data_colocacao: date | None = None
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
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
    data_inicio: date | None = None
    data_fim: date | None = None
    situacao: SituacaoContrato
    signatario: str | None = None


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


class ContratoDetalhe(ContratoResumo):
    documento_assinado: str | None = None
    observacao: str | None = None
    eventos: list[EventoDeContratoResposta] = []
    """Mais recente primeiro."""


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


class ContratoEdicao(BaseModel):
    """O que a tela pode mudar. Tudo opcional: só o que vier é alterado."""

    escopo: str | None = Field(default=None, max_length=200)
    preco_mensal: Decimal | None = None
    preco_anual: Decimal | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    situacao: SituacaoContrato | None = None
    documento_assinado: str | None = Field(default=None, max_length=400)
    signatario: str | None = Field(default=None, max_length=200)
    observacao: str | None = None


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
    motivos_de_encerramento: list[str]
    iniciativas_de_encerramento: list[str]
    papeis_de_contato: list[str]
    linhas_de_servico: list[str]
    situacoes_de_grupo: list[str]
    captadores: list[str]
    portes: list[str]
    servicos: list[str]


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
