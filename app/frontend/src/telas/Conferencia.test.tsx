import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Execucao, Ocorrencia } from "../api/tipos";
import { Conferencia } from "./Conferencia";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: { cargas: vi.fn(), carga: vi.fn(), ocorrencias: vi.fn(), oportunidade: vi.fn(() => new Promise(() => {})) },
  };
});

const execucao = (o: Partial<Execucao> = {}): Execucao => ({
  id: 2, executada_em: "2026-09-21T17:29:00", arquivo: "planilha.xlsx", lidas: 436, de_outro_ano: 279, residuais: 0,
  importadas: 157, criadas: 0, atualizadas: 0, inalteradas: 153, gravadas: 153, ignoradas_incompletas: 3,
  ignoradas_duplicatas: 1, grupos_criados: 0, grupos_reaproveitados: 0, pendencias: 4, ajustes: 0, mudancas: 0, ...o,
});
const ocorrencia = (o: Partial<Ocorrencia>): Ocorrencia => ({
  id: 1, tipo: "Precisa de você", linha: 282, campo: "data de aceite", texto: "aceita sem data — Eduardo preencherá no CRM", ...o,
});
const OCORRENCIAS: Ocorrencia[] = [
  ocorrencia({ id: 1, linha: 282, oportunidade_id: 10, oportunidade_nome: "Alfa BPO", grupo_nome: "Grupo Alfa", data_aceite: null }),
  ocorrencia({ id: 2, linha: 283, oportunidade_id: 11, oportunidade_nome: "Beta Folha", grupo_nome: "Grupo Beta", data_aceite: "2026-03-12" }),
  ocorrencia({ id: 3, linha: 284, oportunidade_id: 12, oportunidade_nome: "Gama BPO", grupo_nome: "Grupo Gama", data_aceite: null }),
  ocorrencia({ id: 4, linha: 301, campo: "situação", texto: "situação vazia", oportunidade_id: null }),
];

function montar(cargas: Execucao[], itens: Ocorrencia[] = OCORRENCIAS) {
  vi.mocked(api.cargas).mockResolvedValue(cargas);
  vi.mocked(api.carga).mockImplementation(async (id) => ({ ...cargas.find((c) => c.id === id)!, por_campo: [] }));
  vi.mocked(api.ocorrencias).mockResolvedValue({ total: itens.length, itens });
  render(<Conferencia listas={null} />);
}

describe("Conferência: o nome de cada linha", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra a oportunidade e o grupo de cada linha, e o que já foi resolvido no CRM", async () => {
    montar([execucao()]);
    const alfa = (await screen.findByRole("button", { name: "Alfa BPO" })).closest("tr")!;
    expect(alfa).toHaveTextContent("Grupo Alfa");
    expect(alfa).toHaveTextContent("· falta preencher");
    expect(screen.getByRole("button", { name: "Beta Folha" }).closest("tr")).toHaveTextContent("✓ preenchida: 12/03/2026");
    expect(screen.getByText("1 já preenchida no CRM, 2 faltam.")).toBeInTheDocument();
    expect(screen.getByText("linha sem oportunidade no CRM").closest("tr")).toHaveTextContent("situação vazia");
  });

  it("o nome abre a oportunidade para preencher a data", async () => {
    montar([execucao()]);
    await userEvent.click(await screen.findByRole("button", { name: "Gama BPO" }));
    expect(api.oportunidade).toHaveBeenCalledWith(12);
  });

  it("em rodada antiga explica por que não há nomes", async () => {
    montar([execucao({ id: 3 }), execucao({ id: 2 })], OCORRENCIAS.map((o) => ({ ...o, oportunidade_id: null, oportunidade_nome: null })));
    await screen.findByText(/4 ocorrências/);
    await userEvent.selectOptions(screen.getByLabelText("Rodada da carga"), "2");
    expect(await screen.findByText(/Rodada antiga: o nome de cada linha só aparece na carga mais recente/)).toBeInTheDocument();
    expect(screen.queryByText("linha sem oportunidade no CRM")).toBeNull();
  });

  it("sem a lista inteira na tela, não conta preenchidas", async () => {
    vi.mocked(api.cargas).mockResolvedValue([execucao()]);
    vi.mocked(api.carga).mockResolvedValue({ ...execucao(), por_campo: [] });
    vi.mocked(api.ocorrencias).mockResolvedValue({ total: 500, itens: OCORRENCIAS });
    render(<Conferencia listas={null} />);
    await screen.findByText(/Mostrando as primeiras 4 de 500/);
    expect(screen.queryByText(/já preenchida/)).toBeNull();
  });
});
