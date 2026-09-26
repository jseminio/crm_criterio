/** O acesso à API. Um lugar só, para o erro ter uma forma só. */

import type {
  AbordagemDetalhe,
  AbordagemResumo,
  Agenda,
  EnderecoDeContato,
  FusaoFeita,
  EntidadeDeContato,
  PaginaDeContatos,
  PessoaComOrigem,
  PessoaDeContato,
  TipoDeContato,
  Mrr,
  CenariosDeTicket,
  ColunaDoFunil,
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
} from "./tipos";

export class ErroDaApi extends Error {
  readonly status: number;

  constructor(status: number, mensagem: string) {
    super(mensagem);
    this.status = status;
  }
}

async function pedir<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, {
      ...opcoes,
      headers: { "Content-Type": "application/json", ...opcoes?.headers },
    });
  } catch {
    // Distinguir "servidor fora do ar" de "servidor recusou" importa: a
    // primeira se resolve subindo a API, a segunda não.
    throw new ErroDaApi(0, "Não consegui falar com o servidor. Ele está no ar?");
  }

  if (!resposta.ok) {
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (typeof corpo?.detail === "string") detalhe = corpo.detail;
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

/** O arquivo de backup vai cru no corpo, não em JSON. */
async function enviarArquivo(caminho: string, arquivo: File, cabecalhos: Record<string, string> = {}) {
  let resposta: Response;
  try {
    resposta = await fetch(caminho, { method: "POST", body: arquivo, headers: cabecalhos });
  } catch {
    throw new ErroDaApi(0, "Não consegui falar com o servidor. Ele está no ar?");
  }
  if (!resposta.ok) {
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (typeof corpo?.detail === "string") detalhe = corpo.detail;
    } catch {
      /* sem JSON */
    }
    throw new ErroDaApi(resposta.status, detalhe);
  }
  return (await resposta.json()) as ResumoDeBackup;
}

export const api = {
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

  criarEmpresaDoGrupo: (grupoId: number, dados: Record<string, unknown> = {}) =>
    pedir<{ id: number; razao_social: string; cnpj: string | null }>(`/api/grupos/${grupoId}/empresas`, {
      method: "POST",
      body: JSON.stringify(dados),
    }),

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

  cenariosDeTicket: (filtros: FiltrosDoFunil = {}) =>
    pedir<CenariosDeTicket | null>(comParametros("/api/indicadores/cenarios-de-ticket", { ...filtros })),

  oportunidades: (filtros: FiltrosDoFunil & { situacao?: string[]; grupo_id?: number } = {}) =>
    pedir<Pagina<OportunidadeResumo>>(
      comParametros("/api/oportunidades", { ...filtros, limite: 1000 }),
    ),

  oportunidade: (id: number) => pedir<OportunidadeDetalhe>(`/api/oportunidades/${id}`),

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

  leads: (filtros: { apenas_abertos?: boolean; busca?: string } = {}) =>
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

  grupos: (filtros: { busca?: string; limite?: number; incluir_fundidos?: boolean } = {}) =>
    pedir<Pagina<GrupoResumo>>(comParametros("/api/grupos", { limite: 500, ...filtros })),

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
