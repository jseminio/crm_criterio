/** O "i" ao lado de Nível no painel do parceiro (21/10/2026): abre com clique, destaca o nível escolhido e o Esc fecha só a
 * explicação, não o painel. */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DetalheDoParceiro } from "../telas/DetalheDoParceiro";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { parceiro: vi.fn(), criarParceiro: vi.fn(), editarParceiro: vi.fn() } };
});

describe("InfoDosNiveis", () => {
  it("abre com o i, destaca o nível escolhido e acompanha a troca", () => {
    render(<DetalheDoParceiro id={null} aoFechar={() => {}} aoSalvar={() => {}} />);
    const botao = screen.getByRole("button", { name: "O que é cada nível" });
    expect(screen.queryByRole("dialog", { name: "Os níveis de parceiro" })).toBeNull();
    fireEvent.click(botao);
    expect(botao.getAttribute("aria-expanded")).toBe("true");
    const info = screen.getByRole("dialog", { name: "Os níveis de parceiro" });
    const secoes = within(info).getAllByRole("region");
    expect(secoes.map((s) => s.getAttribute("aria-label"))).toEqual(["Indicador", "Estruturado", "Estratégico"]);
    expect(within(secoes[0]).getByText("Escolhido")).toBeTruthy();
    expect(within(secoes[0]).getByText(/1ª parcela líquida/)).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Nível"), { target: { value: "Estratégico" } });
    const depois = within(screen.getByRole("dialog", { name: "Os níveis de parceiro" })).getAllByRole("region");
    expect(depois[0].getAttribute("aria-label")).toBe("Estratégico");
    expect(within(depois[0]).getByText(/a Ficus/)).toBeTruthy();
  });

  it("Esc e Fechar fecham só a explicação, não o painel", () => {
    const aoFechar = vi.fn();
    render(<DetalheDoParceiro id={null} aoFechar={aoFechar} aoSalvar={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "O que é cada nível" }));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Os níveis de parceiro" })).toBeNull();
    expect(aoFechar).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "O que é cada nível" }));
    fireEvent.click(within(screen.getByRole("dialog", { name: "Os níveis de parceiro" })).getByRole("button", { name: "Fechar" }));
    expect(screen.queryByRole("dialog", { name: "Os níveis de parceiro" })).toBeNull();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(aoFechar).toHaveBeenCalledOnce();
  });

  it("o texto não usa siglas de parceiro (21/10/2026)", async () => {
    const { NIVEIS_EXPLICADOS } = await import("./InfoDosNiveis");
    const texto = JSON.stringify(NIVEIS_EXPLICADOS);
    expect(texto).not.toMatch(/\b(GPF|MNGM|MSA|NMK)\b/);
  });
});
