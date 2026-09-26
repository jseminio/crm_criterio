import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Agenda as DadosDaAgenda, ItemDaAgenda } from "../api/tipos";
import { Agenda } from "./Agenda";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { agenda: vi.fn(), editarOportunidade: vi.fn(), oportunidade: vi.fn() } };
});

const item = (o: Partial<ItemDaAgenda>): ItemDaAgenda => ({
  tipo: "oportunidade", id: 1, titulo: "Grupo Alfa", subtitulo: "Alfa BPO", situacao: "Enviar proposta",
  temperatura: "Quente", captador: "EL", valor_anual: "65000.00", proxima_acao: null, proxima_acao_em: null,
  balde: "sem_acao", dias_de_atraso: 0, dias_desde_o_envio: 20, ...o,
});

const agenda = (itens: ItemDaAgenda[], contagens: Partial<DadosDaAgenda["contagens"]> = {}): DadosDaAgenda => ({
  hoje: "2026-09-25",
  contagens: { atrasada: 0, hoje: 0, proximos_7_dias: 0, depois: 0, sem_data: 0, sem_acao: 0, ...contagens },
  itens,
});

describe("Agenda", () => {
  beforeEach(() => vi.clearAllMocks());

  it("abre no primeiro balde que tem gente e mostra as contagens de todos", async () => {
    vi.mocked(api.agenda).mockResolvedValue(agenda([item({})], { sem_acao: 1 }));
    render(<Agenda listas={null} aoAbrirLeads={vi.fn()} />);
    expect(await screen.findByText("Grupo Alfa")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Sem próxima ação/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Atrasadas/ })).toHaveTextContent("0");
    expect(screen.getByText(/enviada há 20 dias/)).toBeInTheDocument();
  });

  it("explica que a falta de próxima ação não é falha de ninguém", async () => {
    vi.mocked(api.agenda).mockResolvedValue(agenda([item({})], { sem_acao: 1 }));
    render(<Agenda listas={null} aoAbrirLeads={vi.fn()} />);
    expect(await screen.findByText(/não é falha de ninguém/i)).toBeInTheDocument();
  });

  it("mostra os dias de atraso das atrasadas", async () => {
    vi.mocked(api.agenda).mockResolvedValue(
      agenda([item({ balde: "atrasada", dias_de_atraso: 5, proxima_acao: "ligar", proxima_acao_em: "2026-09-20" })], { atrasada: 1 }),
    );
    render(<Agenda listas={null} aoAbrirLeads={vi.fn()} />);
    expect(await screen.findByText(/5 dias de atraso/)).toBeInTheDocument();
  });

  it("o botão Salvar só libera com a ação escrita", async () => {
    vi.mocked(api.agenda).mockResolvedValue(agenda([item({})], { sem_acao: 1 }));
    render(<Agenda listas={null} aoAbrirLeads={vi.fn()} />);
    await screen.findByText("Grupo Alfa");
    expect(screen.getByRole("button", { name: "Salvar" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText(/Próxima ação de Grupo Alfa/), "Ligar para o decisor");
    expect(screen.getByRole("button", { name: "Salvar" })).toBeEnabled();
  });

  it("salva a próxima ação na própria linha e recarrega a fila", async () => {
    vi.mocked(api.agenda).mockResolvedValue(agenda([item({})], { sem_acao: 1 }));
    vi.mocked(api.editarOportunidade).mockResolvedValue({} as never);
    render(<Agenda listas={null} aoAbrirLeads={vi.fn()} />);
    await screen.findByText("Grupo Alfa");
    await userEvent.type(screen.getByLabelText(/Próxima ação de Grupo Alfa/), "  Ligar  ");
    fireEvent.change(screen.getByLabelText(/Quando, para Grupo Alfa/), { target: { value: "2026-09-30" } });
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledWith(1, { proxima_acao: "Ligar", proxima_acao_em: "2026-09-30" }));
    await waitFor(() => expect(api.agenda).toHaveBeenCalledTimes(2));
  });

  it("data em branco vai como null, não como texto vazio", async () => {
    vi.mocked(api.agenda).mockResolvedValue(agenda([item({})], { sem_acao: 1 }));
    vi.mocked(api.editarOportunidade).mockResolvedValue({} as never);
    render(<Agenda listas={null} aoAbrirLeads={vi.fn()} />);
    await screen.findByText("Grupo Alfa");
    await userEvent.type(screen.getByLabelText(/Próxima ação de Grupo Alfa/), "Ligar");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledWith(1, { proxima_acao: "Ligar", proxima_acao_em: null }));
  });

  it("lead não tem edição na linha e leva para a tela Leads", async () => {
    vi.mocked(api.agenda).mockResolvedValue(agenda([item({ tipo: "lead", id: 9, titulo: "Beta SA", situacao: "Novo" })], { sem_acao: 1 }));
    const aoAbrirLeads = vi.fn();
    render(<Agenda listas={null} aoAbrirLeads={aoAbrirLeads} />);
    await userEvent.click(await screen.findByRole("button", { name: "Beta SA" }));
    expect(aoAbrirLeads).toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Salvar" })).toBeNull();
  });

  it("balde vazio diz que está vazio", async () => {
    vi.mocked(api.agenda).mockResolvedValue(agenda([item({})], { sem_acao: 1 }));
    render(<Agenda listas={null} aoAbrirLeads={vi.fn()} />);
    await screen.findByText("Grupo Alfa");
    await userEvent.click(screen.getByRole("tab", { name: /Atrasadas/ }));
    expect(screen.getByText(/Nada em “Atrasadas”/)).toBeInTheDocument();
  });
});
