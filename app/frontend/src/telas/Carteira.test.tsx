import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type {
  ClassificacaoDaCarteira, ClienteNovo, ItemDaCarteira, NotasDoGrupo, Parametros, PeriodoDeAvaliacao, PorteDoGrupo, RentabilidadeDoGrupo,
} from "../api/tipos";
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
      parametrosAtuais: vi.fn(),
      editarParametros: vi.fn(),
      abrirPeriodo: vi.fn(),
      calcularCarteira: vi.fn(),
      editarJanela: vi.fn(),
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
const NOTAS_VAZIO: NotasDoGrupo = {
  receita: "3.00", rentabilidade: "3.00", rentabilidade_planilha: "3.00", complexidade: "3.00", disciplina: "3.00", risco: "3.00",
  cross_sell: "3.00", adimplencia: "3.00", semaforo: 1, churn: 1, rentabilidade_da_planilha: false,
  atribuido_por: null, motivo: null, registrado_em: "2026-07-31T00:00:00",
};
const item = (o: Partial<ItemDaCarteira> = {}): ItemDaCarteira => ({
  grupo_id: 1, grupo_nome: "Alfa", receita_mensal: "1000.00", score: "3.5270", classe: "B", classe_efetiva: "B3 (TRAVADO)",
  alerta_de_churn: "⚠", em_cobranca: true, eixo_de_acao: "Cobrança — sem tratamento preferencial", semaforo: 3, churn: 4,
  sem_contrato_ativo: false, notas: NOTAS_VAZIO, porte: PORTE_VAZIO,
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

const parametros = (o: Partial<Parametros> = {}): Parametros => ({
  id: 1, criado_em: "2026-09-28T08:02:29-03:00", autor: "Eduardo Luiz", motivo: "Semente inicial",
  peso_receita: "0.20", peso_rentabilidade: "0.25", peso_cross_sell: "0.12", peso_complexidade: "0.12",
  peso_disciplina: "0.09", peso_risco: "0.07", peso_adimplencia: "0.15",
  corte_a: "3.95", corte_b: "3.35", trava_de_adimplencia: 2, churn_alto: 4,
  imposto: "0.11", teto_de_atrito: "1.5",
  atrito_nota_1: "0", atrito_nota_2: "0.05", atrito_nota_3: "0.10", atrito_nota_4: "0.30", atrito_nota_5: "0.50",
  corte_margem_2: "0.30", corte_margem_3: "0.45", corte_margem_4: "0.60", corte_margem_5: "0.70",
  horas_micro: 5, horas_pequeno: 10, horas_medio: 16, horas_grande: 40, horas_extra_grande: 80,
  taxa_socio_senior: "93.75", taxa_socio_junior: "106.25", taxa_supervisor: "75.00",
  taxa_analista_senior: "50.00", taxa_analista_pleno: "31.25", taxa_analista_junior: "18.75",
  mix: [], custo_hora: {}, ...o,
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

  it("mostra a rentabilidade logo depois do Score, e ordena por ela", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      itens: [
        item({ grupo_id: 1, grupo_nome: "Alfa", notas: { ...NOTAS_VAZIO, rentabilidade: "5.00", rentabilidade_planilha: "2.50" } }),
        item({
          grupo_id: 2, grupo_nome: "Beta", classe: "C", classe_efetiva: "C1", em_cobranca: false,
          alerta_de_churn: null, eixo_de_acao: "Sem urgência de churn", churn: 1, receita_mensal: "5000.00",
          notas: { ...NOTAS_VAZIO, rentabilidade: "1.00", rentabilidade_planilha: "4.80" },
        }),
      ],
    }));
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);

    const titulos = screen.getAllByRole("columnheader").map((th) => th.textContent?.trim() ?? "");
    const iScore = titulos.findIndex((t) => t.startsWith("Score"));
    const iRentabilidade = titulos.findIndex((t) => t.startsWith("Rentabilidade"));
    const iClasse = titulos.findIndex((t) => t.startsWith("Classe"));
    expect(iScore).toBeGreaterThanOrEqual(0);
    expect(iRentabilidade).toBe(iScore + 1);
    expect(iClasse).toBe(iRentabilidade + 1);

    expect(screen.getByText("2,50")).toBeInTheDocument();
    expect(screen.getByText("4,80")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /^Rentabilidade/ }));
    const linhas = screen.getAllByRole("row");
    expect(linhas[1]).toHaveTextContent("Alfa"); // crescente: 2,50 (Alfa) antes de 4,80 (Beta)
  });

  it("estado nunca só por cor: cobrança e alerta têm texto, e a cobrança vem primeiro", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    expect(await screen.findByText(/B3 \(TRAVADO\) · \$\$\$ cobrança/)).toBeInTheDocument();
    expect(screen.getByText("⚠ Risco de churn")).toBeInTheDocument();
    const linhas = screen.getAllByRole("row");
    expect(linhas[1]).toHaveTextContent("Alfa");
  });

  it("a receita do retrato abre a lista dos grupos com o total, e o ISC explica o cálculo (10/10/2026)", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    expect(screen.getByText(/ponderada pela receita, com os pesos dos Parâmetros/)).toHaveAttribute("role", "tooltip");
    fireEvent.click(screen.getByRole("button", { name: "Ver composição: Receita mensal recorrente" }));
    const painel = await screen.findByRole("dialog", { name: "Receita mensal recorrente" });
    expect(within(painel).getByText(/Total · 2 grupos/)).toBeInTheDocument();
  });

  it("mostra o retrato com o travado e o percentual juntos num só chip, e filtra ao clicar", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    expect(screen.getByText("unidades (grupos + individuais)").closest(".retrato-chip")!.querySelector("b")).toHaveTextContent("2");
    const chipTravado = screen.getByRole("button", { name: /grupos inadimplentes, 16,7% da receita travada/ });
    expect(chipTravado).toHaveTextContent("1"); // grupos_travados
    const rolou = vi.spyOn(Element.prototype, "scrollIntoView");
    await userEvent.click(chipTravado);
    expect(screen.getByLabelText("Eixo de ação")).toHaveValue("Cobrança — sem tratamento preferencial");
    expect(screen.queryByText(/▸ Beta/)).toBeNull();
    // Sem isto o filtro aplica fora da tela: a pessoa clica e parece que nada aconteceu.
    expect(rolou).toHaveBeenCalled();
    // Filtra pro grupo consolidado — não abre as empresas sozinho.
    expect(screen.queryByText(/Alfa Comércio Ltda/)).toBeNull();
  });

  it("chip de inadimplentes indica com aria-pressed quando está ativo, e desliga ao clicar de novo", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    const chipTravado = screen.getByRole("button", { name: /grupos inadimplentes/ });
    expect(chipTravado).toHaveAttribute("aria-pressed", "false");

    await userEvent.click(chipTravado);
    expect(chipTravado).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByText(/▸ Beta/)).toBeNull();

    await userEvent.click(chipTravado);
    expect(chipTravado).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText(/▸ Beta/)).toBeInTheDocument();
  });

  it("mostra os três semáforos com a contagem, e filtra a lista ao clicar", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    await screen.findByText(/▸ Beta/);

    const botao3 = screen.getByRole("button", { name: /^Semáforo 3/ });
    expect(botao3).toHaveTextContent("2"); // Alfa e Beta são semáforo 3
    expect(screen.getByRole("button", { name: /^Semáforo 1/ })).toHaveTextContent("0");

    const rolou = vi.spyOn(Element.prototype, "scrollIntoView");
    await userEvent.click(botao3);
    expect(botao3).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText(/▸ Alfa/)).toBeInTheDocument();
    expect(screen.getByText(/▸ Beta/)).toBeInTheDocument();
    // Mesma correção do chip de inadimplentes: leva até a lista, não só filtra.
    expect(rolou).toHaveBeenCalled();

    // clicar de novo no mesmo semáforo desliga o filtro
    await userEvent.click(botao3);
    expect(botao3).toHaveAttribute("aria-pressed", "false");
  });

  it("chip de inadimplentes e semáforo não se somam: um clique desliga o outro", async () => {
    // Alfa é o único em_cobranca, e está no semáforo 3; Gama é semáforo 1 mas não é inadimplente.
    // Se os dois filtros se somassem (E), inadimplentes + semáforo 1 não bateria em ninguém —
    // era exatamente o "às vezes some" relatado.
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(
      resposta({ itens: [item(), item({ grupo_id: 3, grupo_nome: "Gama", em_cobranca: false, semaforo: 1, eixo_de_acao: "Sem urgência de churn" })] }),
    );
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);

    await userEvent.click(screen.getByRole("button", { name: /grupos inadimplentes/ }));
    expect(screen.getByText(/▸ Alfa/)).toBeInTheDocument();
    expect(screen.queryByText(/▸ Gama/)).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: /^Semáforo 1/ }));
    // O chip desligou sozinho: aparece Gama (semáforo 1), não fica vazio.
    expect(await screen.findByText(/▸ Gama/)).toBeInTheDocument();
    expect(screen.queryByText(/▸ Alfa/)).toBeNull();
    expect(screen.getByLabelText("Eixo de ação")).toHaveValue("");

    await userEvent.click(screen.getByRole("button", { name: /grupos inadimplentes/ }));
    // E o inverso: religar o chip desliga o semáforo.
    expect(screen.getByRole("button", { name: /^Semáforo 1/ })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText(/▸ Alfa/)).toBeInTheDocument();
    expect(screen.queryByText(/▸ Gama/)).toBeNull();
  });

  it("semáforo sem nenhum grupo filtra para uma lista vazia, com o botão de limpar", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    await userEvent.click(screen.getByRole("button", { name: /^Semáforo 1/ }));
    expect(await screen.findByText(/nenhum resultado/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));
    expect(await screen.findByText(/▸ Alfa/)).toBeInTheDocument();
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

  it("oferece exportar o histórico para Excel", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    const link = await screen.findByRole("link", { name: "Exportar para conferência" });
    expect(link).toHaveAttribute("href", "/api/carteira/exportar");
  });

  it("os parâmetros de cálculo ficam uma vez só, ao lado da exportação — não por grupo", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    vi.mocked(api.parametrosAtuais).mockResolvedValue(parametros());
    render(<Carteira listas={null} />);
    await screen.findByRole("link", { name: "Exportar para conferência" });
    // recolhido por padrão — não busca nada até abrir
    expect(api.parametrosAtuais).not.toHaveBeenCalled();
    await userEvent.click(screen.getByText("Parâmetros de cálculo"));
    expect(await screen.findByText(/Vigente desde/)).toHaveTextContent("Eduardo Luiz");
    // não aparece mais dentro do painel "Avaliar" de um grupo
    await userEvent.click(screen.getAllByRole("button", { name: "Avaliar" })[0]);
    expect(screen.queryByRole("tab", { name: "Parâmetros" })).toBeNull();
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

describe("Carteira: período de avaliação e revisão de honorários", () => {
  beforeEach(() => vi.clearAllMocks());

  const periodo = (o: Partial<PeriodoDeAvaliacao> = {}): PeriodoDeAvaliacao => ({
    id: 1, mes_de_referencia: "2026-10-01", aberto_em: "2026-10-01T09:00:00", aberto_por: "Eduardo Luiz",
    margem_minima: "0.6000", margem_alvo: "0.7000", calculado_em: null, calculado_por: null,
    grupos: 3, completos: 1, abas: 6,
    pendentes: [{ grupo_id: 2, grupo_nome: "Beta", preenchidas: 5, abas: 6, novo: false }, { grupo_id: 3, grupo_nome: "Gama", preenchidas: 0, abas: 6, novo: false }], ...o,
  });
  const rent = (o: Partial<RentabilidadeDoGrupo> = {}): RentabilidadeDoGrupo => ({
    porte: "Médio", horas: "20.8", custo_de_servir: "829.40", honorario_praticado: "5200.00", margem: "0.7428",
    honorario_calculado: "4029.47", defasagem: "0.2905", revisao_de_honorarios: false, ...o,
  });
  const itens = () => [
    item({ grupo_id: 1, grupo_nome: "Alfa", rentabilidade_do_grupo: rent(),
      rascunho: { respostas: {}, preenchidas: ["complexidade", "risco", "disciplina", "cross_sell", "inadimplencia", "porte"], atualizado_em: "2026-10-02T10:00:00", atualizado_por: "Karine" } }),
    item({ grupo_id: 2, grupo_nome: "Beta", rentabilidade_do_grupo: rent({ margem: "0.6596", defasagem: "-0.1753", honorario_calculado: "2303.78" }),
      rascunho: { respostas: {}, preenchidas: ["complexidade", "risco", "disciplina", "cross_sell", "inadimplencia"], atualizado_em: "2026-10-02T10:00:00", atualizado_por: "Karine" } }),
    item({ grupo_id: 3, grupo_nome: "Gama", rentabilidade_do_grupo: rent({ margem: "0.4828", defasagem: "-0.5334", honorario_calculado: "16075.00", revisao_de_honorarios: true }) }),
  ];

  it("mostra quantos faltam, quais são, e só libera o cálculo com todos completos", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ periodo: periodo(), itens: itens() }));
    render(<Carteira listas={null} />);
    expect(await screen.findByText("Faltam 2 de 3 grupos: Beta (5 de 6), Gama (vazio)")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Quem está fazendo"), "Eduardo Luiz");
    expect(screen.getByRole("button", { name: "Calcular carteira" })).toBeDisabled();
  });

  it("o botão Avaliar diz o status do grupo, não só pela cor", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ periodo: periodo(), itens: itens() }));
    render(<Carteira listas={null} />);
    expect(await screen.findByRole("button", { name: "Avaliar ✓ completo" })).toHaveClass("avaliar-ok");
    expect(screen.getByRole("button", { name: "Avaliar · 5 de 6" })).toHaveClass("avaliar-parcial");
    expect(screen.getByRole("button", { name: "Avaliar · vazio" })).toHaveClass("avaliar-vazio");
  });

  it("com todos completos, calcula a carteira depois de confirmar", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      periodo: periodo({ completos: 3, pendentes: [] }), itens: itens(),
    }));
    vi.mocked(api.calcularCarteira).mockResolvedValue({ periodo: periodo({ calculado_em: "2026-10-05T10:00:00" }), grupos_calculados: 3 });
    render(<Carteira listas={null} />);
    expect(await screen.findByText("✓ Todos os 3 grupos completos")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Quem está fazendo"), "Eduardo Luiz");
    await userEvent.click(screen.getByRole("button", { name: "Calcular carteira" }));
    expect(api.calcularCarteira).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirmar: recalcular os 3 grupos" }));
    expect(api.calcularCarteira).toHaveBeenCalledWith("Eduardo Luiz");
  });

  it("sem período, oferece abrir um", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      periodo: null, janela: { margem_minima: "0.6000", margem_alvo: "0.7000", origem: "padrão" }, itens: itens(),
    }));
    vi.mocked(api.abrirPeriodo).mockResolvedValue(periodo());
    render(<Carteira listas={null} />);
    expect(await screen.findByText("Nenhum período aberto")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Quem está fazendo"), "Eduardo Luiz");
    await userEvent.click(screen.getByRole("button", { name: "Abrir período" }));
    expect(api.abrirPeriodo).toHaveBeenCalledWith(expect.objectContaining({ autor: "Eduardo Luiz" }));
    expect(screen.getAllByRole("button", { name: "Avaliar" })).toHaveLength(3); // sem período, sem cor
  });

  it("mostra receita calculada e defasagem, e o filtro Revisão de honorários deixa só quem está abaixo da mínima", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ periodo: periodo(), itens: itens() }));
    render(<Carteira listas={null} />);
    expect(await screen.findByText("+29,0% acima")).toBeInTheDocument();
    expect(screen.getByText("−17,5% abaixo")).toBeInTheDocument();
    expect(screen.getByText(/−53,3% abaixo/)).toHaveTextContent("−53,3% abaixo · revisão");
    expect(screen.getByText("R$ 16.075,00")).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Eixo de ação"), "Revisão de honorários");
    expect(screen.getByText(/▸ Gama/)).toBeInTheDocument();
    expect(screen.queryByText(/▸ Alfa/)).toBeNull();
    expect(screen.queryByText(/▸ Beta/)).toBeNull();
  });
});

describe("Carteira: valor em contrato e cliente novo", () => {
  beforeEach(() => vi.clearAllMocks());

  const periodo: PeriodoDeAvaliacao = {
    id: 1, mes_de_referencia: "2026-10-01", aberto_em: "2026-10-01T09:00:00", aberto_por: "Eduardo Luiz",
    margem_minima: "0.6000", margem_alvo: "0.7000", calculado_em: null, calculado_por: null,
    grupos: 2, completos: 0, abas: 6,
    pendentes: [
      { grupo_id: 1, grupo_nome: "Alfa", preenchidas: 0, abas: 6, novo: false },
      { grupo_id: 9, grupo_nome: "Zeta", preenchidas: 4, abas: 7, novo: true },
    ],
  };
  const novo = (o: Partial<ClienteNovo> = {}): ClienteNovo => ({
    grupo_id: 9, grupo_nome: "Zeta", desde: "2026-10-10", receita_em_contrato: "2600.00", contratos: 1,
    empresas: [], porte: PORTE_VAZIO,
    rascunho: { respostas: {}, preenchidas: ["complexidade", "risco", "cross_sell", "porte"], atualizado_em: "2026-10-02T10:00:00", atualizado_por: "Karine" },
    rentabilidade_do_grupo: {
      porte: "Pequeno", horas: "10.50", custo_de_servir: "437.72", honorario_praticado: "2600.00", margem: "0.7216",
      honorario_calculado: "2303.78", defasagem: "0.1286", revisao_de_honorarios: false,
    },
    ...o,
  });

  it("receita praticada é o valor em contrato, e sem contrato no CRM diz que é da planilha", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      itens: [
        item({ receita_mensal: "1000.00", receita_em_contrato: "4800.00", contratos: 2 }),
        item({ grupo_id: 2, grupo_nome: "Beta", receita_mensal: "7500.00", receita_em_contrato: null, contratos: 0 }),
      ],
    }));
    render(<Carteira listas={null} />);
    expect((await screen.findByText("2 contratos")).closest("td")).toHaveTextContent("R$ 4.800,00");
    expect(screen.getByText("sem contrato no CRM: valor da planilha").closest("td")).toHaveTextContent("R$ 7.500,00");
  });

  it("cliente novo aparece com etiqueta, sem Score e com o Avaliar contando 7 abas", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ periodo, novos: [novo()] }));
    render(<Carteira listas={null} />);
    const linha = (await screen.findByText(/▸ Zeta/)).closest("tr")!;
    expect(linha).toHaveTextContent("novo");
    expect(linha).toHaveTextContent("cliente desde 10/2026, sem leitura anterior");
    expect(linha).toHaveTextContent("R$ 2.600,00");
    expect(linha).toHaveTextContent("1 contrato");
    expect(linha).toHaveTextContent("+12,9% acima");
    expect(linha).toHaveTextContent("após o cálculo");
    expect(screen.getByRole("button", { name: "Avaliar · 4 de 7" })).toHaveClass("avaliar-parcial");
    expect(screen.getByText(/Zeta, novo \(4 de 7\)/)).toBeInTheDocument();
  });

  it("só com cliente novo, a Carteira não fica vazia", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ itens: [], isc: null, retrato: null, periodo, novos: [novo()] }));
    render(<Carteira listas={null} />);
    expect(await screen.findByText(/▸ Zeta/)).toBeInTheDocument();
    expect(screen.queryByText(/Nenhuma classificação carregada/)).toBeNull();
  });

  it("filtro de eixo esconde o cliente novo, e Revisão de honorários mostra se couber", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      periodo,
      novos: [novo(), novo({ grupo_id: 8, grupo_nome: "Eta", rentabilidade_do_grupo: { ...novo().rentabilidade_do_grupo!, margem: "0.4000", revisao_de_honorarios: true } })],
    }));
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Zeta/);
    await userEvent.selectOptions(screen.getByLabelText("Eixo de ação"), "Sem urgência de churn");
    expect(screen.queryByText(/▸ Zeta/)).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText("Eixo de ação"), "Revisão de honorários");
    expect(screen.getByText(/▸ Eta/)).toBeInTheDocument();
    expect(screen.queryByText(/▸ Zeta/)).toBeNull();
  });
});
