/** O contrato da API, espelhado em TypeScript.
 *
 * As listas controladas NÃO são declaradas aqui como união fechada: elas vêm
 * de `/api/listas`, porque `crm.domain.listas` é a única fonte. Fixá-las no
 * React criaria a segunda cópia da mesma regra — e ela envelheceria calada.
 */

export type Situacao = string;
export type Temperatura = string;
export type TipoCanal = string;

export interface Pagina<T> {
  total: number;
  itens: T[];
}

export interface GrupoResumo {
  id: number;
  nome: string;
  situacao: string;
  origem: string;
  responsavel_cs: string | null;
  data_entrada: string | null;
  fundido_em_id: number | null;
  quantas_oportunidades: number;
}

export interface OportunidadeResumo {
  id: number;
  nome: string;
  grupo_id: number;
  grupo_nome: string | null;
  situacao: Situacao;
  temperatura: Temperatura | null;
  servico: string | null;
  tipo_servico: string | null;
  captador: string | null;
  tipo_canal: TipoCanal | null;
  data_colocacao: string | null;
  preco_mensal: string | null;
  preco_anual: string | null;
  proxima_acao: string | null;
  proxima_acao_em: string | null;
}

export interface SugestaoDePorte {
  calculavel: boolean;
  pontuacao: string | null;
  porte: string | null;
  horas_base: number | null;
  direcionadores_aplicados: number;
}

/** Uma mudança de preço: antes, depois, quando e por quê. Só cresce. */
export interface MudancaDePreco {
  id: number;
  registrado_em: string;
  origem: string;
  motivo: string | null;
  preco_mensal_anterior: string | null;
  preco_mensal_novo: string | null;
  preco_anual_anterior: string | null;
  preco_anual_novo: string | null;
}

export interface OportunidadeDetalhe extends OportunidadeResumo {
  canal: string | null;
  linha_servico: string | null;
  data_aceite: string | null;
  motivo_recusa: string | null;
  motivo_recusa_original: string | null;
  valor_mensalizado: string | null;
  observacao: string | null;
  origem: string;
  linha_planilha: number | null;
  /** {campo: "Entrevista" | "Questionário"}, só de campo preenchido. */
  origem_da_volumetria: Record<string, string>;
  historico_de_preco: MudancaDePreco[];

  complexidade: number | null;
  risco_tecnico: number | null;

  documentos_fiscais_mes: number | null;
  lancamentos_contabeis_mes: number | null;
  pagamentos_mes: number | null;
  contas_bancarias: number | null;
  conciliacoes_cartao_mes: number | null;
  empregados_clt: number | null;
  admissoes_desligamentos_mes: number | null;
  cnpjs_no_escopo: number | null;
  tomadores_de_servico: number | null;
  servicos_contratados_alem_do_primeiro: number;
  tem_consolidacao_de_grupo: boolean;
  e_auditada: boolean;

  porte: string | null;
  porte_definido_por: string | null;
  porte_definido_em: string | null;
  sugestao_de_porte: SugestaoDePorte | null;
}

export interface ColunaDoFunil {
  situacao: Situacao;
  quantas: number;
  valor_mensal: string;
  valor_anual: string;
  oportunidades: OportunidadeResumo[];
}

export interface LeadResumo {
  id: number;
  nome: string;
  empresa_texto: string | null;
  email: string | null;
  telefone: string | null;
  situacao: string;
  temperatura: Temperatura | null;
  tipo_canal: TipoCanal | null;
  canal: string | null;
  captador: string | null;
  interesse: string | null;
  campanha: string | null;
  campanha_midia: string | null;
  proxima_acao: string | null;
  proxima_acao_em: string | null;
  observacao: string | null;
  convertido_em_id: number | null;
}

export interface Listas {
  situacoes: string[];
  situacoes_de_lead: string[];
  temperaturas: string[];
  tipos_de_canal: string[];
  tipos_de_canal_em_operacao: string[];
  motivos_de_recusa: string[];
  motivos_de_encerramento: string[];
  iniciativas_de_encerramento: string[];
  papeis_de_contato: string[];
  linhas_de_servico: string[];
  situacoes_de_grupo: string[];
  captadores: string[];
  portes: string[];
  servicos: string[];
}

export interface Recorte {
  quantas: number;
  valor_mensal: string;
  valor_anual: string;
  sem_preco_mensal: number;
  com_preco_mensal: number;
}

/** Originação → aceite — decisão de Eduardo em 23/09/2026.
 *
 * Só entra aceita com as duas datas; `aceitas_sem_as_duas_datas` diz quantas
 * ficaram de fora, para a tela não fingir que a amostra é o total.
 */
export interface CicloMedioDeVendas {
  dias: string | null;
  amostra: number;
  aceitas_sem_as_duas_datas: number;
  calculavel: boolean;
}

/** "Aumentar os pontos de contato" virando número — documento-de-negocio.md, seção 12.5. */
export interface Cobertura {
  em_aberto_com_proxima_acao: number;
  em_aberto_total: number;
  com_volumetria_completa: number;
  total: number;
  percentual_com_proxima_acao: string | null;
  percentual_com_volumetria_completa: string | null;
}

export interface DependenciaDeCanal {
  da_rede_de_socios: number;
  total: number;
  percentual: string | null;
}

/** Aceitas ÷ decididas — decisão de Eduardo em 22/09/2026.
 *
 * Em aberto não entra no denominador: ainda pode fechar. `abaixo_do_alerta` e
 * `atingiu_a_meta` vêm `null` só quando não há decidida nenhuma — não
 * calculável é diferente de "abaixo do alerta".
 */
export interface TaxaDeConversao {
  aceitas: number;
  decididas: number;
  percentual: string | null;
  calculavel: boolean;
  abaixo_do_alerta: boolean | null;
  atingiu_a_meta: boolean | null;
}

/** Ticket das propostas aceitas com preço mensal > 0, com a mediana ao lado.
 * Não é o ticket médio da carteira (R$ 7.407,78, decisão de 23/09/2026). */
export interface TicketRecorrente {
  quantas: number;
  clientes: number;
  valor_mensal: string;
  ticket_medio: string | null;
  mediana: string | null;
  maior_valor: string | null;
  participacao_do_maior: string | null;
  calculavel: boolean;
}

export interface Indicadores {
  em_aberto: Recorte;
  aceitas: Recorte;
  aceitas_com_data_de_aceite: number;
  ciclo_medio: CicloMedioDeVendas;
  taxa_de_conversao: TaxaDeConversao;
  cobertura: Cobertura;
  dependencia_de_canal: DependenciaDeCanal;
  ticket_recorrente: TicketRecorrente;
}

export interface Execucao {
  id: number;
  executada_em: string;
  arquivo: string;
  lidas: number;
  de_outro_ano: number;
  residuais: number;
  importadas: number;
  criadas: number;
  atualizadas: number;
  inalteradas: number;
  gravadas: number;
  ignoradas_incompletas: number;
  ignoradas_duplicatas: number;
  grupos_criados: number;
  grupos_reaproveitados: number;
  pendencias: number;
  ajustes: number;
  mudancas: number;
}

export interface ResumoPorCampo {
  tipo: string;
  campo: string | null;
  quantas: number;
}

export interface ExecucaoDetalhe extends Execucao {
  por_campo: ResumoPorCampo[];
}

export interface ContratoResumo {
  id: number;
  grupo_id: number;
  grupo_nome: string | null;
  oportunidade_id: number | null;
  empresa_id: number | null;
  /** Da carteira que já existia antes do CRM: sem data de assinatura conhecida. */
  anterior_ao_crm: boolean;
  escopo: string | null;
  preco_mensal: string | null;
  preco_anual: string | null;
  data_inicio: string | null;
  data_fim: string | null;
  situacao: string;
  signatario: string | null;
}

/** Um fato do contrato depois de assinado, com o antes e o depois. Só cresce. */
export interface EventoDeContrato {
  id: number;
  tipo: "Aditivo" | "Reajuste" | "Expansão" | "Contração" | "Renovação" | "Encerramento" | "Correção";
  data_do_evento: string;
  registrado_em: string;
  descricao: string | null;
  /** Só no Encerramento. */
  motivo_categoria: string | null;
  /** Quem decidiu encerrar: "Cliente" ou "Critério". Só no Encerramento. */
  iniciativa: string | null;
  preco_mensal_anterior: string | null;
  preco_mensal_novo: string | null;
  preco_anual_anterior: string | null;
  preco_anual_novo: string | null;
  escopo_anterior: string | null;
  escopo_novo: string | null;
  data_fim_anterior: string | null;
  data_fim_nova: string | null;
}

export interface ContratoDetalhe extends ContratoResumo {
  documento_assinado: string | null;
  observacao: string | null;
  /** Mais recente primeiro. */
  eventos: EventoDeContrato[];
}

export interface Ocorrencia {
  id: number;
  tipo: string;
  linha: number | null;
  campo: string | null;
  texto: string;
}

/** Agente SDR (26/09/2026): a fila de abordagens das contas âncora. */
export interface AbordagemResumo {
  id: number;
  grupo_id: number;
  grupo_nome: string;
  mes: string;
  quem_apresenta: string | null;
  canal: "E-mail" | "WhatsApp";
  situacao: string;
  proximo_passo: string;
  atualizado_em: string;
}

export interface Conferencia {
  regra: string;
  ok: boolean;
  texto: string;
}

export interface FichaDaConta {
  historico: string;
  pesquisa: { fato: string; fonte: string }[];
  quem_decide: string | null;
  modelo: string;
  criado_em: string;
}

export interface AbordagemDetalhe extends AbordagemResumo {
  contexto: string | null;
  destinatario: string | null;
  assunto: string | null;
  mensagem: string | null;
  versao: number;
  erro: string | null;
  ficha: FichaDaConta | null;
  conferencias: Conferencia[];
  pode_aprovar: boolean;
  aprovada_por: string | null;
  aprovada_em: string | null;
  enviada_em: string | null;
  diagnostico_agendado_em: string | null;
  link_whatsapp: string | null;
}

export interface ResumoDasAbordagens {
  mes: string;
  na_fila: number;
  abordadas: number;
  diagnosticos: number;
  aguardando_aprovacao: number;
  custo_usd: string | null;
  custo_parcial: boolean;
}

/** Um bloco de grupos que parecem ser o mesmo cliente. Só sugestão: quem funde é uma pessoa. */
export interface SugestaoDeFusao {
  confianca: "alta" | "média";
  motivo: string;
  principal_id: number;
  grupos: GrupoResumo[];
}

export type DimensaoDeRecorte = "servico" | "tipo_canal" | "captador";

/** Um corte do funil por serviço, canal ou captador. */
export interface LinhaDeRecorte {
  chave: string;
  propostas: number;
  em_aberto: number;
  aceitas: number;
  decididas: number;
  conversao: string | null;
  recorrentes: number;
  valor_mensal: string;
  ticket_medio: string | null;
  mediana: string | null;
}

/** Hipóteses de trabalho, não meta. Atípico = acima de 3 × a mediana. */
export interface CenariosDeTicket {
  contratos: number;
  atipicos: number;
  limite_do_atipico: string;
  conservador: string;
  base: string;
  otimista: string;
  atipico_minimo: string | null;
  atipico_medio: string | null;
  atipico_maximo: string | null;
}

export type BaldeDaAgenda = "atrasada" | "hoje" | "proximos_7_dias" | "depois" | "sem_data" | "sem_acao";

export interface ItemDaAgenda {
  tipo: "oportunidade" | "lead" | "contrato";
  id: number;
  titulo: string;
  subtitulo: string | null;
  situacao: string;
  temperatura: string | null;
  captador: string | null;
  valor_anual: string | null;
  proxima_acao: string | null;
  proxima_acao_em: string | null;
  balde: BaldeDaAgenda;
  dias_de_atraso: number;
  dias_desde_o_envio: number | null;
}

/** A fila de follow-up. `contagens` traz todos os baldes, mesmo os vazios. */
export interface Agenda {
  hoje: string;
  contagens: Record<BaldeDaAgenda, number>;
  itens: ItemDaAgenda[];
}

export interface MrrAtual {
  valor: string;
  contratos: number;
  suspenso_valor: string;
  suspenso_contratos: number;
  sem_preco_mensal: number;
  grupos: number;
  /** Receita mensal média por grupo (decisão de 23/09/2026). */
  ticket_por_grupo: string | null;
  mediana_por_grupo: string | null;
}

export interface MovimentoDeMrr {
  de: string;
  ate: string;
  mrr_inicio: string;
  novo: string;
  expansao: string;
  reajuste: string;
  contracao: string;
  churn_cliente: string;
  churn_criterio: string;
  churn: string;
  mrr_fim: string;
  variacao: string;
  nrr: string | null;
  grr: string | null;
}

/** MRR dos contratos registrados no CRM. Parcial: a carteira anterior não está aqui. */
export interface Mrr {
  atual: MrrAtual;
  movimento: MovimentoDeMrr;
  contratos_registrados: number;
  contratos_da_carteira_anterior: number;
  cobertura_completa: boolean;
  aviso: string;
}

export type TipoDeContato = "cliente" | "prospect";

export interface PessoaDeContato {
  id: number;
  nome: string;
  cargo: string | null;
  email: string | null;
  telefone: string | null;
  papel: string | null;
  observacao: string | null;
  nao_contatar: boolean;
  empresa_id: number | null;
  grupo_id: number | null;
  /** Ligada só ao grupo, não a esta empresa. */
  do_grupo: boolean;
}

export interface EnderecoDeContato {
  logradouro: string | null;
  numero: string | null;
  complemento: string | null;
  bairro: string | null;
  municipio: string | null;
  uf: string | null;
  cep: string | null;
}

/** Cliente: uma empresa (CNPJ). Prospect: o grupo, ou a empresa quando já existe. */
export interface EntidadeDeContato {
  tipo: TipoDeContato;
  grupo_id: number;
  grupo_nome: string;
  empresa_id: number | null;
  razao_social: string | null;
  nome_fantasia: string | null;
  cnpj: string | null;
  endereco: EnderecoDeContato;
  /** Só cliente. */
  mensalidade: string | null;
  /** Cliente com contrato recorrente em vigor. Sem ele, é cliente **não recorrente** (consultoria pontual). */
  recorrente: boolean;
  /** Só prospect. */
  propostas: number;
  contatos: PessoaDeContato[];
  /** Dos sete itens (contato, e-mail, telefone, logradouro, município, UF, CEP), o que falta. */
  lacunas: string[];
}

export interface PessoaComOrigem extends PessoaDeContato {
  tipo: TipoDeContato;
  grupo_nome: string;
  razao_social: string | null;
}

export interface PaginaDeContatos<T> {
  total: number;
  itens: T[];
}

/** Uma fusão de grupos que foi feita, com o que ela moveu, para poder ser desfeita. */
export interface FusaoFeita {
  id: number;
  principal_id: number;
  principal_nome: string;
  absorvido_id: number;
  absorvido_nome: string;
  feita_em: string;
  desfeita_em: string | null;
  /** Registro refeito a partir de um backup: a fusão é anterior ao registro. */
  reconstruida: boolean;
  empresas: number;
  oportunidades: number;
  contatos: number;
  contratos: number;
  pode_desfazer: boolean;
}
