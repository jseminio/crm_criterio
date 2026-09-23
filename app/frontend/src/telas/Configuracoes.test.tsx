import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import { Configuracoes } from "./Configuracoes";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { verificarBackup: vi.fn(), importarBackup: vi.fn() } };
});

const RESUMO = {
  criado_em: "2026-09-23T15:00:00+00:00",
  revisao_do_esquema: "abc",
  tabelas: { oportunidade: 156 },
  total: 156,
};
const arquivo = () => new File(["x"], "crm.zip", { type: "application/zip" });

async function escolherArquivo() {
  const entrada = screen.getByLabelText(/arquivo de backup/i);
  fireEvent.change(entrada, { target: { files: [arquivo()] } });
  await screen.findByText(/arquivo íntegro/i);
}

describe("Configurações", () => {
  beforeEach(() => vi.resetAllMocks());

  it("oferece o download do backup completo", () => {
    render(<Configuracoes />);
    const link = screen.getByRole("link", { name: /baixar backup completo/i });
    expect(link).toHaveAttribute("href", "/api/backup/exportar");
  });

  it("confere o arquivo antes de liberar a importação", async () => {
    vi.mocked(api.verificarBackup).mockResolvedValue(RESUMO);
    render(<Configuracoes />);
    expect(screen.queryByRole("button", { name: "Importar" })).toBeNull();
    await escolherArquivo();
    expect(screen.getByText("oportunidade")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importar" })).toBeEnabled();
  });

  it("mostra o erro de um arquivo inválido e não libera a importação", async () => {
    const { ErroDaApi } = await import("../api/cliente");
    vi.mocked(api.verificarBackup).mockRejectedValue(new ErroDaApi(422, "Arquivo corrompido."));
    render(<Configuracoes />);
    fireEvent.change(screen.getByLabelText(/arquivo de backup/i), { target: { files: [arquivo()] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Arquivo corrompido.");
    expect(screen.queryByRole("button", { name: "Importar" })).toBeNull();
  });

  it("substituir só libera depois de digitar SUBSTITUIR", async () => {
    vi.mocked(api.verificarBackup).mockResolvedValue(RESUMO);
    vi.mocked(api.importarBackup).mockResolvedValue(RESUMO);
    render(<Configuracoes />);
    await escolherArquivo();
    fireEvent.click(screen.getByLabelText(/substituir os dados atuais/i));
    const botao = screen.getByRole("button", { name: "Importar" });
    expect(botao).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/digite substituir/i), { target: { value: "SUBSTITUIR" } });
    expect(botao).toBeEnabled();
    fireEvent.click(botao);
    await waitFor(() => expect(api.importarBackup).toHaveBeenCalledWith(expect.any(File), true));
    expect(await screen.findByText(/importado: 156/i)).toBeInTheDocument();
  });
});
