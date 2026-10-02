import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Aprovacao, LinhaDoPainel, PainelDeQuestionarios } from "../api/tipos";
import { AprovacoesPendentes } from "../componentes/AprovacoesPendentes";
import { Questionarios } from "./Questionarios";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      painelDeQuestionarios: vi.fn(), respostasDoQuestionario: vi.fn(), resolverQuestionario: vi.fn(), estadoDaBusca: vi.fn(), buscarQuestionarios: vi.fn(),
      aprovacoes: vi.fn(), aprovar: vi.fn(), recusar: vi.fn(),
    },
  };
});

const linha = (o: Partial<LinhaDoPainel>): LinhaDoPainel => ({
  id: 1, recebido_em: "2026-10-01T20:51:00+00:00", razao_social: "Clínica Exemplo Alfa Ltda", nome_fantasia: "Clínica Exemplo Alfa",
  cnpj: "12345678000190", contato_nome: "Ana Souza", contato_cargo: "Gerente financeira", situacao: "Importado", cliente_novo: true,
  o_que_fez: "", grupo_id: 1, grupo_nome: "Clínica Exemplo Alfa", oportunidade_id: 10, oportunidade_em_aberto_id: null,
  porte_crm: "Grande", porte_site: "Médio", tem_pdf: true, servicos: ["Financeiro"], situacao_do_painel: "aguardando_proposta",
  proposta_numero: null, proposta_enviada_em: null, motivo_da_perda: null, dias_uteis_aguardando: 1, ...o,
});

const PAINEL: PainelDeQuestionarios = {
  numeros: { recebidos: 7, recebidos_antes: 4, aguardando: 3, aguardando_atrasados: 1, enviados: 4, media_de_dias_ate_a_proposta: "3.5", precisam_de_voce: 1 },
  itens: [
    linha({}),
    linha({ id: 2, nome_fantasia: "Beta Engenharia", situacao_do_painel: "proposta_enviada", proposta_numero: "157.2026",
      proposta_enviada_em: "2026-10-02", porte_site: null, servicos: ["Contábil", "Fiscal", "Folha / DP"] }),
    linha({ id: 3, nome_fantasia: "Delta Serviços", situacao: "Precisa de você", situacao_do_painel: "precisa_de_voce" }),
  ],
};

describe("Questionários", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.painelDeQuestionarios).mockResolvedValue(PAINEL);
  });

  it("mostra os cinco números, com o porquê em texto", async () => {
    render(<Questionarios listas={null} />);
    expect(await screen.findByText("4 de 7")).toBeInTheDocument();
    expect(screen.getByText("57% no período")).toBeInTheDocument();
    expect(screen.getByText("30 dias anteriores: 4")).toBeInTheDocument();
    expect(screen.getByText("⚠ 1 há mais de 5 dias úteis")).toBeInTheDocument();
    expect(screen.getByText("3,5 dias")).toBeInTheDocument();
  });

  it("a situação tem ícone e texto, e o porte mostra quando o site discordou", async () => {
    render(<Questionarios listas={null} />);
    const tabela = await screen.findByRole("table", { name: "Questionários" });
    const alfa = within(tabela).getByText("Clínica Exemplo Alfa").closest("tr")!;
    expect(alfa).toHaveTextContent("⏳ aguardando proposta · 1 dia útil");
    expect(alfa).toHaveTextContent("régua do CRM · o site dizia Médio");
    expect(within(tabela).getByText("Beta Engenharia").closest("tr")!).toHaveTextContent("↗ proposta enviada · 157.2026");
    const delta = within(tabela).getByText("Delta Serviços").closest("tr")!;
    expect(within(delta).getByRole("button", { name: "Anexar à existente" })).toBeInTheDocument();
  });

  it("clicar na linha abre as respostas por seção", async () => {
    vi.mocked(api.respostasDoQuestionario).mockResolvedValue([
      { numero: 3, titulo: "Volumes mensais para dimensionamento", respostas: [{ rotulo: "Pagamentos efetuados", valor: "250" }] },
    ]);
    render(<Questionarios listas={null} />);
    await userEvent.click(await screen.findByText("Clínica Exemplo Alfa"));
    const respostas = await screen.findByLabelText("Respostas de Clínica Exemplo Alfa");
    expect(respostas).toHaveTextContent("3 · Volumes mensais para dimensionamento");
    expect(respostas).toHaveTextContent("Pagamentos efetuados250");
    expect(api.respostasDoQuestionario).toHaveBeenCalledWith(1);
  });

  it("os filtros vão para a API", async () => {
    render(<Questionarios listas={null} />);
    await screen.findByText("4 de 7");
    fireEvent.change(screen.getByLabelText("Situação"), { target: { value: "aceita" } });
    await waitFor(() => expect(api.painelDeQuestionarios).toHaveBeenLastCalledWith(
      { dias: 30, servico: "", porte: "", situacao: "aceita" }));
    fireEvent.change(screen.getByLabelText("Período"), { target: { value: "0" } });
    await waitFor(() => expect(api.painelDeQuestionarios).toHaveBeenLastCalledWith(
      { dias: 0, servico: "", porte: "", situacao: "aceita" }));
  });

  it("sem nenhum questionário explica de onde eles vêm; com filtro, oferece limpar", async () => {
    vi.mocked(api.painelDeQuestionarios).mockResolvedValue({ ...PAINEL, itens: [] });
    render(<Questionarios listas={null} />);
    expect(await screen.findByText("Nenhum questionário no período")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Situação"), { target: { value: "aceita" } });
    expect(await screen.findByRole("button", { name: "Limpar filtros" })).toBeInTheDocument();
  });
});

const PEDIDO: Aprovacao = {
  id: 5, contrato_id: 7, grupo_nome: "Gama Comércio", tipo: "Contração", data_do_evento: "2026-10-01", descricao: "reduziu o DP",
  preco_mensal_anterior: "4800.00", preco_mensal_novo: "3900.00", preco_anual_anterior: null, preco_anual_novo: null,
  escopo_anterior: null, escopo_novo: null, motivo: "redução de 18,8% no preço mensal", pedido_por: "Karine",
  pedido_em: "2026-10-02T12:00:00+00:00", situacao: "Aguardando", decidido_por: null, decidido_em: null, motivo_da_recusa: null,
};

describe("Agenda › Aprovações", () => {
  beforeEach(() => vi.resetAllMocks());

  it("sem pedido, não aparece", async () => {
    vi.mocked(api.aprovacoes).mockResolvedValue([]);
    const { container } = render(<AprovacoesPendentes />);
    await waitFor(() => expect(api.aprovacoes).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("aprovar chama a API e avisa o que aconteceu", async () => {
    vi.mocked(api.aprovacoes).mockResolvedValueOnce([PEDIDO]).mockResolvedValue([]);
    vi.mocked(api.aprovar).mockResolvedValue({ ...PEDIDO, situacao: "Aprovado" });
    render(<AprovacoesPendentes />);
    const linha = (await screen.findByText("Gama Comércio · evento em 01/10/2026", { exact: false })).closest("tr")!;
    expect(linha).toHaveTextContent("R$ 4.800,00 → R$ 3.900,00");
    expect(linha).toHaveTextContent("redução de 18,8% no preço mensal");
    await userEvent.click(within(linha).getByRole("button", { name: "Aprovar" }));
    expect(api.aprovar).toHaveBeenCalledWith(5);
    expect(await screen.findByRole("status")).toHaveTextContent("Pedido de contração de Gama Comércio aprovado e aplicado ao contrato.");
  });

  it("recusar pede o porquê antes de chamar a API", async () => {
    vi.mocked(api.aprovacoes).mockResolvedValue([PEDIDO]);
    vi.mocked(api.recusar).mockResolvedValue({ ...PEDIDO, situacao: "Recusado" });
    render(<AprovacoesPendentes />);
    await userEvent.click(await screen.findByRole("button", { name: "Recusar" }));
    const confirmar = screen.getByRole("button", { name: "Confirmar recusa" });
    expect(confirmar).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Por que recusa Contração de Gama Comércio"), "escopo em negociação");
    await userEvent.click(confirmar);
    expect(api.recusar).toHaveBeenCalledWith(5, "escopo em negociação");
  });
});
