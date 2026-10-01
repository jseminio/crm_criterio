/** A proposta nascendo direto no CRM — sem passar pela planilha nem por um
 * lead. Decisão de Eduardo em 22/09/2026 (E4). */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Listas, OportunidadeDetalhe } from "../api/tipos";
import { precoPelasParcelas } from "../parcelas";
import { NovaOportunidade } from "./NovaOportunidade";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { criarOportunidade: vi.fn(), servicos: vi.fn().mockResolvedValue([
        { nome: "BPO Contábil e Fiscal", nome_por_extenso: null, linha: "C1", recorrente: true,
          para_quem: "Empresa que terceiriza contabilidade e fiscal.", perguntas: [{ texto: "CNPJs no escopo", direcionador: "cnpjs_no_escopo" }],
          fora_do_perfil: ["MEI"], transbordo: "Comercial · BPO (C1)", nomes_antigos: ["BPO Contábil"], rascunho: true, temas: [] },
        { nome: "Auditoria", nome_por_extenso: null, linha: "C2", recorrente: false,
          para_quem: "Auditoria das demonstrações.", perguntas: [{ texto: "Exercício a auditar", direcionador: null }],
          fora_do_perfil: [], transbordo: "Consultoria (C2)", nomes_antigos: [], rascunho: true, temas: [] },
      ]) } };
});

const LISTAS: Listas = {
  situacoes: [],
  situacoes_de_lead: [],
  temperaturas: ["Frio", "Morno", "Quente"],
  tipos_de_canal: ["Sócios"],
  tipos_de_canal_em_operacao: ["Sócios"],
  motivos_de_recusa: [],
  motivos_de_encerramento: [],
  iniciativas_de_encerramento: [],
  papeis_de_contato: [],
  linhas_de_servico: [],
  situacoes_de_grupo: [],
  captadores: ["EL", "BO"],
  portes: [],
  servicos: [],
  indices_de_reajuste: ["IPCA (IBGE)", "IGP-M (FGV)", "Sem reajuste"],
};

describe("NovaOportunidade", () => {
  beforeEach(() => vi.clearAllMocks());

  it("o botão de criar começa desabilitado sem nome", () => {
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={() => {}} />);

    expect(screen.getByRole("button", { name: /criar oportunidade/i })).toBeDisabled();
  });

  it("a data de originação já vem preenchida com hoje", () => {
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={() => {}} />);

    // Data local, não UTC — `toISOString` desloca o dia perto da meia-noite
    // (mesmo cuidado do componente e de `periodo.ts`).
    const hoje = new Date().toLocaleDateString("sv");
    expect(screen.getByLabelText("Data de originação")).toHaveValue(hoje);
  });

  it("preenchendo o nome, libera criar — e manda só os campos preenchidos", async () => {
    vi.mocked(api.criarOportunidade).mockResolvedValue({} as OportunidadeDetalhe);
    const aoCriar = vi.fn();
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={aoCriar} />);

    await userEvent.type(screen.getByLabelText("Nome da oportunidade"), "Delta Engenharia");
    expect(screen.getByRole("button", { name: /criar oportunidade/i })).toBeEnabled();

    await userEvent.click(screen.getByRole("button", { name: /criar oportunidade/i }));

    await waitFor(() => expect(api.criarOportunidade).toHaveBeenCalledOnce());
    const [corpo] = vi.mocked(api.criarOportunidade).mock.calls[0];
    expect(corpo.nome).toBe("Delta Engenharia");
    // Campo em branco não é mandado — evita sobrescrever com string vazia o
    // que o servidor decidiria por padrão (ex. data de hoje).
    expect(corpo).not.toHaveProperty("servico");
    expect(aoCriar).toHaveBeenCalledOnce();
  });

  it("o serviço vem do catálogo e vai no pedido pelo nome", async () => {
    vi.mocked(api.criarOportunidade).mockResolvedValue({} as OportunidadeDetalhe);
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={() => {}} />);

    await userEvent.type(screen.getByLabelText("Nome da oportunidade"), "Delta Engenharia");
    await userEvent.click(screen.getByRole("button", { name: /^Serviço/ }));
    await userEvent.click(await screen.findByRole("option", { name: "Auditoria" }));
    await userEvent.click(screen.getByRole("button", { name: "Usar este serviço" }));
    await userEvent.click(screen.getByRole("button", { name: /criar oportunidade/i }));

    await waitFor(() => expect(api.criarOportunidade).toHaveBeenCalledOnce());
    expect(vi.mocked(api.criarOportunidade).mock.calls[0][0]).toMatchObject({ servico: "Auditoria" });
  });

  it("serviço recorrente pede parcelas e trava o anual em mensal × parcelas", async () => {
    vi.mocked(api.criarOportunidade).mockResolvedValue({} as OportunidadeDetalhe);
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={() => {}} />);

    expect(screen.queryByLabelText("Quantidade de parcelas")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Nome da oportunidade"), "Delta");
    await userEvent.click(screen.getByRole("button", { name: /^Serviço/ }));
    await userEvent.click(await screen.findByRole("option", { name: "BPO Contábil e Fiscal" }));
    await userEvent.click(screen.getByRole("button", { name: "Usar este serviço" }));

    await userEvent.type(screen.getByLabelText("Preço mensal"), "5000");
    await userEvent.type(screen.getByLabelText("Quantidade de parcelas"), "12");
    const anual = screen.getByLabelText("Preço anual");
    expect(anual).toHaveAttribute("readonly");
    expect(anual).toHaveValue(60000);

    await userEvent.click(screen.getByRole("button", { name: /criar oportunidade/i }));
    await waitFor(() => expect(api.criarOportunidade).toHaveBeenCalledOnce());
    expect(vi.mocked(api.criarOportunidade).mock.calls[0][0]).toMatchObject({
      preco_mensal: "5000",
      quantidade_parcelas: "12",
      preco_anual: "60000.00",
    });
  });

  it("serviço não recorrente não tem parcelas e o anual segue livre", async () => {
    vi.mocked(api.criarOportunidade).mockResolvedValue({} as OportunidadeDetalhe);
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={() => {}} />);

    await userEvent.type(screen.getByLabelText("Nome da oportunidade"), "Delta");
    await userEvent.click(screen.getByRole("button", { name: /^Serviço/ }));
    await userEvent.click(await screen.findByRole("option", { name: "Auditoria" }));
    await userEvent.click(screen.getByRole("button", { name: "Usar este serviço" }));

    expect(screen.queryByLabelText("Quantidade de parcelas")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Preço anual"), "4000");
    await userEvent.click(screen.getByRole("button", { name: /criar oportunidade/i }));

    await waitFor(() => expect(api.criarOportunidade).toHaveBeenCalledOnce());
    const [corpo] = vi.mocked(api.criarOportunidade).mock.calls[0];
    expect(corpo).toMatchObject({ preco_anual: "4000" });
    expect(corpo).not.toHaveProperty("quantidade_parcelas");
  });

  it("o reajuste lista os índices e vai no pedido", async () => {
    vi.mocked(api.criarOportunidade).mockResolvedValue({} as OportunidadeDetalhe);
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={() => {}} />);

    const reajuste = screen.getByLabelText("Reajuste");
    expect([...reajuste.querySelectorAll("option")].map((o) => o.textContent)).toEqual([
      "Não informado",
      "IPCA (IBGE)",
      "IGP-M (FGV)",
      "Sem reajuste",
    ]);
    await userEvent.type(screen.getByLabelText("Nome da oportunidade"), "Delta");
    await userEvent.selectOptions(reajuste, "IPCA (IBGE)");
    await userEvent.click(screen.getByRole("button", { name: /criar oportunidade/i }));

    await waitFor(() => expect(api.criarOportunidade).toHaveBeenCalledOnce());
    expect(vi.mocked(api.criarOportunidade).mock.calls[0][0]).toMatchObject({ reajuste: "IPCA (IBGE)" });
  });

  it("a conta das parcelas é feita em centavos", () => {
    expect(precoPelasParcelas("0.10", "3")).toBe("0.30");
    expect(precoPelasParcelas("1234.56", "12")).toBe("14814.72");
    expect(precoPelasParcelas("", "12")).toBe("");
    expect(precoPelasParcelas("100", "0")).toBe("");
  });

  it("mostra o erro da API sem fechar o painel", async () => {
    vi.mocked(api.criarOportunidade).mockRejectedValue(new Error("Falha ao salvar."));
    const aoFechar = vi.fn();
    render(<NovaOportunidade listas={LISTAS} aoFechar={aoFechar} aoCriar={() => {}} />);

    await userEvent.type(screen.getByLabelText("Nome da oportunidade"), "Épsilon");
    await userEvent.click(screen.getByRole("button", { name: /criar oportunidade/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Falha ao salvar."));
    expect(aoFechar).not.toHaveBeenCalled();
  });
});
