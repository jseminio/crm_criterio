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
  observacao: string | null;
  data_entrada: string | null;
  fundido_em_id: number | null;
  quantas_oportunidades: number;
}

export interface OportunidadeResumo {
  id: number;
  nome: string;
  grupo_id: number;
  grupo_nome: string | null;
  /** A empresa (CNPJ) da oportunidade; o grupo vem dela (01/10/2026). */
  empresa_id?: number | null;
  empresa_razao_social?: string | null;
  empresa_cnpj?: string | null;
  situacao: Situacao;
  temperatura: Temperatura | null;
  servico: string | null;
  tipo_servico: string | null;
  captador: string | null;
  tipo_canal: TipoCanal | null;
  data_colocacao: string | null;
  preco_mensal: string | null;
  preco_anual: string | null;
  /** Só em serviço recorrente: o anual é mensal × parcelas. */
  quantidade_parcelas?: number | null;
  reajuste?: string | null;
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
  /** Já virou contrato: a empresa não troca mais pelo detalhe. */
  tem_contrato?: boolean;
  canal: string | null;
  linha_servico: string | null;
  servico_descricao?: string | null;
  servico_tema?: string | null;
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
  interesse_descricao?: string | null;
  interesse_tema?: string | null;
  campanha: string | null;
  campanha_midia: string | null;
  proxima_acao: string | null;
  proxima_acao_em: string | null;
  observacao: string | null;
  convertido_em_id: number | null;
  cnpj?: string | null;
  porte_estimado?: string | null;
  qualificado_em?: string | null;
  descartado_em?: string | null;
  motivo_descarte?: string | null;
  reuniao_marcada_para?: string | null;
  nao_contatar?: boolean;
  criado_em?: string | null;
}

export interface Listas {
  situacoes: string[];
  situacoes_de_lead: string[];
  temperaturas: string[];
  /** Índices de reajuste do contrato (IPCA, IGP-M, Sem reajuste). */
  indices_de_reajuste?: string[];
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
  motivos_de_descarte?: string[];
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
  /** A oportunidade desta linha, só na rodada mais recente (a linha pode mudar entre cargas). */
  oportunidade_id?: number | null;
  oportunidade_nome?: string | null;
  grupo_nome?: string | null;
  /** Como está no CRM agora, não como veio da planilha. */
  data_aceite?: string | null;
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
  tipo: "oportunidade" | "lead" | "contrato" | "pendencia";
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
  /** Na pendência da proposta, a oportunidade a abrir (o `id` é o da pendência). */
  oportunidade_id?: number | null;
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

/** Uma empresa em que a pessoa está — a pessoa pode estar em várias (30/09/2026). */
/** Uma empresa da base, para escolher a da oportunidade (01/10/2026). */
export interface EmpresaEncontrada {
  id: number;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj: string | null;
  grupo_id: number;
  grupo_nome: string;
  tipo: TipoDeContato;
}

export interface EmpresaDaPessoa {
  empresa_id: number;
  razao_social: string;
  grupo_id: number;
  grupo_nome: string;
  principal: boolean;
}

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
  /** Grupo da empresa desta linha — informação; o contato é ligado só a empresas (01/10/2026). */
  grupo_id: number | null;
  /** Contato principal desta empresa. Uma empresa pode ter vários. */
  principal?: boolean;
  /** Todas as empresas em que a pessoa está. */
  empresas?: EmpresaDaPessoa[];
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
  /** A empresa tem contrato (em qualquer situação): não pode ser excluída. */
  tem_contrato?: boolean;
  contatos: PessoaDeContato[];
  /** Dos sete itens (contato, e-mail, telefone, logradouro, município, UF, CEP), o que falta. */
  lacunas: string[];
}

export interface PessoaComOrigem extends PessoaDeContato {
  tipo: TipoDeContato;
  /** Nulo quando a pessoa ainda não está em empresa nem grupo. */
  grupo_nome: string | null;
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

export interface EmpresaDoGrupo {
  id: number;
  razao_social: string;
  cnpj: string | null;
  mensalidade: string | null;
}

export interface NotasDoGrupo {
  receita: string;
  rentabilidade: string;
  /** A nota tal como veio da planilha/deck de classificação (revisão 1), sem o recálculo do
   * defeito 7.2 — pode diferir de `rentabilidade` acima, que é a que entra no Score. */
  rentabilidade_planilha: string;
  complexidade: string;
  disciplina: string;
  risco: string;
  cross_sell: string;
  adimplencia: string;
  semaforo: number;
  churn: number | null;
  rentabilidade_da_planilha: boolean;
  atribuido_por: string | null;
  motivo: string | null;
  registrado_em: string;
}

export interface ItemDaCarteira {
  grupo_id: number;
  grupo_nome: string;
  receita_mensal: string;
  score: string;
  classe: string;
  classe_efetiva: string;
  alerta_de_churn: string | null;
  em_cobranca: boolean;
  eixo_de_acao: string;
  semaforo: number;
  churn: number | null;
  sem_contrato_ativo: boolean;
  empresas: EmpresaDoGrupo[];
  notas: NotasDoGrupo;
  porte: PorteDoGrupo;
  /** Respostas da avaliação mais recente que as gravou (pode ser anterior à leitura mostrada). */
  avaliacao?: AvaliacaoGravada | null;
  /** Rascunho do período aberto, se houver. */
  rascunho?: RascunhoDaAvaliacao | null;
  /** Margem e honorário calculado no nível do grupo; `null` sem porte confirmado. */
  rentabilidade_do_grupo?: RentabilidadeDoGrupo | null;
  /** Soma das mensalidades dos contratos ativos e suspensos; `null` = sem contrato no CRM (vale a planilha). */
  receita_em_contrato?: string | null;
  contratos?: number;
}

/** Com contrato valendo e sem nenhuma leitura: entra no período com 7 abas (30/09/2026). */
export interface ClienteNovo {
  grupo_id: number;
  grupo_nome: string;
  desde: string | null;
  receita_em_contrato: string;
  contratos: number;
  empresas: EmpresaDoGrupo[];
  porte: PorteDoGrupo;
  rascunho?: RascunhoDaAvaliacao | null;
  rentabilidade_do_grupo?: RentabilidadeDoGrupo | null;
}

export type AbaDaAvaliacao = "complexidade" | "risco" | "disciplina" | "cross_sell" | "inadimplencia" | "porte" | "saude";

export interface RespostasDeSaude {
  semaforo: number;
  churn: number;
}

export interface RespostasDePorte extends VolumetriaEntrada {
  porte: string;
  justificativa?: string | null;
}

/** Cada aba presente foi revista por alguém neste período. */
export interface RespostasDoRascunho {
  complexidade?: string[];
  risco?: string[];
  cross_sell?: string[];
  disciplina?: RespostasDaAvaliacao["disciplina"];
  inadimplencia?: RespostasDaAvaliacao["inadimplencia"];
  porte?: RespostasDePorte;
  /** Só cliente novo. */
  saude?: RespostasDeSaude;
}

export interface RascunhoDaAvaliacao {
  respostas: RespostasDoRascunho;
  preenchidas: AbaDaAvaliacao[];
  atualizado_em: string;
  atualizado_por: string;
}

export interface RentabilidadeDoGrupo {
  porte: string;
  horas: string;
  custo_de_servir: string;
  honorario_praticado: string;
  margem: string | null;
  honorario_calculado: string;
  defasagem: string | null;
  revisao_de_honorarios: boolean;
}

export interface PeriodoDeAvaliacao {
  id: number;
  mes_de_referencia: string;
  aberto_em: string;
  aberto_por: string;
  margem_minima: string;
  margem_alvo: string;
  calculado_em: string | null;
  calculado_por: string | null;
  grupos: number;
  completos: number;
  abas: number;
  pendentes: { grupo_id: number; grupo_nome: string; preenchidas: number; abas: number; novo: boolean }[];
}

export interface JanelaDeRentabilidade {
  margem_minima: string;
  margem_alvo: string;
  origem: string;
}

export interface SimulacaoDoCliente {
  pendentes: AbaDaAvaliacao[];
  /** `null` para cliente novo, que não tem leitura anterior. */
  notas_antes: Record<string, string> | null;
  /** Cliente novo: `null` na nota cuja aba ainda falta. */
  notas_depois: Record<string, string | null>;
  score_antes: string | null;
  score_depois: string | null;
  classe_antes: string | null;
  classe_depois: string | null;
  rentabilidade: RentabilidadeDoGrupo | null;
  novo?: boolean;
}

export interface RespostasDaAvaliacao {
  complexidade: string[];
  risco: string[];
  cross_sell: string[];
  disciplina: { meses_no_prazo: number; cobranca_dobrada: boolean; atraso_recorrente: boolean };
  inadimplencia: { meses_em_dia: number; em_negociacao: boolean; ja_suspenso: boolean };
}

export interface AvaliacaoGravada {
  respostas: RespostasDaAvaliacao;
  registrado_em: string;
  atribuido_por: string | null;
}

export interface IscDaCarteira {
  valor: string;
  zona: string;
  componente_classe: string;
  componente_semaforo: string;
  componente_churn: string;
  receita_total: string;
  grupos: number;
  fora_do_isc: number;
}

export interface RetratoDaCarteira {
  unidades: number;
  receita_total: string;
  grupos_travados: number;
  receita_travada: string;
  percentual_travado: string;
}

export interface FaixaDeClasse {
  classe: string;
  minimo: number;
  maximo: number;
  unidades: number;
  percentual: string;
  dentro_da_meta: boolean;
}

/** Os nove direcionadores da régua de porte. `null` = "não se aplica ao escopo contratado" —
 * fora da média, nunca zero (ver `direcionadoresDePorte.ts`). */
export interface DirecionadoresDePorte {
  documentos_fiscais_mes: number | null;
  lancamentos_contabeis_mes: number | null;
  pagamentos_mes: number | null;
  contas_bancarias: number | null;
  conciliacoes_cartao_mes: number | null;
  empregados_clt: number | null;
  admissoes_desligamentos_mes: number | null;
  cnpjs_no_escopo: number | null;
  tomadores_de_servico: number | null;
}

export interface VolumetriaEntrada extends Partial<DirecionadoresDePorte> {
  servicos_contratados_alem_do_primeiro?: number;
  tem_consolidacao_de_grupo?: boolean;
  e_auditada?: boolean;
}

export interface SugestaoDePorte {
  calculavel: boolean;
  pontuacao: string | null;
  porte: string | null;
  horas_base: number | null;
  direcionadores_aplicados: number;
}

export interface EdicaoDePorte extends VolumetriaEntrada {
  autor: string;
  porte?: string;
}

export interface PorteDoGrupo extends DirecionadoresDePorte {
  servicos_contratados_alem_do_primeiro: number;
  tem_consolidacao_de_grupo: boolean;
  e_auditada: boolean;
  porte: string | null;
  porte_definido_por: string | null;
  porte_definido_em: string | null;
  porte_justificativa?: string | null;
}

export interface EdicaoDeNotas {
  autor: string;
  motivo: string;
  complexidade?: number;
  disciplina?: number;
  risco?: number;
  cross_sell?: number;
  adimplencia?: number;
  semaforo?: number;
  churn?: number;
  respostas?: RespostasDaAvaliacao;
}

export interface ResultadoDaEdicao {
  item: ItemDaCarteira;
  isc: IscDaCarteira | null;
  avisos: string[];
}

export interface CelulaDeMix {
  porte: string;
  cargo: string;
  mix_percentual: string;
}

export interface Parametros {
  id: number;
  criado_em: string;
  autor: string;
  motivo: string;
  peso_receita: string;
  peso_rentabilidade: string;
  peso_cross_sell: string;
  peso_complexidade: string;
  peso_disciplina: string;
  peso_risco: string;
  peso_adimplencia: string;
  corte_a: string;
  corte_b: string;
  trava_de_adimplencia: number;
  churn_alto: number;
  imposto: string;
  teto_de_atrito: string;
  atrito_nota_1: string;
  atrito_nota_2: string;
  atrito_nota_3: string;
  atrito_nota_4: string;
  atrito_nota_5: string;
  corte_margem_2: string;
  corte_margem_3: string;
  corte_margem_4: string;
  corte_margem_5: string;
  horas_micro: number;
  horas_pequeno: number;
  horas_medio: number;
  horas_grande: number;
  horas_extra_grande: number;
  taxa_socio_senior: string;
  taxa_socio_junior: string;
  taxa_supervisor: string;
  taxa_analista_senior: string;
  taxa_analista_pleno: string;
  taxa_analista_junior: string;
  mix: CelulaDeMix[];
  custo_hora: Record<string, string>;
}

export interface CelulaDeMixEntrada {
  porte: string;
  cargo: string;
  mix_percentual: number;
}

export interface EdicaoDeParametros {
  autor: string;
  motivo: string;
  peso_receita: number;
  peso_rentabilidade: number;
  peso_cross_sell: number;
  peso_complexidade: number;
  peso_disciplina: number;
  peso_risco: number;
  peso_adimplencia: number;
  corte_a: number;
  corte_b: number;
  trava_de_adimplencia: number;
  churn_alto: number;
  imposto: number;
  teto_de_atrito: number;
  atrito_nota_1: number;
  atrito_nota_2: number;
  atrito_nota_3: number;
  atrito_nota_4: number;
  atrito_nota_5: number;
  corte_margem_2: number;
  corte_margem_3: number;
  corte_margem_4: number;
  corte_margem_5: number;
  horas_micro: number;
  horas_pequeno: number;
  horas_medio: number;
  horas_grande: number;
  horas_extra_grande: number;
  taxa_socio_senior: number;
  taxa_socio_junior: number;
  taxa_supervisor: number;
  taxa_analista_senior: number;
  taxa_analista_pleno: number;
  taxa_analista_junior: number;
  mix: CelulaDeMixEntrada[];
}

export interface ClassificacaoDaCarteira {
  referencia: string | null;
  versao_dos_parametros: string | null;
  isc: IscDaCarteira | null;
  retrato: RetratoDaCarteira | null;
  por_classe: Record<string, number>;
  distribuicao_por_classe: FaixaDeClasse[];
  itens: ItemDaCarteira[];
  avisos: string[];
  periodo?: PeriodoDeAvaliacao | null;
  janela?: JanelaDeRentabilidade | null;
  /** Clientes novos, sem leitura: fora do ISC, do retrato e da distribuição por classe. */
  novos?: ClienteNovo[];
}

export interface AnaliseDaCarteira {
  texto: string;
  gerada_em: string;
  gerada_por: string;
  modelo: string;
  custo_usd: string | null;
}

export interface RevisaoDaCarteira {
  id: number;
  mes_de_referencia: string;
  registrada_em: string;
  registrada_por: string;
  isc_valor: string;
  isc_zona: string;
  componente_classe: string;
  componente_semaforo: string;
  componente_churn: string;
  grupos: number;
  receita_total: string;
  grupos_travados: number;
  receita_travada: string;
  percentual_travado: string;
  baseado_em_referencia: string;
}

// ------------------------------------------------------------ SDR de IA
export interface MensagemDoSdr {
  id: number;
  autor: "Lead" | "IA" | "Equipe";
  enviada_em: string;
  texto: string;
  intencao: string | null;
  confianca: string | null;
  fallback: boolean;
  termo_nao_reconhecido: string | null;
  tom: string | null;
}

export interface ConversaDoSdr {
  id: number;
  lead_id: number;
  canal: string;
  iniciada_em: string;
  encerrada_em: string | null;
  desfecho: string | null;
  motivo_transbordo: string | null;
  destino_transbordo: string | null;
  atendida_em: string | null;
  nota: number | null;
  mensagens: MensagemDoSdr[];
}

export interface ParametrosDoSdr {
  custo_hora_sdr: string | null;
  minutos_por_conversa: number | null;
  cotacao_dolar: string | null;
  atualizado_por: string | null;
  atualizado_em: string | null;
}

export interface InvestimentoEmMidia {
  id: number;
  mes: string;
  canal: string;
  valor: string;
}

/** Percentual com a conta à vista. `valor` é nulo quando não há denominador. */
export interface Taxa {
  numerador: number;
  denominador: number;
  valor: number | null;
}

export interface Contagem {
  nome: string;
  quantidade: number;
}

export interface IndicadorDoSdr {
  valor: number | null;
  avaliacao: string | null;
  meta: string | null;
}

export interface LinhaDeOrigem {
  origem: string;
  leads: number;
  responderam: Taxa;
  qualificados: Taxa;
  reunioes: number;
  midia: string | null;
  custo_por_lead: string | null;
  custo_por_qualificado: string | null;
  avaliacao_resposta: string | null;
  avaliacao_qualificados: string | null;
  avaliacao_custo: string | null;
}

export interface PainelDoSdr {
  mes: string;
  origem: string | null;
  leads: number;
  responderam: number;
  com_desfecho: number;
  em_andamento: number;
  qualificados: number;
  fora_do_perfil: number;
  reunioes: number;
  qualificados_sobre_leads: Taxa;
  qualificados_sobre_responderam: Taxa;
  qualificacao_concluida: Taxa;
  transbordo: Taxa;
  parou: Taxa;
  reunioes_sobre_qualificados: Taxa;
  indicador_qualificacao: IndicadorDoSdr;
  indicador_transbordo: IndicadorDoSdr;
  indicador_reuniao: IndicadorDoSdr;
  tma_segundos: number | null;
  primeira_resposta: IndicadorDoSdr;
  csat: IndicadorDoSdr;
  notas: number;
  satisfeitos: Taxa;
  por_origem: LinhaDeOrigem[];
  interesses: Contagem[];
  confianca: { media: number | null; respostas: number; faixas: Contagem[]; abaixo_de_0_6: Taxa };
  falhas_por_resposta: Taxa;
  falhas_por_conversa: Taxa;
  indicador_falhas: IndicadorDoSdr;
  termos: Contagem[];
  funil: { nome: string; leads: number; saidas: Contagem[] }[];
  gatilhos: Contagem[];
  descartes: Contagem[];
  tom: Contagem[];
  portes: Contagem[];
  destinos: {
    destino: string;
    transbordos: number;
    atendidos: number;
    espera_media_min: number | null;
    avaliacao: string | null;
  }[];
  com_dados_da_empresa: number;
  oportunidades: number;
  custo_poupado: {
    calculavel: boolean;
    falta: string[];
    conversas_concluidas: number;
    custo_por_conversa: string | null;
    bruto: string | null;
    custo_ia: string | null;
    liquido: string | null;
    mensagens_sem_custo: number;
  };
  anterior: {
    qualificados: number;
    qualificacao_concluida: number | null;
    transbordo: number | null;
    tma_segundos: number | null;
    csat: number | null;
  } | null;
}

/** Um serviço do catálogo (`GET /api/servicos`). Sem preço, de propósito. */
export interface ServicoDoCatalogo {
  nome: string;
  nome_por_extenso: string | null;
  linha: "C1" | "C2";
  recorrente: boolean;
  para_quem: string;
  perguntas: { texto: string; direcionador: string | null }[];
  fora_do_perfil: string[];
  transbordo: string;
  nomes_antigos: string[];
  rascunho: boolean;
  /** Quando há temas, escolher um é obrigatório. */
  temas: { nome: string; perguntas: { texto: string; direcionador: string | null }[] }[];
}

/** Um "Outro" registrado: o que o lead pediu fora do catálogo. */
export interface PedidoDeServicoNovo {
  onde: "Oportunidade" | "Lead";
  id: number;
  nome: string;
  descricao: string;
  registrado_em: string;
}

/** Questionário para proposta enviado pelo cliente no site e trazido pelo "Buscar questionários" (01/10/2026). */
export interface QuestionarioResumo {
  id: number;
  recebido_em: string;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj: string;
  contato_nome: string;
  contato_cargo: string | null;
  /** "Importado" ou "Precisa de você". */
  situacao: string;
  cliente_novo: boolean;
  o_que_fez: string;
  grupo_id: number | null;
  grupo_nome: string | null;
  oportunidade_id: number | null;
  /** Só em "Precisa de você": a oportunidade em aberto que já existia para o CNPJ. */
  oportunidade_em_aberto_id: number | null;
  porte_crm: string | null;
  porte_site: string | null;
  tem_pdf: boolean;
}

export interface ResultadoDaBusca {
  buscado_em: string;
  novos: QuestionarioResumo[];
  avisos: string[];
}

export interface QuestionarioDaOportunidade {
  id: number;
  recebido_em: string;
  versao: string;
  contato_nome: string;
  contato_cargo: string | null;
  contato_email: string | null;
  contato_celular: string | null;
  servicos: string[];
  porte_crm: string | null;
  porte_site: string | null;
  pontuacao: string | null;
  horas_base: number | null;
  nota_complexidade: number;
  fatores_complexidade: { id: string; rotulo: string }[];
  nota_risco: number;
  fatores_risco: { id: string; rotulo: string }[];
  /** [texto, área] */
  pontos_de_atencao: [string, string][];
  notas_emitidas: number | null;
  notas_recebidas: number | null;
  tem_pdf: boolean;
}

/** Proposta em PowerPoint (01/10/2026). Dinheiro chega como texto decimal ("6900.00"). */
export type TipoDeMatriz = "Contábil" | "Financeiro";

export interface SugestaoDePreco {
  porte: string;
  porte_confirmado: boolean;
  horas_base: string;
  complexidade: number;
  complexidade_informada: boolean;
  risco: number;
  risco_informado: boolean;
  disciplina: number;
  atrito: string;
  horas: string;
  custo_hora: string;
  custo: string;
  imposto: string;
  margem_alvo: string;
  origem_da_margem: string;
  bruto: string;
  liquido: string;
}

export interface EntradaDaProposta {
  matriz: TipoDeMatriz;
  cliente: string;
  tratamento: string;
  contextualizacao: string;
  valor_contabil: string | null;
  valor_dp: string | null;
  horas_contabil: number | null;
  horas_dp: number | null;
  plano_bpo: string | null;
  plano_plus: string | null;
  plano_cfo: string | null;
}

export interface PropostaResumo {
  id: number;
  numero: string;
  matriz: TipoDeMatriz;
  gerada_em: string;
  valor_liquido: string | null;
  valor_bruto: string | null;
  enviada_em: string | null;
  enviada_por: string | null;
  arquivo: string;
}

export interface MatrizResumo {
  id: number;
  tipo: TipoDeMatriz;
  nome_arquivo: string;
  enviada_em: string;
  enviada_por: string;
  encontrados: number;
  obrigatorios: number;
  faltando: string[];
  desconhecidos: string[];
  utilizavel: boolean;
}

export interface AbaDaProposta {
  matriz_sugerida: TipoDeMatriz;
  servicos: string[];
  tem_dp: boolean;
  sugestao: SugestaoDePreco | null;
  sem_sugestao: string | null;
  rascunho: EntradaDaProposta;
  perfil: Record<string, string>;
  imposto: string;
  matrizes: Record<TipoDeMatriz, MatrizResumo | null>;
  revisores: string[];
  proximo_numero: string;
  propostas: PropostaResumo[];
}

export interface ConfiguracaoDeProposta {
  proximo_numero: number;
  revisores: string[];
  plano_bpo: string;
  plano_plus: string;
  plano_cfo: string;
  imposto: string;
  ultimo_usado: string | null;
}

export interface MarcadorDeProposta {
  nome: string;
  descricao: string;
  obrigatorio_em: TipoDeMatriz[];
}

export interface MatrizesDeProposta {
  em_uso: Record<TipoDeMatriz, MatrizResumo | null>;
  marcadores: MarcadorDeProposta[];
}

/* ---------------------------------------------------------- ficha e pendências (E4, 02/10/2026) */

export type TipoDeCampoDaFicha = "texto" | "texto_longo" | "numero" | "data" | "uma" | "varias";

export interface CampoDaFicha {
  chave: string;
  rotulo: string;
  tipo: TipoDeCampoDaFicha;
  opcoes: string[];
  sub: boolean;
  valor: string | string[] | null;
  /** "Questionário", "Entrevista" ou null (sem resposta). */
  origem: "Questionário" | "Entrevista" | null;
  por: string | null;
  em: string | null;
}

export interface SecaoDaFicha {
  numero: number;
  titulo: string;
  no_escopo: boolean;
  /** A seção 9 (implantação) e as fora do escopo não contam como pendência da proposta. */
  conta_pendencia: boolean;
  respondidas: number;
  total: number;
  campos: CampoDaFicha[];
}

export interface Ficha {
  questionario_em: string | null;
  respondidas: number;
  total: number;
  revisores: string[];
  secoes: SecaoDaFicha[];
}

export interface PendenciaDaProposta {
  /** Regra automática ("volumes", "porte"…) ou "manual-<id>". */
  chave: string;
  descricao: string;
  automatica: boolean;
  aberta: boolean;
  responsavel: string | null;
  prazo: string | null;
  dias_de_atraso: number;
  feita_em: string | null;
  feita_por: string | null;
}

export interface PendenciasDaProposta {
  abertas: number;
  atrasadas: number;
  feitas: number;
  revisores: string[];
  itens: PendenciaDaProposta[];
}

export interface MudancaDePendencia {
  responsavel?: string | null;
  prazo?: string | null;
  feita?: boolean;
  por: string;
}

/* ------------------------------------------------------ acesso (E1, 02/10/2026) */

export interface ConfiguracaoDeEntrada {
  /** "microsoft": entra pela conta Microsoft; "local": sem login, só na máquina do CRM. */
  modo: "microsoft" | "local";
  tenant_id: string | null;
  client_id: string | null;
  escopo: string | null;
}

export interface Eu {
  modo: "microsoft" | "local";
  email: string | null;
  nome: string | null;
  perfil: string;
  administrador: boolean;
  permissoes: string[];
}

export interface MenuDoCatalogo {
  chave: string;
  rotulo: string;
  funcionalidades: { chave: string; rotulo: string }[];
}

export interface PerfilDeAcesso {
  id: number;
  nome: string;
  administrador: boolean;
  permissoes: string[];
  pessoas: number;
}

export interface UsuarioDoCrm {
  id: number;
  email: string;
  nome: string | null;
  perfil_id: number;
  perfil: string;
  ativo: boolean;
  liberado_por: string | null;
  criado_em: string;
}

export interface Alteracao {
  id: number;
  quando: string;
  usuario_email: string;
  usuario_nome: string | null;
  acao: "criou" | "alterou" | "excluiu";
  tabela: string;
  registro_id: number | null;
  descricao: string | null;
  campo: string | null;
  antes: string | null;
  depois: string | null;
}
