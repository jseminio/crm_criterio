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
}

export interface Recorte {
  quantas: number;
  valor_mensal: string;
  valor_anual: string;
  sem_preco_mensal: number;
  com_preco_mensal: number;
}

/** Um indicador que existe no desenho mas ainda não pode ser calculado. */
export interface Pendencia {
  calculavel: boolean;
  motivo: string;
  o_que_falta: string;
}

export interface Indicadores {
  em_aberto: Recorte;
  aceitas: Recorte;
  aceitas_com_data_de_aceite: number;
  ciclo_medio: Pendencia;
  taxa_de_conversao: Pendencia;
}
