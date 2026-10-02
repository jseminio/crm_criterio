import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import { CadenciaDeReunioes } from "./CadenciaDeReunioes";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { cadenciaDeReunioes: vi.fn(), mudarCadenciaDeReunioes: vi.fn() } };
});

const CADENCIA = {
  cadencia: { A: ["mensal", "bimestral", "trimestral", "anual"], B: ["trimestral", "anual"], C: ["anual"] },
  alterado_por: null, alterado_em: null,
};

describe("Configurações › Metas: reuniões por classe", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.cadenciaDeReunioes).mockResolvedValue(CADENCIA);
  });

  it("mostra a cadência aceita e salva a mudança na ordem do fluxograma", async () => {
    vi.mocked(api.mudarCadenciaDeReunioes).mockResolvedValue(CADENCIA);
    render(<CadenciaDeReunioes />);
    expect(await screen.findByLabelText("Classe B: Trimestral")).toBeChecked();
    expect(screen.getByLabelText("Classe C: Mensal")).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Salvar cadência" })).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Classe C: Trimestral"));
    await userEvent.click(screen.getByRole("button", { name: "Salvar cadência" }));
    expect(api.mudarCadenciaDeReunioes).toHaveBeenCalledWith({ ...CADENCIA.cadencia, C: ["trimestral", "anual"] });
    expect(await screen.findByRole("status")).toHaveTextContent("Cadência salva");
  });

  it("classe sem nenhuma reunião não salva", async () => {
    render(<CadenciaDeReunioes />);
    await userEvent.click(await screen.findByLabelText("Classe C: Anual"));
    expect(screen.getByRole("button", { name: "Salvar cadência" })).toBeDisabled();
    expect(screen.getByText("· a classe C precisa de ao menos uma reunião")).toBeInTheDocument();
  });
});
