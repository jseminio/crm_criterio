import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { FusaoFeita } from "../api/tipos";
import { FusoesFeitas } from "./FusoesFeitas";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { fusoesFeitas: vi.fn(), desfazerFusao: vi.fn() } };
});

const fusao = (o: Partial<FusaoFeita> = {}): FusaoFeita => ({
  id: 1, principal_id: 10, principal_nome: "Grupo Alfa", absorvido_id: 11, absorvido_nome: "Alfa - proposta",
  feita_em: "2026-09-26T20:59:00+00:00", desfeita_em: null, reconstruida: false,
  empresas: 1, oportunidades: 2, contatos: 0, contratos: 1, pode_desfazer: true, ...o,
});

describe("FusoesFeitas — o botão desfazer", () => {
  beforeEach(() => vi.clearAllMocks());

  it("não aparece quando não há fusão feita", async () => {
    vi.mocked(api.fusoesFeitas).mockResolvedValue([]);
    const { container } = render(<FusoesFeitas versao={0} aoMudar={vi.fn()} />);
    await waitFor(() => expect(api.fusoesFeitas).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("lista as fusões, fechada por padrão, dizendo quantas são", async () => {
    vi.mocked(api.fusoesFeitas).mockResolvedValue([fusao(), fusao({ id: 2 })]);
    render(<FusoesFeitas versao={0} aoMudar={vi.fn()} />);
    const abrir = await screen.findByRole("button", { name: /ver as 2 fusões feitas/i });
    expect(screen.queryByText("Alfa - proposta")).toBeNull();
    await userEvent.click(abrir);
    expect(screen.getAllByText("Alfa - proposta")).toHaveLength(2);
    expect(screen.getAllByText(/1 empresa, 2 propostas, 1 contrato/).length).toBeGreaterThan(0);
  });

  it("desfaz em dois passos: só chama a API depois de confirmar", async () => {
    vi.mocked(api.fusoesFeitas).mockResolvedValue([fusao()]);
    vi.mocked(api.desfazerFusao).mockResolvedValue(fusao({ desfeita_em: "2026-09-26T21:10:00+00:00", pode_desfazer: false }));
    const aoMudar = vi.fn();
    render(<FusoesFeitas versao={0} aoMudar={aoMudar} />);
    await userEvent.click(await screen.findByRole("button", { name: /ver as 1 fusões? feitas/i }));
    await userEvent.click(screen.getByRole("button", { name: "Desfazer" }));
    expect(api.desfazerFusao).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /confirmar: devolver 1 empresa, 2 propostas, 1 contrato/i }));
    await waitFor(() => expect(api.desfazerFusao).toHaveBeenCalledWith(1));
    await waitFor(() => expect(aoMudar).toHaveBeenCalled());
  });

  it("cancelar o segundo passo não desfaz nada", async () => {
    vi.mocked(api.fusoesFeitas).mockResolvedValue([fusao()]);
    render(<FusoesFeitas versao={0} aoMudar={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /ver as 1 fusões? feitas/i }));
    await userEvent.click(screen.getByRole("button", { name: "Desfazer" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(api.desfazerFusao).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Desfazer" })).toBeInTheDocument();
  });

  it("fusão que não dá para desfazer não oferece o botão", async () => {
    vi.mocked(api.fusoesFeitas).mockResolvedValue([fusao({ pode_desfazer: false })]);
    render(<FusoesFeitas versao={0} aoMudar={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /ver as 1 fusões? feitas/i }));
    expect(screen.queryByRole("button", { name: "Desfazer" })).toBeNull();
    expect(screen.getByText("não dá para desfazer")).toBeInTheDocument();
  });

  it("mostra o erro do servidor e volta ao primeiro passo", async () => {
    vi.mocked(api.fusoesFeitas).mockResolvedValue([fusao()]);
    vi.mocked(api.desfazerFusao).mockRejectedValue(new ErroDaApi(409, "esta fusão já foi desfeita"));
    render(<FusoesFeitas versao={0} aoMudar={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /ver as 1 fusões? feitas/i }));
    await userEvent.click(screen.getByRole("button", { name: "Desfazer" }));
    await userEvent.click(screen.getByRole("button", { name: /confirmar: devolver/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/já foi desfeita/);
    expect(screen.getByRole("button", { name: "Desfazer" })).toBeInTheDocument();
  });

  it("avisa quando o registro foi refeito a partir de um backup", async () => {
    vi.mocked(api.fusoesFeitas).mockResolvedValue([fusao({ reconstruida: true })]);
    render(<FusoesFeitas versao={0} aoMudar={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /ver as 1 fusões? feitas/i }));
    expect(screen.getByText(/registro refeito do backup/)).toBeInTheDocument();
  });
});
