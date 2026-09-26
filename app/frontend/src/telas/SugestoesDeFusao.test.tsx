import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { GrupoResumo, SugestaoDeFusao } from "../api/tipos";
import { SugestoesDeFusao } from "./SugestoesDeFusao";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { sugestoesDeFusao: vi.fn(), fundirGrupos: vi.fn() } };
});

const grupo = (id: number, nome: string, n: number): GrupoResumo => ({
  id, nome, situacao: "Prospect", origem: "Carga 2026", responsavel_cs: null,
  data_entrada: null, fundido_em_id: null, quantas_oportunidades: n,
} as GrupoResumo);

const SUGESTAO: SugestaoDeFusao = {
  confianca: "alta",
  motivo: "Mesmo nome de cliente: “sete brasil”.",
  principal_id: 2,
  grupos: [grupo(1, "Sete Brasil - BPO", 1), grupo(2, "Sete Brasil - Bacen", 3)],
};

describe("SugestoesDeFusao", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("não aparece quando não há sugestão", async () => {
    vi.mocked(api.sugestoesDeFusao).mockResolvedValue([]);
    const { container } = render(<SugestoesDeFusao aoJuntar={vi.fn()} />);
    await waitFor(() => expect(api.sugestoesDeFusao).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("mostra a sugestão com o principal já marcado e não funde sozinha", async () => {
    vi.mocked(api.sugestoesDeFusao).mockResolvedValue([SUGESTAO]);
    render(<SugestoesDeFusao aoJuntar={vi.fn()} />);
    expect(await screen.findByText(/Confiança alta/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Sete Brasil - Bacen/)).toBeChecked();
    expect(api.fundirGrupos).not.toHaveBeenCalled();
  });

  it("junta em dois passos: só chama a API depois da confirmação", async () => {
    vi.mocked(api.sugestoesDeFusao).mockResolvedValue([SUGESTAO]);
    vi.mocked(api.fundirGrupos).mockResolvedValue(grupo(2, "x", 4));
    const aoJuntar = vi.fn();
    render(<SugestoesDeFusao aoJuntar={aoJuntar} />);
    fireEvent.click(await screen.findByRole("button", { name: /Juntar 2 grupos/ }));
    expect(api.fundirGrupos).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Confirmar: juntar 1 em Sete Brasil - Bacen/ }));
    await waitFor(() => expect(api.fundirGrupos).toHaveBeenCalledWith(2, 1));
    await waitFor(() => expect(aoJuntar).toHaveBeenCalled());
  });

  it("dá para escolher outro grupo como principal", async () => {
    vi.mocked(api.sugestoesDeFusao).mockResolvedValue([SUGESTAO]);
    vi.mocked(api.fundirGrupos).mockResolvedValue(grupo(1, "x", 4));
    render(<SugestoesDeFusao aoJuntar={vi.fn()} />);
    fireEvent.click(await screen.findByLabelText(/Sete Brasil - BPO/));
    fireEvent.click(screen.getByRole("button", { name: /Juntar 2 grupos/ }));
    fireEvent.click(screen.getByRole("button", { name: /Confirmar: juntar 1 em Sete Brasil - BPO/ }));
    await waitFor(() => expect(api.fundirGrupos).toHaveBeenCalledWith(1, 2));
  });

  it("'Não é o mesmo cliente' esconde a sugestão e não funde", async () => {
    vi.mocked(api.sugestoesDeFusao).mockResolvedValue([SUGESTAO]);
    render(<SugestoesDeFusao aoJuntar={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /Não é o mesmo cliente/ }));
    await waitFor(() => expect(screen.queryByText(/Confiança alta/)).toBeNull());
    expect(api.fundirGrupos).not.toHaveBeenCalled();
  });
});
