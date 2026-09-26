import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { CenariosDeTicket as Cenarios } from "../api/tipos";
import { CenariosDeTicket } from "./CenariosDeTicket";
import { FILTROS_VAZIOS } from "./Filtros";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { cenariosDeTicket: vi.fn() } };
});

/** Os números dos 19 contratos de 2026, validados por Eduardo em 25/09/2026. */
const DADOS: Cenarios = {
  contratos: 19, atipicos: 2, limite_do_atipico: "7350.00",
  conservador: "2450.00", base: "2956.42", otimista: "3500.00",
  atipico_minimo: "15000.00", atipico_medio: "27500.00", atipico_maximo: "40000.00",
};

describe("CenariosDeTicket", () => {
  beforeEach(() => vi.clearAllMocks());

  it("reproduz a tabela de 20 clientes com 1 atípico: R$ 61.550, 83.672 e 106.500 por mês", async () => {
    vi.mocked(api.cenariosDeTicket).mockResolvedValue(DADOS);
    render(<CenariosDeTicket filtros={FILTROS_VAZIOS} />);
    expect(await screen.findByText("Conservador")).toBeInTheDocument();
    expect(screen.getByText(/61\.550,00/)).toBeInTheDocument();
    expect(screen.getByText(/83\.67[12]/)).toBeInTheDocument();
    expect(screen.getByText(/106\.500,00/)).toBeInTheDocument();
  });

  it("a frequência do atípico é editável e muda o total", async () => {
    vi.mocked(api.cenariosDeTicket).mockResolvedValue(DADOS);
    render(<CenariosDeTicket filtros={FILTROS_VAZIOS} />);
    await screen.findByText("Conservador");
    fireEvent.change(screen.getByLabelText(/1 atípico a cada/i), { target: { value: "10" } });
    // 20 clientes, 2 atípicos: 18 × 2.450 + 2 × 15.000 = 74.100
    expect(screen.getByText(/74\.100,00/)).toBeInTheDocument();
  });

  it("diz que são hipóteses, não meta", async () => {
    vi.mocked(api.cenariosDeTicket).mockResolvedValue(DADOS);
    render(<CenariosDeTicket filtros={FILTROS_VAZIOS} />);
    expect(await screen.findByText(/hipóteses de trabalho, não meta/i)).toBeInTheDocument();
  });

  it("com menos de 4 contratos diz que não é calculável, não mostra zero", async () => {
    vi.mocked(api.cenariosDeTicket).mockResolvedValue(null);
    render(<CenariosDeTicket filtros={FILTROS_VAZIOS} />);
    expect(await screen.findByText(/não calculável/i)).toBeInTheDocument();
    expect(screen.queryByText("Conservador")).toBeNull();
  });
});
