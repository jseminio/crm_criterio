/** Migrar do CRM local (10/10/2026): prévia sem gravar, o que fica da nuvem à vista e confirmação com MIGRAR. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import { MigrarDoCrmLocal } from "./MigrarDoCrmLocal";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { previaDaMigracao: vi.fn(), migrarDoCrmLocal: vi.fn() } };
});

const PREVIA = {
  criado_em: "2026-10-10T15:00:00Z", revisao_do_arquivo: "d9f1b3c7e5a2", revisao_da_nuvem: "d9f1b3c7e5a2",
  pode_migrar: true, motivo: null, registros_que_entram: 1200, registros_que_saem: 40,
  linhas: [
    { tabela: "grupo_economico", no_arquivo: 120, na_nuvem: 3, acao: "substitui" as const },
    { tabela: "usuario", no_arquivo: 0, na_nuvem: 2, acao: "preserva" as const },
  ],
};

describe("Migrar do CRM local", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra a prévia e só migra com MIGRAR", async () => {
    vi.mocked(api.previaDaMigracao).mockResolvedValue(PREVIA);
    vi.mocked(api.migrarDoCrmLocal).mockResolvedValue({ registros: 1200, backup_de_antes: "crm-antes-de-migrar-x.zip" });
    render(<MigrarDoCrmLocal />);
    const arquivo = new File(["zip"], "crm.zip", { type: "application/zip" });
    fireEvent.change(screen.getByLabelText("Backup do CRM local (.zip)"), { target: { files: [arquivo] } });
    expect(await screen.findByText("fica a da nuvem")).toBeInTheDocument();
    expect(screen.getByText("vem do local")).toBeInTheDocument();
    const botao = screen.getByRole("button", { name: "Migrar e substituir" });
    expect(botao).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Digite MIGRAR para confirmar"), { target: { value: "MIGRAR" } });
    fireEvent.click(botao);
    await waitFor(() => expect(api.migrarDoCrmLocal).toHaveBeenCalledWith(arquivo));
    expect(await screen.findByText(/Migrado: 1\.200 registros/)).toBeInTheDocument();
  });

  it("versões diferentes não deixam migrar e dizem o porquê", async () => {
    vi.mocked(api.previaDaMigracao).mockResolvedValue({ ...PREVIA, pode_migrar: false, motivo: "versões diferentes" });
    render(<MigrarDoCrmLocal />);
    fireEvent.change(screen.getByLabelText("Backup do CRM local (.zip)"), { target: { files: [new File(["z"], "c.zip")] } });
    expect(await screen.findByText(/Não dá para migrar: versões diferentes/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Migrar e substituir" })).toBeNull();
  });
});
