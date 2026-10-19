import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { ContratoResumo, DocumentoAnexado, Eu, OportunidadeResumo } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { DocumentosDoGrupo } from "./DocumentosDoGrupo";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { documentos: vi.fn(), contratos: vi.fn(), baixarDocumentoAnexado: vi.fn() } };
});

const ADMIN: Eu = { modo: "microsoft", email: "e@grupocriterio.com.br", nome: "Eduardo", perfil: "Administrador", administrador: true, permissoes: [] };
const LEITURA: Eu = { ...ADMIN, perfil: "Contratos", administrador: false, permissoes: ["contratos.ver"] };

const DOC: DocumentoAnexado = {
  id: 1, tipo: "contrato", nome_arquivo: "contrato-assinado.pdf", tamanho: 300000, origem: "tela",
  enviado_em: "2026-10-18T15:00:00Z", enviado_por: "Eduardo", substituido_em: null, leitura_situacao: "conferida",
  leitura_erro: null, tipo_lido: "contrato", grupo_id: 3, grupo_nome: "Grupo Alfa", contrato_id: 11, oportunidade_id: null,
  numero_no_documento: "CONT CCE RJ1 102.2026", data_do_documento: "2026-03-12", conferido_em: "2026-10-18T16:00:00Z",
  conferido_por: "Eduardo", sugestao: null, cnpjs_lidos: [], razao_social_lida: null, custo_usd: null,
};
const DOCS: DocumentoAnexado[] = [
  { ...DOC, id: 4, nome_arquivo: "digitalizacao.pdf", contrato_id: null, numero_no_documento: null, data_do_documento: null, leitura_situacao: "lendo", origem: "lote" },
  { ...DOC, id: 3, tipo: "proposta", nome_arquivo: "proposta-aceita.pdf", contrato_id: 11, oportunidade_id: 7, numero_no_documento: "PROP CCE RJ 154.2026", data_do_documento: "2026-02-20" },
  DOC,
  { ...DOC, id: 2, tipo: "aditivo", nome_arquivo: "aditivo-01.pdf", numero_no_documento: null, data_do_documento: "2026-08-05", leitura_situacao: "lida" },
];
const CONTRATO = { id: 11, grupo_id: 3, escopo: "BPO Financeiro", situacao: "Ativo", anterior_ao_crm: false, empresa_nome: "Alfa Ltda" } as ContratoResumo;
const PROPOSTA = { id: 7, nome: "BPO Financeiro 2026", situacao: "Aceita" } as OportunidadeResumo;

function abrir(eu: Eu = ADMIN) {
  const aoAbrirContrato = vi.fn();
  const aoAbrirOportunidade = vi.fn();
  render(
    <ProvedorDeAcesso eu={eu}>
      <DocumentosDoGrupo grupoId={3} propostas={[PROPOSTA]} aoAbrirContrato={aoAbrirContrato} aoAbrirOportunidade={aoAbrirOportunidade} />
    </ProvedorDeAcesso>,
  );
  return { aoAbrirContrato, aoAbrirOportunidade };
}

describe("Documentos no card do grupo (19/10/2026)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.contratos).mockResolvedValue({ total: 1, itens: [CONTRATO] });
  });

  it("lista os PDFs do grupo do mais recente ao sem data, com número, data, dono e conferência", async () => {
    vi.mocked(api.documentos).mockResolvedValue(DOCS);
    abrir();
    const tabela = await screen.findByRole("table", { name: "Documentos do grupo" });
    expect(api.documentos).toHaveBeenCalledWith({ grupo_id: 3 });
    const linhas = within(tabela).getAllByRole("row").slice(1);
    expect(linhas.map((l) => within(l).getAllByRole("cell")[1].textContent)).toEqual([
      "aditivo-01.pdfnúmero não lido · de 05/08/2026",
      "contrato-assinado.pdfnº CONT CCE RJ1 102.2026 · de 12/03/2026",
      "proposta-aceita.pdfnº PROP CCE RJ 154.2026 · de 20/02/2026",
      "digitalizacao.pdfnúmero não lido · data não lida",
    ]);
    expect(within(linhas[1]).getByText("Contrato · BPO Financeiro")).toBeInTheDocument();
    expect(within(linhas[1]).getByText("Ativo · Alfa Ltda")).toBeInTheDocument();
    expect(within(linhas[1]).getByText("Gravado")).toBeInTheDocument();
    expect(within(linhas[0]).getByText("Aditivo")).toBeInTheDocument();
    expect(within(linhas[0]).getByText("Conferir")).toBeInTheDocument();
    // a proposta é da oportunidade, mesmo ligada ao contrato
    expect(within(linhas[2]).getByText("Oportunidade · BPO Financeiro 2026")).toBeInTheDocument();
    expect(within(linhas[3]).getByText("Sem contrato nem oportunidade")).toBeInTheDocument();
    expect(within(linhas[3]).getByText("Lendo…")).toBeInTheDocument();
    expect(within(linhas[3]).queryByRole("button", { name: "digitalizacao.pdf" })).not.toBeInTheDocument();
  });

  it("clicar no nome abre o contrato ou a oportunidade", async () => {
    vi.mocked(api.documentos).mockResolvedValue(DOCS);
    const { aoAbrirContrato, aoAbrirOportunidade } = abrir();
    await userEvent.click(await screen.findByRole("button", { name: "contrato-assinado.pdf" }));
    expect(aoAbrirContrato).toHaveBeenCalledWith(11);
    await userEvent.click(screen.getByRole("button", { name: "proposta-aceita.pdf" }));
    expect(aoAbrirOportunidade).toHaveBeenCalledWith(7);
  });

  it("Baixar só com a permissão contratos.baixar", async () => {
    vi.mocked(api.documentos).mockResolvedValue([DOC]);
    abrir();
    await userEvent.click(await screen.findByRole("button", { name: "Baixar contrato-assinado.pdf" }));
    expect(api.baixarDocumentoAnexado).toHaveBeenCalledWith(1, "contrato-assinado.pdf");
  });

  it("sem a permissão de baixar, some o botão e diz qual permissão falta", async () => {
    vi.mocked(api.documentos).mockResolvedValue([DOC]);
    abrir(LEITURA);
    expect(await screen.findByText("contrato-assinado.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Baixar/ })).not.toBeInTheDocument();
    expect(screen.getByText(/baixar PDF assinado/)).toBeInTheDocument();
  });

  it("sem ver contratos, ainda mostra os PDFs", async () => {
    vi.mocked(api.documentos).mockResolvedValue([DOC]);
    vi.mocked(api.contratos).mockRejectedValue(new ErroDaApi(403, "sem permissão"));
    abrir(LEITURA);
    expect(await screen.findByText("Contrato · sem escopo")).toBeInTheDocument();
  });

  it("vazio, carregando e erro com tentar de novo", async () => {
    vi.mocked(api.documentos).mockResolvedValueOnce([]);
    const { unmount } = render(
      <ProvedorDeAcesso eu={ADMIN}>
        <DocumentosDoGrupo grupoId={3} propostas={[]} aoAbrirContrato={vi.fn()} aoAbrirOportunidade={vi.fn()} />
      </ProvedorDeAcesso>,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("Nenhum PDF neste grupo")).toBeInTheDocument();
    unmount();

    vi.mocked(api.documentos).mockRejectedValueOnce(new ErroDaApi(500, "Falha ao carregar os documentos.")).mockResolvedValueOnce([DOC]);
    abrir();
    expect(await screen.findByText("Falha ao carregar os documentos.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Tentar de novo/i }));
    expect(await screen.findByText("contrato-assinado.pdf")).toBeInTheDocument();
  });
});
