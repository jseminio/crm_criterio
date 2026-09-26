import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ClassificacaoDaCarteira, ItemDaCarteira } from "../api/tipos";
import { Carteira } from "./Carteira";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { classificacaoDaCarteira: vi.fn() } };
});

const item = (o: Partial<ItemDaCarteira> = {}): ItemDaCarteira => ({
  grupo_id: 1, grupo_nome: "Alfa", receita_mensal: "1000.00", score: "3.5270", classe: "B", classe_efetiva: "B3 (TRAVADO)",
  alerta_de_churn: "⚠", em_cobranca: true, eixo_de_acao: "Cobrança — sem tratamento preferencial", semaforo: 3, churn: 4,
  sem_contrato_ativo: false,
  empresas: [
    { id: 10, razao_social: "Alfa Comércio Ltda", cnpj: "11222333000181", mensalidade: "700.00" },
    { id: 11, razao_social: "Alfa Serviços SA", cnpj: null, mensalidade: null },
  ], ...o,
});
const resposta = (o: Partial<ClassificacaoDaCarteira> = {}): ClassificacaoDaCarteira => ({
  referencia: "2026-07-31", versao_dos_parametros: "v1",
  isc: { valor: "53.65", zona: "atenção", componente_classe: "59.45", componente_semaforo: "42.33", componente_churn: "59.01", receita_total: "2000.00", grupos: 2, fora_do_isc: 0 },
  por_classe: { B: 1, C: 1 },
  itens: [
    item(),
    item({ grupo_id: 2, grupo_nome: "Beta", classe: "C", classe_efetiva: "C1", em_cobranca: false, alerta_de_churn: null, eixo_de_acao: "Sem urgência de churn", churn: 1, receita_mensal: "5000.00" }),
  ],
  avisos: ["A nota de rentabilidade vem da planilha."], ...o,
});

describe("Carteira", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra o ISC com a zona escrita, os avisos e a distribuição", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira />);
    expect(await screen.findByText("53,7")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /ISC 53,7 de 100, zona atenção/ })).toBeInTheDocument();
    expect(screen.getByText(/rentabilidade vem da planilha/)).toBeInTheDocument();
    expect(screen.getByText(/B 1 · C 1, ponderado por receita/)).toBeInTheDocument();
    expect(screen.getByText("ZONA DE ATENÇÃO")).toBeInTheDocument();
  });

  it("estado nunca só por cor: cobrança e alerta têm texto, e a cobrança vem primeiro", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira />);
    expect(await screen.findByText(/B3 \(TRAVADO\) · \$\$\$ cobrança/)).toBeInTheDocument();
    expect(screen.getByText("⚠ Risco de churn")).toBeInTheDocument();
    const linhas = screen.getAllByRole("row");
    expect(linhas[1]).toHaveTextContent("Alfa");
  });

  it("filtra por eixo e oferece limpar quando nada passa", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira />);
    await screen.findByText(/▸ Alfa/);
    await userEvent.selectOptions(screen.getByLabelText("Eixo de ação"), "Sem urgência de churn");
    expect(screen.queryByText(/▸ Alfa/)).toBeNull();
    expect(screen.getByText(/▸ Beta/)).toBeInTheDocument();
  });

  it("explica como o ISC é calculado, recolhido por padrão", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira />);
    expect(await screen.findByText("Como é calculado")).toBeInTheDocument();
    expect(screen.getByText(/Classe × 33% \+ Semáforo × 33% \+ Churn × 34%/)).toBeInTheDocument();
  });

  it("as empresas do grupo ficam ocultas e abrem no +", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira />);
    await screen.findByText(/▸ Alfa/);
    expect(screen.queryByText(/Alfa Comércio Ltda/)).toBeNull();
    const botao = screen.getByRole("button", { name: "Mostrar as empresas de Alfa" });
    expect(botao).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(botao);
    expect(screen.getByText(/Alfa Comércio Ltda/)).toBeInTheDocument();
    expect(screen.getByText(/11\.222\.333\/0001-81/)).toBeInTheDocument();
    expect(screen.getByText("R$ 700,00")).toBeInTheDocument();
    const aberto = screen.getByRole("button", { name: "Ocultar as empresas de Alfa" });
    expect(aberto).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(aberto);
    expect(screen.queryByText(/Alfa Comércio Ltda/)).toBeNull();
  });

  it("grupo sem empresas não tem o +", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ itens: [item({ empresas: [] })] }));
    render(<Carteira />);
    await screen.findByText(/▸ Alfa/);
    expect(screen.queryByRole("button", { name: /empresas de Alfa/ })).toBeNull();
  });

  it("traz a legenda do eixo de ação, com os cinco eixos e o que cada um significa", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira />);
    const legenda = (await screen.findByText(/Legenda do eixo de ação/)).closest("details")!;
    for (const nome of ["Cobrança — sem tratamento preferencial", "Reter já (crítico)", "Reter / vigiar", "Saída organizada", "Sem urgência de churn"])
      expect(legenda).toHaveTextContent(nome);
    expect(legenda).toHaveTextContent(/Adimplência ≤ 2/);
    expect(legenda).toHaveTextContent(/vale o primeiro que se aplica/);
  });

  it("marca o grupo sem contrato ativo", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ itens: [item({ sem_contrato_ativo: true })] }));
    render(<Carteira />);
    expect(await screen.findByText(/sem contrato ativo hoje/)).toBeInTheDocument();
  });

  it("vazio sem dados explica como carregar", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ itens: [], isc: null, avisos: [] }));
    render(<Carteira />);
    expect(await screen.findByText(/Nenhuma classificação carregada/)).toBeInTheDocument();
  });

  it("erro oferece tentar de novo", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockRejectedValue(new Error("falhou"));
    render(<Carteira />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /tentar de novo/i })).toBeInTheDocument();
  });
});
