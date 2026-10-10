import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { AbaDaProposta, MatrizResumo, SugestaoDoContexto } from "../api/tipos";
import { PropostaDaOportunidade } from "./PropostaDaOportunidade";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      abaDaProposta: vi.fn(), gerarProposta: vi.fn(), marcarPropostaEnviada: vi.fn(),
      sugerirContextoDaReuniao: vi.fn(), guardarReuniaoComLead: vi.fn(),
    },
  };
});

const MATRIZ: MatrizResumo = {
  id: 1, tipo: "Contábil", nome_arquivo: "Proposta.pptx", enviada_em: "2026-10-01T10:00:00", enviada_por: "Karine",
  encontrados: 11, obrigatorios: 11, faltando: [], desconhecidos: [], utilizavel: true,
};

const ABA: AbaDaProposta = {
  matriz_sugerida: "Contábil", servicos: ["Contábil"], tem_dp: false, sugestao: null, sem_sugestao: "sem porte",
  contabil_apurado: null, colaboradores: null, valor_da_hora_de_consulta: "350.00",
  rascunho: {
    matriz: "Contábil", cliente: "Exemplo Alfa", tratamento: "Prezado(a) Sr(a). Ana Souza",
    contextualizacao: "A Exemplo Alfa busca um novo parceiro.", valor_contabil: "4500", valor_dp: null,
    horas_contabil: null, horas_dp: null, plano_bpo: null, plano_plus: null, plano_cfo: null,
  },
  perfil: {
    cnpj: "12.345.678/0001-90", regime: "Lucro Presumido", faturamento: "N/D", funcionarios: "18", movimentacao: "250",
    volume_documentos: "N/D", instituicoes: "2", meios_de_pagamento: "N/D", sistema: "N/D", segmento: "N/D",
    empresas: "1 empresa", localidade: "N/D",
  },
  imposto: "0.11", matrizes: { "Contábil": MATRIZ, Financeiro: null }, revisores: ["Eduardo"], proximo_numero: "154.2026",
  propostas: [], perfil_da_reuniao: [], reunioes_com_o_lead: [],
};

const RESUMO = "## Empresa\nDistribuidora de insumos hospitalares, matriz no Rio e filiais em Niterói e Campinas. Usa o Omie.";
const CONTEXTO = "A Exemplo Alfa distribui insumos hospitalares.\nEsta proposta foi construída…";

const SUGESTAO: SugestaoDoContexto = {
  contextualizacao: CONTEXTO,
  perfil: [
    { campo: "sistema", rotulo: "Sistema", valor: "Omie", trecho: "Usa o Omie", atual: "N/D", diverge: false },
    { campo: "regime", rotulo: "Regime", valor: "Lucro Real", trecho: null, atual: "Lucro Presumido", diverge: true },
  ],
  nao_apareceu: ["Movimentação", "Instituições"],
  para_a_carta: ["Dor: fechamento atrasado"],
  custo_usd: "0.0123",
};

const DEPOIS: AbaDaProposta = {
  ...ABA,
  perfil: { ...ABA.perfil, sistema: "Omie" },
  perfil_da_reuniao: ["sistema"],
  reunioes_com_o_lead: [{
    id: 1, data: "2026-10-08", participantes: "Ana (sócia)", link_do_granola: null, resumo_do_granola: RESUMO,
    ciencia_da_gravacao: true, contextualizacao_aplicada: true, campos_aplicados: ["sistema"], registrada_por: "Eduardo",
    registrada_em: "2026-10-10T18:00:00",
  }],
};

async function colarESugerir() {
  render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
  const resumo = await screen.findByLabelText("Resumo da nota [Potencial Cliente]");
  const botao = screen.getByRole("button", { name: "Sugerir contexto e perfil com a IA" });
  expect(botao).toBeDisabled(); // sem resumo, não há o que ler
  fireEvent.change(screen.getByLabelText("Participantes"), { target: { value: "Ana (sócia)" } });
  fireEvent.change(resumo, { target: { value: RESUMO } });
  await userEvent.click(botao);
  return screen.findByLabelText("Sugestão da IA");
}

describe("reunião com o lead na aba Proposta", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    vi.mocked(api.abaDaProposta).mockResolvedValue(ABA);
    vi.mocked(api.sugerirContextoDaReuniao).mockResolvedValue(SUGESTAO);
    vi.mocked(api.guardarReuniaoComLead).mockResolvedValue(DEPOIS);
  });

  it("sugere sem mudar a proposta: contexto lado a lado e o campo que diverge desmarcado", async () => {
    const painel = await colarESugerir();
    expect(api.sugerirContextoDaReuniao).toHaveBeenCalledWith(10, expect.objectContaining({
      matriz: "Contábil", participantes: "Ana (sócia)", resumo: RESUMO,
    }));
    expect(within(painel).getByLabelText(/Usar a sugestão da reunião/)).toBeChecked();
    expect(within(painel).getByLabelText(/Manter a atual/).closest("label")).toHaveTextContent("A Exemplo Alfa busca um novo parceiro.");
    expect(within(painel).getByLabelText("Usar Sistema da reunião")).toBeChecked();
    expect(within(painel).getByLabelText("Usar Regime da reunião")).not.toBeChecked();
    expect(within(painel).getByText("⚠ diverge")).toBeInTheDocument(); // estado com palavra, não só cor
    expect(within(painel).getByText("“Usa o Omie”")).toBeInTheDocument();
    expect(within(painel).getByText(/Movimentação, Instituições/)).toBeInTheDocument();
    // Nada aplicado ainda: a contextualização da proposta é a mesma.
    expect(screen.getByDisplayValue("A Exemplo Alfa busca um novo parceiro.")).toBeInTheDocument();
    // Sem a ciência da gravação, não aplica.
    expect(within(painel).getByRole("button", { name: "Aplicar à proposta" })).toBeDisabled();
  });

  it("aplica só o marcado, guarda a reunião e preenche a proposta", async () => {
    const painel = await colarESugerir();
    await userEvent.click(screen.getByLabelText(/O lead foi avisado de que a reunião foi gravada/));
    await userEvent.click(within(painel).getByRole("button", { name: "Aplicar à proposta" }));
    expect(api.guardarReuniaoComLead).toHaveBeenCalledWith(10, expect.objectContaining({
      resumo: RESUMO, ciencia_da_gravacao: true, contextualizacao: CONTEXTO, perfil: { sistema: "Omie" },
    }));
    expect(await screen.findByText(/Reunião guardada e aplicada à proposta/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Contextualização \(da reunião de 08\/10\/2026/)).toHaveValue(CONTEXTO);
    expect(screen.getByText("Omie").closest("dd")).toHaveTextContent("da reunião");
    expect(screen.queryByLabelText("Sugestão da IA")).not.toBeInTheDocument();
    expect(screen.getByText("✓ Reunião guardada")).toBeInTheDocument();
  });

  it("manter a atual não troca a contextualização", async () => {
    const painel = await colarESugerir();
    await userEvent.click(within(painel).getByLabelText(/Manter a atual/));
    await userEvent.click(screen.getByLabelText(/O lead foi avisado/));
    await userEvent.click(within(painel).getByRole("button", { name: "Aplicar à proposta" }));
    expect(api.guardarReuniaoComLead).toHaveBeenCalledWith(10, expect.objectContaining({ contextualizacao: null }));
  });

  it("falha da IA aparece para a pessoa", async () => {
    vi.mocked(api.sugerirContextoDaReuniao).mockRejectedValue(new ErroDaApi(502, "A Anthropic recusou a chave da API."));
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    fireEvent.change(await screen.findByLabelText("Resumo da nota [Potencial Cliente]"), { target: { value: RESUMO } });
    await userEvent.click(screen.getByRole("button", { name: "Sugerir contexto e perfil com a IA" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A Anthropic recusou a chave da API.");
  });

  it("com reunião guardada, mostra o resumo e deixa colar outra", async () => {
    vi.mocked(api.abaDaProposta).mockResolvedValue(DEPOIS);
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    expect(await screen.findByText("✓ Reunião guardada")).toBeInTheDocument();
    expect(screen.queryByLabelText("Resumo da nota [Potencial Cliente]")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ver o resumo" }));
    expect(screen.getByText(/Distribuidora de insumos hospitalares/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Colar outra reunião" }));
    expect(screen.getByLabelText("Resumo da nota [Potencial Cliente]")).toHaveValue("");
  });
});
