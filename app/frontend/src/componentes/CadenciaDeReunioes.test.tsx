import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import { CadenciaDeReunioes } from "./CadenciaDeReunioes";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { cadenciaDeReunioes: vi.fn(), mudarCadenciaDeReunioes: vi.fn() } };
});

const CADENCIA = {
  cadencia: { A: ["mensal"], B: ["trimestral"], C: ["semestral"] },
  intencao: { A: "Reter e expandir", B: "Subir para A", C: "Entender a estratégia" },
  alterado_por: null, alterado_em: null,
};

describe("Configurações › Metas: uma reunião e uma intenção por classe (03/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.cadenciaDeReunioes).mockResolvedValue(CADENCIA);
  });

  it("mostra a reunião e a intenção de cada classe e salva só o que mudou", async () => {
    vi.mocked(api.mudarCadenciaDeReunioes).mockResolvedValue(CADENCIA);
    render(<CadenciaDeReunioes />);
    expect(await screen.findByLabelText("Classe C: reunião")).toHaveValue("semestral");
    expect(screen.getByLabelText("Classe A: intenção")).toHaveValue("Reter e expandir");
    expect(screen.queryByRole("option", { name: "Anual" })).not.toBeInTheDocument();
    const salvar = screen.getByRole("button", { name: "Salvar" });
    expect(salvar).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Classe B: reunião"), "semestral");
    fireEvent.change(screen.getByLabelText("Classe C: intenção"), { target: { value: "Vender valuation" } });
    expect(screen.getByText("· alterações ainda não salvas")).toBeInTheDocument();
    await userEvent.click(salvar);
    expect(api.mudarCadenciaDeReunioes).toHaveBeenCalledWith({
      cadencia: { B: ["semestral"] }, intencao: { C: "Vender valuation" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Salvo");
  });

  it("a bimestral da carteira fica fora das classes", async () => {
    render(<CadenciaDeReunioes />);
    expect(await screen.findByText(/bimestral da carteira \(interna, Head do BPO e CEO da Critério\)/)).toBeInTheDocument();
  });
});
