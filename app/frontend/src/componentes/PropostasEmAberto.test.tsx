import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { QuadroDePropostas } from "../api/tipos";
import { PropostasEmAberto, quadroEmTexto } from "./PropostasEmAberto";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { propostasEmAberto: vi.fn(), baixarPropostasEmAberto: vi.fn() } };
});

const linha = (etapa: string, quantas: number, o: Partial<QuadroDePropostas["total"]> = {}) => ({
  etapa, quantas, anual: "0", mensalizado: "0", recorrente: "0", pontual: "0", quente: "0", morno: "0", frio: "0",
  sem_classificacao: "0", ...o,
});
const proposta = (id: number, etapa: string, o = {}) => ({
  id, grupo: `Grupo ${id}`, nome: "BPO", servico: "BPO Contábil", etapa, temperatura: "Frio", captador: "EL",
  anual: "15600.00", mensalizado: "1300.00", recorrente: true, em_on_hold_desde: null, on_hold_pela_originacao: false,
  dias_em_on_hold: null, ...o,
});

const QUADRO: QuadroDePropostas = {
  hoje: "2026-10-14",
  linhas: [
    linha("Em avaliação pela empresa", 1, { anual: "78000.00", mensalizado: "6500.00", recorrente: "6500.00", quente: "6500.00" }),
    linha("On hold", 1, { anual: "15600.00", mensalizado: "1300.00", recorrente: "1300.00", frio: "1300.00" }),
    linha("Enviar proposta", 0),
  ],
  total: linha("Total em aberto", 2, { anual: "93600.00", mensalizado: "7800.00", recorrente: "7800.00", quente: "6500.00", frio: "1300.00" }),
  conversao_do_ano: { rotulo: "Conversão · 2026", aceitas: 41, decididas: 107, percentual: "38.3" },
  conversao_12_meses: { rotulo: "Conversão · últ. 12 meses", aceitas: 41, decididas: 107, percentual: "38.3" },
  enviadas_no_mes: 1, enviadas_no_mes_em_aberto: "78000.00", mes_das_enviadas: "10/2026",
  on_hold_antigas: 1, on_hold_antigas_mensalizado: "1300.00",
  resumo: ["Do mensalizado em aberto (R$ 7.800,00/mês), R$ 6.500,00 está quente (83,3%)."],
  propostas: [
    proposta(1, "Em avaliação pela empresa", { temperatura: "Quente", anual: "78000.00", mensalizado: "6500.00" }),
    proposta(2, "On hold", { em_on_hold_desde: "2026-03-01", on_hold_pela_originacao: true, dias_em_on_hold: 227 }),
  ],
};

describe("Propostas em aberto · visão gerencial (14/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.propostasEmAberto).mockResolvedValue(QUADRO);
  });

  it("mostra o quadro por etapa, com a temperatura e o total", async () => {
    render(<PropostasEmAberto />);
    const total = (await screen.findByText("Total em aberto")).closest("tr")!;
    expect(total).toHaveTextContent("R$ 93.600,00");
    expect(total).toHaveTextContent("R$ 7.800,00");
    const enviar = screen.getByText("Enviar proposta").closest("tr")!;
    expect(within(enviar).getAllByText("—").length).toBe(5);  // zero vira traço; o mensalizado mostra R$ 0,00
    expect(screen.getAllByText("38,3%", { selector: ".ind-valor" })).toHaveLength(2);
    expect(screen.getByText(/O que o quadro mostra/).closest("[role=note]")).toHaveTextContent("83,3%");
  });

  it("On hold há mais de 60 dias abre a lista com a data de entrada", async () => {
    render(<PropostasEmAberto />);
    const card = (await screen.findByText("On hold há mais de 60 dias")).closest("section")!;
    fireEvent.click(within(card).getByRole("button", { name: /Ver composição/ }));
    const painel = await screen.findByRole("dialog", { name: "On hold há mais de 60 dias" });
    expect(within(painel).getByText(/01\/03\/2026 · 227 dias/)).toBeInTheDocument();
    expect(within(painel).getByText("(pela originação)")).toBeInTheDocument();
  });

  it("copia o quadro em texto e baixa a planilha", async () => {
    const escrever = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText: escrever } });
    render(<PropostasEmAberto />);
    fireEvent.click(await screen.findByRole("button", { name: "Copiar para enviar" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Quadro copiado");
    expect(escrever).toHaveBeenCalledWith(quadroEmTexto(QUADRO));
    fireEvent.click(screen.getByRole("button", { name: "Baixar planilha" }));
    expect(api.baixarPropostasEmAberto).toHaveBeenCalledOnce();
  });

  it("o texto leva as linhas, a conversão, as enviadas, o On hold antigo e o resumo", () => {
    const t = quadroEmTexto(QUADRO).replace(/\u00a0/g, " ");
    expect(t).toContain("Propostas em aberto · visão gerencial · 14/10/2026");
    expect(t).toContain("Total em aberto: 2 · R$ 93.600,00 ao ano · R$ 7.800,00/mês");
    expect(t).toContain("Conversão · 2026: 38,3% (41 aceitas / 107 decididas)");
    expect(t).toContain("On hold há mais de 60 dias: 1 · R$ 1.300,00/mês");
    expect(t).toContain("- Do mensalizado em aberto");
  });
});
