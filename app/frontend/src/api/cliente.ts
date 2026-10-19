/** O acesso à API. Um lugar só, para o erro ter uma forma só. */

import type {
  AlertaDaIndicacao,
  IndicacaoRegistrada,
  RelatorioDoParceiro,
  CadastroDoParceiro,
  FeeDeParceiro,
  IndicadorDosParceiros,
  IndicadoresDosParceiros,
  ItemDaComposicaoDosParceiros,
  OportunidadeParaIndicar,
  ParceiroDetalhe,
  ParceiroResumo,
  TextoSemParceiro,
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
  MrrDaCarteira,
  IndicadorDoFunil,
  ItemDoRealizado,
  SaidaAnunciada,
  PreviaDaMigracao,
  ItemDoPainelDoSdr,
  LinhaDaFase,
  ItemDaComposicao,
  ItemDoMovimento,
  PreviaDeRecebimentos,
  ImportacaoDeRecebimentos,
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
  InvestimentoPorCampanha,
  LeituraDosAnuncios,
  PainelDeCampanhas,
  ResultadoDaBuscaDeLeads,
  ResumoDasConversoes,
  RodadaDeConversoes,
  SituacaoDosLeadsDoMeta,
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
  CadastroDaLacuna,
  Lacuna,
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
  NovaReuniaoComLead,
  SugestaoDoContexto,
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
  Integracoes,
  KpisDaLideranca,
  QuadroDePropostas,
  PreviaDaMescla,
  SugestaoDeMescla,
  ResultadoDoTeste,
  EstadoDaBusca,
  FunilDoSucesso,
  RascunhoDaAta,
  ResponsavelPorAjuste,
  GrupoNoFunilDoSucesso,
  NovaReuniaoDeResultado,
  ReuniaoDeResultado,
  SessaoAberta,
  ItemDoReajuste,
  MesDoIpca,
  ModeloDeContrato,
  ReajusteDoAno,
  ReajusteDoServico,
  ServicoNoContrato,
  ConfiguracaoDoDocumento,
  DocumentoDoContrato,
  AbaDaAssinatura,
  SignatarioNovo,
  DocumentoAnexado,
  DocumentoComConferencia,
  TipoDeDocumento,
  VinculoDoDocumento,
  MatrizDeContratoResumo,
  MatrizDoContrato,
} from "./tipos";
import type { VersaoDaApi } from "../versao";

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

/* ------------------------------------------- sessão do login com senha (issue #89) */

/** O token do login com senha mora no `sessionStorage` (some ao fechar a aba), nunca no
 * `localStorage`. Navegador que recusa o armazenamento (modo privado restrito) só perde a sessão. */
const CHAVE_DA_SESSAO = "crm.sessao";

export interface SessaoGuardada {
  token: string;
  expira_em: string;
}

/** Sessão vencida conta como ausente. `expira_em` que não se lê fica a cargo do servidor (401). */
export function sessaoVencida(sessao: SessaoGuardada, agora = Date.now()): boolean {
  const fim = Date.parse(sessao.expira_em);
  return !Number.isNaN(fim) && fim <= agora;
}

export function lerSessao(): SessaoGuardada | null {
  try {
    const bruto = window.sessionStorage.getItem(CHAVE_DA_SESSAO);
    if (!bruto) return null;
    const sessao = JSON.parse(bruto) as Partial<SessaoGuardada>;
    if (typeof sessao?.token !== "string" || !sessao.token || typeof sessao.expira_em !== "string") {
      apagarSessao();
      return null;
    }
    return { token: sessao.token, expira_em: sessao.expira_em };
  } catch {
    return null;
  }
}

/** A sessão em uso nesta página. É ela que os pedidos levam; o `sessionStorage` só a traz de volta
 * depois de recarregar. Trocar a senha troca o token (o servidor invalida os antigos), e o novo
 * passa a valer no próximo pedido sem a pessoa sair. */
let sessaoEmUso: SessaoGuardada | null = null;

export function sessaoAtual(): SessaoGuardada | null {
  return sessaoEmUso ?? lerSessao();
}

/** Guarda a sessão aberta pelo login ou renovada pela troca de senha. */
export function guardarSessao(sessao: SessaoGuardada) {
  sessaoEmUso = { token: sessao.token, expira_em: sessao.expira_em };
  try {
    window.sessionStorage.setItem(CHAVE_DA_SESSAO, JSON.stringify(sessaoEmUso));
  } catch {
    /* sem armazenamento: a sessão vale só enquanto a página estiver aberta */
  }
}

export function apagarSessao() {
  sessaoEmUso = null;
  try {
    window.sessionStorage.removeItem(CHAVE_DA_SESSAO);
  } catch {
    /* nada a apagar */
  }
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

/** `avisar` desligado: o 401 é resposta do próprio pedido (senha errada no login), não sessão perdida. */
async function pedir<T>(caminho: string, opcoes?: RequestInit, avisar = true): Promise<T> {
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
    if (avisar) avisarSePerdeu(resposta.status);
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

export interface FiltrosDosParceiros {
  busca?: string;
  nivel?: string[];
  acordo?: string[];
  data_tipo?: "indicacao" | "fechamento";
  data_de?: string;
  data_ate?: string;
}

export interface FiltrosDoFunil {
  captador?: string[];
  servico?: string[];
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
  // Sem aviso de erro: a versão na barra lateral não vale um alerta na tela se a API não responder.
  versao: () => pedir<VersaoDaApi>("/api/versao", undefined, false),
  login: (email: string, senha: string) =>
    pedir<SessaoAberta>("/api/acesso/login", { method: "POST", body: JSON.stringify({ email, senha }) }, false),
  /** 200 com a sessão nova (o servidor invalida os tokens antigos ao trocar a senha). */
  trocarMinhaSenha: (senhaAtual: string, senhaNova: string) =>
    pedir<SessaoAberta>("/api/acesso/senha", { method: "POST", body: JSON.stringify({ senha_atual: senhaAtual, senha_nova: senhaNova }) }),
  redefinirSenha: (id: number, senha: string) =>
    pedir<void>(`/api/acesso/usuarios/${id}/senha`, { method: "POST", body: JSON.stringify({ senha }) }),
  catalogoDeAcesso: () => pedir<MenuDoCatalogo[]>("/api/acesso/catalogo"),
  perfis: () => pedir<PerfilDeAcesso[]>("/api/acesso/perfis"),
  criarPerfil: (nome: string, permissoes: string[]) =>
    pedir<PerfilDeAcesso>("/api/acesso/perfis", { method: "POST", body: JSON.stringify({ nome, permissoes }) }),
  mudarPerfil: (id: number, mudanca: { nome?: string; permissoes?: string[] }) =>
    pedir<PerfilDeAcesso>(`/api/acesso/perfis/${id}`, { method: "PATCH", body: JSON.stringify(mudanca) }),
  usuarios: () => pedir<UsuarioDoCrm[]>("/api/acesso/usuarios"),
  /** `senha`: a provisória, obrigatória no modo senha; no modo Microsoft não vai. */
  liberarUsuario: (email: string, perfilId: number, senha?: string) =>
    pedir<UsuarioDoCrm>("/api/acesso/usuarios", {
      method: "POST",
      body: JSON.stringify(senha === undefined ? { email, perfil_id: perfilId } : { email, perfil_id: perfilId, senha }),
    }),
  mudarUsuario: (id: number, mudanca: { perfil_id?: number; ativo?: boolean }) =>
    pedir<UsuarioDoCrm>(`/api/acesso/usuarios/${id}`, { method: "PATCH", body: JSON.stringify(mudanca) }),
  historico: (filtros: { usuario?: string; tabela?: string; registro_id?: number; de?: string; ate?: string; limite?: number }) =>
    pedir<Alteracao[]>(comParametros("/api/historico", filtros)),

  verificarBackup: (arquivo: File) => enviarArquivo("/api/backup/verificar", arquivo),
  previaDaMigracao: (arquivo: File) => enviarArquivo<PreviaDaMigracao>("/api/migracao/previa", arquivo),
  migrarDoCrmLocal: (arquivo: File) =>
    enviarArquivo<{ registros: number; backup_de_antes: string }>("/api/migracao/migrar", arquivo, { "x-confirmacao": "MIGRAR" }),

  importarBackup: (arquivo: File, substituir: boolean) =>
    enviarArquivo(
      `/api/backup/importar${substituir ? "?substituir=true" : ""}`,
      arquivo,
      substituir ? { "X-Confirmacao": "SUBSTITUIR" } : {},
    ),

  /** As empresas de um grupo, cliente ou prospect, com os contatos (18/10/2026): o card da empresa a partir da lacuna. */
  empresasDoGrupo: (tipo: TipoDeContato, grupoId: number) =>
    pedir<PaginaDeContatos<EntidadeDeContato>>(comParametros("/api/contatos/empresas", { tipo, grupo_id: grupoId, limite: 500 })),

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
  mrrDaCarteira: (competencia?: string) => pedir<MrrDaCarteira>(comParametros("/api/mrr/carteira", { competencia })),
  /** `soExistentes`: só os contratos que já existiam em `de`, a conta do NRR (18/10/2026). */
  itensDoMovimento: (de: string, soExistentes = false) =>
    pedir<{ de: string; ate: string; itens: ItemDoMovimento[]; churn_anunciado?: SaidaAnunciada[] }>(
      comParametros("/api/mrr/movimento", { de, so_existentes: soExistentes ? "true" : undefined })),
  previaDeRecebimentos: (arquivo: string, conteudo_base64: string) =>
    pedir<PreviaDeRecebimentos>("/api/recebimentos/previa", { method: "POST", body: JSON.stringify({ arquivo, conteudo_base64 }) }),
  importarRecebimentos: (arquivo: string, conteudo_base64: string) =>
    pedir<ImportacaoDeRecebimentos>("/api/recebimentos/importar", { method: "POST", body: JSON.stringify({ arquivo, conteudo_base64 }) }),
  importacoesDeRecebimentos: () => pedir<ImportacaoDeRecebimentos[]>("/api/recebimentos/importacoes"),

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

  composicaoDoFunil: (indicador: IndicadorDoFunil, filtros: FiltrosDoFunil = {}, recorte?: { dimensao: DimensaoDeRecorte; chave: string }) =>
    pedir<{ indicador: string; itens: ItemDaComposicao[] }>(comParametros("/api/indicadores/composicao", {
      indicador, ...filtros, recorte: recorte?.dimensao, chave: recorte?.chave,
    })),

  recortes: (dimensao: DimensaoDeRecorte, filtros: FiltrosDoFunil = {}) =>
    pedir<LinhaDeRecorte[]>(comParametros("/api/indicadores/recortes", { dimensao, ...filtros })),

  planoDeMrr: () => pedir<PlanoDeMrr>("/api/inteligencia/plano"),
  realizadoDoPlano: () => pedir<ItemDoRealizado[]>("/api/inteligencia/plano/realizado"),
  mudarPlanoDeMrr: (premissas: PremissasDoPlano) =>
    pedir<PlanoDeMrr>("/api/inteligencia/plano", { method: "PUT", body: JSON.stringify(premissas) }),
  cenariosPorServico: () => pedir<CenariosDoServico[]>("/api/inteligencia/cenarios-de-ticket"),
  fasesDoMes: (mes?: string) => pedir<FasesDoMes>(comParametros("/api/inteligencia/fases", { mes })),
  composicaoDaFase: (mes: string, chave: string) =>
    pedir<LinhaDaFase[]>(comParametros("/api/inteligencia/fases/composicao", { mes, chave })),

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
  sugestoesDeMescla: (id: number) => pedir<SugestaoDeMescla[]>(`/api/questionarios/${id}/sugestoes`),
  previaDaMescla: (id: number, oportunidadeId: number) =>
    pedir<PreviaDaMescla>(comParametros(`/api/questionarios/${id}/mescla`, { oportunidade_id: oportunidadeId })),
  mesclarQuestionario: (id: number, corpo: { oportunidade_id: number; usar_do_questionario: string[]; excluir_duplicada: boolean }) =>
    pedir<QuestionarioResumo>(`/api/questionarios/${id}/mesclar`, { method: "POST", body: JSON.stringify(corpo) }),

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
  sugerirContextoDaReuniao: (
    oportunidadeId: number,
    pedido: { matriz: TipoDeMatriz; data: string; participantes?: string; resumo: string },
  ) =>
    pedir<SugestaoDoContexto>(`/api/oportunidades/${oportunidadeId}/proposta/reuniao-com-lead/sugestao`, {
      method: "POST", body: JSON.stringify(pedido),
    }),
  guardarReuniaoComLead: (oportunidadeId: number, reuniao: NovaReuniaoComLead) =>
    pedir<AbaDaProposta>(`/api/oportunidades/${oportunidadeId}/proposta/reuniao-com-lead`, {
      method: "POST", body: JSON.stringify(reuniao),
    }),
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
  composicaoDoPainelDoSdr: (filtros: { mes: string; origem?: string | null; chave: string }) =>
    pedir<ItemDoPainelDoSdr[]>(comParametros("/api/sdr/painel/composicao", { ...filtros })),
  painelDoSdr: (filtros: { mes: string; origem?: string }) =>
    pedir<PainelDoSdr>(comParametros("/api/sdr/painel", filtros)),

  campanhas: (mes: string) => pedir<PainelDeCampanhas>(comParametros("/api/sdr/campanhas", { mes })),

  atualizarDosAnuncios: (mes: string) =>
    pedir<LeituraDosAnuncios>(comParametros("/api/sdr/campanhas/atualizar", { mes }), { method: "POST" }),

  leadsDoMeta: () => pedir<SituacaoDosLeadsDoMeta>("/api/sdr/leads-do-meta"),

  buscarLeadsDoMeta: () => pedir<ResultadoDaBuscaDeLeads>("/api/sdr/leads-do-meta/buscar", { method: "POST" }),

  leadsDoGoogle: () => pedir<SituacaoDosLeadsDoMeta>("/api/sdr/leads-do-google"),

  buscarLeadsDoGoogle: () => pedir<ResultadoDaBuscaDeLeads>("/api/sdr/leads-do-google/buscar", { method: "POST" }),

  conversoes: (mes: string) => pedir<ResumoDasConversoes>(comParametros("/api/sdr/conversoes", { mes })),

  enviarConversoes: () => pedir<RodadaDeConversoes>("/api/sdr/conversoes/enviar", { method: "POST" }),

  midiaPorCampanha: (mes: string) =>
    pedir<InvestimentoPorCampanha[]>(comParametros("/api/sdr/midia/campanhas", { mes })),

  gravarMidiaPorCampanha: (dados: { mes: string; canal: string; campanha: string; valor: string }) =>
    pedir<InvestimentoPorCampanha>("/api/sdr/midia/campanha", { method: "PUT", body: JSON.stringify(dados) }),

  apagarMidiaPorCampanha: (id: number) => pedir<void>(`/api/sdr/midia/campanha/${id}`, { method: "DELETE" }),

  conversasDoLead: (leadId: number) =>
    pedir<ConversaDoSdr[]>(`/api/sdr/leads/${leadId}/conversas`),

  parametrosDoSdr: () => pedir<ParametrosDoSdr>("/api/sdr/parametros"),

  gravarParametrosDoSdr: (dados: Record<string, unknown>) =>
    pedir<ParametrosDoSdr>("/api/sdr/parametros", { method: "PUT", body: JSON.stringify(dados) }),

  midia: (mes: string) => pedir<InvestimentoEmMidia[]>(comParametros("/api/sdr/midia", { mes })),

  gravarMidia: (dados: { mes: string; canal: string; valor: string }) =>
    pedir<InvestimentoEmMidia>("/api/sdr/midia", { method: "PUT", body: JSON.stringify(dados) }),

  /** Um grupo pelo id (18/10/2026): o nome numa composição abre o card dele. */
  grupo: (id: number) => pedir<GrupoResumo>(`/api/grupos/${id}`),

  /** O que falta no cadastro de um grupo ou de um registro (18/10/2026). */
  lacunas: (filtro: { grupo_id?: number; cadastro?: CadastroDaLacuna; registro_id?: number }) =>
    pedir<Lacuna[]>(comParametros("/api/lacunas", filtro)),

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

  parceiros: (filtros: FiltrosDosParceiros = {}) => pedir<ParceiroResumo[]>(comParametros("/api/parceiros", { ...filtros })),
  indicadoresDosParceiros: (filtros: FiltrosDosParceiros = {}) =>
    pedir<IndicadoresDosParceiros>(comParametros("/api/parceiros/indicadores", { ...filtros })),
  composicaoDosParceiros: (indicador: IndicadorDosParceiros, filtros: FiltrosDosParceiros = {}) =>
    pedir<ItemDaComposicaoDosParceiros[]>(comParametros("/api/parceiros/indicadores/composicao", { ...filtros, indicador })),
  enderecoDaExportacaoDosParceiros: (filtros: FiltrosDosParceiros = {}) => comParametros("/api/parceiros/exportar", { ...filtros }),
  parceiro: (id: number) => pedir<ParceiroDetalhe>(`/api/parceiros/${id}`),
  criarParceiro: (dados: Partial<CadastroDoParceiro> & { nome: string }) =>
    pedir<ParceiroDetalhe>("/api/parceiros", { method: "POST", body: JSON.stringify(dados) }),
  editarParceiro: (id: number, dados: Partial<CadastroDoParceiro>) =>
    pedir<ParceiroDetalhe>(`/api/parceiros/${id}`, { method: "PATCH", body: JSON.stringify(dados) }),
  moverParceiro: (id: number, etapa: string) =>
    pedir<ParceiroDetalhe>(`/api/parceiros/${id}/etapa`, { method: "POST", body: JSON.stringify({ etapa }) }),
  buscarOportunidadesParaIndicar: (busca: string) =>
    pedir<OportunidadeParaIndicar[]>(comParametros("/api/parceiros/oportunidades", { busca })),
  ligarIndicacao: (id: number, dados: { oportunidade_id: number; recebida_em?: string | null; validada_em?: string | null }) =>
    pedir<ParceiroDetalhe>(`/api/parceiros/${id}/indicacoes`, { method: "POST", body: JSON.stringify(dados) }),
  editarIndicacao: (oportunidadeId: number, dados: { recebida_em?: string | null; validada_em?: string | null; recusada?: string | null }) =>
    pedir<ParceiroDetalhe>(`/api/parceiros/indicacoes/${oportunidadeId}`, { method: "PATCH", body: JSON.stringify(dados) }),
  desligarIndicacao: (oportunidadeId: number) =>
    pedir<ParceiroDetalhe>(`/api/parceiros/indicacoes/${oportunidadeId}/desligar`, { method: "POST" }),
  nomesDosParceiros: () => pedir<{ id: number; nome: string; tipo: string | null }[]>("/api/parceiros/nomes"),
  alertasDaIndicacao: (parceiroId: number, empresaId: number) =>
    pedir<AlertaDaIndicacao[]>(comParametros(`/api/parceiros/${parceiroId}/alertas`, { empresa_id: empresaId })),
  registrarIndicacao: (parceiroId: number, dados: IndicacaoRegistrada) =>
    pedir<ParceiroDetalhe>(`/api/parceiros/${parceiroId}/indicacoes/registrar`, { method: "POST", body: JSON.stringify(dados) }),
  relatorioDoParceiro: (parceiroId: number, mes: string) =>
    pedir<RelatorioDoParceiro>(comParametros(`/api/parceiros/${parceiroId}/relatorio`, { mes })),
  relatoriosDosParceiros: (mes: string) => pedir<RelatorioDoParceiro[]>(comParametros("/api/parceiros/relatorios", { mes })),
  conferenciaDosParceiros: () => pedir<TextoSemParceiro[]>("/api/parceiros/conferencia"),
  ligarTextoDoCanal: (texto: string, parceiroId: number) =>
    pedir<ParceiroDetalhe>("/api/parceiros/conferencia", { method: "POST", body: JSON.stringify({ texto, parceiro_id: parceiroId }) }),
  feesDosParceiros: (situacao?: string[]) => pedir<FeeDeParceiro[]>(comParametros("/api/parceiros/fees", { situacao })),
  calcularFees: () => pedir<{ novos: number }>("/api/parceiros/fees/calcular", { method: "POST" }),
  aprovarFee: (id: number, valor: string) =>
    pedir<FeeDeParceiro>(`/api/parceiros/fees/${id}/aprovar`, { method: "POST", body: JSON.stringify({ valor }) }),
  recusarFee: (id: number, motivo: string) =>
    pedir<FeeDeParceiro>(`/api/parceiros/fees/${id}/recusar`, { method: "POST", body: JSON.stringify({ motivo }) }),
  marcarFeePago: (id: number, pagoEm: string) =>
    pedir<FeeDeParceiro>(`/api/parceiros/fees/${id}/pago`, { method: "POST", body: JSON.stringify({ pago_em: pagoEm }) }),

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
  // KPIs da liderança (09/10/2026), só o Administrador
  kpisDaLideranca: (mes: string) => pedir<KpisDaLideranca>(`/api/inteligencia/kpis-lideranca?mes=${mes}`),
  baixarPendenciasDeCadastro: (corte?: "Novos" | "Passado") =>
    baixarArquivo(comParametros("/api/inteligencia/integralidade/planilha", { corte }), "pendencias-de-cadastro.xlsx"),
  propostasEmAberto: () => pedir<QuadroDePropostas>("/api/inteligencia/propostas-em-aberto"),
  baixarPropostasEmAberto: () => baixarArquivo("/api/inteligencia/propostas-em-aberto/planilha", "propostas-em-aberto.xlsx"),
  // Configurações › Integrações (07/10/2026)
  integracoes: () => pedir<Integracoes>("/api/configuracoes/integracoes"),
  salvarIntegracao: (chave: string, mudanca: { valores?: Record<string, string>; apagar?: string[] }) =>
    pedir<Integracoes>(`/api/configuracoes/integracoes/${chave}`, { method: "PUT", body: JSON.stringify(mudanca) }),
  testarIntegracao: (chave: string) =>
    pedir<ResultadoDoTeste>(`/api/configuracoes/integracoes/${chave}/testar`, { method: "POST" }),
  enviarTesteDeIntegracao: (chave: string, para: string) =>
    pedir<ResultadoDoTeste>(`/api/configuracoes/integracoes/${chave}/enviar-teste`, { method: "POST", body: JSON.stringify({ para }) }),
  cadenciaDeReunioes: () => pedir<CadenciaDeReunioes>("/api/sucesso/cadencia"),
  mudarCadenciaDeReunioes: (mudanca: { cadencia?: Record<string, string[]>; intencao?: Record<string, string> }) =>
    pedir<CadenciaDeReunioes>("/api/sucesso/cadencia", { method: "PUT", body: JSON.stringify(mudanca) }),
  reunioesDaCarteira: () => pedir<CarteiraComReunioes>("/api/sucesso/carteira"),
  registrarReuniaoDaCarteira: (reuniao: { data: string; participantes?: string; resumo?: string; correcoes_de_rota?: string }) =>
    pedir<CarteiraComReunioes>("/api/sucesso/carteira/reunioes", { method: "POST", body: JSON.stringify(reuniao) }),
  reajuste: (ano: number) => pedir<ReajusteDoAno>(`/api/reajustes?ano=${ano}`),
  aprovarReajuste: (ano: number, itens: ItemDoReajuste[], autorizador?: string) =>
    pedir<{ aplicados: number; autorizado_por: string }>("/api/reajustes/aprovar", {
      method: "POST",
      body: JSON.stringify({ ano, itens, autorizador: autorizador || null }),
    }),
  documentoDoContrato: (id: number) => pedir<DocumentoDoContrato>(`/api/contratos/${id}/documento`),
  gerarDocumentoDoContrato: (id: number, valores: Record<string, string>, geradoPor?: string) =>
    pedir<DocumentoDoContrato>(`/api/contratos/${id}/documento`, {
      method: "POST",
      body: JSON.stringify({ valores, gerado_por: geradoPor || null }),
    }),
  assinaturaDoContrato: (id: number) => pedir<AbaDaAssinatura>(`/api/contratos/${id}/assinatura`),
  enviarParaAssinatura: (id: number, envio: { nome_arquivo: string; conteudo_base64: string; prazo: string;
    signatarios: SignatarioNovo[]; enviado_por?: string }) =>
    pedir<AbaDaAssinatura>(`/api/contratos/${id}/assinatura`, {
      method: "POST",
      body: JSON.stringify({ ...envio, enviado_por: envio.enviado_por || null }),
    }),
  conferirAssinatura: (id: number) => pedir<AbaDaAssinatura>(`/api/contratos/${id}/assinatura/conferir`, { method: "POST" }),
  lembrarSignatario: (id: number, email: string) =>
    pedir<AbaDaAssinatura>(`/api/contratos/${id}/assinatura/lembrete`, { method: "POST", body: JSON.stringify({ email }) }),
  cancelarAssinatura: (id: number) => pedir<AbaDaAssinatura>(`/api/contratos/${id}/assinatura/cancelar`, { method: "POST" }),
  baixarDocumentoDoContrato: (documentoId: number) =>
    baixarArquivo(`/api/documentos-de-contrato/${documentoId}/docx`, "contrato.docx"),
  matrizDoContrato: () => pedir<MatrizDoContrato>("/api/documentos-de-contrato/matriz"),
  subirMatrizDoContrato: (arquivo: File) =>
    enviarArquivo<MatrizDeContratoResumo>(
      comParametros("/api/documentos-de-contrato/matriz", { nome_arquivo: arquivo.name }),
      arquivo,
    ),
  baixarMatrizDoContrato: (matrizId: number) =>
    baixarArquivo(`/api/documentos-de-contrato/matriz/${matrizId}/docx`, "matriz.docx"),
  configuracaoDoDocumento: () => pedir<ConfiguracaoDoDocumento>("/api/documentos-de-contrato/configuracao"),
  editarConfiguracaoDoDocumento: (c: Omit<ConfiguracaoDoDocumento, "ultimo_usado">) =>
    pedir<ConfiguracaoDoDocumento>("/api/documentos-de-contrato/configuracao", { method: "PUT", body: JSON.stringify(c) }),
  // PDF assinado e documentos antigos (18/10/2026)
  documentos: (filtro: { contrato_id?: number; oportunidade_id?: number; grupo_id?: number; origem?: "lote"; historico?: boolean }) =>
    pedir<DocumentoAnexado[]>(comParametros("/api/documentos", filtro)),
  documento: (id: number) => pedir<DocumentoComConferencia>(`/api/documentos/${id}`),
  anexarDocumento: (arquivo: File, onde: { tipo?: TipoDeDocumento; contrato_id?: number; oportunidade_id?: number }) =>
    enviarArquivo<DocumentoComConferencia>(comParametros("/api/documentos", { nome_arquivo: arquivo.name, ...onde }), arquivo),
  lerDocumentoDeNovo: (id: number) => pedir<DocumentoComConferencia>(`/api/documentos/${id}/ler`, { method: "POST" }),
  vincularDocumento: (id: number, vinculo: VinculoDoDocumento) =>
    pedir<DocumentoComConferencia>(`/api/documentos/${id}`, { method: "PATCH", body: JSON.stringify(vinculo) }),
  conferirDocumento: (id: number, campos: string[], valores: Record<string, string>, conferidoPor?: string) =>
    pedir<DocumentoComConferencia>(`/api/documentos/${id}/conferir`, {
      method: "POST",
      body: JSON.stringify({ campos, valores, conferido_por: conferidoPor || null }),
    }),
  baixarDocumentoAnexado: (id: number, nome: string) => baixarArquivo(`/api/documentos/${id}/pdf`, nome),
  servicosEContratos: () => pedir<ServicoNoContrato[]>("/api/servicos/contratos"),
  gravarServicosEContratos: (itens: { servico: string; modelo: ModeloDeContrato; reajuste: ReajusteDoServico }[]) =>
    pedir<ServicoNoContrato[]>("/api/servicos/contratos", { method: "PUT", body: JSON.stringify({ itens }) }),
  ipca: (desde?: string) => pedir<MesDoIpca[]>(`/api/ipca${desde ? `?desde=${desde}` : ""}`),
  atualizarIpca: () =>
    pedir<ReajusteDoAno["ipca"]>("/api/ipca/atualizar", { method: "POST" }),
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
