import { fireEvent, render, screen, within } from "@testing-library/react";
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
  chave, titulo, valor: null, unidade: "%", resumo: "", falta: [], meta: null, extras: {}, itens: [],
  explicacao: `Como se calcula o ${titulo}`, ...extra,
});

const KPIS: Kpis = {
  mes: "2026-10", de: "2026-10-01", ate: "2026-10-09",
  kpis: [
    kpi("mrr_novo", "MRR novo no mês", { valor: "12172.29", unidade: "R$", resumo: "1 contrato(s) recorrente(s)",
      itens: [{ grupo: "Mainô", detalhe: "BPO Contábil", valor: "12172.29", entra: true }] }),
    kpi("ticket", "Ticket médio mensal", { valor: "12172.29", unidade: "R$",
      extras: { mes_por_grupo: "12172.29", mes_por_cnpj: "12172.29", mes_grupos: 1, mes_cnpjs: 1,
        ano_por_grupo: "5872.66", ano_mediana_por_grupo: "3141.67", ano_por_cnpj: "5220.14", ano_mediana_por_cnpj: "3629.17" } }),
    kpi("upsell", "Upsell sobre o MRR", { valor: "11.9", meta: "10% do MRR do mês anterior",
      extras: { recorrente: "0.00", recorrente_pct: "0.0", nao_recorrente: "31850.00", nao_recorrente_pct: "11.9" },
      falta: ["Nenhum aditivo ou expansão registrado no mês (Contratos › eventos)"] }),
    kpi("churn", "Churn da base no ano", { valor: "10.0", falta: ["Os clientes perdidos em 2025, para o baseline"],
      resumo: "Base de 31/12/2025 · no mês: 1 grupo(s) · R$ 4.875,00/mês",
      extras: { grupos: 2, grupos_perdidos: 1, grupos_perdidos_no_mes: 1, mrr_de_partida: "79916.67", mrr_perdido: "4875.00",
        faturamento_pct: "6.1", mrr_perdido_no_mes: "4875.00" },
      itens: [
        { grupo: "IMND", detalhe: "anunciou em 08/10/2026 · sai em 30/11/2026 · no mês", valor: "4875.00", entra: true,
          secao: "Base de 31/12/2025 que saiu em 2026" },
        { grupo: "Inbel", detalhe: "na base de 31/12/2025", valor: "75041.67", entra: false, secao: "Os demais clientes da base" },
      ] }),
    kpi("churn_novos", "Churn de quem entrou em 2026", { valor: "11.1", resumo: "Entraram em 2026 · no mês: 0 grupo(s) · R$ 0,00/mês",
      extras: { grupos: 9, grupos_perdidos: 1, grupos_perdidos_no_mes: 0, mrr_de_partida: "59900.00", mrr_perdido: "7458.33",
        faturamento_pct: "12.5", tempo_medio_meses: "1.3" },
      itens: [{ grupo: "SENTIRE", detalhe: "entrou em 05/2026 · anunciou em 14/08/2026 · sai em 13/10/2026", valor: "7458.33",
        entra: true, secao: "Entraram e saíram em 2026" }] }),
    kpi("cobertura", "Cobertura de relacionamento", { valor: null }),
  ],
};

describe("KPIs da liderança (09/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.kpisDaLideranca).mockResolvedValue(KPIS);
  });

  it("mostra os seis, com sem dado e o que falta", async () => {
    render(<KpisDaLideranca />);
    expect(await screen.findByText("MRR novo no mês")).toBeInTheDocument();
    expect(screen.getAllByText("R$ 12.172,29").length).toBeGreaterThan(0);
    expect(screen.getByText("11,9%")).toBeInTheDocument();
    expect(screen.getByText("sem dado")).toBeInTheDocument();
    expect(screen.getByText(/Falta: Os clientes perdidos em 2025/)).toBeInTheDocument();
    expect(screen.getByText(/Não recorrente:/)).toBeInTheDocument();
    expect(screen.getByText(/No ano: por grupo/)).toBeInTheDocument();
  });

  it("o churn mostra, no mesmo card, grupos e faturamento, da base e de quem entrou no ano (13/10/2026)", async () => {
    render(<KpisDaLideranca />);
    const churn = (await screen.findByText("Churn da base no ano")).closest("section")!;
    const [grupos, faturamento] = Array.from(churn.querySelectorAll(".ind-valores-item"));
    expect(grupos).toHaveTextContent("Por grupos10,0%1 de 2 grupos");
    expect(faturamento).toHaveTextContent("Por faturamento6,1%R$ 4.875,00 de R$ 79.916,67/mês");
    const novos = screen.getByText("Churn de quem entrou em 2026").closest("section")!;
    expect(within(novos).getByText("11,1%")).toBeInTheDocument();
    expect(within(novos).getByText("12,5%")).toBeInTheDocument();
    expect(within(novos).getByText(/Tempo médio como cliente: 1,3 meses/)).toBeInTheDocument();
  });

  it("nenhum indicador tem número na frente do nome", async () => {
    render(<KpisDaLideranca />);
    await screen.findByText("MRR novo no mês");
    const titulos = Array.from(document.querySelectorAll(".ind-rotulo")).map((t) => t.textContent);
    expect(titulos.every((t) => !/^\d/.test(t ?? ""))).toBe(true);
  });

  it("cada KPI tem a explicação ao passar o mouse, no padrão dos indicadores", async () => {
    render(<KpisDaLideranca />);
    const card = (await screen.findByText("MRR novo no mês")).closest("section")!;
    const janela = document.getElementById(card.getAttribute("aria-describedby")!)!;
    expect(janela).toHaveAttribute("role", "tooltip");
    expect(janela).toHaveTextContent("Como se calcula o MRR novo no mês");
  });

  it("Ver composição abre a lista com o total do card; o churn mostra a base à parte", async () => {
    render(<KpisDaLideranca />);
    const card = (await screen.findByText("MRR novo no mês")).closest("section")!;
    fireEvent.click(within(card).getByRole("button", { name: "Ver composição (1)" }));
    const painel = await screen.findByRole("dialog", { name: "MRR novo no mês" });
    expect(within(painel).getByText("Mainô")).toBeInTheDocument();
    expect(within(painel).getAllByText("R$ 12.172,29").length).toBeGreaterThan(1);
    fireEvent.keyDown(window, { key: "Escape" });
    const churn = screen.getByText("Churn da base no ano").closest("section")!;
    fireEvent.click(within(churn).getByRole("button", { name: /Ver composição/ }));
    const p2 = await screen.findByRole("dialog", { name: "Churn da base no ano" });
    expect(within(p2).getByText("Base de 31/12/2025 que saiu em 2026 (1)")).toBeInTheDocument();
    expect(within(p2).getByText(/Os demais clientes da base \(1\)/)).toBeInTheDocument();
    expect(within(p2).getByText("IMND")).toBeInTheDocument();
    expect(within(p2).getAllByText("R$ 4.875,00").length).toBe(2);  // a linha e o total da seção que entra
  });

  it("troca o mês", async () => {
    render(<KpisDaLideranca />);
    await screen.findByText("MRR novo no mês");
    const anterior = ultimosMeses()[1];
    await userEvent.selectOptions(screen.getByLabelText("Mês dos KPIs"), anterior.valor);
    expect(api.kpisDaLideranca).toHaveBeenLastCalledWith(anterior.valor);
  });
});
