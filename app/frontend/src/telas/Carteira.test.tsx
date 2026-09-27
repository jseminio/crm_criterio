import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ClassificacaoDaCarteira, ItemDaCarteira, PorteDoGrupo } from "../api/tipos";
import { Carteira } from "./Carteira";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      classificacaoDaCarteira: vi.fn(),
      analiseDaCarteira: vi.fn().mockResolvedValue(null),
      gerarAnaliseDaCarteira: vi.fn(),
      revisoesDaCarteira: vi.fn().mockResolvedValue([]),
      registrarRevisaoDaCarteira: vi.fn(),
      editarMesDaRevisao: vi.fn(),
    },
  };
});

const PORTE_VAZIO: PorteDoGrupo = {
  documentos_fiscais_mes: null, lancamentos_contabeis_mes: null, pagamentos_mes: null,
  contas_bancarias: null, conciliacoes_cartao_mes: null, empregados_clt: null,
  admissoes_desligamentos_mes: null, cnpjs_no_escopo: null, tomadores_de_servico: null,
  servicos_contratados_alem_do_primeiro: 0, tem_consolidacao_de_grupo: false, e_auditada: false,
  porte: null, porte_definido_por: null, porte_definido_em: null,
};
const item = (o: Partial<ItemDaCarteira> = {}): ItemDaCarteira => ({
  grupo_id: 1, grupo_nome: "Alfa", receita_mensal: "1000.00", score: "3.5270", classe: "B", classe_efetiva: "B3 (TRAVADO)",
  alerta_de_churn: "⚠", em_cobranca: true, eixo_de_acao: "Cobrança — sem tratamento preferencial", semaforo: 3, churn: 4,
  sem_contrato_ativo: false, porte: PORTE_VAZIO,
  empresas: [
    { id: 10, razao_social: "Alfa Comércio Ltda", cnpj: "11222333000181", mensalidade: "700.00" },
    { id: 11, razao_social: "Alfa Serviços SA", cnpj: null, mensalidade: null },
  ], ...o,
});
const resposta = (o: Partial<ClassificacaoDaCarteira> = {}): ClassificacaoDaCarteira => ({
  referencia: "2026-07-31", versao_dos_parametros: "v1",
  isc: { valor: "53.65", zona: "atenção", componente_classe: "59.45", componente_semaforo: "42.33", componente_churn: "59.01", receita_total: "2000.00", grupos: 2, fora_do_isc: 0 },
  retrato: { unidades: 2, receita_total: "6000.00", grupos_travados: 1, receita_travada: "1000.00", percentual_travado: "16.7" },
  por_classe: { B: 1, C: 1 },
  distribuicao_por_classe: [
    { classe: "A", minimo: 15, maximo: 20, unidades: 0, percentual: "0.0", dentro_da_meta: false },
    { classe: "B", minimo: 35, maximo: 40, unidades: 1, percentual: "50.0", dentro_da_meta: false },
    { classe: "C", minimo: 40, maximo: 50, unidades: 1, percentual: "50.0", dentro_da_meta: true },
  ],
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
    render(<Carteira listas={null} />);
    expect(await screen.findByText("53,7")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /ISC 53,7 de 100, zona atenção/ })).toBeInTheDocument();
    expect(screen.getByText(/rentabilidade vem da planilha/)).toBeInTheDocument();
    expect(screen.getByText(/B 1 · C 1, ponderado por receita/)).toBeInTheDocument();
    expect(screen.getByText("ZONA DE ATENÇÃO")).toBeInTheDocument();
  });

  it("mostra a distribuição por classe contra a meta, com texto além da cor", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText("53,7");
    expect(screen.getByText("DISTRIBUIÇÃO")).toBeInTheDocument();
    expect(screen.getByText("0 · 0,0%")).toBeInTheDocument(); // A
    expect(screen.getAllByText("1 · 50,0%")).toHaveLength(2); // B e C
    // B está fora da meta (50% contra 35–40%), C está dentro (50% contra 40–50%): o texto, não só a cor, marca a diferença.
    expect(screen.getByText("fora da meta (meta 35–40%)")).toBeInTheDocument();
    expect(screen.getByText("dentro da meta (meta 40–50%)")).toBeInTheDocument();
  });

  it("estado nunca só por cor: cobrança e alerta têm texto, e a cobrança vem primeiro", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    expect(await screen.findByText(/B3 \(TRAVADO\) · \$\$\$ cobrança/)).toBeInTheDocument();
    expect(screen.getByText("⚠ Risco de churn")).toBeInTheDocument();
    const linhas = screen.getAllByRole("row");
    expect(linhas[1]).toHaveTextContent("Alfa");
  });

  it("mostra o retrato da carteira e filtra ao clicar nos chips travados", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("16,7%")).toBeInTheDocument();
    expect(screen.getByText("1", { selector: "b" })).toBeInTheDocument();
    await userEvent.click(screen.getByText("16,7%").closest("button")!);
    expect(screen.getByLabelText("Eixo de ação")).toHaveValue("Cobrança — sem tratamento preferencial");
    expect(screen.queryByText(/▸ Beta/)).toBeNull();
  });

  it("filtra por eixo e oferece limpar quando nada passa", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    await userEvent.selectOptions(screen.getByLabelText("Eixo de ação"), "Sem urgência de churn");
    expect(screen.queryByText(/▸ Alfa/)).toBeNull();
    expect(screen.getByText(/▸ Beta/)).toBeInTheDocument();
  });

  it("explica como o ISC é calculado, recolhido por padrão", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    expect(await screen.findByText("Como é calculado")).toBeInTheDocument();
    expect(screen.getByText(/Classe × 33% \+ Semáforo × 33% \+ Churn × 34%/)).toBeInTheDocument();
  });

  it("as empresas do grupo ficam ocultas e abrem no +", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
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
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    expect(screen.queryByRole("button", { name: /empresas de Alfa/ })).toBeNull();
  });

  it("traz a legenda do eixo de ação, com os cinco eixos e o que cada um significa", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    const legenda = (await screen.findByText(/Legenda do eixo de ação/)).closest("details")!;
    for (const nome of ["Cobrança — sem tratamento preferencial", "Reter já (crítico)", "Reter / vigiar", "Saída organizada", "Sem urgência de churn"])
      expect(legenda).toHaveTextContent(nome);
    expect(legenda).toHaveTextContent(/Adimplência ≤ 2/);
    expect(legenda).toHaveTextContent(/vale o primeiro que se aplica/);
  });

  it("a coluna Eixo de ação remete à legenda no rodapé", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    expect(await screen.findByText("Legenda do Eixo de Ação no rodapé")).toBeInTheDocument();
  });

  it("marca o grupo sem contrato ativo", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ itens: [item({ sem_contrato_ativo: true })] }));
    render(<Carteira listas={null} />);
    expect(await screen.findByText(/sem contrato ativo hoje/)).toBeInTheDocument();
  });

  it("vazio sem dados explica como carregar", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ itens: [], isc: null, avisos: [] }));
    render(<Carteira listas={null} />);
    expect(await screen.findByText(/Nenhuma classificação carregada/)).toBeInTheDocument();
  });

  it("erro oferece tentar de novo", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockRejectedValue(new Error("falhou"));
    render(<Carteira listas={null} />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /tentar de novo/i })).toBeInTheDocument();
  });
});
