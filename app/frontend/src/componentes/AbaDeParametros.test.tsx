import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { Parametros } from "../api/tipos";
import { AbaDeParametros } from "./AbaDeParametros";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { parametrosAtuais: vi.fn(), editarParametros: vi.fn() } };
});

const MIX_POR_PORTE: Record<string, Record<string, string>> = {
  Micro: { "Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.02", "Analista Sênior": "0.47", "Analista Pleno": "0.50", "Analista Júnior": "0" },
  Pequeno: { "Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.02", "Analista Sênior": "0.47", "Analista Pleno": "0.50", "Analista Júnior": "0" },
  Médio: { "Sócio Sênior": "0", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.08", "Analista Sênior": "0.30", "Analista Pleno": "0.51", "Analista Júnior": "0.10" },
  Grande: { "Sócio Sênior": "0.01", "Sócio Júnior/Gerente": "0.01", "Supervisor/Especialista": "0.09", "Analista Sênior": "0.30", "Analista Pleno": "0.43", "Analista Júnior": "0.16" },
  "Extra Grande": { "Sócio Sênior": "0.02", "Sócio Júnior/Gerente": "0.05", "Supervisor/Especialista": "0.13", "Analista Sênior": "0.30", "Analista Pleno": "0.30", "Analista Júnior": "0.20" },
};

function parametros(o: Partial<Parametros> = {}): Parametros {
  return {
    id: 1, criado_em: "2026-09-28T08:02:29-03:00", autor: "Migração automática", motivo: "Semente inicial",
    peso_receita: "0.20", peso_rentabilidade: "0.25", peso_cross_sell: "0.12", peso_complexidade: "0.12",
    peso_disciplina: "0.09", peso_risco: "0.07", peso_adimplencia: "0.15",
    corte_a: "3.95", corte_b: "3.35", trava_de_adimplencia: 2, churn_alto: 4,
    imposto: "0.11", teto_de_atrito: "1.5",
    atrito_nota_1: "0", atrito_nota_2: "0.05", atrito_nota_3: "0.10", atrito_nota_4: "0.30", atrito_nota_5: "0.50",
    corte_margem_2: "0.30", corte_margem_3: "0.45", corte_margem_4: "0.60", corte_margem_5: "0.70",
    horas_micro: 5, horas_pequeno: 10, horas_medio: 16, horas_grande: 40, horas_extra_grande: 80,
    taxa_socio_senior: "93.75", taxa_socio_junior: "106.25", taxa_supervisor: "75.00",
    taxa_analista_senior: "50.00", taxa_analista_pleno: "31.25", taxa_analista_junior: "18.75",
    mix: Object.entries(MIX_POR_PORTE).flatMap(([porte, cargos]) =>
      Object.entries(cargos).map(([cargo, mix_percentual]) => ({ porte, cargo, mix_percentual }))),
    custo_hora: { Micro: "41.6875", Pequeno: "41.6875", Médio: "39.875", Grande: "40.1875", "Extra Grande": "45.0625" },
    ...o,
  };
}

describe("AbaDeParametros", () => {
  beforeEach(() => vi.clearAllMocks());

  it("carrega e mostra os pesos e o custo/hora calculado por Porte", async () => {
    vi.mocked(api.parametrosAtuais).mockResolvedValue(parametros());
    render(<AbaDeParametros />);
    expect(await screen.findByRole("tab", { name: "Pesos do Score" })).toBeInTheDocument();
    expect(screen.getByLabelText("Receita")).toHaveValue(20);
    expect(screen.getByLabelText("Rentabilidade")).toHaveValue(25);
    await userEvent.click(screen.getByRole("tab", { name: "Matriz por Porte" }));
    expect(screen.getAllByText("R$ 41,69").length).toBeGreaterThan(0); // Micro e Pequeno
    expect(screen.getByText("R$ 45,06")).toBeInTheDocument(); // Extra Grande
  });

  it("mostra o erro quando ainda não há parâmetros gravados", async () => {
    vi.mocked(api.parametrosAtuais).mockRejectedValue(new ErroDaApi(409, "ainda não há parâmetros"));
    render(<AbaDeParametros />);
    expect(await screen.findByText("ainda não há parâmetros")).toBeInTheDocument();
  });

  it("pesos que não somam 100% avisam e desabilitam salvar", async () => {
    vi.mocked(api.parametrosAtuais).mockResolvedValue(parametros());
    render(<AbaDeParametros />);
    await screen.findByLabelText("Receita");
    await userEvent.type(screen.getByLabelText("Quem está alterando"), "Eduardo Luiz");
    await userEvent.type(screen.getByLabelText("Motivo da mudança"), "teste");
    await userEvent.clear(screen.getByLabelText("Receita"));
    await userEvent.type(screen.getByLabelText("Receita"), "30");
    expect(screen.getByText(/soma 110%/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Salvar nova versão/ })).toBeDisabled();
  });

  it("salva e grava a versão nova com autor e motivo", async () => {
    vi.mocked(api.parametrosAtuais).mockResolvedValue(parametros());
    vi.mocked(api.editarParametros).mockResolvedValue(parametros({ id: 2, autor: "Eduardo Luiz" }));
    render(<AbaDeParametros />);
    await screen.findByLabelText("Receita");
    await userEvent.type(screen.getByLabelText("Quem está alterando"), "Eduardo Luiz");
    await userEvent.type(screen.getByLabelText("Motivo da mudança"), "ajuste de taxa");
    await userEvent.click(screen.getByRole("button", { name: /Salvar nova versão/ }));
    expect(api.editarParametros).toHaveBeenCalledWith(expect.objectContaining({
      autor: "Eduardo Luiz", motivo: "ajuste de taxa", mix: expect.arrayContaining([
        expect.objectContaining({ porte: "Micro", cargo: "Analista Pleno", mix_percentual: 0.5 }),
      ]),
    }));
    expect(await screen.findByText("Nova versão salva.")).toBeInTheDocument();
  });

  it("mix que não soma 100% num Porte é sinalizado", async () => {
    const p = parametros();
    p.mix = p.mix.map((c) => (c.porte === "Grande" && c.cargo === "Analista Júnior" ? { ...c, mix_percentual: "0.50" } : c));
    vi.mocked(api.parametrosAtuais).mockResolvedValue(p);
    render(<AbaDeParametros />);
    await screen.findByLabelText("Receita");
    await userEvent.type(screen.getByLabelText("Quem está alterando"), "Eduardo Luiz");
    await userEvent.type(screen.getByLabelText("Motivo da mudança"), "teste");
    expect(screen.getByRole("button", { name: /Salvar nova versão/ })).toBeDisabled();
  });
});
