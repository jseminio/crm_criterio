import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { KpisDaLideranca as Kpis } from "../api/tipos";
import { KpisDaLideranca, ultimosMeses } from "./KpisDaLideranca";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { kpisDaLideranca: vi.fn() } };
});

const kpi = (chave: string, titulo: string, extra: object = {}) => ({
  chave, titulo, valor: null, unidade: "%", resumo: "", falta: [], meta: null, extras: {}, itens: [], ...extra,
});

const KPIS: Kpis = {
  mes: "2026-10", de: "2026-10-01", ate: "2026-10-09",
  kpis: [
    kpi("mrr_novo", "20 · MRR novo no mês", { valor: "12172.29", unidade: "R$", resumo: "1 contrato(s) recorrente(s)",
      itens: [{ grupo: "Mainô", detalhe: "BPO Contábil", valor: "12172.29" }] }),
    kpi("ticket", "19 · Ticket médio mensal", { valor: "12172.29", unidade: "R$",
      extras: { mes_por_grupo: "12172.29", mes_por_cnpj: "12172.29", mes_grupos: 1, mes_cnpjs: 1,
        ano_por_grupo: "5872.66", ano_mediana_por_grupo: "3141.67", ano_por_cnpj: "5220.14", ano_mediana_por_cnpj: "3629.17" } }),
    kpi("upsell", "18 · Upsell sobre o MRR", { valor: "11.9", meta: "10% do MRR do mês anterior",
      extras: { recorrente: "0.00", recorrente_pct: "0.0", nao_recorrente: "31850.00", nao_recorrente_pct: "11.9" },
      falta: ["Nenhum aditivo ou expansão registrado no mês (Contratos › eventos)"] }),
    kpi("churn", "17 · Churn de clientes", { valor: "0.0", falta: ["Os clientes perdidos em 2025, para o baseline"] }),
    kpi("cobertura", "21 · Cobertura de relacionamento", { valor: null }),
  ],
};

describe("KPIs da liderança (09/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.kpisDaLideranca).mockResolvedValue(KPIS);
  });

  it("mostra os cinco, com sem dado e o que falta", async () => {
    render(<KpisDaLideranca />);
    expect(await screen.findByText("20 · MRR novo no mês")).toBeInTheDocument();
    expect(screen.getAllByText("R$ 12.172,29").length).toBeGreaterThan(0);
    expect(screen.getByText("11,9%")).toBeInTheDocument();
    expect(screen.getByText("sem dado")).toBeInTheDocument();
    expect(screen.getByText(/Falta: Os clientes perdidos em 2025/)).toBeInTheDocument();
    expect(screen.getByText(/Não recorrente:/)).toBeInTheDocument();
    expect(screen.getByText(/No ano: por grupo/)).toBeInTheDocument();
  });

  it("troca o mês", async () => {
    render(<KpisDaLideranca />);
    await screen.findByText("20 · MRR novo no mês");
    const anterior = ultimosMeses()[1];
    await userEvent.selectOptions(screen.getByLabelText("Mês dos KPIs"), anterior.valor);
    expect(api.kpisDaLideranca).toHaveBeenLastCalledWith(anterior.valor);
  });
});
