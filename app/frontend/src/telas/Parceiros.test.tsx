/** A tela Parceiros (19/10/2026): indicadores com composição, filtro de período, Kanban e Grade com ordenação, o
 * arrasto só nas etapas manuais e o painel do parceiro. */

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { IndicadoresDosParceiros, ParceiroDetalhe, ParceiroResumo } from "../api/tipos";
import { Parceiros, paraConsulta } from "./Parceiros";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      parceiros: vi.fn(), indicadoresDosParceiros: vi.fn(), composicaoDosParceiros: vi.fn(), parceiro: vi.fn(),
      moverParceiro: vi.fn(), criarParceiro: vi.fn(), editarParceiro: vi.fn(), feesDosParceiros: vi.fn().mockResolvedValue([]),
      conferenciaDosParceiros: vi.fn().mockResolvedValue([]),
      enderecoDaExportacaoDosParceiros: real.api.enderecoDaExportacaoDosParceiros,
    },
  };
});

const m = vi.mocked(api);

function parceiro(extra: Partial<ParceiroResumo>): ParceiroResumo {
  return { id: 1, nome: "MNGM", tipo_pessoa: "PJ", nivel: "Estruturado", acordo: "Informal, com fee", etapa: "Produtivo",
    socio_responsavel: "Eduardo", indicacoes: 4, abertas: 1, fechadas: 2, mrr: "21000.00", pontual: "0.00",
    proximo_follow_up: null, proximo_follow_up_em: null, ...extra };
}

const NUMEROS: IndicadoresDosParceiros = {
  ativos: 2, indicacoes: 9, conversao: "50.0", mrr: "35500.00", sem_contrato: 2, fees: "12000.00", fees_quantos: 1,
  sem_follow_up: 1, follow_up_atrasado: 1,
  explicacoes: { ativos: "Parceiros com indicação.", indicacoes: "Indicações válidas.", conversao: "Fechadas ÷ decididas.",
    mrr: "Parcela × 13 ÷ 12.", sem_contrato: "Fila da regularização.", fees: "Esperando o sócio.",
    sem_follow_up: "Sem data marcada." },
};

beforeEach(() => {
  vi.clearAllMocks();
  m.parceiros.mockResolvedValue([
    parceiro({}),
    parceiro({ id: 2, nome: "Molina", tipo_pessoa: "PF", mrr: "14500.00", indicacoes: 5 }),
    parceiro({ id: 3, nome: "Ficus", etapa: "Qualificado", nivel: "Estratégico", acordo: "Contrato em minuta",
      indicacoes: 0, abertas: 0, fechadas: 0, mrr: "0.00" }),
  ]);
  m.indicadoresDosParceiros.mockResolvedValue(NUMEROS);
  m.feesDosParceiros.mockResolvedValue([]);
  m.conferenciaDosParceiros.mockResolvedValue([]);
});

describe("Parceiros", () => {
  it("mostra os indicadores e a composição com o total", async () => {
    m.composicaoDosParceiros.mockResolvedValue([
      { parceiro: "MNGM", detalhe: "BPO Tupi", valor: "21000.00", referencia: "Aceita" },
      { parceiro: "Molina", detalhe: "BPO Vezzo", valor: "14500.00", referencia: "Aceita" },
    ]);
    render(<Parceiros />);
    const mrr = (await screen.findByText("MRR originado")).closest("section")!;
    expect(within(mrr).getByText("R$ 35.500,00")).toBeTruthy();
    fireEvent.click(within(mrr).getByRole("button", { name: /Ver composição/ }));
    expect(await screen.findByText("BPO Vezzo")).toBeTruthy();
    expect(m.composicaoDosParceiros).toHaveBeenCalledWith("mrr", expect.any(Object));
    expect(screen.getAllByText("R$ 35.500,00").length).toBeGreaterThan(1);
  });

  it("Kanban por etapa e Grade com ordenação crescente e decrescente", async () => {
    render(<Parceiros />);
    const produtivo = await screen.findByRole("region", { name: "Produtivo" });
    expect(within(produtivo).getByText("MNGM")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Qualificado" })).getByText("Ficus")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Grade/ }));
    const nomes = () => screen.getAllByRole("row").slice(1).map((r) => r.querySelector("td")!.textContent);
    expect(nomes()[0]).toContain("MNGM");
    fireEvent.click(screen.getByRole("button", { name: /MRR originado/ }));
    expect(nomes()[0]).toContain("Ficus");
    fireEvent.click(screen.getByRole("button", { name: /MRR originado/ }));
    expect(nomes()[0]).toContain("MNGM");
  });

  it("período pela data de fechamento vai para a API", async () => {
    render(<Parceiros />);
    await screen.findByRole("region", { name: "Produtivo" });
    fireEvent.change(screen.getByLabelText("Período"), { target: { value: "ano" } });
    fireEvent.change(await screen.findByLabelText("Data de"), { target: { value: "fechamento" } });
    await waitFor(() => expect(m.parceiros).toHaveBeenLastCalledWith(expect.objectContaining({ data_tipo: "fechamento" })));
    const ultima = m.parceiros.mock.calls.at(-1)![0]!;
    expect(ultima.data_de?.endsWith("-01-01")).toBe(true);
    expect(ultima.data_ate?.endsWith("-12-31")).toBe(true);
  });

  it("sem período, a consulta não manda datas", () => {
    expect(paraConsulta({ busca: " x ", nivel: "", acordo: "Sem acordo", periodo: "", dataTipo: "fechamento", dataDe: "", dataAte: "" }))
      .toEqual({ busca: "x", nivel: undefined, acordo: ["Sem acordo"], data_tipo: undefined, data_de: undefined, data_ate: undefined });
  });

  it("arrastar para etapa que sai dos dados avisa e não chama a API", async () => {
    render(<Parceiros />);
    const ficus = await screen.findByText("Ficus");
    const dados = { effectAllowed: "", dropEffect: "", setData: vi.fn() };
    fireEvent.dragStart(ficus.closest("button")!, { dataTransfer: dados });
    const produtivo = screen.getByRole("region", { name: "Produtivo" });
    fireEvent.dragOver(produtivo, { dataTransfer: dados });
    fireEvent.drop(produtivo, { dataTransfer: dados });
    expect((await screen.findByRole("alert")).textContent).toContain("muda sozinha pelos dados");
    expect(m.moverParceiro).not.toHaveBeenCalled();

    fireEvent.dragStart(screen.getByText("Ficus").closest("button")!, { dataTransfer: dados });
    const mapeado = screen.getByRole("region", { name: "Mapeado" });
    fireEvent.dragOver(mapeado, { dataTransfer: dados });
    fireEvent.drop(mapeado, { dataTransfer: dados });
    await waitFor(() => expect(m.moverParceiro).toHaveBeenCalledWith(3, "Mapeado"));
  });

  it("abre o painel do parceiro com o fee combinado no acordo informal", async () => {
    const detalhe: ParceiroDetalhe = {
      id: 1, nome: "MNGM", tipo_pessoa: "PJ", documento: null, tipo: null, nivel: "Estruturado", etapa: "Produtivo",
      etapa_manual: "Mapeado", acordo: "Informal, com fee", contrato_assinado_em: null,
      regra_combinada: "1ª parcela de cada contrato", combinado_por: "Eduardo", combinado_em: "2025-03-01",
      socio_responsavel: "Eduardo", perfil_pedido: null, contato: null, observacao: null, textos_do_canal: ["MNGM"],
      indicacoes: [{ oportunidade_id: 9, nome: "BPO Tupi", grupo: "Tupi", grupo_id: 3, situacao: "Em avaliação pela empresa",
        recebida_em: "2026-10-06", validada_em: null, recusada: null, vinculo_ate: null, mensal: null, anual: null, mrr: "0.00" }],
      fees: [], proximo_follow_up: "Pedir indicação", proximo_follow_up_em: "2026-01-10", cadencia_meses: 3,
      follow_ups: [{ id: 1, feito_em: "2025-10-10", resultado: "Recebeu indicação", nota: "Indicou a Tupi", registrado_por: "Eduardo" }],
    };
    m.parceiro.mockResolvedValue(detalhe);
    render(<Parceiros />);
    fireEvent.click(await screen.findByText("MNGM"));
    expect(await screen.findByDisplayValue("1ª parcela de cada contrato")).toBeTruthy();
    expect(screen.getByText("Indicações (1)")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Validar hoje" })).toBeTruthy();
    expect(screen.getByDisplayValue("Pedir indicação")).toBeTruthy();
    expect(screen.getByText(/FUP atrasado/)).toBeTruthy();
    expect(screen.getByText("Indicou a Tupi")).toBeTruthy();
  });
});
