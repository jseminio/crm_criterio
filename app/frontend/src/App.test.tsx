import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

// As telas têm testes próprios; aqui só importa o esqueleto (menu e faixa do título).
vi.mock("./api/cliente", async () => {
  const real = await vi.importActual<typeof import("./api/cliente")>("./api/cliente");
  return { ...real, api: { listas: vi.fn().mockResolvedValue(null) } };
});
vi.mock("./telas/Agenda", () => ({ Agenda: () => <p>tela da agenda</p> }));
vi.mock("./telas/Contatos", () => ({ Contatos: () => <p>tela de contatos</p> }));
vi.mock("./telas/Configuracoes", () => ({ Configuracoes: () => <p>tela de configurações</p> }));
vi.mock("./telas/SdrEAbordagens", () => ({ SdrEAbordagens: () => <p>tela do SDR</p> }));
vi.mock("./telas/FunilEQuestionarios", () => ({ FunilEQuestionarios: () => <p>tela do funil</p> }));
vi.mock("./telas/SucessoDoCliente", () => ({ SucessoDoCliente: () => <p>tela do sucesso</p> }));
vi.mock("./componentes/AjustesDaAreaTecnica", () => ({ AjustesDaAreaTecnica: () => null }));

const navegacao = () => screen.getByRole("navigation", { name: "Navegação principal" });

describe("Menu em gaveta (celular)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("o ☰ abre a gaveta e diz que ela está aberta", async () => {
    render(<App />);
    const botao = screen.getByRole("button", { name: "Abrir menu" });
    expect(botao).toHaveAttribute("aria-expanded", "false");
    expect(navegacao()).not.toHaveClass("lateral-aberta");

    await userEvent.click(botao);
    expect(botao).toHaveAttribute("aria-expanded", "true");
    expect(navegacao()).toHaveClass("lateral-aberta");
  });

  it("escolher uma tela troca a tela e fecha a gaveta", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir menu" }));
    await userEvent.click(screen.getByRole("button", { name: "Contatos" }));
    expect(screen.getByText("tela de contatos")).toBeInTheDocument();
    expect(navegacao()).not.toHaveClass("lateral-aberta");
  });

  it("fecha pelo botão, pelo Esc e pela cortina", async () => {
    const { container } = render(<App />);
    const abrir = screen.getByRole("button", { name: "Abrir menu" });

    await userEvent.click(abrir);
    await userEvent.click(screen.getByRole("button", { name: "Fechar menu" }));
    expect(navegacao()).not.toHaveClass("lateral-aberta");

    await userEvent.click(abrir);
    await userEvent.keyboard("{Escape}");
    expect(navegacao()).not.toHaveClass("lateral-aberta");

    await userEvent.click(abrir);
    await userEvent.click(container.querySelector(".cortina-do-menu")!);
    expect(navegacao()).not.toHaveClass("lateral-aberta");
    expect(container.querySelector(".cortina-do-menu")).toBeNull();
  });
});
