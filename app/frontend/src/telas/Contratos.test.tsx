import { render, screen, waitFor } from "@testing-library/react";
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
      mrr: vi.fn().mockResolvedValue(null), itensDoMovimento: vi.fn().mockResolvedValue({ de: "", ate: "", itens: [] }),
    },
  };
});

const resumo = (o: Partial<ContratoResumo> = {}): ContratoResumo => ({
  id: 7, grupo_id: 1, grupo_nome: "Alfa", oportunidade_id: 1, escopo: "BPO", preco_mensal: "1000.00",
  preco_anual: "12000.00", base_do_valor: null, empresa_id: null, anterior_ao_crm: false, data_inicio: null, data_fim: null, situacao: "Aguardando assinatura", signatario: null, ...o,
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
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.mrr).mockResolvedValue(null as never);
  });

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
    await userEvent.type(screen.getByLabelText(/data da assinatura/i), "01032026");
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

describe("Contratos — mudanças de situação permitidas (01/10/2026)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.mrr).mockResolvedValue(null as never);
  });

  const opcoes = () =>
    Array.from(screen.getByLabelText("Situação", { selector: "#c-situacao" }).querySelectorAll("option")).map((o) => o.textContent);

  it("antes da assinatura: tudo menos Encerrado", async () => {
    await abrir();
    expect(opcoes()).toEqual(["Aguardando assinatura", "Ativo", "Suspenso"]);
  });

  it("assinado só alterna entre Ativo e Suspenso, sem voltar para Aguardando assinatura", async () => {
    await abrir({ situacao: "Ativo", data_inicio: "2026-03-01" });
    expect(opcoes()).toEqual(["Ativo", "Suspenso"]);
  });

  it("encerrado não se mexe: tudo travado, sem salvar", async () => {
    await abrir({ situacao: "Encerrado", data_inicio: "2026-03-01", data_fim: "2026-09-20" });
    const situacao = screen.getByLabelText("Situação", { selector: "#c-situacao" });
    await waitFor(() => expect(situacao).toBeDisabled());
    expect(opcoes()).toEqual(["Encerrado"]);
    for (const rotulo of ["Escopo", "Preço mensal", "Preço anual", /data da assinatura/i, "Fim da vigência", "Signatário"]) {
      expect(screen.getByLabelText(rotulo)).toBeDisabled();
    }
    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeDisabled();
    expect(screen.getByText(/contrato encerrado: nada mais muda/i)).toBeInTheDocument();
    expect(screen.queryByText(/só mudam por um evento/i)).toBeNull();
  });

  it("bruto ou líquido: escolhe em cada contrato, até no encerrado, e a lista avisa quando falta", async () => {
    vi.mocked(api.editarContrato).mockResolvedValue(detalhe() as never);
    vi.mocked(api.mrr).mockResolvedValue({
      atual: { valor: "0.00", contratos: 0, suspenso_valor: "0.00", suspenso_contratos: 0, sem_preco_mensal: 0, grupos: 0,
        ticket_por_grupo: null, mediana_por_grupo: null },
      movimento: { de: "2026-10-01", ate: "2026-10-02", mrr_inicio: "0.00", novo: "0.00", expansao: "0.00", reajuste: "0.00",
        contracao: "0.00", churn_cliente: "0.00", churn_criterio: "0.00", churn: "0.00", mrr_fim: "0.00", variacao: "0.00", nrr: null, grr: null },
      contratos_registrados: 1, contratos_da_carteira_anterior: 0, cobertura_completa: false, aviso: "parcial",
      meta: "400000", alerta: "200000", contra_a_meta: null, falta_para_a_meta: null,
      imposto: "0.11", contratos_liquidos: 0, contratos_sem_base: 1,
    });
    await abrir({ situacao: "Encerrado", data_inicio: "2026-03-01", preco_mensal: "8900.00" });
    expect(screen.getByText("⚠ bruto ou líquido?")).toBeInTheDocument();
    const salvar = screen.getByRole("button", { name: /salvar alterações/i });
    expect(salvar).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Líquido (sem o imposto)"));
    expect(await screen.findByText(/Entra no MRR como R\$\s*10\.000,00 bruto, com o imposto de 11%/)).toBeInTheDocument();
    expect(salvar).toBeEnabled();
    await userEvent.click(salvar);
    expect(api.editarContrato).toHaveBeenCalledWith(7, expect.objectContaining({ base_do_valor: "liquido" }));
  });

  it("a lista mostra se o preço é bruto ou líquido", async () => {
    vi.mocked(api.contratos).mockResolvedValue({ total: 2, itens: [
      resumo({ id: 1, base_do_valor: "liquido" }), resumo({ id: 2, grupo_nome: "Beta", base_do_valor: "bruto" }),
    ] } as never);
    render(<Contratos listas={null} />);
    expect(await screen.findByText("líquido")).toBeInTheDocument();
    expect(screen.getByText("bruto")).toBeInTheDocument();
  });

  it("o fim trava pelo que está gravado, não pelo que veio da lista (Renovação)", async () => {
    // A lista ainda mostra o contrato sem fim; o detalhe, depois da Renovação, já tem.
    vi.mocked(api.contratos).mockResolvedValue({
      total: 1, itens: [resumo({ situacao: "Ativo", data_inicio: "2026-03-01", data_fim: null })],
    } as never);
    vi.mocked(api.contrato).mockResolvedValue(detalhe({ situacao: "Ativo", data_inicio: "2026-03-01", data_fim: "2028-03-01" }));
    render(<Contratos listas={null} />);
    await userEvent.click(await screen.findByRole("button", { name: "Abrir" }));
    await waitFor(() => expect(screen.getByLabelText("Fim da vigência")).toBeDisabled());
  });
});
