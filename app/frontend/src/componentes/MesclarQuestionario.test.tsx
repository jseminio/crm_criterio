import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { PreviaDaMescla } from "../api/tipos";
import { BotaoMesclar } from "./MesclarQuestionario";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { sugestoesDeMescla: vi.fn(), previaDaMescla: vi.fn(), mesclarQuestionario: vi.fn(), oportunidades: vi.fn() } };
});

const Q = { id: 9, razao_social: "Empresa Exemplo Ltda", nome_fantasia: "Exemplo", cnpj: "11222333000181",
  recebido_em: "2026-10-14T10:00:00", oportunidade_em_aberto_id: null };

const PREVIA: PreviaDaMescla = {
  oportunidade_id: 5, oportunidade_nome: "Exemplo · BPO Financeiro", recusa: null,
  campos: [
    { campo: "empresa_id", rotulo: "CNPJ (empresa)", no_card: null, no_questionario: "11222333000181", acao: "preenche" },
    { campo: "documentos_fiscais_mes", rotulo: "Documentos fiscais/mês", no_card: null, no_questionario: "320", acao: "preenche" },
    { campo: "contas_bancarias", rotulo: "Contas bancárias", no_card: "4", no_questionario: "6", acao: "diferente" },
  ],
  fusao_de: "Empresa Exemplo Ltda", fusao_em: "Exemplo", cnpj_novo_no_grupo: null,
  duplicada_id: 12, duplicada_nome: "Empresa Exemplo Ltda", duplicada_intocada: true, duplicada_recusa: null,
};

describe("Mesclar o questionário com uma oportunidade (15/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.sugestoesDeMescla).mockResolvedValue([
      { oportunidade_id: 5, nome: "Exemplo · BPO", grupo_nome: "Exemplo", situacao: "Enviar proposta", servico: "BPO Financeiro",
        captador: "EL", data_colocacao: "2026-10-02", motivo: "mesmo e-mail do contato" },
      { oportunidade_id: 6, nome: "Holding", grupo_nome: "Exemplo Holding", situacao: "On hold", servico: "Consultoria",
        captador: "KN", data_colocacao: null, motivo: "nome parecido" },
    ]);
    vi.mocked(api.previaDaMescla).mockResolvedValue(PREVIA);
    vi.mocked(api.oportunidades).mockResolvedValue({ total: 0, itens: [] });
  });

  it("traz a sugestão marcada, a prévia com fusão e duplicada, e mescla com o que a pessoa escolheu", async () => {
    vi.mocked(api.mesclarQuestionario).mockResolvedValue({ o_que_fez: 'Mesclado em "Exemplo · BPO Financeiro".' } as never);
    const aoMesclar = vi.fn();
    render(<BotaoMesclar q={Q} aoMesclar={aoMesclar} />);
    await userEvent.click(screen.getByRole("button", { name: "Mesclar com existente" }));
    const painel = await screen.findByRole("dialog", { name: "Mesclar o questionário com uma oportunidade" });
    const opcoes = within(painel).getByRole("radiogroup", { name: "Oportunidade de destino" });
    expect(within(opcoes).getAllByRole("radio")[0]).toBeChecked();
    expect(opcoes).toHaveTextContent("mesmo e-mail do contato");
    expect(await within(painel).findByText(/será/)).toHaveTextContent("fundido");
    const excluir = within(painel).getByRole("checkbox", { name: /Excluir a oportunidade/ });
    expect(excluir).toBeChecked();
    expect(within(painel).getByText(/ninguém mexeu nela/)).toBeInTheDocument();
    await userEvent.click(within(painel).getByRole("checkbox", { name: /diferente: fica 4/ }));
    await userEvent.click(within(painel).getByRole("button", { name: "Mesclar" }));
    expect(api.mesclarQuestionario).toHaveBeenCalledWith(9, { oportunidade_id: 5, usar_do_questionario: ["contas_bancarias"], excluir_duplicada: true });
    expect(aoMesclar).toHaveBeenCalledWith('Mesclado em "Exemplo · BPO Financeiro".');
  });

  it("recusa aparece e não deixa mesclar", async () => {
    vi.mocked(api.previaDaMescla).mockResolvedValue({ ...PREVIA, recusa: "O CNPJ já é do grupo X: funda os grupos." });
    render(<BotaoMesclar q={Q} aoMesclar={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Mesclar com existente" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("funda os grupos");
    expect(screen.getByRole("button", { name: "Mesclar" })).toBeDisabled();
  });

  it("duplicada mexida vem desmarcada, com aviso", async () => {
    vi.mocked(api.previaDaMescla).mockResolvedValue({ ...PREVIA, duplicada_intocada: false });
    render(<BotaoMesclar q={Q} aoMesclar={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Mesclar com existente" }));
    expect(await screen.findByRole("checkbox", { name: /Excluir a oportunidade/ })).not.toBeChecked();
    expect(screen.getByText(/alguém já mexeu nela/)).toBeInTheDocument();
  });
});
