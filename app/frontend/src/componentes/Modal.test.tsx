import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Indicador } from "./Indicador";
import { Modal } from "./Modal";

describe("Modal das composições (15/10/2026)", () => {
  it("abre centralizado, com foco no fechar, e fecha por Esc, X e clique fora", async () => {
    const aoFechar = vi.fn();
    render(<Modal titulo="Churn da base no ano" subtitulo="No ano" aoFechar={aoFechar}><p>lista</p></Modal>);
    const modal = screen.getByRole("dialog", { name: "Churn da base no ano" });
    expect(modal).toHaveClass("modal");
    expect(screen.getByRole("button", { name: "Fechar" })).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    await userEvent.click(screen.getByRole("button", { name: "Fechar" }));
    fireEvent.click(modal.parentElement!);
    expect(aoFechar).toHaveBeenCalledTimes(3);
    fireEvent.click(screen.getByText("lista"));  // clique dentro não fecha
    expect(aoFechar).toHaveBeenCalledTimes(3);
  });

  it("Ver composição do indicador abre no modal, não no painel lateral", async () => {
    render(
      <Indicador rotulo="MRR novo no mês" tom="verde" destaque="R$ 1,00"
        composicao={{ titulo: "MRR novo no mês", quantos: 1, conteudo: () => <p>Mainô</p> }} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Ver composição (1)" }));
    const modal = await screen.findByRole("dialog", { name: "MRR novo no mês" });
    expect(modal).toHaveClass("modal");
    expect(document.querySelector(".painel")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Fechar" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Ver composição (1)" })).toHaveFocus();
  });
});
