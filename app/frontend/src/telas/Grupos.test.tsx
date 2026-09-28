import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { GrupoResumo, Pagina } from "../api/tipos";
import { Grupos } from "./Grupos";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      grupos: vi.fn(),
      editarGrupo: vi.fn(),
      oportunidades: vi.fn().mockResolvedValue({ total: 0, itens: [] }),
      sugestoesDeFusao: vi.fn().mockResolvedValue([]),
      fusoesFeitas: vi.fn().mockResolvedValue([]),
      fundirGrupos: vi.fn(),
      desfazerFusao: vi.fn(),
    },
  };
});

const grupo = (o: Partial<GrupoResumo> = {}): GrupoResumo => ({
  id: 1, nome: "Alfa Participações", situacao: "Prospect", origem: "Carga 2026",
  responsavel_cs: null, observacao: null, data_entrada: null, fundido_em_id: null,
  quantas_oportunidades: 2, ...o,
});
const pagina = (o: Partial<Pagina<GrupoResumo>> = {}): Pagina<GrupoResumo> => ({
  total: 1, itens: [grupo()], ...o,
});

describe("Grupos", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lista os grupos e abre o detalhe ao clicar no nome", async () => {
    vi.mocked(api.grupos).mockResolvedValue(pagina());
    render(<Grupos listas={null} />);
    const link = await screen.findByRole("button", { name: "Alfa Participações" });
    await userEvent.click(link);
    expect(await screen.findByRole("heading", { name: "Alfa Participações" })).toBeInTheDocument();
    expect(screen.getByText("Grupo econômico", { selector: ".painel-subtitulo" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar" })).toBeInTheDocument();
  });

  it("corrige nome, responsável CS e observação, e a lista recarrega", async () => {
    vi.mocked(api.grupos).mockResolvedValue(pagina());
    vi.mocked(api.editarGrupo).mockResolvedValue(
      grupo({ nome: "Alfa Holding", responsavel_cs: "EL", observacao: "nome corrigido em 28/09" }),
    );
    render(<Grupos listas={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Alfa Participações" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));

    const campoNome = screen.getByLabelText("Nome");
    await userEvent.clear(campoNome);
    await userEvent.type(campoNome, "Alfa Holding");
    await userEvent.type(screen.getByLabelText("Responsável CS"), "EL");
    await userEvent.type(screen.getByLabelText("Observação"), "nome corrigido em 28/09");
    await userEvent.click(screen.getByRole("button", { name: "Salvar grupo" }));

    await waitFor(() => expect(api.editarGrupo).toHaveBeenCalledWith(1, {
      nome: "Alfa Holding", responsavel_cs: "EL", observacao: "nome corrigido em 28/09",
    }));
    // volta pra visão de leitura, já com o nome novo (sem esperar reabrir o painel)
    expect(await screen.findByRole("heading", { name: "Alfa Holding" })).toBeInTheDocument();
    expect(screen.getByText("Responsável CS: EL")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Salvar grupo" })).toBeNull();
    // a lista por trás também recarrega depois de salvar (aoMudar chama recarregar)
    await waitFor(() => expect(vi.mocked(api.grupos).mock.calls.length).toBeGreaterThan(1));
  });

  it("cancelar a edição não chama a API e mantém o que já estava salvo", async () => {
    vi.mocked(api.grupos).mockResolvedValue(pagina());
    render(<Grupos listas={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Alfa Participações" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    await userEvent.clear(screen.getByLabelText("Nome"));
    await userEvent.type(screen.getByLabelText("Nome"), "Outro nome qualquer");
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(api.editarGrupo).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: "Alfa Participações" })).toBeInTheDocument();
  });

  it("o botão de salvar não libera com o nome em branco", async () => {
    vi.mocked(api.grupos).mockResolvedValue(pagina());
    render(<Grupos listas={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Alfa Participações" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    await userEvent.clear(screen.getByLabelText("Nome"));
    expect(screen.getByRole("button", { name: "Salvar grupo" })).toBeDisabled();
  });

  it("mostra o erro da API sem travar a tela", async () => {
    vi.mocked(api.grupos).mockResolvedValue(pagina());
    vi.mocked(api.editarGrupo).mockRejectedValue(new Error("falhou"));
    render(<Grupos listas={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Alfa Participações" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    await userEvent.click(screen.getByRole("button", { name: "Salvar grupo" }));
    expect(await screen.findByText("Falha ao salvar.")).toBeInTheDocument();
  });
});
