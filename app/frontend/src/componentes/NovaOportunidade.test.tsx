/** A proposta nascendo direto no CRM — sem passar pela planilha nem por um
 * lead. Decisão de Eduardo em 22/09/2026 (E4). */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Listas, OportunidadeDetalhe } from "../api/tipos";
import { NovaOportunidade } from "./NovaOportunidade";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { criarOportunidade: vi.fn() } };
});

const LISTAS: Listas = {
  situacoes: [],
  situacoes_de_lead: [],
  temperaturas: ["Frio", "Morno", "Quente"],
  tipos_de_canal: ["Sócios"],
  tipos_de_canal_em_operacao: ["Sócios"],
  motivos_de_recusa: [],
  linhas_de_servico: [],
  situacoes_de_grupo: [],
  captadores: ["EL", "BO"],
};

describe("NovaOportunidade", () => {
  beforeEach(() => vi.clearAllMocks());

  it("o botão de criar começa desabilitado sem nome", () => {
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={() => {}} />);

    expect(screen.getByRole("button", { name: /criar oportunidade/i })).toBeDisabled();
  });

  it("a data de originação já vem preenchida com hoje", () => {
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={() => {}} />);

    // Data local, não UTC — `toISOString` desloca o dia perto da meia-noite
    // (mesmo cuidado do componente e de `periodo.ts`).
    const hoje = new Date().toLocaleDateString("sv");
    expect(screen.getByLabelText("Data de originação")).toHaveValue(hoje);
  });

  it("preenchendo o nome, libera criar — e manda só os campos preenchidos", async () => {
    vi.mocked(api.criarOportunidade).mockResolvedValue({} as OportunidadeDetalhe);
    const aoCriar = vi.fn();
    render(<NovaOportunidade listas={LISTAS} aoFechar={() => {}} aoCriar={aoCriar} />);

    await userEvent.type(screen.getByLabelText("Nome da oportunidade"), "Delta Engenharia");
    expect(screen.getByRole("button", { name: /criar oportunidade/i })).toBeEnabled();

    await userEvent.click(screen.getByRole("button", { name: /criar oportunidade/i }));

    await waitFor(() => expect(api.criarOportunidade).toHaveBeenCalledOnce());
    const [corpo] = vi.mocked(api.criarOportunidade).mock.calls[0];
    expect(corpo.nome).toBe("Delta Engenharia");
    // Campo em branco não é mandado — evita sobrescrever com string vazia o
    // que o servidor decidiria por padrão (ex. data de hoje).
    expect(corpo).not.toHaveProperty("servico");
    expect(aoCriar).toHaveBeenCalledOnce();
  });

  it("mostra o erro da API sem fechar o painel", async () => {
    vi.mocked(api.criarOportunidade).mockRejectedValue(new Error("Falha ao salvar."));
    const aoFechar = vi.fn();
    render(<NovaOportunidade listas={LISTAS} aoFechar={aoFechar} aoCriar={() => {}} />);

    await userEvent.type(screen.getByLabelText("Nome da oportunidade"), "Épsilon");
    await userEvent.click(screen.getByRole("button", { name: /criar oportunidade/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Falha ao salvar."));
    expect(aoFechar).not.toHaveBeenCalled();
  });
});
