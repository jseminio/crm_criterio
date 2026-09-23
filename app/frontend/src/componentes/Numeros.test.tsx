/** A faixa de números do funil — em especial a taxa de conversão, decidida
 * por Eduardo em 22/09/2026 (denominador = só decididas) depois de ficar
 * pendente por dois dias. Os três estados contra os limiares oficiais (meta
 * 50%, alerta <30%) precisam da palavra junto da cor — regra 4 do PAD-002. */

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Indicadores } from "../api/tipos";
import { FILTROS_VAZIOS } from "./Filtros";
import { Numeros } from "./Numeros";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { indicadores: vi.fn() } };
});

function indicadores(taxa: Partial<Indicadores["taxa_de_conversao"]> = {}, extra: Partial<Indicadores> = {}): Indicadores {
  return {
    em_aberto: { quantas: 0, valor_mensal: "0", valor_anual: "0", sem_preco_mensal: 0, com_preco_mensal: 0 },
    aceitas: { quantas: 0, valor_mensal: "0", valor_anual: "0", sem_preco_mensal: 0, com_preco_mensal: 0 },
    aceitas_com_data_de_aceite: 0,
    ciclo_medio: { calculavel: false, dias: null, amostra: 0, aceitas_sem_as_duas_datas: 0 },
    taxa_de_conversao: {
      aceitas: 0,
      decididas: 0,
      percentual: null,
      calculavel: false,
      abaixo_do_alerta: null,
      atingiu_a_meta: null,
      ...taxa,
    },
    cobertura: {
      em_aberto_com_proxima_acao: 0,
      em_aberto_total: 0,
      com_volumetria_completa: 0,
      total: 0,
      percentual_com_proxima_acao: null,
      percentual_com_volumetria_completa: null,
    },
    dependencia_de_canal: { da_rede_de_socios: 0, total: 0, percentual: null },
    ...extra,
  };
}

async function abrir(dados: Indicadores) {
  vi.mocked(api.indicadores).mockResolvedValue(dados);
  render(<Numeros filtros={FILTROS_VAZIOS} />);
  await screen.findByText("Taxa de conversão");
}

describe("Numeros — taxa de conversão", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sem nenhuma decidida, mostra não calculável, não 0%", async () => {
    await abrir(indicadores({ calculavel: false, percentual: null }));

    expect(
      screen.getByText(/não calculável — nenhuma proposta decidida/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("0%")).not.toBeInTheDocument();
  });

  it("38,1% aparece como o destaque do cartão, com vírgula, não ponto", async () => {
    await abrir(
      indicadores({
        aceitas: 40, decididas: 105, percentual: "38.1",
        calculavel: true, abaixo_do_alerta: false, atingiu_a_meta: false,
      }),
    );

    expect(screen.getByText("38,1%")).toBeInTheDocument();
    // "40 de 105 decididas" vem em vários nós de texto (JSX intercala com a
    // etiqueta) — comparamos o texto completo do parágrafo, não um nó só.
    expect(screen.getByText("Taxa de conversão").closest(".numero")).toHaveTextContent(
      "40 de 105 decididas",
    );
  });

  it("abaixo do alerta mostra a etiqueta em palavra, não só cor", async () => {
    await abrir(
      indicadores({
        aceitas: 10, decididas: 100, percentual: "10.0",
        calculavel: true, abaixo_do_alerta: true, atingiu_a_meta: false,
      }),
    );

    expect(screen.getByText("Abaixo do alerta")).toHaveClass("etiqueta-perda");
  });

  it("entre o alerta e a meta tem etiqueta própria — não é nem uma coisa nem outra", async () => {
    await abrir(
      indicadores({
        aceitas: 40, decididas: 100, percentual: "40.0",
        calculavel: true, abaixo_do_alerta: false, atingiu_a_meta: false,
      }),
    );

    expect(screen.getByText("Entre o alerta e a meta")).toHaveClass("etiqueta-espera");
  });

  it("na meta mostra etiqueta de ganho", async () => {
    await abrir(
      indicadores({
        aceitas: 50, decididas: 100, percentual: "50.0",
        calculavel: true, abaixo_do_alerta: false, atingiu_a_meta: true,
      }),
    );

    expect(screen.getByText("Na meta")).toHaveClass("etiqueta-ganho");
  });

  it("o cartão só fica com a aparência de pendência quando não é calculável", async () => {
    await abrir(
      indicadores({
        aceitas: 1, decididas: 1, percentual: "100.0",
        calculavel: true, abaixo_do_alerta: false, atingiu_a_meta: true,
      }),
    );

    const cartao = screen.getByText("Taxa de conversão").closest(".numero");
    expect(cartao).not.toHaveClass("numero-pendente");
  });
});

describe("Numeros — ciclo médio, cobertura e dependência de canal (23/09/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("ciclo médio não calculável não mostra 0 dias", async () => {
    await abrir(indicadores());

    expect(
      screen.getByText(/não calculável — nenhuma aceita com data de originação/i),
    ).toBeInTheDocument();
    expect(screen.queryByText("0 dias")).not.toBeInTheDocument();
  });

  it("ciclo médio calculável mostra os dias com vírgula", async () => {
    await abrir(
      indicadores({}, {
        ciclo_medio: { calculavel: true, dias: "61.0", amostra: 1, aceitas_sem_as_duas_datas: 0 },
      }),
    );

    expect(screen.getByText("61,0 dias")).toBeInTheDocument();
  });

  it("avisa quantas aceitas ficaram de fora por falta de data", async () => {
    await abrir(
      indicadores({}, {
        ciclo_medio: { calculavel: true, dias: "10.0", amostra: 1, aceitas_sem_as_duas_datas: 2 },
      }),
    );

    expect(screen.getByText(/2 aceitas sem as duas datas/i)).toBeInTheDocument();
  });

  it("cobertura mostra os dois percentuais", async () => {
    await abrir(
      indicadores({}, {
        cobertura: {
          em_aberto_com_proxima_acao: 3, em_aberto_total: 4,
          com_volumetria_completa: 1, total: 10,
          percentual_com_proxima_acao: "75.0", percentual_com_volumetria_completa: "10.0",
        },
      }),
    );

    expect(screen.getByText(/75,0% com próxima ação/)).toBeInTheDocument();
    expect(screen.getByText(/10,0% com ficha de/)).toBeInTheDocument();
  });

  it("dependência de canal mostra o percentual da rede dos sócios", async () => {
    await abrir(
      indicadores({}, {
        dependencia_de_canal: { da_rede_de_socios: 86, total: 154, percentual: "55.8" },
      }),
    );

    expect(screen.getByText("55,8%")).toBeInTheDocument();
    expect(screen.getByText(/86 de 154 propostas/i)).toBeInTheDocument();
  });
});
