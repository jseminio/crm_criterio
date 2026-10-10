import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Eu, FasesDoMes, PlanoDeMrr } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { InteligenciaDeConversao } from "./InteligenciaDeConversao";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { planoDeMrr: vi.fn(), mudarPlanoDeMrr: vi.fn(), cenariosPorServico: vi.fn(), fasesDoMes: vi.fn(), kpisDaLideranca: vi.fn(),
    composicaoDaFase: vi.fn(), realizadoDoPlano: vi.fn() } };
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

const indicador = (rotulo: string, unidade: "numero" | "pct" | "reais" | "horas" | "dias", previsto: string | null, realizado: string | null, nota: string | null = null) =>
  ({ rotulo, unidade, previsto, realizado, nota });

const FASES: FasesDoMes = {
  mes: "2026-11-01",
  meses: ["2026-09-01", "2026-10-01", "2026-11-01", "2026-12-01"],
  mes_fechado: false,
  tem_previsto: true,
  cadeia: [
    { chave: "leads_icp", rotulo: "Leads no ICP", previsto: "60.0", realizado: "54", taxa_prevista: "40", taxa_realizada: "31.5" },
    { chave: "reunioes", rotulo: "Reuniões", previsto: "24.0", realizado: "17", taxa_prevista: "83", taxa_realizada: "94.1" },
    { chave: "propostas", rotulo: "Propostas", previsto: "20.0", realizado: "16", taxa_prevista: "30", taxa_realizada: "31.3" },
    { chave: "contratos", rotulo: "Contratos", previsto: "6", realizado: "5", taxa_prevista: null, taxa_realizada: null },
    { chave: "mrr_novo", rotulo: "MRR novo", previsto: "47403.28", realizado: "43100", taxa_prevista: null, taxa_realizada: null },
  ],
  gargalo: "reunioes",
  gargalo_texto: "Gargalo: reuniões, com 70,8% do previsto no mês.",
  fases: [
    { chave: "atracao", titulo: "Atração", pergunta: "Trazemos gente certa em volume?", kpi: { ...indicador("Leads no ICP no mês", "numero", "60.0", "54"), chave: "leads_icp", explicacao: "Leads criados no mês, menos os fora do ICP." },
      apoio: [indicador("% dos leads dentro do ICP", "pct", "55", "46")], situacao: { chave: "atencao", percentual: "90.0" },
      ajuste: "Faltaram 6 leads no ICP para o previsto do mês." },
    { chave: "engajamento", titulo: "Engajamento", pergunta: "A promessa bate com o 1º contato?",
      kpi: indicador("Aderência da promessa", "pct", null, null, "ainda não medida: falta o campo no primeiro contato"),
      apoio: [indicador("Lead no ICP → reunião", "pct", "40", "31.5"), indicador("Tempo até o 1º contato (mediana)", "horas", "24", "31")],
      situacao: { chave: "abaixo", percentual: "78.8" }, ajuste: "Só 31,5% dos leads no ICP chegaram a reunião." },
    { chave: "conversao", titulo: "Conversão", pergunta: "Fechamos no ritmo e no preço?", kpi: indicador("Contratos no mês", "numero", "6", "5"),
      apoio: [indicador("Ticket contábil normal", "reais", "2903.28", "4100.00")], situacao: { chave: "abaixo", percentual: "83.3" },
      ajuste: "Faltou 1 BPO Financeiro (−R$ 7.000)." },
    { chave: "pos_venda", titulo: "Pós-venda", pergunta: "O cliente fica, cresce e indica?", kpi: indicador("NRR do mês", "pct", "99.0", "99.4"),
      apoio: [indicador("Reuniões de resultado em dia", "pct", "100", "92.0")], situacao: { chave: "no_ritmo", percentual: "100.4" },
      ajuste: "Nenhum ajuste no número." },
  ],
  taxas: { lead_reuniao: { valor: "40", origem: "premissa" }, reuniao_proposta: { valor: "83", origem: "historico" }, conversao: { valor: null, origem: "sem_dado" } },
  aviso: null,
};

const COMERCIAL: Eu = { modo: "microsoft", email: "k@x", nome: "Karine", perfil: "Comercial", administrador: false, permissoes: ["funil.ver"] };

describe("Funil › Inteligência de Conversão", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.planoDeMrr).mockResolvedValue(PLANO);
    vi.mocked(api.cenariosPorServico).mockResolvedValue([]);
    vi.mocked(api.fasesDoMes).mockResolvedValue(FASES);
    vi.mocked(api.kpisDaLideranca).mockResolvedValue({ mes: "2026-10", de: "2026-10-01", ate: "2026-10-09", kpis: [] });
  });

  it("quatro fases: explicação ao passar o mouse e 'ver' com a lista que compõe o número (10/10/2026)", async () => {
    vi.mocked(api.composicaoDaFase).mockResolvedValue([
      { titulo: "Clínica Sorriso", detalhe: "Google", data: "2026-11-03", valor: null, entra: true },
    ]);
    render(<InteligenciaDeConversao />);
    const janela = await screen.findByText("Leads criados no mês, menos os fora do ICP.");
    expect(janela).toHaveAttribute("role", "tooltip");
    fireEvent.click(screen.getByRole("button", { name: "Ver composição: Leads no ICP no mês" }));
    const painel = await screen.findByRole("dialog", { name: "Leads no ICP no mês" });
    expect(await within(painel).findByText("Clínica Sorriso")).toBeInTheDocument();
    expect(api.composicaoDaFase).toHaveBeenCalledWith("2026-11-01", "leads_icp");
  });

  it("os KPIs da liderança aparecem só para o Administrador (09/10/2026)", async () => {
    const { unmount } = render(<InteligenciaDeConversao />);  // sem login: a máquina do CRM é Administrador
    expect(await screen.findByRole("heading", { name: "KPIs da liderança" })).toBeInTheDocument();
    unmount();
    render(<ProvedorDeAcesso eu={COMERCIAL}><InteligenciaDeConversao /></ProvedorDeAcesso>);
    await screen.findByText("Plano de MRR");
    expect(screen.queryByRole("heading", { name: "KPIs da liderança" })).not.toBeInTheDocument();
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
    await userEvent.click(screen.getByRole("tab", { name: "Cenários" }));
    const previsto = screen.getByRole("group", { name: "Previsto" });
    fireEvent.change(within(previsto).getByLabelText("BPO Fin. novos/mês"), { target: { value: "4" } });
    await userEvent.click(screen.getByRole("tab", { name: "Meta" }));
    await userEvent.click(screen.getByRole("tab", { name: "Cenários" }));
    expect(within(screen.getByRole("group", { name: "Previsto" })).getByLabelText("BPO Fin. novos/mês")).toHaveValue(4);
    await userEvent.click(screen.getByRole("button", { name: "Salvar premissas" }));
    const enviado = vi.mocked(api.mudarPlanoDeMrr).mock.calls[0][0];
    expect(enviado.previsto.bpo_por_mes).toBe("4");
    expect(enviado).not.toHaveProperty("alterado_por");
    expect(await screen.findByRole("status")).toHaveTextContent("Premissas salvas");
    expect(screen.getByText("No ritmo · 100,0%")).toBeInTheDocument();
  });

  it("mostra a cadeia com o gargalo em palavra e os quatro cartões com o ajuste", async () => {
    render(<InteligenciaDeConversao />);
    expect(await screen.findByText("Gargalo: reuniões, com 70,8% do previsto no mês.")).toBeInTheDocument();
    expect(screen.getByText("Reuniões · gargalo")).toBeInTheDocument();
    const engajamento = screen.getByRole("region", { name: "2 · Engajamento" });
    expect(within(engajamento).getByText("ainda não medida: falta o campo no primeiro contato")).toBeInTheDocument();
    expect(within(engajamento).getByText(/Abaixo do previsto · gargalo/)).toBeInTheDocument();
    expect(within(engajamento).getByText("31 h")).toBeInTheDocument();
    const conversao = screen.getByRole("region", { name: "3 · Conversão" });
    expect(within(conversao).getByText(/Faltou 1 BPO Financeiro/)).toBeInTheDocument();
    expect(within(conversao).getByText("R$ 4.100,00")).toBeInTheDocument();
    expect(screen.getByText(/conversão — \(sem dado\)/)).toBeInTheDocument();
  });

  it("troca o mês e busca as fases dele", async () => {
    render(<InteligenciaDeConversao />);
    const mes = await screen.findByLabelText("Mês");
    await userEvent.selectOptions(mes, "2026-12-01");
    expect(api.fasesDoMes).toHaveBeenLastCalledWith("2026-12-01");
  });

  it("o painel de premissas tem seis abas e marca a aba com campo a corrigir", async () => {
    render(<InteligenciaDeConversao />);
    await userEvent.click(await screen.findByRole("button", { name: "Editar premissas" }));
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(
      expect.arrayContaining(["Meta", "Motores", "Escada", "Cenários", "Quatro fases", "Contratos previstos"]),
    );
    expect(screen.getByRole("tab", { name: "Meta" })).toHaveAttribute("aria-selected", "true");
    await userEvent.click(screen.getByRole("tab", { name: "Contratos previstos" }));
    await userEvent.click(screen.getByRole("button", { name: "Acrescentar contrato previsto" }));
    expect(screen.getByRole("tab", { name: /Contratos previstos.*2 campos a corrigir/ })).toBeInTheDocument();
    expect(screen.getByText("Descreva o contrato")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar premissas" })).toBeDisabled();
    expect(screen.getByText(/Corrija 2 campos/)).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Tirar do plano" }).at(-1)!);
    expect(screen.getByRole("button", { name: "Salvar premissas" })).toBeEnabled();
  });
});
