import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ClassificacaoDaCarteira, ItemDaCarteira, NotasDoGrupo, Parametros, PorteDoGrupo } from "../api/tipos";
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
  receita: "3.00", rentabilidade: "3.00", complexidade: "3.00", disciplina: "3.00", risco: "3.00",
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
        item({ grupo_id: 1, grupo_nome: "Alfa", notas: { ...NOTAS_VAZIO, rentabilidade: "2.50" } }),
        item({
          grupo_id: 2, grupo_nome: "Beta", classe: "C", classe_efetiva: "C1", em_cobranca: false,
          alerta_de_churn: null, eixo_de_acao: "Sem urgência de churn", churn: 1, receita_mensal: "5000.00",
          notas: { ...NOTAS_VAZIO, rentabilidade: "4.80" },
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

  it("mostra o retrato com o travado e o percentual juntos num só chip, e filtra ao clicar", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
    render(<Carteira listas={null} />);
    await screen.findByText(/▸ Alfa/);
    expect(screen.getByText("unidades (grupos + individuais)").previousElementSibling).toHaveTextContent("2");
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
