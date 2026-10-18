import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { DocumentoAnexado, DocumentoComConferencia, Eu, LinhaDaConferencia } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { DocumentosAnexados } from "./DocumentosAnexados";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      documentos: vi.fn(), documento: vi.fn(), anexarDocumento: vi.fn(), lerDocumentoDeNovo: vi.fn(),
      conferirDocumento: vi.fn(), baixarDocumentoAnexado: vi.fn(),
    },
  };
});

const ADMIN: Eu = { modo: "microsoft", email: "e@grupocriterio.com.br", nome: "Eduardo", perfil: "Administrador", administrador: true, permissoes: [] };
const LEITURA: Eu = { ...ADMIN, perfil: "Contratos", administrador: false, permissoes: ["contratos.ver"] };

const DOC: DocumentoAnexado = {
  id: 5, tipo: "contrato", nome_arquivo: "CONT 102.2026 assinado.pdf", tamanho: 421888, origem: "tela",
  enviado_em: "2026-10-18T15:42:00Z", enviado_por: "Eduardo", substituido_em: null, leitura_situacao: "lida",
  leitura_erro: null, tipo_lido: "contrato", grupo_id: 1, grupo_nome: "Grupo Exemplo", contrato_id: 7, oportunidade_id: null,
  numero_no_documento: null, data_do_documento: null, conferido_em: null, conferido_por: null, sugestao: null,
  cnpjs_lidos: ["11222333000181"], razao_social_lida: "Exemplo Ltda", custo_usd: null,
};

function linha(l: Partial<LinhaDaConferencia> & Pick<LinhaDaConferencia, "campo" | "rotulo">): LinhaDaConferencia {
  return {
    tipo_do_valor: "texto", no_crm: "", lido: "", pagina: 0, trecho: "", situacao: "nao_achou", destino: "contrato",
    gravavel: false, motivo: null, marcar: false, ...l,
  };
}

const CONFERENCIA: DocumentoComConferencia = {
  ...DOC, aviso: null,
  conferencia: [
    linha({ campo: "data_assinatura", rotulo: "Data da assinatura", tipo_do_valor: "data", lido: "2026-10-14", pagina: 9,
      trecho: "Rio de Janeiro, 14 de outubro", situacao: "novo", gravavel: true, marcar: true }),
    linha({ campo: "preco_mensal", rotulo: "Preço mensal", tipo_do_valor: "dinheiro", no_crm: "7000.00", lido: "7000.00",
      pagina: 2, situacao: "igual" }),
    linha({ campo: "base_do_valor", rotulo: "Base do valor", no_crm: "liquido", lido: "bruto", pagina: 2, situacao: "diferente",
      gravavel: true }),
    linha({ campo: "aviso_previo_dias", rotulo: "Aviso prévio (dias)", tipo_do_valor: "inteiro" }),
  ],
};

function abrir(eu: Eu = ADMIN, aoGravar = vi.fn()) {
  render(
    <ProvedorDeAcesso eu={eu}>
      <DocumentosAnexados contratoId={7} tipo="contrato" titulo="Documento assinado" aoGravar={aoGravar} />
    </ProvedorDeAcesso>,
  );
  return aoGravar;
}

describe("Documento assinado (18/10/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra o PDF e a conferência; diferente não vem marcado e só grava o marcado", async () => {
    vi.mocked(api.documentos).mockResolvedValue([DOC]);
    vi.mocked(api.documento).mockResolvedValue(CONFERENCIA);
    vi.mocked(api.conferirDocumento).mockResolvedValue({ ...CONFERENCIA, leitura_situacao: "conferida", conferido_em: "2026-10-18T16:00:00Z", conferido_por: "Eduardo" });
    const aoGravar = abrir();
    const tabela = await screen.findByRole("table", { name: "Conferência do documento" });
    expect(within(tabela).getByText("Igual")).toBeInTheDocument();
    expect(within(tabela).getByText(/p\. 9/)).toBeInTheDocument();
    expect(screen.getByLabelText("Usar Data da assinatura")).toBeChecked();
    expect(screen.getByLabelText("Usar Base do valor")).not.toBeChecked();
    expect(screen.queryByLabelText("Usar Preço mensal")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Gravar 1 campo marcado" }));
    expect(api.conferirDocumento).toHaveBeenCalledWith(5, ["data_assinatura"], {}, undefined);
    expect(await screen.findByText("✓ 1 campo gravado.")).toBeInTheDocument();
    expect(aoGravar).toHaveBeenCalled();
  });

  it("o valor digitado vai junto e deixa marcar o que a IA não achou", async () => {
    vi.mocked(api.documentos).mockResolvedValue([DOC]);
    vi.mocked(api.documento).mockResolvedValue(CONFERENCIA);
    vi.mocked(api.conferirDocumento).mockResolvedValue(CONFERENCIA);
    abrir();
    await userEvent.type(await screen.findByLabelText("Aviso prévio (dias) lido"), "30");
    await userEvent.click(screen.getByLabelText("Usar Aviso prévio (dias)"));
    await userEvent.click(screen.getByRole("button", { name: "Gravar 2 campos marcados" }));
    expect(api.conferirDocumento).toHaveBeenCalledWith(5, ["data_assinatura", "aviso_previo_dias"], { aviso_previo_dias: "30" }, undefined);
  });

  it("sem documento convida a anexar; quem só vê não anexa nem baixa", async () => {
    vi.mocked(api.documentos).mockResolvedValue([]);
    abrir();
    expect(await screen.findByText(/Nenhum PDF assinado anexado/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Anexar PDF" })).toBeInTheDocument();

    vi.mocked(api.documentos).mockResolvedValue([DOC]);
    vi.mocked(api.documento).mockResolvedValue(CONFERENCIA);
    document.body.innerHTML = "";
    abrir(LEITURA);
    expect(await screen.findByText("CONT 102.2026 assinado.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Substituir" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Baixar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Gravar/ })).not.toBeInTheDocument();
  });

  it("enquanto a IA lê, diz que está lendo e não oferece gravar", async () => {
    vi.mocked(api.documentos).mockResolvedValue([{ ...DOC, leitura_situacao: "lendo" }]);
    vi.mocked(api.documento).mockResolvedValue({ ...CONFERENCIA, leitura_situacao: "lendo", conferencia: [],
      aviso: "A IA está lendo o PDF. Pode fechar a tela: a leitura continua." });
    abrir();
    expect(await screen.findByText(/A IA está lendo o PDF/)).toBeInTheDocument();
    expect(screen.getAllByText("Lendo…").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /Gravar/ })).not.toBeInTheDocument();
  });
});
