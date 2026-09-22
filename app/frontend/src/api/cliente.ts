/** O acesso à API. Um lugar só, para o erro ter uma forma só. */

import type {
  ColunaDoFunil,
  Execucao,
  ExecucaoDetalhe,
  GrupoResumo,
  Indicadores,
  LeadResumo,
  Listas,
  Ocorrencia,
  OportunidadeDetalhe,
  OportunidadeResumo,
  Pagina,
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

export const api = {
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

  fundirGrupos: (principalId: number, absorvidoId: number) =>
    pedir<GrupoResumo>(`/api/grupos/${principalId}/fundir`, {
      method: "POST",
      body: JSON.stringify({ absorvido_id: absorvidoId }),
    }),
};
