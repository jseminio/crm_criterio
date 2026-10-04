/** O acesso à API. Um lugar só, para o erro ter uma forma só. */

import type {
  BaseDeConhecimento,
  EdicaoDeFicha,
  FichaDaBase,
  AbordagemDetalhe,
  AbordagemResumo,
  Agenda,
  EnderecoDeContato,
  ExclusaoDaOportunidade,
  FusaoFeita,
  EntidadeDeContato,
  EmpresaEncontrada,
  PaginaDeContatos,
  PessoaComOrigem,
  PessoaDeContato,
  TipoDeContato,
  Mrr,
  AnaliseDaCarteira,
  RevisaoDaCarteira,
  ClassificacaoDaCarteira,
  EdicaoDeNotas,
  EdicaoDeParametros,
  EdicaoDePorte,
  PeriodoDeAvaliacao,
  RascunhoDaAvaliacao,
  RespostasDoRascunho,
  SimulacaoDoCliente,
  Parametros,
  PorteDoGrupo,
  ResultadoDaEdicao,
  SugestaoDePorte,
  VolumetriaEntrada,
  CenariosDoServico,
  FasesDoMes,
  PlanoDeMrr,
  PremissasDoPlano,
  ColunaDoFunil,
  ConversaDoSdr,
  InvestimentoEmMidia,
  PainelDoSdr,
  ParametrosDoSdr,
  PedidoDeServicoNovo,
  ServicoDoCatalogo,
  CarteiraComReunioes,
  DimensaoDeRecorte,
  LinhaDeRecorte,
  ContratoDetalhe,
  ContratoResumo,
  Execucao,
  ExecucaoDetalhe,
  GrupoResumo,
  SugestaoDeFusao,
  Indicadores,
  LeadResumo,
  Listas,
  Ocorrencia,
  OportunidadeDetalhe,
  OportunidadeResumo,
  Pagina,
  ResumoDasAbordagens,
  QuestionarioDaOportunidade,
  QuestionarioResumo,
  ResultadoDaBusca,
  AbaDaProposta,
  ConfiguracaoDeProposta,
  Alteracao,
  ConfiguracaoDeEntrada,
  EntradaDaProposta,
  Eu,
  Ficha,
  MenuDoCatalogo,
  PerfilDeAcesso,
  UsuarioDoCrm,
  MudancaDePendencia,
  PendenciasDaProposta,
  MatrizesDeProposta,
  MatrizResumo,
  PropostaResumo,
  TipoDeMatriz,
  Aprovacao,
  PainelDeQuestionarios,
  SecaoDeRespostas,
  SituacaoDoPainel,
  Metas,
  AjusteTecnico,
  CadenciaDeReunioes,
  EstadoDaBusca,
  FunilDoSucesso,
  RascunhoDaAta,
  ResponsavelPorAjuste,
  GrupoNoFunilDoSucesso,
  NovaReuniaoDeResultado,
  ReuniaoDeResultado,
} from "./tipos";

export class ErroDaApi extends Error {
  readonly status: number;

  constructor(status: number, mensagem: string) {
    super(mensagem);
    this.status = status;
  }
}

/* ------------------------------------------------ entrada (E1, 02/10/2026) */

/** Com a entrada pela Microsoft, quem dá o token é o `Entrada` (src/entrada.tsx). Sem login, fica
 * vazio e os pedidos saem como antes. */
let fornecedorDeToken: (() => Promise<string | null>) | null = null;
let aoPerderEntrada: (() => void) | null = null;

export function definirEntrada(fornecedor: (() => Promise<string | null>) | null, perdeu: (() => void) | null = null) {
  fornecedorDeToken = fornecedor;
  aoPerderEntrada = perdeu;
}

async function cabecalhoDeEntrada(): Promise<Record<string, string>> {
  const token = fornecedorDeToken ? await fornecedorDeToken() : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Com login, um link comum não leva o token: os downloads passam pelo `baixarArquivo`. */
export function entradaLigada(): boolean {
  return fornecedorDeToken !== null;
}

function avisarSePerdeu(status: number) {
  if (status === 401 && aoPerderEntrada) aoPerderEntrada();
}

/** Baixa um arquivo da API levando a entrada junto (um link comum não leva o token). O nome vem do
 * cabeçalho da resposta; sem ele, o `sugerido`. */
export async function baixarArquivo(caminho: string, sugerido = "arquivo", novaAba = false): Promise<void> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, { headers: await cabecalhoDeEntrada() });
  } catch {
    throw new ErroDaApi(0, "Não consegui falar com o servidor. Ele está no ar?");
  }
  if (!resposta.ok) {
    avisarSePerdeu(resposta.status);
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (typeof corpo?.detail === "string") detalhe = corpo.detail;
    } catch {
      /* sem JSON */
    }
    throw new ErroDaApi(resposta.status, detalhe);
  }
  const disposicao = resposta.headers.get("content-disposition") ?? "";
  const codificado = /filename\*=UTF-8''([^;]+)/i.exec(disposicao)?.[1];
  const nome = (codificado && decodeURIComponent(codificado)) || /filename="?([^";]+)"?/i.exec(disposicao)?.[1] || sugerido;
  const url = URL.createObjectURL(await resposta.blob());
  if (novaAba) {
    window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
    return;
  }
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    a.remove();
    URL.revokeObjectURL(url);
  }, 1000);
}

/** Nome de campo como aparece na tela; o que não estiver aqui sai com o nome técnico. */
const ROTULO_DO_CAMPO: Record<string, string> = {
  cliente: "Cliente",
  tratamento: "Tratamento",
  contextualizacao: "Contextualização",
  valor_contabil: "Honorário Contábil/Fiscal",
  valor_dp: "Honorário DP",
  horas_contabil: "Horas Contábil/Fiscal",
  horas_dp: "Horas DP",
  plano_bpo: "Plano BPO Financeiro",
  plano_plus: "Plano BPO Financeiro PLUS",
  plano_cfo: "Plano CFO as a Service",
};

type ErroDeValidacao = { loc?: unknown[]; type?: string; msg?: string; ctx?: Record<string, unknown> };

function motivo(e: ErroDeValidacao): string {
  const ctx = e.ctx ?? {};
  switch (e.type) {
    case "missing":
    case "string_type":
    case "string_too_short":
      return "não pode ficar em branco";
    case "string_too_long":
      return `texto longo demais (máximo de ${ctx.max_length} caracteres)`;
    case "decimal_max_places":
      return "use no máximo 2 casas decimais";
    case "decimal_max_digits":
    case "decimal_whole_digits":
    case "less_than_equal":
      return "valor alto demais";
    case "greater_than_equal":
      return "não pode ser negativo";
    case "greater_than":
      return "precisa ser maior que zero";
    case "decimal_parsing":
    case "int_parsing":
    case "int_from_float":
      return "não é um número válido";
    default:
      return e.msg ?? "valor inválido";
  }
}

/** A recusa da validação do FastAPI (422 com `detail` em lista) vira frase: "Campo: motivo". Sem
 * isto a tela mostrava só "Erro 422", sem dizer o que corrigir. */
export function explicarValidacao(detalhes: ErroDeValidacao[]): string {
  return detalhes
    .map((e) => {
      const campo = String((e.loc ?? []).filter((x) => x !== "body").at(-1) ?? "");
      return `${ROTULO_DO_CAMPO[campo] ?? (campo || "Pedido")}: ${motivo(e)}`;
    })
    .join("; ");
}

async function pedir<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, {
      ...opcoes,
      headers: { "Content-Type": "application/json", ...(await cabecalhoDeEntrada()), ...opcoes?.headers },
    });
  } catch {
    // Distinguir "servidor fora do ar" de "servidor recusou" importa: a
    // primeira se resolve subindo a API, a segunda não.
    throw new ErroDaApi(0, "Não consegui falar com o servidor. Ele está no ar?");
  }

  if (!resposta.ok) {
    avisarSePerdeu(resposta.status);
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (typeof corpo?.detail === "string") detalhe = corpo.detail;
      else if (Array.isArray(corpo?.detail) && corpo.detail.length) detalhe = explicarValidacao(corpo.detail);
    } catch {
      /* resposta sem JSON: fica o texto genérico */
    }
    throw new ErroDaApi(resposta.status, detalhe);
  }

  return resposta.status === 204 ? (undefined as T) : resposta.json();
}

function comParametros(caminho: string, parametros: Record<string, unknown>) {
  const busca = new URLSearchParams();
  for (const [chave, valor] of Object.entries(parametros)) {
    if (valor === undefined || valor === null || valor === "") continue;
    if (Array.isArray(valor)) valor.forEach((v) => busca.append(chave, String(v)));
    else busca.append(chave, String(valor));
  }
  const texto = busca.toString();
  return texto ? `${caminho}?${texto}` : caminho;
}

export interface FiltrosDoFunil {
  captador?: string[];
  tipo_canal?: string[];
  temperatura?: string[];
  busca?: string;
  data_tipo?: "colocacao" | "aceite";
  data_de?: string;
  data_ate?: string;
}

export interface ResumoDeBackup {
  criado_em: string;
  revisao_do_esquema: string | null;
  tabelas: Record<string, number>;
  total: number;
}

/** O arquivo (backup, matriz de proposta) vai cru no corpo, não em JSON. */
async function enviarArquivo<T = ResumoDeBackup>(caminho: string, arquivo: File, cabecalhos: Record<string, string> = {}): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, { method: "POST", body: arquivo, headers: { ...(await cabecalhoDeEntrada()), ...cabecalhos } });
  } catch {
    throw new ErroDaApi(0, "Não consegui falar com o servidor. Ele está no ar?");
  }
  if (!resposta.ok) {
    avisarSePerdeu(resposta.status);
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (typeof corpo?.detail === "string") detalhe = corpo.detail;
      else if (Array.isArray(corpo?.detail) && corpo.detail.length) detalhe = explicarValidacao(corpo.detail);
    } catch {
      /* sem JSON */
    }
    throw new ErroDaApi(resposta.status, detalhe);
  }
  return (await resposta.json()) as T;
}

export const api = {
  entrada: () => pedir<ConfiguracaoDeEntrada>("/api/acesso/entrada"),
  eu: () => pedir<Eu>("/api/eu"),
  catalogoDeAcesso: () => pedir<MenuDoCatalogo[]>("/api/acesso/catalogo"),
  perfis: () => pedir<PerfilDeAcesso[]>("/api/acesso/perfis"),
  criarPerfil: (nome: string, permissoes: string[]) =>
    pedir<PerfilDeAcesso>("/api/acesso/perfis", { method: "POST", body: JSON.stringify({ nome, permissoes }) }),
  mudarPerfil: (id: number, mudanca: { nome?: string; permissoes?: string[] }) =>
    pedir<PerfilDeAcesso>(`/api/acesso/perfis/${id}`, { method: "PATCH", body: JSON.stringify(mudanca) }),
  usuarios: () => pedir<UsuarioDoCrm[]>("/api/acesso/usuarios"),
  liberarUsuario: (email: string, perfilId: number) =>
    pedir<UsuarioDoCrm>("/api/acesso/usuarios", { method: "POST", body: JSON.stringify({ email, perfil_id: perfilId }) }),
  mudarUsuario: (id: number, mudanca: { perfil_id?: number; ativo?: boolean }) =>
    pedir<UsuarioDoCrm>(`/api/acesso/usuarios/${id}`, { method: "PATCH", body: JSON.stringify(mudanca) }),
  historico: (filtros: { usuario?: string; tabela?: string; registro_id?: number; de?: string; ate?: string; limite?: number }) =>
    pedir<Alteracao[]>(comParametros("/api/historico", filtros)),

  verificarBackup: (arquivo: File) => enviarArquivo("/api/backup/verificar", arquivo),

  importarBackup: (arquivo: File, substituir: boolean) =>
    enviarArquivo(
      `/api/backup/importar${substituir ? "?substituir=true" : ""}`,
      arquivo,
      substituir ? { "X-Confirmacao": "SUBSTITUIR" } : {},
    ),

  contatosPorEmpresa: (tipo: TipoDeContato, busca: string, soComLacunas: boolean) =>
    pedir<PaginaDeContatos<EntidadeDeContato>>(
      comParametros("/api/contatos/empresas", { tipo, busca, so_com_lacunas: soComLacunas || undefined, limite: 200 }),
    ),

  contatosPorPessoa: (tipo: TipoDeContato, busca: string) =>
    pedir<PaginaDeContatos<PessoaComOrigem>>(comParametros("/api/contatos/pessoas", { tipo, busca, limite: 200 })),

  criarContato: (dados: Record<string, unknown>) =>
    pedir<PessoaDeContato>("/api/contatos/pessoas", { method: "POST", body: JSON.stringify(dados) }),

  editarContato: (id: number, mudancas: Record<string, unknown>) =>
    pedir<PessoaDeContato>(`/api/contatos/pessoas/${id}`, { method: "PATCH", body: JSON.stringify(mudancas) }),

  editarEmpresa: (id: number, mudancas: Record<string, unknown>) =>
    pedir<EnderecoDeContato>(`/api/empresas/${id}`, { method: "PATCH", body: JSON.stringify(mudancas) }),

  /** A base de empresas, por nome, razão social ou CNPJ — para escolher a da oportunidade. */
  buscarEmpresas: (busca: string) =>
    pedir<EmpresaEncontrada[]>(comParametros("/api/empresas/busca", { busca })),

  /** Toda a base de contatos (clientes e prospects), por nome, e-mail ou telefone. */
  buscarPessoas: (busca: string) =>
    pedir<PessoaDeContato[]>(comParametros("/api/contatos/pessoas/busca", { busca })),

  /** Contatos > Nova empresa: dados, endereço e os contatos vinculados. */
  criarEmpresa: (dados: Record<string, unknown>) =>
    pedir<{ id: number; razao_social: string; cnpj: string | null; grupo_id: number; grupo_nome: string }>(
      "/api/empresas",
      { method: "POST", body: JSON.stringify(dados) },
    ),

  vincularContato: (empresaId: number, pessoaId: number, principal = false) =>
    pedir<unknown>(`/api/empresas/${empresaId}/contatos`, {
      method: "POST",
      body: JSON.stringify({ pessoa_id: pessoaId, principal }),
    }),

  marcarPrincipal: (empresaId: number, pessoaId: number, principal: boolean) =>
    pedir<unknown>(`/api/empresas/${empresaId}/contatos/${pessoaId}`, {
      method: "PATCH",
      body: JSON.stringify({ principal }),
    }),

  desvincularContato: (empresaId: number, pessoaId: number) =>
    pedir<unknown>(`/api/empresas/${empresaId}/contatos/${pessoaId}`, { method: "DELETE" }),

  /** Irreversível: a tela confirma antes. Tira a pessoa de todas as empresas. */
  excluirPessoa: (id: number) => pedir<unknown>(`/api/contatos/pessoas/${id}`, { method: "DELETE" }),

  /** Irreversível: a tela confirma antes. Empresa com contrato é recusada (409). */
  excluirEmpresa: (id: number) => pedir<unknown>(`/api/empresas/${id}`, { method: "DELETE" }),

  criarEmpresaDoGrupo: (grupoId: number, dados: Record<string, unknown> = {}) =>
    pedir<{ id: number; razao_social: string; cnpj: string | null }>(`/api/grupos/${grupoId}/empresas`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  classificacaoDaCarteira: () => pedir<ClassificacaoDaCarteira>("/api/carteira/classificacao"),
  analiseDaCarteira: () => pedir<AnaliseDaCarteira | null>("/api/carteira/analise"),
  gerarAnaliseDaCarteira: (autor: string) =>
    pedir<AnaliseDaCarteira>("/api/carteira/analise", { method: "POST", body: JSON.stringify({ autor }) }),
  revisoesDaCarteira: () => pedir<RevisaoDaCarteira[]>("/api/carteira/revisoes"),
  registrarRevisaoDaCarteira: (autor: string) =>
    pedir<RevisaoDaCarteira>("/api/carteira/revisoes", { method: "POST", body: JSON.stringify({ autor }) }),
  editarMesDaRevisao: (id: number, mes: string) =>
    pedir<RevisaoDaCarteira>(`/api/carteira/revisoes/${id}/mes`, { method: "PATCH", body: JSON.stringify({ mes }) }),
  editarNotasDaCarteira: (grupoId: number, corpo: EdicaoDeNotas) =>
    pedir<ResultadoDaEdicao>(`/api/carteira/grupos/${grupoId}/notas`, { method: "POST", body: JSON.stringify(corpo) }),
  sugestaoDePorte: (corpo: VolumetriaEntrada) =>
    pedir<SugestaoDePorte>("/api/carteira/porte/sugestao", { method: "POST", body: JSON.stringify(corpo) }),
  editarPorte: (grupoId: number, corpo: EdicaoDePorte) =>
    pedir<PorteDoGrupo>(`/api/carteira/grupos/${grupoId}/porte`, { method: "POST", body: JSON.stringify(corpo) }),
  abrirPeriodo: (corpo: { autor: string; mes: string; margem_minima?: number; margem_alvo?: number }) =>
    pedir<PeriodoDeAvaliacao>("/api/carteira/periodo", { method: "POST", body: JSON.stringify(corpo) }),
  editarJanela: (corpo: { autor: string; margem_minima: number; margem_alvo: number }) =>
    pedir<PeriodoDeAvaliacao>("/api/carteira/periodo/janela", { method: "PATCH", body: JSON.stringify(corpo) }),
  salvarRascunho: (grupoId: number, corpo: RespostasDoRascunho & { autor: string }) =>
    pedir<RascunhoDaAvaliacao>(`/api/carteira/periodo/grupos/${grupoId}/rascunho`, { method: "PUT", body: JSON.stringify(corpo) }),
  simularCliente: (grupoId: number) =>
    pedir<SimulacaoDoCliente>(`/api/carteira/periodo/grupos/${grupoId}/simulacao`, { method: "POST" }),
  calcularCarteira: (autor: string) =>
    pedir<{ periodo: PeriodoDeAvaliacao; grupos_calculados: number }>("/api/carteira/periodo/calcular", {
      method: "POST", body: JSON.stringify({ autor }),
    }),
  parametrosAtuais: () => pedir<Parametros>("/api/carteira/parametros"),
  editarParametros: (corpo: EdicaoDeParametros) =>
    pedir<Parametros>("/api/carteira/parametros", { method: "POST", body: JSON.stringify(corpo) }),
  mrr: (de?: string) => pedir<Mrr>(comParametros("/api/mrr", { de })),

  agenda: (captador?: string[]) =>
    pedir<Agenda>(comParametros("/api/agenda", { captador })),

  listas: () => pedir<Listas>("/api/listas"),

  funil: (filtros: FiltrosDoFunil = {}) =>
    pedir<ColunaDoFunil[]>(comParametros("/api/funil", { ...filtros })),

  cargas: () => pedir<Execucao[]>("/api/cargas"),

  carga: (id: number) => pedir<ExecucaoDetalhe>(`/api/cargas/${id}`),

  ocorrencias: (id: number, filtros: { tipo?: string; campo?: string } = {}) =>
    pedir<Pagina<Ocorrencia>>(
      comParametros(`/api/cargas/${id}/ocorrencias`, { ...filtros, limite: 200 }),
    ),

  indicadores: (filtros: FiltrosDoFunil = {}) =>
    pedir<Indicadores>(comParametros("/api/indicadores", { ...filtros })),

  recortes: (dimensao: DimensaoDeRecorte, filtros: FiltrosDoFunil = {}) =>
    pedir<LinhaDeRecorte[]>(comParametros("/api/indicadores/recortes", { dimensao, ...filtros })),

  planoDeMrr: () => pedir<PlanoDeMrr>("/api/inteligencia/plano"),
  mudarPlanoDeMrr: (premissas: PremissasDoPlano) =>
    pedir<PlanoDeMrr>("/api/inteligencia/plano", { method: "PUT", body: JSON.stringify(premissas) }),
  cenariosPorServico: () => pedir<CenariosDoServico[]>("/api/inteligencia/cenarios-de-ticket"),
  fasesDoMes: (mes?: string) => pedir<FasesDoMes>(comParametros("/api/inteligencia/fases", { mes })),

  oportunidades: (filtros: FiltrosDoFunil & { situacao?: string[]; grupo_id?: number } = {}) =>
    pedir<Pagina<OportunidadeResumo>>(
      comParametros("/api/oportunidades", { ...filtros, limite: 1000 }),
    ),

  /** Endereço (não pedido): a Grade em Excel, com os mesmos filtros. Vai num link de download. */
  enderecoDaExportacaoDoFunil: (filtros: FiltrosDoFunil & { situacao?: string[] } = {}) =>
    comParametros("/api/oportunidades/exportar", { ...filtros }),

  oportunidade: (id: number) => pedir<OportunidadeDetalhe>(`/api/oportunidades/${id}`),
  questionarioDaOportunidade: (id: number) =>
    pedir<QuestionarioDaOportunidade | null>(`/api/oportunidades/${id}/questionario`),
  buscarQuestionarios: () => pedir<ResultadoDaBusca>("/api/questionarios/buscar", { method: "POST" }),
  questionarios: () => pedir<QuestionarioResumo[]>("/api/questionarios"),
  estadoDaBusca: () => pedir<EstadoDaBusca>("/api/questionarios/busca"),
  painelDeQuestionarios: (filtros: { dias?: number | null; servico?: string; porte?: string; situacao?: SituacaoDoPainel | "" }) =>
    pedir<PainelDeQuestionarios>(comParametros("/api/questionarios/painel", { ...filtros })),
  respostasDoQuestionario: (id: number) => pedir<SecaoDeRespostas[]>(`/api/questionarios/${id}/respostas`),
  resolverQuestionario: (id: number, acao: "anexar" | "criar") =>
    pedir<QuestionarioResumo>(`/api/questionarios/${id}/resolver`, { method: "POST", body: JSON.stringify({ acao }) }),

  ficha: (oportunidadeId: number) => pedir<Ficha>(`/api/oportunidades/${oportunidadeId}/ficha`),
  corrigirFicha: (oportunidadeId: number, chave: string, valor: string | string[] | null, por: string) =>
    pedir<Ficha>(`/api/oportunidades/${oportunidadeId}/ficha/${encodeURIComponent(chave)}`, {
      method: "PUT",
      body: JSON.stringify({ valor, por }),
    }),
  pendencias: (oportunidadeId: number) => pedir<PendenciasDaProposta>(`/api/oportunidades/${oportunidadeId}/pendencias`),
  novaPendencia: (oportunidadeId: number, corpo: { descricao: string; responsavel?: string | null; prazo?: string | null; por: string }) =>
    pedir<PendenciasDaProposta>(`/api/oportunidades/${oportunidadeId}/pendencias`, { method: "POST", body: JSON.stringify(corpo) }),
  mudarPendencia: (oportunidadeId: number, chave: string, mudanca: MudancaDePendencia) =>
    pedir<PendenciasDaProposta>(`/api/oportunidades/${oportunidadeId}/pendencias/${encodeURIComponent(chave)}`, {
      method: "PATCH",
      body: JSON.stringify(mudanca),
    }),
  abaDaProposta: (oportunidadeId: number) => pedir<AbaDaProposta>(`/api/oportunidades/${oportunidadeId}/proposta`),
  gerarProposta: (oportunidadeId: number, entrada: EntradaDaProposta) =>
    pedir<PropostaResumo>(`/api/oportunidades/${oportunidadeId}/proposta`, { method: "POST", body: JSON.stringify(entrada) }),
  marcarPropostaEnviada: (propostaId: number, por: string, em: string) =>
    pedir<PropostaResumo>(`/api/propostas/${propostaId}/enviada`, { method: "POST", body: JSON.stringify({ por, em }) }),
  matrizesDeProposta: () => pedir<MatrizesDeProposta>("/api/propostas/matrizes"),
  subirMatriz: (tipo: TipoDeMatriz, arquivo: File, enviadaPor: string) =>
    enviarArquivo<MatrizResumo>(
      comParametros(`/api/propostas/matrizes/${encodeURIComponent(tipo)}`, { nome_arquivo: arquivo.name, enviada_por: enviadaPor }),
      arquivo,
    ),
  configuracaoDeProposta: () => pedir<ConfiguracaoDeProposta>("/api/propostas/configuracao"),
  editarConfiguracaoDeProposta: (c: Omit<ConfiguracaoDeProposta, "imposto" | "ultimo_usado">) =>
    pedir<ConfiguracaoDeProposta>("/api/propostas/configuracao", { method: "PUT", body: JSON.stringify(c) }),

  criarOportunidade: (oportunidade: Record<string, unknown>) =>
    pedir<OportunidadeDetalhe>("/api/oportunidades", {
      method: "POST",
      body: JSON.stringify(oportunidade),
    }),

  editarOportunidade: (id: number, mudancas: Record<string, unknown>) =>
    pedir<OportunidadeDetalhe>(`/api/oportunidades/${id}`, {
      method: "PATCH",
      body: JSON.stringify(mudancas),
    }),

  leads: (filtros: { apenas_abertos?: boolean; busca?: string; tipo_canal?: string } = {}) =>
    pedir<Pagina<LeadResumo>>(comParametros("/api/leads", filtros)),

  criarLead: (lead: Record<string, unknown>) =>
    pedir<LeadResumo>("/api/leads", { method: "POST", body: JSON.stringify(lead) }),

  editarLead: (id: number, mudancas: Record<string, unknown>) =>
    pedir<LeadResumo>(`/api/leads/${id}`, {
      method: "PATCH",
      body: JSON.stringify(mudancas),
    }),

  converterLead: (id: number, dados: Record<string, unknown>) =>
    pedir<OportunidadeDetalhe>(`/api/leads/${id}/converter`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  servicos: () => pedir<ServicoDoCatalogo[]>("/api/servicos"),

  pedidosDeServicoNovo: () => pedir<PedidoDeServicoNovo[]>("/api/servicos/pedidos"),

  // ---------------------------------------------------------- SDR de IA
  painelDoSdr: (filtros: { mes: string; origem?: string }) =>
    pedir<PainelDoSdr>(comParametros("/api/sdr/painel", filtros)),

  conversasDoLead: (leadId: number) =>
    pedir<ConversaDoSdr[]>(`/api/sdr/leads/${leadId}/conversas`),

  parametrosDoSdr: () => pedir<ParametrosDoSdr>("/api/sdr/parametros"),

  gravarParametrosDoSdr: (dados: Record<string, unknown>) =>
    pedir<ParametrosDoSdr>("/api/sdr/parametros", { method: "PUT", body: JSON.stringify(dados) }),

  midia: (mes: string) => pedir<InvestimentoEmMidia[]>(comParametros("/api/sdr/midia", { mes })),

  gravarMidia: (dados: { mes: string; canal: string; valor: string }) =>
    pedir<InvestimentoEmMidia>("/api/sdr/midia", { method: "PUT", body: JSON.stringify(dados) }),

  grupos: (filtros: { busca?: string; limite?: number; incluir_fundidos?: boolean } = {}) =>
    pedir<Pagina<GrupoResumo>>(comParametros("/api/grupos", { limite: 500, ...filtros })),

  editarGrupo: (id: number, mudancas: Record<string, unknown>) =>
    pedir<GrupoResumo>(`/api/grupos/${id}`, { method: "PATCH", body: JSON.stringify(mudancas) }),

  sugestoesDeFusao: () => pedir<SugestaoDeFusao[]>("/api/grupos/sugestoes-de-fusao"),

  fusoesFeitas: () => pedir<FusaoFeita[]>("/api/grupos/fusoes"),

  desfazerFusao: (id: number) => pedir<FusaoFeita>(`/api/grupos/fusoes/${id}/desfazer`, { method: "POST" }),

  fundirGrupos: (principalId: number, absorvidoId: number) =>
    pedir<GrupoResumo>(`/api/grupos/${principalId}/fundir`, {
      method: "POST",
      body: JSON.stringify({ absorvido_id: absorvidoId }),
    }),

  contratos: (filtros: { situacao?: string[]; grupo_id?: number } = {}) =>
    pedir<Pagina<ContratoResumo>>(comParametros("/api/contratos", { ...filtros, limite: 500 })),

  contrato: (id: number) => pedir<ContratoDetalhe>(`/api/contratos/${id}`),

  metas: () => pedir<Metas>("/api/metas"),
  mudarMetas: (metas: { mrr?: { meta: string; alerta: string }; conversao?: { meta: string; alerta: string } }) =>
    pedir<Metas>("/api/metas", { method: "PUT", body: JSON.stringify(metas) }),
  funilDoSucesso: () => pedir<FunilDoSucesso>("/api/sucesso/funil"),
  marcarItemDoSucesso: (grupoId: number, item: string, feito: boolean) =>
    pedir<GrupoNoFunilDoSucesso>(`/api/sucesso/grupos/${grupoId}/itens`, { method: "PATCH", body: JSON.stringify({ item, feito }) }),
  concluirEtapaDoSucesso: (grupoId: number) =>
    pedir<GrupoNoFunilDoSucesso>(`/api/sucesso/grupos/${grupoId}/concluir-etapa`, { method: "POST" }),
  reunioesDoGrupo: (grupoId: number) => pedir<ReuniaoDeResultado[]>(`/api/sucesso/grupos/${grupoId}/reunioes`),
  registrarReuniao: (grupoId: number, reuniao: NovaReuniaoDeResultado) =>
    pedir<GrupoNoFunilDoSucesso>(`/api/sucesso/grupos/${grupoId}/reunioes`, { method: "POST", body: JSON.stringify(reuniao) }),
  montarAta: (grupoId: number, pedido: { tipo: string; data: string; participantes?: string; transcricao: string }) =>
    pedir<RascunhoDaAta>(`/api/sucesso/grupos/${grupoId}/ata`, { method: "POST", body: JSON.stringify(pedido) }),
  responsaveisPorAjuste: () => pedir<ResponsavelPorAjuste[]>("/api/ajustes/responsaveis"),
  ajustes: (situacao: "pendentes" | "feitos" | "todos" = "pendentes") =>
    pedir<AjusteTecnico[]>(`/api/ajustes?situacao=${situacao}`),
  marcarAjusteFeito: (id: number, observacao: string) =>
    pedir<AjusteTecnico>(`/api/ajustes/${id}/feito`, { method: "POST", body: JSON.stringify({ observacao }) }),
  reabrirAjuste: (id: number) => pedir<AjusteTecnico>(`/api/ajustes/${id}/reabrir`, { method: "POST" }),
  baseDoSdr: () => pedir<BaseDeConhecimento>("/api/sdr/base"),
  criarFicha: (ficha: EdicaoDeFicha) =>
    pedir<FichaDaBase>("/api/sdr/base/fichas", { method: "POST", body: JSON.stringify(ficha) }),
  alterarFicha: (id: number, mudanca: EdicaoDeFicha) =>
    pedir<FichaDaBase>(`/api/sdr/base/fichas/${id}`, { method: "PATCH", body: JSON.stringify(mudanca) }),
  moverFicha: (id: number, acao: "revisao" | "arquivar" | "reabrir") =>
    pedir<FichaDaBase>(`/api/sdr/base/fichas/${id}/${acao}`, { method: "POST" }),
  aprovarFicha: (id: number, aprovador: string | null) =>
    pedir<FichaDaBase>(`/api/sdr/base/fichas/${id}/aprovar`, { method: "POST", body: JSON.stringify({ aprovador }) }),
  cargaInicialDaBase: () =>
    pedir<{ acrescentadas: number; ja_existiam: number }>("/api/sdr/base/carga-inicial", { method: "POST" }),
  cadenciaDeReunioes: () => pedir<CadenciaDeReunioes>("/api/sucesso/cadencia"),
  mudarCadenciaDeReunioes: (mudanca: { cadencia?: Record<string, string[]>; intencao?: Record<string, string> }) =>
    pedir<CadenciaDeReunioes>("/api/sucesso/cadencia", { method: "PUT", body: JSON.stringify(mudanca) }),
  reunioesDaCarteira: () => pedir<CarteiraComReunioes>("/api/sucesso/carteira"),
  registrarReuniaoDaCarteira: (reuniao: { data: string; participantes?: string; resumo?: string; correcoes_de_rota?: string }) =>
    pedir<CarteiraComReunioes>("/api/sucesso/carteira/reunioes", { method: "POST", body: JSON.stringify(reuniao) }),
  aprovacoes: () => pedir<Aprovacao[]>("/api/aprovacoes"),
  aprovar: (id: number) => pedir<Aprovacao>(`/api/aprovacoes/${id}/aprovar`, { method: "POST" }),
  recusar: (id: number, motivo: string) =>
    pedir<Aprovacao>(`/api/aprovacoes/${id}/recusar`, { method: "POST", body: JSON.stringify({ motivo }) }),

  registrarEventoDeContrato: (id: number, evento: Record<string, unknown>) =>
    pedir<ContratoDetalhe>(`/api/contratos/${id}/eventos`, {
      method: "POST",
      body: JSON.stringify(evento),
    }),

  editarContrato: (id: number, mudancas: Record<string, unknown>) =>
    pedir<ContratoDetalhe>(`/api/contratos/${id}`, {
      method: "PATCH",
      body: JSON.stringify(mudancas),
    }),

  exclusaoDaOportunidade: (id: number) => pedir<ExclusaoDaOportunidade>(`/api/oportunidades/${id}/exclusao`),
  excluirOportunidade: (id: number, motivo: string) =>
    pedir<unknown>(`/api/oportunidades/${id}/excluir`, { method: "POST", body: JSON.stringify({ motivo }) }),

  converterEmContrato: (oportunidadeId: number, dados: Record<string, unknown> = {}) =>
    pedir<ContratoDetalhe>(`/api/oportunidades/${oportunidadeId}/converter-em-contrato`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

  abordagens: () => pedir<Pagina<AbordagemResumo>>("/api/abordagens"),

  abordagem: (id: number) => pedir<AbordagemDetalhe>(`/api/abordagens/${id}`),

  resumoDasAbordagens: (mes: string) =>
    pedir<ResumoDasAbordagens>(comParametros("/api/abordagens/resumo", { mes })),

  editarAbordagem: (id: number, mudancas: Record<string, unknown>) =>
    pedir<AbordagemDetalhe>(`/api/abordagens/${id}`, {
      method: "PATCH",
      body: JSON.stringify(mudancas),
    }),

  prepararAbordagem: (id: number) =>
    pedir<AbordagemDetalhe>(`/api/abordagens/${id}/preparar`, { method: "POST" }),

  pedirOutraVersao: (id: number, instrucao: string) =>
    pedir<AbordagemDetalhe>(`/api/abordagens/${id}/nova-versao`, {
      method: "POST",
      body: JSON.stringify({ instrucao }),
    }),

  aprovarAbordagem: (id: number) =>
    pedir<AbordagemDetalhe>(`/api/abordagens/${id}/aprovar`, {
      method: "POST",
      body: JSON.stringify({}),
    }),

  marcarAbordagemEnviada: (id: number) =>
    pedir<AbordagemDetalhe>(`/api/abordagens/${id}/marcar-enviada`, { method: "POST" }),

  descartarAbordagem: (id: number) =>
    pedir<AbordagemDetalhe>(`/api/abordagens/${id}/descartar`, { method: "POST" }),
};
