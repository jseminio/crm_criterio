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
  escopo: string | null;
  preco_mensal: string | null;
  preco_anual: string | null;
  data_inicio: string | null;
  data_fim: string | null;
  situacao: string;
  signatario: string | null;
}

export interface ContratoDetalhe extends ContratoResumo {
  documento_assinado: string | null;
  observacao: string | null;
}

export interface Ocorrencia {
  id: number;
  tipo: string;
  linha: number | null;
  campo: string | null;
  texto: string;
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
