import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { DocumentoAnexado, Eu } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { DocumentosAntigos } from "./DocumentosAntigos";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      documentos: vi.fn(), documento: vi.fn(), anexarDocumento: vi.fn(), vincularDocumento: vi.fn(), grupos: vi.fn(),
      contratos: vi.fn(), conferirDocumento: vi.fn(), lerDocumentoDeNovo: vi.fn(), baixarDocumentoAnexado: vi.fn(),
    },
  };
});

const ADMIN: Eu = { modo: "microsoft", email: "e@grupocriterio.com.br", nome: "Eduardo", perfil: "Administrador", administrador: true, permissoes: [] };

const BASE: DocumentoAnexado = {
  id: 1, tipo: "contrato", nome_arquivo: "Contrato Alfa 2019.pdf", tamanho: 300000, origem: "lote",
  enviado_em: "2026-10-18T15:00:00Z", enviado_por: "Eduardo", substituido_em: null, leitura_situacao: "lida",
  leitura_erro: null, tipo_lido: "contrato", grupo_id: null, grupo_nome: null, contrato_id: null, oportunidade_id: null,
  numero_no_documento: null, data_do_documento: null, conferido_em: null, conferido_por: null,
  sugestao: { grupo_id: 3, grupo_nome: "Grupo Alfa", empresa_id: 9, contrato_id: 11, oportunidade_id: null, motivo: "pelo CNPJ" },
  cnpjs_lidos: ["11222333000181"], razao_social_lida: "Alfa Ltda", custo_usd: null,
};

function abrir() {
  render(<ProvedorDeAcesso eu={ADMIN}><DocumentosAntigos /></ProvedorDeAcesso>);
}

describe("Incluir documentos antigos (18/10/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra o cliente achado pelo CNPJ e a situação de cada PDF", async () => {
    vi.mocked(api.documentos).mockResolvedValue([
      BASE,
      { ...BASE, id: 2, nome_arquivo: "Contrato Gama.pdf", sugestao: { ...BASE.sugestao!, grupo_id: null, grupo_nome: null, contrato_id: null, motivo: "CNPJ fora do cadastro" } },
      { ...BASE, id: 3, nome_arquivo: "Contrato Delta.pdf", contrato_id: 4, grupo_nome: "Grupo Delta", leitura_situacao: "conferida", conferido_em: "2026-10-18T16:00:00Z" },
    ]);
    abrir();
    expect(await screen.findByText("Grupo Alfa")).toBeInTheDocument();
    expect(screen.getByText("Contrato sugerido")).toBeInTheDocument();
    expect(screen.getByText("CNPJ fora do cadastro")).toBeInTheDocument();
    expect(screen.getByText("Gravado")).toBeInTheDocument();
    expect(screen.getByText("3 enviados · 1 conferidos")).toBeInTheDocument();
  });

  it("envia vários PDFs e lista o que foi recusado", async () => {
    vi.mocked(api.documentos).mockResolvedValue([]);
    vi.mocked(api.anexarDocumento)
      .mockResolvedValueOnce({ ...BASE, conferencia: [], aviso: null })
      .mockRejectedValueOnce(new (await import("../api/cliente")).ErroDaApi(409, "este PDF já está no CRM"));
    abrir();
    expect(await screen.findByText("Nenhum documento antigo incluído")).toBeInTheDocument();
    const a = new File(["%PDF a"], "a.pdf", { type: "application/pdf" });
    const b = new File(["%PDF b"], "b.pdf", { type: "application/pdf" });
    await userEvent.upload(screen.getByLabelText("Escolher os PDFs"), [a, b]);
    expect(api.anexarDocumento).toHaveBeenCalledTimes(2);
    expect(await screen.findByText("✗ b.pdf: este PDF já está no CRM")).toBeInTheDocument();
  });

  it("abre o documento e vincula ao contrato sugerido", async () => {
    vi.mocked(api.documentos).mockResolvedValue([BASE]);
    vi.mocked(api.documento).mockResolvedValue({ ...BASE, conferencia: [], aviso: "Vincule o documento a um contrato ou oportunidade para gravar os campos." });
    vi.mocked(api.grupos).mockResolvedValue({ total: 1, itens: [{ id: 3, nome: "Grupo Alfa" }] } as never);
    vi.mocked(api.contratos).mockResolvedValue({ total: 1, itens: [{ id: 11, grupo_id: 3, escopo: "BPO Contábil", situacao: "Ativo", preco_mensal: "5000.00", data_inicio: null }] } as never);
    vi.mocked(api.vincularDocumento).mockResolvedValue({ ...BASE, contrato_id: 11, grupo_id: 3, conferencia: [], aviso: null });
    abrir();
    await userEvent.click(await screen.findByRole("button", { name: "Contrato Alfa 2019.pdf" }));
    const contrato = await screen.findByLabelText("Vincular ao contrato");
    expect(await screen.findByRole("option", { name: /BPO Contábil · Ativo .*\(sugerido\)/ })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Criar contrato anterior ao CRM" })).toBeInTheDocument();
    await userEvent.selectOptions(contrato, "11");
    expect(api.vincularDocumento).toHaveBeenCalledWith(1, { contrato_id: 11 });
  });
});
