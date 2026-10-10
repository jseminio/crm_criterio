/** "Ver composição" dos números do funil (10/10/2026): a lista de oportunidades, com o resumo que repete o
 * número do card e quem fica fora da conta dito em palavra, não só pela cor. */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Indicadores, ItemDaComposicao } from "../api/tipos";
import { ComposicaoDoFunil } from "./ComposicaoDoFunil";
import { FILTROS_VAZIOS } from "./Filtros";
import { Numeros } from "./Numeros";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { indicadores: vi.fn(), composicaoDoFunil: vi.fn() } };
});
vi.mock("./MrrDaCarteira", () => ({ MrrDaCarteira: () => null }));

const item = (o: Partial<ItemDaComposicao>): ItemDaComposicao => ({
  id: 1, nome: "Alfa BPO", grupo: "Grupo Alfa", servico: "BPO Contábil", situacao: "Enviar proposta", captador: "EL",
  tipo_canal: "Sócios", data_colocacao: "2026-03-01", data_aceite: null, proxima_acao: null, entra: true,
  parte: "Enviar proposta", valor: "5000.00", anual: "65000.00", falta: [], ...o,
});

describe("Composição do funil", () => {
  beforeEach(() => vi.clearAllMocks());

  it("em aberto: lista as propostas com mensal e anual e o total do card", async () => {
    vi.mocked(api.composicaoDoFunil).mockResolvedValue({ indicador: "em_aberto", itens: [
      item({}), item({ id: 2, nome: "Alfa DP", servico: "DP", valor: "1200.00", anual: null }),
    ] });
    render(<ComposicaoDoFunil indicador="em_aberto" filtros={{ captador: ["EL"] }} />);
    expect(await screen.findByText(/2 propostas · R\$ 6.200,00 por mês · R\$ 65.000,00 ao ano/)).toBeInTheDocument();
    expect(api.composicaoDoFunil).toHaveBeenCalledWith("em_aberto", { captador: ["EL"] }, undefined);
    expect(screen.getByText("Alfa DP")).toBeInTheDocument();
  });

  it("conversão: diz aceita ou não em palavra e calcula o mesmo percentual", async () => {
    vi.mocked(api.composicaoDoFunil).mockResolvedValue({ indicador: "taxa_de_conversao", itens: [
      item({ situacao: "Aceita", parte: "Aceita" }), item({ id: 2, situacao: "Perdida", parte: "Perdida", entra: false }),
    ] });
    render(<ComposicaoDoFunil indicador="taxa_de_conversao" filtros={{}} />);
    expect(await screen.findByText(/1 aceita de 2 decididas · 50,0%/)).toBeInTheDocument();
    expect(screen.getByText("Perdida")).toBeInTheDocument();
  });

  it("volumetria: diz o que falta preencher", async () => {
    vi.mocked(api.composicaoDoFunil).mockResolvedValue({ indicador: "cobertura_volumetria", itens: [
      item({ entra: false, falta: ["empregados_clt", "pagamentos_mes"] }),
    ] });
    render(<ComposicaoDoFunil indicador="cobertura_volumetria" filtros={{}} />);
    expect(await screen.findByText("falta: empregados CLT, pagamentos")).toBeInTheDocument();
  });

  it("o card Em aberto abre a composição no painel", async () => {
    vi.mocked(api.indicadores).mockResolvedValue({
      em_aberto: { quantas: 2, valor_mensal: "6200", valor_anual: "65000", sem_preco_mensal: 0, com_preco_mensal: 2 },
      aceitas: { quantas: 0, valor_mensal: "0", valor_anual: "0", sem_preco_mensal: 0, com_preco_mensal: 0 },
      aceitas_com_data_de_aceite: 0,
      ciclo_medio: { calculavel: false, dias: null, amostra: 0, aceitas_sem_as_duas_datas: 0 },
      taxa_de_conversao: { aceitas: 0, decididas: 0, percentual: null, calculavel: false, abaixo_do_alerta: null, atingiu_a_meta: null },
      cobertura: { em_aberto_com_proxima_acao: 0, em_aberto_total: 2, com_volumetria_completa: 0, total: 2,
        percentual_com_proxima_acao: "0", percentual_com_volumetria_completa: "0" },
      dependencia_de_canal: { da_rede_de_socios: 0, total: 2, percentual: "0" },
      ticket_recorrente: { quantas: 0, clientes: 0, valor_mensal: "0", ticket_medio: null, mediana: null, maior_valor: null, participacao_do_maior: null, calculavel: false },
    } as Indicadores);
    vi.mocked(api.composicaoDoFunil).mockResolvedValue({ indicador: "em_aberto", itens: [item({})] });
    render(<Numeros filtros={FILTROS_VAZIOS} />);
    const card = (await screen.findByText("Em aberto")).closest("section")!;
    fireEvent.click(within(card).getByRole("button", { name: "Ver composição (2)" }));
    const painel = await screen.findByRole("dialog", { name: "Em aberto" });
    expect(await within(painel).findByText("Alfa BPO")).toBeInTheDocument();
  });
});
