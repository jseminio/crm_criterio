import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Mrr } from "../api/tipos";
import { inicioDoPeriodo, Receita } from "./Receita";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { mrr: vi.fn() } };
});

const AVISO = "Só entram os contratos registrados no CRM. A carteira anterior ainda não foi carregada.";

const mrr = (o: Partial<Mrr> = {}, mov: Partial<Mrr["movimento"]> = {}, atual: Partial<Mrr["atual"]> = {}): Mrr => ({
  atual: { valor: "0.00", contratos: 0, suspenso_valor: "0.00", suspenso_contratos: 0, sem_preco_mensal: 0, grupos: 0, ticket_por_grupo: null, mediana_por_grupo: null, ...atual },
  movimento: {
    de: "2026-09-01", ate: "2026-09-25", mrr_inicio: "0.00", novo: "0.00", expansao: "0.00", reajuste: "0.00",
    contracao: "0.00", churn_cliente: "0.00", churn_criterio: "0.00", churn: "0.00", mrr_fim: "0.00",
    variacao: "0.00", nrr: null, grr: null, ...mov,
  },
  contratos_registrados: 0, contratos_da_carteira_anterior: 0, cobertura_completa: false, aviso: AVISO, ...o,
});

describe("Receita (MRR)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sempre avisa que o MRR é parcial, mesmo com valor", async () => {
    vi.mocked(api.mrr).mockResolvedValue(mrr({ contratos_registrados: 2 }, {}, { valor: "9000.00", contratos: 2 }));
    render(<Receita />);
    expect(await screen.findByText(/MRR parcial/)).toBeInTheDocument();
    expect(screen.getByText(/carteira anterior ainda não foi carregada/)).toBeInTheDocument();
    expect(screen.getByText(/2 contratos ativos/)).toBeInTheDocument();
  });

  it("mostra o ticket médio por grupo com a mediana ao lado", async () => {
    vi.mocked(api.mrr).mockResolvedValue(
      mrr({ contratos_registrados: 58 }, {}, { valor: "225141.20", contratos: 57, grupos: 30, ticket_por_grupo: "7504.71", mediana_por_grupo: "3481.42" }),
    );
    render(<Receita />);
    expect(await screen.findByText(/7\.504,71/)).toBeInTheDocument();
    expect(screen.getByText(/3\.481,42/)).toBeInTheDocument();
    expect(screen.getByText(/30 grupos/)).toBeInTheDocument();
    expect(screen.getByText(/não é venda nova/i)).toBeInTheDocument();
  });

  it("sem contrato ativo não mostra ticket, em vez de zero", async () => {
    vi.mocked(api.mrr).mockResolvedValue(mrr());
    render(<Receita />);
    await screen.findByText(/MRR parcial/);
    expect(screen.queryByText(/ticket médio por grupo/i)).toBeNull();
  });

  it("com a carteira carregada o aviso deixa de dizer 'parcial' e pede para conferir a fonte", async () => {
    vi.mocked(api.mrr).mockResolvedValue(mrr({ cobertura_completa: true, contratos_da_carteira_anterior: 58, aviso: "Inclui a carteira anterior ao CRM." }));
    render(<Receita />);
    expect(await screen.findByText("Confira a fonte.")).toBeInTheDocument();
    expect(screen.queryByText(/MRR parcial/)).toBeNull();
  });

  it("sem contrato nenhum, diz que ainda não há, não só mostra zero", async () => {
    vi.mocked(api.mrr).mockResolvedValue(mrr());
    render(<Receita />);
    expect(await screen.findByText(/nenhum contrato registrado ainda/i)).toBeInTheDocument();
  });

  it("NRR e GRR sem base dizem não calculável, nunca 0%", async () => {
    vi.mocked(api.mrr).mockResolvedValue(mrr());
    render(<Receita />);
    await screen.findByText(/MRR parcial/);
    const linha = screen.getByText("NRR").closest("p")!;
    expect(linha).toHaveTextContent(/NRR não calculável/);
    expect(linha).toHaveTextContent(/GRR não calculável/);
    expect(linha).not.toHaveTextContent("0,0%");
  });

  it("mostra o movimento com churn separado por quem decidiu", async () => {
    vi.mocked(api.mrr).mockResolvedValue(
      mrr({ contratos_registrados: 3 },
        { mrr_inicio: "4000.00", churn_cliente: "1000.00", churn_criterio: "500.00", churn: "1500.00", mrr_fim: "2500.00", nrr: "62.5", grr: "62.5" },
        { valor: "2500.00", contratos: 1 }),
    );
    render(<Receita />);
    expect(await screen.findByText(/decidido pelo cliente/)).toBeInTheDocument();
    expect(screen.getByText(/decidida pela Critério/)).toBeInTheDocument();
    expect(screen.getByText(/− R\$\s*1\.000,00/)).toBeInTheDocument();
    expect(screen.getByText(/− R\$\s*500,00/)).toBeInTheDocument();
    const linha = screen.getByText("NRR").closest("p")!;
    expect(linha).toHaveTextContent(/NRR\s*62,5%/);
    expect(linha).toHaveTextContent(/GRR\s*62,5%/);
  });

  it("avisa de contrato sem preço mensal que ficou de fora e de suspenso à parte", async () => {
    vi.mocked(api.mrr).mockResolvedValue(mrr({ contratos_registrados: 3 }, {}, { valor: "1000.00", contratos: 1, sem_preco_mensal: 1, suspenso_valor: "500.00", suspenso_contratos: 1 }));
    render(<Receita />);
    expect(await screen.findByText(/sem preço mensal ficou de fora/)).toBeInTheDocument();
    expect(screen.getByText(/1 suspenso/)).toBeInTheDocument();
  });

  it("trocar o período refaz a consulta com o novo início", async () => {
    vi.mocked(api.mrr).mockResolvedValue(mrr());
    render(<Receita />);
    await screen.findByText(/MRR parcial/);
    fireEvent.change(screen.getByLabelText("Período"), { target: { value: "ano" } });
    await waitFor(() => expect(api.mrr).toHaveBeenLastCalledWith(inicioDoPeriodo("ano")));
  });
});

describe("inicioDoPeriodo", () => {
  const hoje = new Date(2026, 8, 25); // 25/09/2026
  it("mês: dia 1 do mês", () => expect(inicioDoPeriodo("mes", hoje)).toBe("2026-09-01"));
  it("trimestre: dia 1 de dois meses antes", () => expect(inicioDoPeriodo("trimestre", hoje)).toBe("2026-07-01"));
  it("ano: 1º de janeiro", () => expect(inicioDoPeriodo("ano", hoje)).toBe("2026-01-01"));
  it("trimestre cruza o ano sem quebrar", () => expect(inicioDoPeriodo("trimestre", new Date(2026, 0, 10))).toBe("2025-11-01"));
});
