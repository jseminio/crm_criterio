import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Eu, PlanoDeMrr } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { InteligenciaDeConversao } from "./InteligenciaDeConversao";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { planoDeMrr: vi.fn(), mudarPlanoDeMrr: vi.fn(), cenariosPorServico: vi.fn() } };
});

const cenario = (bpo: string) => ({ bpo_por_mes: bpo, ticket_contabil: "2903.28", com_contratos_previstos: true });
const linha = (mes: string, acumulado: string) => ({
  mes, contabil: "11613.12", bpo: "21000.00", escada: "0.00", churn: "2523.41", acumulado, contratos_bpo: "3", contratos_contabil: "4",
});

const PLANO: PlanoDeMrr = {
  hoje: "2026-10-04",
  premissas: {
    meta_liquida: "250000", inicio: "2026-09-01", fim: "2027-06-30", inicio_da_projecao: "2026-11-01",
    ponto_de_partida: "26000", mrr_de_partida: "252341", churn_anual_pct: "12", bpo_ticket: "7000", bpo_teto: "5",
    contabil_vagas: "4", atipico_vagas: "2", escada_prazo_meses: 3, plus_acrescimo: "3000", plus_pct: "80",
    cfo_acrescimo: "6000", cfo_pct: "30", alerta: { ...cenario("2"), com_contratos_previstos: false }, previsto: cenario("3"),
    otimista: { bpo_por_mes: "5", ticket_contabil: "5000", com_contratos_previstos: true },
    contratos_previstos: [{ descricao: "Atípico do pipeline (nov)", mes: "2026-11-01", valor: "18000", atipico: true }],
    alterado_por: null, alterado_em: null,
  },
  meta: {
    meta_liquida: "250000", realizado: "13000", previsto_ate_hoje: "26000.00", alerta_ate_hoje: "26000.00",
    situacao: { chave: "abaixo", percentual: "50.0" }, percentual_da_meta: "5.2", meses_restantes: 8, ritmo_necessario: "29625.00",
  },
  cenarios: (["alerta", "previsto", "otimista"] as const).map((nome, i) => ({
    nome, contabil: "92904.96", bpo: "168000.00", escada: "44640.00", churn: "30803.31", bruto: "356528.56",
    liquido: ["233636.22", "325725.25", "518120.88"][i], percentual_da_meta: ["93.5", "130.3", "207.2"][i],
    linhas: [linha("2026-11-01", "56089.71"), linha("2026-12-01", "86179.42")],
  })),
  realizado: [
    { mes: "2026-09-01", novo_contabil: "0", novo_bpo: "7000", escada: "3000", outros: "0", perdas: "0", acumulado: "10000", contratos_contabil: 0, contratos_bpo: 1 },
    { mes: "2026-10-01", novo_contabil: "3000", novo_bpo: "0", escada: "0", outros: "0", perdas: "0", acumulado: "13000", contratos_contabil: 1, contratos_bpo: 0 },
  ],
  motores: [
    { motor: "bpo", rotulo: "BPO Financeiro", previsto_no_plano: "168000.00", previsto_ate_hoje: "0.00", realizado: "7000", situacao: null,
      ajuste: "Faltam R$ 161.000: 2,9 contratos/mês no ticket de R$ 7.000 até o fim do prazo (teto: 5, a célula de BPO)." },
    { motor: "outros", rotulo: "Reajuste e outras expansões", previsto_no_plano: null, previsto_ate_hoje: null, realizado: "0", situacao: null,
      ajuste: "Fora do plano: entra no realizado, mas não tem previsto." },
  ],
  aviso: null,
};

const COMERCIAL: Eu = { modo: "microsoft", email: "k@x", nome: "Karine", perfil: "Comercial", administrador: false, permissoes: ["funil.ver"] };

describe("Funil › Inteligência de Conversão", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.planoDeMrr).mockResolvedValue(PLANO);
    vi.mocked(api.cenariosPorServico).mockResolvedValue([]);
  });

  it("mostra a meta líquida com a situação em palavra, o plano por motor e os três cenários", async () => {
    render(<InteligenciaDeConversao />);
    expect(await screen.findByText("Abaixo do previsto · 50,0%")).toBeInTheDocument();
    expect(screen.getByText(/ritmo necessário R\$\s29\.625,00\/mês/)).toBeInTheDocument();
    const motores = screen.getByRole("table", { name: /Por motor/ });
    expect(within(motores).getByText("BPO Financeiro")).toBeInTheDocument();
    expect(within(motores).getByText(/2,9 contratos\/mês/)).toBeInTheDocument();
    expect(within(motores).getByText("Fora do plano")).toBeInTheDocument();
    expect(screen.getByText("R$ 325.725,25")).toBeInTheDocument();
    expect(screen.getByText(/Atípico do pipeline \(nov\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar premissas" })).toBeInTheDocument();
  });

  it("quem não altera metas não vê o botão de editar", async () => {
    render(
      <ProvedorDeAcesso eu={COMERCIAL}>
        <InteligenciaDeConversao />
      </ProvedorDeAcesso>,
    );
    await screen.findByText("Abaixo do previsto · 50,0%");
    expect(screen.queryByRole("button", { name: "Editar premissas" })).not.toBeInTheDocument();
  });

  it("o Administrador edita as premissas e a tela passa a usar o plano devolvido", async () => {
    const novo = { ...PLANO, meta: { ...PLANO.meta, situacao: { chave: "no_ritmo" as const, percentual: "100.0" } } };
    vi.mocked(api.mudarPlanoDeMrr).mockResolvedValue(novo);
    render(<InteligenciaDeConversao />);
    await userEvent.click(await screen.findByRole("button", { name: "Editar premissas" }));
    const previsto = screen.getByRole("group", { name: "Cenário previsto" });
    fireEvent.change(within(previsto).getByLabelText("BPO Financeiro novos/mês"), { target: { value: "4" } });
    await userEvent.click(screen.getByRole("button", { name: "Salvar premissas" }));
    const enviado = vi.mocked(api.mudarPlanoDeMrr).mock.calls[0][0];
    expect(enviado.previsto.bpo_por_mes).toBe("4");
    expect(enviado).not.toHaveProperty("alterado_por");
    expect(await screen.findByRole("status")).toHaveTextContent("Premissas salvas");
    expect(screen.getByText("No ritmo · 100,0%")).toBeInTheDocument();
  });
});
