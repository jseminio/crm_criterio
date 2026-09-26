import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { LinhaDeRecorte } from "../api/tipos";
import { FILTROS_VAZIOS } from "./Filtros";
import { Recortes } from "./Recortes";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { recortes: vi.fn() } };
});

const linha = (o: Partial<LinhaDeRecorte>): LinhaDeRecorte => ({
  chave: "BPO Contábil", propostas: 69, em_aberto: 26, aceitas: 17, decididas: 43, conversao: "39.5",
  recorrentes: 14, valor_mensal: "74770.62", ticket_medio: "5340.76", mediana: "2040.00", ...o,
});

describe("Recortes", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra propostas, conversão, ticket e mediana por serviço", async () => {
    vi.mocked(api.recortes).mockResolvedValue([linha({})]);
    render(<Recortes filtros={FILTROS_VAZIOS} />);
    expect(await screen.findByText("BPO Contábil")).toBeInTheDocument();
    expect(screen.getByText("69")).toBeInTheDocument();
    expect(screen.getByText("39,5%")).toBeInTheDocument();
    expect(screen.getByText(/5\.340,76/)).toBeInTheDocument();
    expect(screen.getByText(/2\.040,00/)).toBeInTheDocument();
    expect(api.recortes).toHaveBeenCalledWith("servico", expect.anything());
  });

  it("sem recorrente mostra traço, não zero", async () => {
    vi.mocked(api.recortes).mockResolvedValue([
      linha({ chave: "Legalização", recorrentes: 0, valor_mensal: "0", ticket_medio: null, mediana: null, conversao: null }),
    ]);
    render(<Recortes filtros={FILTROS_VAZIOS} />);
    await screen.findByText("Legalização");
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(4);
  });

  it("trocar a dimensão refaz a consulta", async () => {
    vi.mocked(api.recortes).mockResolvedValue([linha({})]);
    render(<Recortes filtros={FILTROS_VAZIOS} />);
    await screen.findByText("BPO Contábil");
    fireEvent.change(screen.getByLabelText(/cortar por/i), { target: { value: "captador" } });
    await waitFor(() => expect(api.recortes).toHaveBeenLastCalledWith("captador", expect.anything()));
  });
});
