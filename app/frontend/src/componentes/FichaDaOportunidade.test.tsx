import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { CampoDaFicha, Ficha } from "../api/tipos";
import { FichaDaOportunidade } from "./FichaDaOportunidade";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { ficha: vi.fn(), corrigirFicha: vi.fn() } };
});

const campo = (c: Partial<CampoDaFicha>): CampoDaFicha => ({
  chave: "x", rotulo: "X", tipo: "texto", opcoes: [], sub: false, valor: null, origem: null, por: null, em: null, ...c,
});

const FICHA: Ficha = {
  questionario_em: "2026-10-01T10:00:00", respondidas: 3, total: 6, revisores: ["Eduardo", "Karine"],
  secoes: [
    { numero: 1, titulo: "Empresa, escopo e responsáveis", no_escopo: true, conta_pendencia: true, respondidas: 2, total: 2,
      campos: [
        campo({ chave: "razao_social", rotulo: "Razão social", valor: "Exemplo Alfa Ltda", origem: "Questionário", em: "2026-10-01T10:00:00" }),
        campo({ chave: "servicos", rotulo: "Serviços no escopo", tipo: "varias", opcoes: ["Contábil", "Fiscal", "Folha / DP"],
          valor: ["Contábil"], origem: "Questionário", em: "2026-10-01T10:00:00" }),
      ] },
    { numero: 4, titulo: "Contábil e gerencial", no_escopo: true, conta_pendencia: true, respondidas: 1, total: 4,
      campos: [
        campo({ chave: "plano_contas", rotulo: "Plano de contas com centro de custo?", tipo: "uma", opcoes: ["Não", "Sim"],
          valor: "Sim", origem: "Entrevista", por: "Karine", em: "2026-10-02T09:00:00" }),
        campo({ chave: "auditada", rotulo: "A empresa é auditada?", tipo: "uma", opcoes: ["Sim", "Não"] }),
        campo({ chave: "vol.lancamentos", rotulo: "Lançamentos contábeis", tipo: "numero" }),
        campo({ chave: "fechamento", rotulo: "Fechamento", tipo: "texto_longo" }),
      ] },
    { numero: 6, titulo: "Folha de pagamento e departamento pessoal", no_escopo: true, conta_pendencia: true, respondidas: 0, total: 0, campos: [] },
    { numero: 7, titulo: "Financeiro", no_escopo: false, conta_pendencia: false, respondidas: 0, total: 4, campos: [] },
    { numero: 9, titulo: "Acessos, documentos e estrutura — para a implantação", no_escopo: true, conta_pendencia: false,
      respondidas: 1, total: 5, campos: [] },
  ],
};

describe("aba Ficha", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
    vi.mocked(api.ficha).mockResolvedValue(FICHA);
  });

  it("resume o que foi respondido e diz o estado de cada seção em texto", async () => {
    render(<FichaDaOportunidade oportunidadeId={10} />);
    expect(await screen.findByText(/perguntas respondidas/)).toHaveTextContent("3 de 6 perguntas respondidas");
    expect(screen.getByText(/questionário de 01\/10\/2026/)).toBeInTheDocument();
    expect(screen.getByText("✓ 2 de 2")).toBeInTheDocument();
    expect(screen.getByText("◐ 1 de 4")).toBeInTheDocument();
    expect(screen.getByText("fora do escopo")).toBeInTheDocument();
    expect(screen.getByText("para a implantação · 1 de 5")).toBeInTheDocument();
  });

  it("cada resposta diz de onde veio", async () => {
    render(<FichaDaOportunidade oportunidadeId={10} />);
    const plano = (await screen.findByLabelText("Plano de contas com centro de custo?")).closest(".ficha-pergunta") as HTMLElement;
    expect(within(plano).getByText(/Entrevista/).parentElement).toHaveTextContent("Entrevista · Karine · 02/10/2026");
    const razao = screen.getByLabelText("Razão social").closest(".ficha-pergunta") as HTMLElement;
    expect(razao).toHaveTextContent("Questionário · 01/10/2026");
    expect(screen.getByLabelText("A empresa é auditada?").closest(".ficha-pergunta")).toHaveTextContent("· sem resposta");
  });

  it("corrigir grava como entrevista de quem preenche, e avisa quem mudou", async () => {
    const aoMudar = vi.fn();
    vi.mocked(api.corrigirFicha).mockResolvedValue(FICHA);
    render(<FichaDaOportunidade oportunidadeId={10} aoMudar={aoMudar} />);
    await userEvent.selectOptions(await screen.findByLabelText("Quem preenche"), "Karine");
    await userEvent.selectOptions(screen.getByLabelText("A empresa é auditada?"), "Sim");
    expect(api.corrigirFicha).toHaveBeenCalledWith(10, "auditada", "Sim", "Karine");
    expect(aoMudar).toHaveBeenCalled();
    expect(localStorage.getItem("crm.quem_preenche")).toBe("Karine");
  });

  it("texto salva ao sair do campo, número aceita só dígitos e múltipla escolha manda a lista", async () => {
    vi.mocked(api.corrigirFicha).mockResolvedValue(FICHA);
    render(<FichaDaOportunidade oportunidadeId={10} />);
    const lanc = await screen.findByLabelText("Lançamentos contábeis");
    fireEvent.change(lanc, { target: { value: "2.500" } });
    expect(lanc).toHaveValue("2500");
    fireEvent.blur(lanc);
    expect(api.corrigirFicha).toHaveBeenCalledWith(10, "vol.lancamentos", "2500", "Eduardo");
    await userEvent.click(screen.getByRole("checkbox", { name: "Folha / DP" }));
    expect(api.corrigirFicha).toHaveBeenLastCalledWith(10, "servicos", ["Contábil", "Folha / DP"], "Eduardo");
  });

  it("sem mudança não grava; recusa do servidor aparece no campo", async () => {
    vi.mocked(api.corrigirFicha).mockRejectedValue(new ErroDaApi(422, "Lançamentos contábeis: use um número inteiro"));
    render(<FichaDaOportunidade oportunidadeId={10} />);
    fireEvent.blur(await screen.findByLabelText("Razão social"));
    expect(api.corrigirFicha).not.toHaveBeenCalled();
    const lanc = screen.getByLabelText("Lançamentos contábeis");
    fireEvent.change(lanc, { target: { value: "12" } });
    fireEvent.blur(lanc);
    expect(await screen.findByRole("alert")).toHaveTextContent("✗ Lançamentos contábeis: use um número inteiro");
  });
});
