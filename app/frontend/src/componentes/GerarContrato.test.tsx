import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { DocumentoDoContrato, Eu } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { GerarContrato } from "./GerarContrato";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { documentoDoContrato: vi.fn(), gerarDocumentoDoContrato: vi.fn(), baixarDocumentoDoContrato: vi.fn() } };
});

const ADMIN: Eu = { modo: "microsoft", email: "e@grupocriterio.com.br", nome: "Eduardo", perfil: "Administrador", administrador: true, permissoes: [] };
const LEITURA: Eu = { ...ADMIN, perfil: "Contratos", administrador: false, permissoes: ["contratos.ver"] };

const ABA: DocumentoDoContrato = {
  modelo: "Recorrente padrão", recorrente: true, problema: null, numero: "102.2026", gerado: null,
  matriz: { id: 1, nome_arquivo: "m.docx", enviada_em: "2026-10-14T12:00:00Z", enviada_por: "Eduardo", encontrados: [], faltando: [], desconhecidos: [], em_condicao: true },
  campos: [
    { nome: "numero", descricao: "número", valor: "102.2026", origem: "sequência" },
    { nome: "razao_social", descricao: "razão social do cliente", valor: "Cliente A Ltda", origem: "empresa" },
    { nome: "competencia_inicial", descricao: "primeira competência faturada", valor: "", origem: "digitar" },
  ],
};

function abrir(eu: Eu = ADMIN) {
  render(<ProvedorDeAcesso eu={eu}><GerarContrato contratoId={7} /></ProvedorDeAcesso>);
}

describe("Gerar contrato (14/10/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra cada campo com a origem e não gera com campo vazio", async () => {
    vi.mocked(api.documentoDoContrato).mockResolvedValue(ABA);
    abrir();
    expect(await screen.findByText("Gerar contrato · CONT CCE RJ1 102.2026")).toBeInTheDocument();
    expect(screen.getByText("empresa")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Gerar Word" }));
    expect(screen.getByRole("alert")).toHaveTextContent("primeira competência faturada");
    expect(api.gerarDocumentoDoContrato).not.toHaveBeenCalled();
  });

  it("gera com os valores conferidos e baixa o Word", async () => {
    vi.mocked(api.documentoDoContrato).mockResolvedValue(ABA);
    vi.mocked(api.gerarDocumentoDoContrato).mockResolvedValue({
      ...ABA, gerado: { id: 3, numero: "CONT CCE RJ1 102.2026", gerado_em: "2026-10-14T12:00:00Z", gerado_por: "Eduardo" },
    });
    abrir();
    await userEvent.type(await screen.findByLabelText("primeira competência faturada"), "novembro de 2026");
    await userEvent.click(screen.getByRole("button", { name: "Gerar Word" }));
    expect(api.gerarDocumentoDoContrato).toHaveBeenCalledWith(7, {
      numero: "102.2026", razao_social: "Cliente A Ltda", competencia_inicial: "novembro de 2026",
    }, undefined);
    expect(api.baixarDocumentoDoContrato).toHaveBeenCalledWith(3);
    expect(await screen.findByText(/CONT CCE RJ1 102.2026 gerado/)).toBeInTheDocument();
  });

  it("sem matriz explica e não oferece gerar; quem só vê não edita", async () => {
    vi.mocked(api.documentoDoContrato).mockResolvedValue({ ...ABA, problema: "Ainda não há matriz do contrato recorrente." });
    abrir();
    expect(await screen.findByText(/Ainda não há matriz/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Gerar Word" })).toBeNull();
  });

  it("perfil sem editar contratos não vê o botão nem os campos editáveis", async () => {
    vi.mocked(api.documentoDoContrato).mockResolvedValue(ABA);
    abrir(LEITURA);
    await screen.findByText("Cliente A Ltda");
    expect(screen.queryByRole("button", { name: "Gerar Word" })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});
