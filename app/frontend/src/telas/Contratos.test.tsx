import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ContratoDetalhe, ContratoResumo } from "../api/tipos";
import { Contratos } from "./Contratos";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      contratos: vi.fn(), contrato: vi.fn(), editarContrato: vi.fn(), registrarEventoDeContrato: vi.fn(),
      mrr: vi.fn().mockResolvedValue(null),
    },
  };
});

const resumo = (o: Partial<ContratoResumo> = {}): ContratoResumo => ({
  id: 7, grupo_id: 1, grupo_nome: "Alfa", oportunidade_id: 1, escopo: "BPO", preco_mensal: "1000.00",
  preco_anual: "12000.00", empresa_id: null, anterior_ao_crm: false, data_inicio: null, data_fim: null, situacao: "Aguardando assinatura", signatario: null, ...o,
});
const detalhe = (o: Partial<ContratoDetalhe> = {}): ContratoDetalhe => ({ ...resumo(o), documento_assinado: null, observacao: null, eventos: [], ...o } as ContratoDetalhe);

async function abrir(c: Partial<ContratoDetalhe> = {}) {
  vi.mocked(api.contratos).mockResolvedValue({ total: 1, itens: [resumo(c)] } as never);
  vi.mocked(api.contrato).mockResolvedValue(detalhe(c));
  render(<Contratos listas={null} />);
  await userEvent.click(await screen.findByRole("button", { name: "Abrir" }));
  await screen.findByLabelText("Situação", { selector: "#c-situacao" });
}

describe("Contratos — vigência na assinatura (25/09/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("o campo de início se chama data da assinatura", async () => {
    await abrir();
    expect(screen.getByLabelText(/data da assinatura \(início da vigência\)/i)).toBeInTheDocument();
  });

  it("não deixa salvar como Ativo sem a data da assinatura", async () => {
    await abrir();
    await userEvent.selectOptions(screen.getByLabelText("Situação", { selector: "#c-situacao" }), "Ativo");
    expect(screen.getByRole("alert")).toHaveTextContent(/informe a data da assinatura/i);
    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeDisabled();
  });

  it("libera quando a data da assinatura é preenchida", async () => {
    await abrir();
    await userEvent.selectOptions(screen.getByLabelText("Situação", { selector: "#c-situacao" }), "Ativo");
    await userEvent.type(screen.getByLabelText(/data da assinatura/i), "2026-03-01");
    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeEnabled();
  });

  it("depois de assinado, preço e fim ficam travados e a tela manda usar evento", async () => {
    await abrir({ situacao: "Ativo", data_inicio: "2026-03-01", data_fim: "2027-03-01" });
    expect(screen.getByLabelText("Preço mensal")).toBeDisabled();
    expect(screen.getByLabelText("Preço anual")).toBeDisabled();
    expect(screen.getByLabelText("Fim da vigência")).toBeDisabled();
    expect(screen.getByText(/só mudam por um evento/i)).toBeInTheDocument();
  });

  it("encerrar não é opção da lista: só por evento com motivo", async () => {
    await abrir({ situacao: "Ativo", data_inicio: "2026-03-01" });
    const opcoes = Array.from(screen.getByLabelText("Situação", { selector: "#c-situacao" }).querySelectorAll("option")).map((o) => o.textContent);
    expect(opcoes).not.toContain("Encerrado");
  });

  it("contrato da carteira anterior ativa sem data de assinatura e a lista diz que é anterior ao CRM", async () => {
    await abrir({ anterior_ao_crm: true, situacao: "Aguardando assinatura" });
    expect(screen.getByText("anterior ao CRM")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Situação", { selector: "#c-situacao" }), "Ativo");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeEnabled();
  });

  it("antes de assinar, o preço continua editável", async () => {
    await abrir();
    expect(screen.getByLabelText("Preço mensal")).toBeEnabled();
  });
});
