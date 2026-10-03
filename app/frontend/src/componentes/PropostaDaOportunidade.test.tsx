import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { AbaDaProposta, MatrizResumo, PropostaResumo } from "../api/tipos";
import { brutoPrevio } from "../proposta";
import { MatrizesDeProposta } from "./MatrizesDeProposta";
import { PropostaDaOportunidade } from "./PropostaDaOportunidade";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      abaDaProposta: vi.fn(), gerarProposta: vi.fn(), marcarPropostaEnviada: vi.fn(), matrizesDeProposta: vi.fn(),
      configuracaoDeProposta: vi.fn(), subirMatriz: vi.fn(), editarConfiguracaoDeProposta: vi.fn(),
    },
  };
});

const MATRIZ: MatrizResumo = {
  id: 1, tipo: "Contábil", nome_arquivo: "Proposta BPO Full.pptx", enviada_em: "2026-10-01T10:00:00", enviada_por: "Karine",
  encontrados: 11, obrigatorios: 11, faltando: [], desconhecidos: [], utilizavel: true,
};

// A amostra aprovada: Pequeno, complexidade 2, risco 1 → 11,5 h, bruto 2.523,19, líquido 2.245,64.
const ABA: AbaDaProposta = {
  matriz_sugerida: "Contábil", servicos: ["Contábil", "Fiscal", "Folha / DP"], tem_dp: true,
  sugestao: {
    porte: "Pequeno", porte_confirmado: false, horas_base: "10", complexidade: 2, complexidade_informada: true, risco: 1,
    risco_informado: true, disciplina: 3, atrito: "0.1500", horas: "11.50", custo_hora: "41.69", custo: "479.41",
    imposto: "0.11", margem_alvo: "0.7000", origem_da_margem: "padrão", bruto: "2523.19", liquido: "2245.64",
  },
  sem_sugestao: null,
  contabil_apurado: "2250.00",
  colaboradores: { clt: 80, pjs_estagiarios: 32, total: 112, valor_por_colaborador: "50.00", valor_dp: "5600.00" },
  valor_da_hora_de_consulta: "350.00",
  rascunho: {
    matriz: "Contábil", cliente: "Exemplo Alfa", tratamento: "Prezado(a) Sr(a). Ana Souza",
    contextualizacao: "A Exemplo Alfa busca um novo parceiro.", valor_contabil: null, valor_dp: null, horas_contabil: null,
    horas_dp: null, plano_bpo: "5000.00", plano_plus: "7000.00", plano_cfo: "9000.00",
  },
  perfil: {
    cnpj: "12.345.678/0001-90", regime: "Lucro Presumido", faturamento: "R$ 4,8 milhões", funcionarios: "18",
    movimentacao: "250", volume_documentos: "120", instituicoes: "2", meios_de_pagamento: "N/D", sistema: "N/D",
    segmento: "N/D", empresas: "1 empresa", localidade: "N/D",
  },
  imposto: "0.11", matrizes: { "Contábil": MATRIZ, Financeiro: null }, revisores: ["Eduardo", "Karine"],
  proximo_numero: "154.2026", propostas: [],
};

const GERADA: PropostaResumo = {
  id: 7, numero: "154.2026", matriz: "Contábil", gerada_em: "2026-10-01T10:15:00", valor_liquido: "2250.00",
  valor_bruto: "2550.00", enviada_em: null, enviada_por: null, arquivo: "Exemplo Alfa_Proposta BPO Contabil_154.2026.pptx",
};

describe("aba Proposta", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    vi.mocked(api.abaDaProposta).mockResolvedValue(ABA);
  });

  it("mostra a conta aberta, sem estado só por cor, e o perfil com N/D", async () => {
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    const conta = await screen.findByText(/Custo de servir/);
    expect(conta).toHaveTextContent("11,5 h × R$ 41,69 = R$ 479,41");
    expect(screen.getByText(/Líquido sugerido/)).toHaveTextContent("R$ 2.245,64 por mês");
    expect(screen.getByText(/Porte/, { selector: "p" })).toHaveTextContent("Pequeno (sugerido pela régua) → 10 h/mês · atrito +15%");
    expect(screen.getByText("Matriz:", { exact: false })).toHaveTextContent("(enviada por Karine em 01/10/2026)");
    expect(screen.getByDisplayValue("PROP CCE RJ 154.2026")).toHaveAttribute("readonly");
    expect(screen.getByText("Sistema").nextSibling).toHaveTextContent("N/D");
    expect(screen.getByText("Nenhuma proposta gerada ainda.")).toBeInTheDocument();
  });

  it("soma o líquido, compara com o sugerido e mostra o bruto ao múltiplo de 50", async () => {
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    fireEvent.change(await screen.findByLabelText("Contábil / Fiscal (R$/mês)"), { target: { value: "1600" } });
    fireEvent.change(screen.getByLabelText("Departamento Pessoal (R$/mês)"), { target: { value: "650" } });
    const total = screen.getByText("Total líquido").closest("div")!;
    expect(total).toHaveTextContent("R$ 2.250,00");
    expect(total).toHaveTextContent("sugerido R$ 2.245,64 · diferença +0,2%");
    expect(screen.getByText(/Valor bruto/).closest("div")).toHaveTextContent("R$ 2.550,00"); // 2.528,09 → 2.550
  });

  it("horas de consulta saem dos honorários: 50% do 13º ÷ R$ 350, 70% Contábil e 30% DP", async () => {
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    fireEvent.change(await screen.findByLabelText("Contábil / Fiscal (R$/mês)"), { target: { value: "8650" } });
    fireEvent.change(screen.getByLabelText("Departamento Pessoal (R$/mês)"), { target: { value: "5600" } });
    expect(screen.queryByRole("spinbutton")).toBeNull(); // horas não se digitam
    expect(screen.getByText(/Horas de consulta\/ano: Contábil/).closest("div")).toHaveTextContent("14 h");
    expect(screen.getByText(/Horas de consulta\/ano: DP/).closest("div")).toHaveTextContent("6 h");
    expect(screen.getByText(/calculadas, não se digitam/)).toHaveTextContent("R$ 7.125,00 ÷ R$ 350,00/h = 20,4 h → 20 h");
  });

  it("sem DP, todas as horas são de Contábil", async () => {
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    fireEvent.change(await screen.findByLabelText("Contábil / Fiscal (R$/mês)"), { target: { value: "4500" } });
    expect(screen.getByText(/Horas de consulta\/ano: Contábil/).closest("div")).toHaveTextContent("6 h");
    expect(screen.getByText(/Horas de consulta\/ano: DP/).closest("div")).toHaveTextContent("—");
  });

  it("DP a R$ 50 por colaborador e Contábil do apurado, com volta ao valor calculado", async () => {
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    expect(await screen.findByText(/112 colaboradores/)).toHaveTextContent("112 colaboradores × R$ 50,00 (80 CLT + 32 PJs/estagiários)");
    expect(screen.getByText(/apurado pelo questionário/)).toHaveTextContent("R$ 2.250,00");
    await userEvent.click(screen.getByRole("button", { name: "voltar ao calculado" }));
    expect(screen.getByLabelText("Departamento Pessoal (R$/mês)")).toHaveValue("5.600,00");
    expect(screen.queryByRole("button", { name: "voltar ao calculado" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "voltar ao apurado" }));
    expect(screen.getByLabelText("Contábil / Fiscal (R$/mês)")).toHaveValue("2.250,00");
  });

  it("gera, baixa e mostra a proposta gerada", async () => {
    vi.mocked(api.gerarProposta).mockResolvedValue(GERADA);
    const clique = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    fireEvent.change(await screen.findByLabelText("Contábil / Fiscal (R$/mês)"), { target: { value: "1600" } });
    vi.mocked(api.abaDaProposta).mockResolvedValue({ ...ABA, propostas: [GERADA] });
    await userEvent.click(screen.getByRole("button", { name: "Gerar PowerPoint" }));
    expect(api.gerarProposta).toHaveBeenCalledWith(10, expect.objectContaining({ valor_contabil: "1600", horas_contabil: 2, horas_dp: null, matriz: "Contábil" }));
    expect(clique).toHaveBeenCalled();
    expect(await screen.findByRole("status")).toHaveTextContent("Proposta 154.2026 gerada");
    const linha = (await screen.findByRole("table", { name: "Propostas geradas" })).querySelector("tbody tr")!;
    expect(linha).toHaveTextContent("gerada, não enviada");
    expect(within(linha as HTMLElement).getByRole("link", { name: "Baixar de novo" })).toHaveAttribute("href", "/api/propostas/7/pptx");
    clique.mockRestore();
  });

  it("aceita o valor no padrão brasileiro e manda o decimal para a API", async () => {
    vi.mocked(api.gerarProposta).mockResolvedValue(GERADA);
    const clique = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    const campo = await screen.findByLabelText("Contábil / Fiscal (R$/mês)");
    fireEvent.change(campo, { target: { value: "3.287,38" } });
    fireEvent.blur(campo);
    expect(campo).toHaveValue("3.287,38");
    expect(screen.getByText("Total líquido").closest("div")).toHaveTextContent("R$ 3.287,38");
    await userEvent.click(screen.getByRole("button", { name: "Gerar PowerPoint" }));
    expect(api.gerarProposta).toHaveBeenCalledWith(10, expect.objectContaining({ valor_contabil: "3287.38" }));
    clique.mockRestore();
  });

  it("valor que não dá para ler avisa no próprio campo e não deixa o anterior valendo", async () => {
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    const campo = await screen.findByLabelText("Contábil / Fiscal (R$/mês)");
    fireEvent.change(campo, { target: { value: "1600" } });
    fireEvent.change(campo, { target: { value: "3,2,1" } });
    expect(campo).toHaveValue("3,2,1");
    expect(screen.getByRole("alert")).toHaveTextContent("Valor inválido: escreva como 3.287,38");
    // o 1600 de antes não fica valendo escondido
    expect(screen.getByText("Total líquido").closest("div")).toHaveTextContent("R$ 0,00");
  });

  it("o resultado de gerar aparece logo abaixo do botão, com o nome do arquivo e a pasta", async () => {
    vi.mocked(api.gerarProposta).mockResolvedValue(GERADA);
    const clique = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    fireEvent.change(await screen.findByLabelText("Contábil / Fiscal (R$/mês)"), { target: { value: "1600" } });
    const botao = screen.getByRole("button", { name: "Gerar PowerPoint" });
    await userEvent.click(botao);
    const recado = await screen.findByRole("status");
    expect(recado).toHaveTextContent(
      "✓ Proposta 154.2026 gerada. O arquivo Exemplo Alfa_Proposta BPO Contabil_154.2026.pptx foi para a pasta Downloads do navegador.",
    );
    // depois do botão na página, não lá no alto do painel
    expect(botao.compareDocumentPosition(recado) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    clique.mockRestore();
  });

  it("marca como enviada dizendo quem e quando", async () => {
    vi.mocked(api.abaDaProposta).mockResolvedValue({ ...ABA, propostas: [GERADA] });
    vi.mocked(api.marcarPropostaEnviada).mockResolvedValue({ ...GERADA, enviada_em: "2026-10-01", enviada_por: "Karine" });
    const aoEnviar = vi.fn();
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={aoEnviar} />);
    await userEvent.click(await screen.findByRole("button", { name: "Marcar como enviada" }));
    await userEvent.selectOptions(screen.getByLabelText("Quem enviou"), "Karine");
    fireEvent.change(screen.getByLabelText("Quando"), { target: { value: "2026-10-01" } });
    await userEvent.click(screen.getByRole("button", { name: "Confirmar envio" }));
    expect(api.marcarPropostaEnviada).toHaveBeenCalledWith(7, "Karine", "2026-10-01");
    expect(await screen.findByRole("status")).toHaveTextContent("Proposta 154.2026 marcada como enviada por Karine em 01/10/2026.");
    expect(aoEnviar).toHaveBeenCalled();
  });

  it("matriz Financeiro mostra os planos; sem matriz não deixa gerar", async () => {
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: "usar a Financeiro" }));
    expect(screen.getByLabelText("2 · BPO Financeiro PLUS")).toHaveValue("7.000,00");
    expect(screen.queryByText(/Custo de servir/)).toBeNull();
    expect(screen.getByText(/ainda não há matriz Financeiro/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gerar PowerPoint" })).toBeDisabled();
  });

  it("sem porte explica o que falta e erro de geração aparece", async () => {
    vi.mocked(api.abaDaProposta).mockResolvedValue({ ...ABA, sugestao: null, sem_sugestao: "Sem porte: preencha a volumetria." });
    vi.mocked(api.gerarProposta).mockRejectedValue(new ErroDaApi(422, "preencha o honorário de Contábil/Fiscal"));
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    expect(await screen.findByText("Sem porte: preencha a volumetria.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Gerar PowerPoint" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("preencha o honorário de Contábil/Fiscal");
  });

  it("o que foi digitado sobrevive a trocar de aba e fechar o painel, e some ao gerar", async () => {
    const primeiro = render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    fireEvent.change(await screen.findByLabelText("Contábil / Fiscal (R$/mês)"), { target: { value: "4500" } });
    primeiro.unmount(); // trocar de aba ou salvar a oportunidade desmonta a aba

    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    expect(await screen.findByLabelText("Contábil / Fiscal (R$/mês)")).toHaveValue("4.500");
    expect(screen.getByText(/Horas de consulta\/ano: Contábil/).closest("div")).toHaveTextContent("6 h");
    expect(screen.getByText(/Rascunho ainda não gerado/)).toBeInTheDocument();

    vi.mocked(api.gerarProposta).mockResolvedValue(GERADA);
    const clique = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    await userEvent.click(screen.getByRole("button", { name: "Gerar PowerPoint" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Proposta 154.2026 gerada");
    expect(localStorage.getItem("crm.proposta.rascunho.10")).toBeNull();
    clique.mockRestore();
  });

  it("descartar o rascunho volta ao sugerido", async () => {
    localStorage.setItem("crm.proposta.rascunho.10", JSON.stringify({ entrada: { ...ABA.rascunho, valor_contabil: "999" }, salvo_em: "2026-10-01T10:00:00" }));
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    expect(await screen.findByLabelText("Contábil / Fiscal (R$/mês)")).toHaveValue("999");
    await userEvent.click(screen.getByRole("button", { name: "descartar e voltar ao sugerido" }));
    expect(screen.getByLabelText("Contábil / Fiscal (R$/mês)")).toHaveValue("");
    expect(localStorage.getItem("crm.proposta.rascunho.10")).toBeNull();
  });

  it("sem matriz, diz por que não dá para gerar", async () => {
    vi.mocked(api.abaDaProposta).mockResolvedValue({ ...ABA, matrizes: { "Contábil": null, Financeiro: null } });
    render(<PropostaDaOportunidade oportunidadeId={10} aoEnviar={vi.fn()} />);
    expect(await screen.findByRole("note")).toHaveTextContent("Falta a matriz Contábil: suba o PowerPoint com os marcadores em Configurações › Propostas.");
    expect(screen.getByRole("button", { name: "Gerar PowerPoint" })).toBeDisabled();
  });

  it("prévia do bruto segue a regra da API", () => {
    expect(brutoPrevio(6900, 0.11)).toBe(7750);
    expect(brutoPrevio(2250, 0.11)).toBe(2550);
  });
});

describe("Configurações › Propostas", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.matrizesDeProposta).mockResolvedValue({
      em_uso: {
        "Contábil": MATRIZ,
        Financeiro: { ...MATRIZ, id: 2, tipo: "Financeiro", encontrados: 6, obrigatorios: 7, faltando: ["plano_cfo"], desconhecidos: ["valr"], utilizavel: false },
      },
      marcadores: [{ nome: "valor_dp", descricao: "honorário de DP", obrigatorio_em: ["Contábil"] }, { nome: "sistema", descricao: "ERP", obrigatorio_em: [] }],
    });
    vi.mocked(api.configuracaoDeProposta).mockResolvedValue({
      proximo_numero: 154, revisores: ["Eduardo", "Karine"], plano_bpo: "5000.00", plano_plus: "7000.00", plano_cfo: "9000.00",
      imposto: "0.11", ultimo_usado: "153.2026",
    });
  });

  it("mostra o estado de cada matriz com palavra e a lista de marcadores", async () => {
    render(<MatrizesDeProposta />);
    const tabela = await screen.findByRole("table", { name: "Matrizes de proposta" });
    expect(tabela).toHaveTextContent("✓ 11 de 11 obrigatórios");
    expect(tabela).toHaveTextContent("✗ falta {{plano_cfo}}");
    expect(tabela).toHaveTextContent("✗ desconhecido {{valr}}");
    expect(tabela).toHaveTextContent("não será usada até corrigir");
    expect(screen.getByText(/Último usado: 153.2026/)).toBeInTheDocument();
    await userEvent.click(screen.getByText("Lista de marcadores"));
    expect(screen.getByText("{{sistema}}").closest("tr")).toHaveTextContent("opcional");
  });

  it("troca a matriz dizendo quem subiu", async () => {
    vi.mocked(api.subirMatriz).mockResolvedValue({ ...MATRIZ, id: 3, nome_arquivo: "Nova.pptx" });
    render(<MatrizesDeProposta />);
    await userEvent.selectOptions(await screen.findByLabelText("Quem está subindo a matriz"), "Karine");
    const arquivo = new File(["pptx"], "Nova.pptx");
    fireEvent.change(screen.getByLabelText("Trocar a matriz Contábil"), { target: { files: [arquivo] } });
    expect(await screen.findByRole("status")).toHaveTextContent("Matriz Contábil trocada: Nova.pptx");
    expect(api.subirMatriz).toHaveBeenCalledWith("Contábil", arquivo, "Karine");
  });

  it("salva a configuração e mostra a recusa da API", async () => {
    vi.mocked(api.editarConfiguracaoDeProposta).mockRejectedValue(new ErroDaApi(422, "o 153.2026 já foi usado"));
    render(<MatrizesDeProposta />);
    fireEvent.change(await screen.findByLabelText(/Próximo número de proposta/), { target: { value: "150" } });
    fireEvent.change(screen.getByLabelText(/Quem revisa e envia/), { target: { value: "Eduardo, Karine, Bruno" } });
    await userEvent.click(screen.getByRole("button", { name: "Salvar configuração das propostas" }));
    expect(api.editarConfiguracaoDeProposta).toHaveBeenCalledWith(expect.objectContaining({
      proximo_numero: 150, revisores: ["Eduardo", "Karine", "Bruno"],
    }));
    expect(await screen.findByRole("alert")).toHaveTextContent("o 153.2026 já foi usado");
  });
});
