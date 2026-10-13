import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Eu, LinhaDoReajuste, ReajusteDoAno } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { ReajusteAnual } from "./ReajusteAnual";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { reajuste: vi.fn(), aprovarReajuste: vi.fn(), ipca: vi.fn(), atualizarIpca: vi.fn() } };
});

const EDUARDO: Eu = {
  modo: "microsoft", email: "eduardo@grupocriterio.com.br", nome: "Eduardo Luiz", perfil: "Administrador",
  administrador: true, permissoes: [],
};
const KARINE: Eu = { ...EDUARDO, email: "karine@grupocriterio.com.br", nome: "Karine", perfil: "Contratos", administrador: false, permissoes: ["contratos.ver"] };

const linha = (o: Partial<LinhaDoReajuste>): LinhaDoReajuste => ({
  contrato_id: 1, grupo: "Cliente A", empresa: null, escopo: "BPO Financeiro", recorrente: true, situacao: "Reajustar",
  observacao: null, base: "2026-07-01", base_presumida: false, de: "2026-07-01", ate: "2027-06-01", meses: 12,
  ipca: "4.2000", meses_faltando: [], preco_mensal: "7000.00", preco_anual: "91000.00", mensal_sugerido: "7294.00",
  anual_sugerido: "94822.00", adiado_para: null, aprovavel: true, reajustado: null, ...o,
});

const tabela = (o: Partial<ReajusteDoAno> = {}): ReajusteDoAno => ({
  ano: 2027,
  ipca: { ultimo_mes: "2027-06-01", buscado_em: "2027-07-11T12:00:00+00:00", aviso: null },
  ipca_completo: true,
  linhas: [
    linha({}),
    linha({ contrato_id: 2, grupo: "Cliente B", de: "2026-01-01", meses: 18, ipca: "6.1000", preco_mensal: "5000.00",
      preco_anual: null, mensal_sugerido: "5305.00", anual_sugerido: null }),
    linha({ contrato_id: 3, grupo: "Cliente C", situacao: "Adiado", de: null, ate: null, meses: 4, ipca: null,
      adiado_para: 2028, aprovavel: false, mensal_sugerido: null, anual_sugerido: null }),
    linha({ contrato_id: 4, grupo: "Cliente D", situacao: "Você decide", recorrente: false, preco_mensal: null,
      preco_anual: "60000.00", mensal_sugerido: null, anual_sugerido: "63180.00", observacao: "Não recorrente com mais de 12 meses." }),
  ],
  ...o,
});

function abrir(eu = EDUARDO) {
  return render(
    <ProvedorDeAcesso eu={eu}>
      <ReajusteAnual />
    </ProvedorDeAcesso>,
  );
}

describe("Reajuste anual (13/10/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra os números, o adiado para o ano seguinte e marca só o 'Reajustar'", async () => {
    vi.mocked(api.reajuste).mockResolvedValue(tabela());
    abrir();
    const tabelaNaTela = await screen.findByRole("table", { name: /reajuste de julho/i });
    expect(within(tabelaNaTela).getByText("fica para jul/2028")).toBeInTheDocument();
    expect(within(tabelaNaTela).getByText("jan/26 a jun/27")).toBeInTheDocument();
    expect(screen.getByLabelText("Aprovar o reajuste de Cliente A")).toBeChecked();
    expect(screen.getByLabelText("Aprovar o reajuste de Cliente D")).not.toBeChecked();
    expect(screen.queryByLabelText("Aprovar o reajuste de Cliente C")).toBeNull();
  });

  it("aprova com o valor alterado à mão e o anual acompanhando as parcelas", async () => {
    vi.mocked(api.reajuste).mockResolvedValue(tabela());
    vi.mocked(api.aprovarReajuste).mockResolvedValue({ aplicados: 2, autorizado_por: "Eduardo Luiz" });
    abrir();
    const campo = await screen.findByLabelText("Valor reajustado de Cliente A");
    await userEvent.clear(campo);
    await userEvent.type(campo, "7.300,00");
    await userEvent.click(screen.getByRole("button", { name: "Aprovar selecionados" }));
    await userEvent.click(screen.getByRole("button", { name: /confirmar 2 reajustes/i }));
    expect(api.aprovarReajuste).toHaveBeenCalledWith(2027, [
      { contrato_id: 1, preco_mensal_novo: "7300.00", preco_anual_novo: "94900.00" },
      { contrato_id: 2, preco_mensal_novo: "5305.00", preco_anual_novo: null },
    ], undefined);
    expect(await screen.findByText(/2 reajustes aplicados, autorizados por Eduardo Luiz/)).toBeInTheDocument();
  });

  it("sem junho publicado é prévia e não deixa aprovar", async () => {
    vi.mocked(api.reajuste).mockResolvedValue(tabela({
      ipca_completo: false,
      linhas: [linha({ meses_faltando: ["2027-06-01"], aprovavel: false })],
    }));
    abrir();
    expect(await screen.findByText(/os valores abaixo são\s+prévia/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aprovar selecionados" })).toBeNull();
    expect(screen.getByText(/falta jun\/2027/)).toBeInTheDocument();
  });

  it("quem só vê contratos vê a tabela, sem aprovar", async () => {
    vi.mocked(api.reajuste).mockResolvedValue(tabela());
    abrir(KARINE);
    await screen.findByRole("table", { name: /reajuste de julho/i });
    expect(screen.queryByRole("button", { name: "Aprovar selecionados" })).toBeNull();
    expect(screen.queryByLabelText("Valor reajustado de Cliente A")).toBeNull();
  });
});
