import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import { Configuracoes } from "./Configuracoes";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { verificarBackup: vi.fn(), importarBackup: vi.fn(), pedidosDeServicoNovo: vi.fn().mockResolvedValue([]),
    matrizesDeProposta: vi.fn(), configuracaoDeProposta: vi.fn(), catalogoDeAcesso: vi.fn(), perfis: vi.fn(), usuarios: vi.fn(),
    historico: vi.fn(), metas: vi.fn() } };
});

const RESUMO = {
  criado_em: "2026-09-23T15:00:00+00:00",
  revisao_do_esquema: "abc",
  tabelas: { oportunidade: 156 },
  total: 156,
};
const arquivo = () => new File(["x"], "crm.zip", { type: "application/zip" });

/** A seção de propostas abre junto; aqui ela só precisa existir. */
function semMatrizes() {
  vi.mocked(api.catalogoDeAcesso).mockResolvedValue([]);
  vi.mocked(api.perfis).mockResolvedValue([]);
  vi.mocked(api.usuarios).mockResolvedValue([]);
  vi.mocked(api.historico).mockResolvedValue([]);
  vi.mocked(api.metas).mockResolvedValue({
    mrr: { meta: "400000.00", alerta: "200000.00", alterado_por: null, alterado_em: null },
    conversao: { meta: "50.00", alerta: "30.00", alterado_por: null, alterado_em: null },
  });
  vi.mocked(api.matrizesDeProposta).mockResolvedValue({ em_uso: { "Contábil": null, Financeiro: null }, marcadores: [] });
  vi.mocked(api.configuracaoDeProposta).mockResolvedValue({
    proximo_numero: 154, revisores: ["Eduardo", "Karine"], plano_bpo: "5000.00", plano_plus: "7000.00",
    plano_cfo: "9000.00", imposto: "0.11", ultimo_usado: null,
  });
}

async function escolherArquivo() {
  const entrada = screen.getByLabelText(/arquivo de backup/i);
  fireEvent.change(entrada, { target: { files: [arquivo()] } });
  await screen.findByText(/arquivo íntegro/i);
}

/** Configurações abre em abas (02/10/2026): cada teste abre a aba do assunto. */
function abrirAba(nome: string) {
  render(<Configuracoes />);
  fireEvent.click(screen.getByRole("tab", { name: nome }));
}

describe("abas de Configurações", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    vi.mocked(api.pedidosDeServicoNovo).mockResolvedValue([]);
    semMatrizes();
  });

  it("mostra as oito abas na ordem aprovada e abre na primeira", async () => {
    render(<Configuracoes />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
      "Perfis e acesso", "Metas", "Propostas", "Grupos", "Conferência", "Histórico", "Backup", "Serviços pedidos",
    ]);
    expect(screen.getByRole("tab", { name: "Perfis e acesso" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText(/Baixar backup completo/)).toBeNull();
  });

  it("troca o conteúdo pela aba e lembra a escolhida", () => {
    abrirAba("Backup");
    expect(screen.getByRole("link", { name: /baixar backup completo/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Perfis e acesso" })).toBeNull();
    render(<Configuracoes />);
    expect(screen.getAllByRole("tab", { name: "Backup" })[1]).toHaveAttribute("aria-selected", "true");
  });
});

describe("Configurações", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    vi.mocked(api.pedidosDeServicoNovo).mockResolvedValue([]);
    semMatrizes();
  });

  it("oferece o download do backup completo", () => {
    abrirAba("Backup");
    const link = screen.getByRole("link", { name: /baixar backup completo/i });
    expect(link).toHaveAttribute("href", "/api/backup/exportar");
  });

  it("confere o arquivo antes de liberar a importação", async () => {
    vi.mocked(api.verificarBackup).mockResolvedValue(RESUMO);
    abrirAba("Backup");
    expect(screen.queryByRole("button", { name: "Importar" })).toBeNull();
    await escolherArquivo();
    expect(screen.getByText("oportunidade")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Importar" })).toBeEnabled();
  });

  it("mostra o erro de um arquivo inválido e não libera a importação", async () => {
    const { ErroDaApi } = await import("../api/cliente");
    vi.mocked(api.verificarBackup).mockRejectedValue(new ErroDaApi(422, "Arquivo corrompido."));
    abrirAba("Backup");
    fireEvent.change(screen.getByLabelText(/arquivo de backup/i), { target: { files: [arquivo()] } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Arquivo corrompido.");
    expect(screen.queryByRole("button", { name: "Importar" })).toBeNull();
  });

  it("substituir só libera depois de digitar SUBSTITUIR", async () => {
    vi.mocked(api.verificarBackup).mockResolvedValue(RESUMO);
    vi.mocked(api.importarBackup).mockResolvedValue(RESUMO);
    abrirAba("Backup");
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

describe("pedidos de serviço novo", () => {
  beforeEach(() => localStorage.clear());
  it("lista o que o lead pediu fora do catálogo", async () => {
    vi.mocked(api.pedidosDeServicoNovo).mockResolvedValue([
      { onde: "Lead", id: 3, nome: "Lead da feira", descricao: "Perícia contábil judicial", registrado_em: "2026-09-27T15:00:00Z" },
    ]);
    abrirAba("Serviços pedidos");

    const linha = (await screen.findByText("Perícia contábil judicial")).closest("tr")!;
    expect(within(linha).getByText("Lead da feira")).toBeInTheDocument();
    expect(within(linha).getByText("Lead")).toBeInTheDocument();
  });

  it("sem pedido explica de onde eles vêm", async () => {
    vi.mocked(api.pedidosDeServicoNovo).mockResolvedValue([]);
    abrirAba("Serviços pedidos");

    expect(await screen.findByText(/Nenhum pedido ainda/)).toBeInTheDocument();
  });
});


describe("Configurações para o perfil Comercial (02/10/2026)", () => {
  it("vê só Grupos, Conferência e Serviços pedidos", async () => {
    vi.mocked(api.pedidosDeServicoNovo).mockResolvedValue([]);
    const { ProvedorDeAcesso } = await import("../entrada");
    render(
      <ProvedorDeAcesso eu={{ modo: "microsoft", email: "k@grupocriterio.com.br", nome: "Karine", perfil: "Comercial", administrador: false,
        permissoes: ["grupos.ver", "conferencia.ver"] }}>
        <Configuracoes />
      </ProvedorDeAcesso>,
    );
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Grupos", "Conferência", "Serviços pedidos"]);
  });
});

describe("histórico de alterações", () => {
  beforeEach(() => vi.clearAllMocks());

  it("a exclusão de oportunidade mostra o motivo (04/10/2026)", async () => {
    semMatrizes();
    vi.mocked(api.historico).mockResolvedValue([
      { id: 1, quando: "2026-10-04T12:00:00Z", usuario_email: "sem login", usuario_nome: null, acao: "excluiu",
        tabela: "oportunidade", registro_id: 3, descricao: "Rede Farma", campo: "motivo", antes: null,
        depois: "Cadastrada em duplicidade" },
    ]);
    abrirAba("Histórico");
    const linha = (await screen.findByText("Cadastrada em duplicidade")).closest("tr")!;
    expect(linha).toHaveTextContent("registro excluído · motivo: Cadastrada em duplicidade");
    expect(within(linha).getAllByRole("cell")[3]).toHaveTextContent(/^excluiu$/);
  });
});
