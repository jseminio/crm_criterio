/** A tela do SDR de IA: painel, estados da lista e custos.
 *
 * O que mais importa aqui é a regra de sempre do CRM: número sem base não vira
 * zero. Taxa sem denominador, nota que não existe e custo sem parâmetro
 * aparecem como frase, dizendo o que falta.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { PainelDoSdr } from "../api/tipos";
import { Sdr } from "./Sdr";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      painelDoSdr: vi.fn(),
      parametrosDoSdr: vi.fn(),
      gravarParametrosDoSdr: vi.fn(),
      midia: vi.fn(),
      gravarMidia: vi.fn(),
      leads: vi.fn(),
    },
  };
});

const taxa = (numerador: number, denominador: number) => ({
  numerador,
  denominador,
  valor: denominador ? (100 * numerador) / denominador : null,
});

function painel(extra: Partial<PainelDoSdr> = {}): PainelDoSdr {
  return {
    mes: "2026-09",
    origem: null,
    leads: 560,
    responderam: 232,
    com_desfecho: 232,
    em_andamento: 0,
    qualificados: 80,
    fora_do_perfil: 92,
    reunioes: 49,
    qualificados_sobre_leads: taxa(80, 560),
    qualificados_sobre_responderam: taxa(80, 232),
    qualificacao_concluida: taxa(172, 232),
    transbordo: taxa(38, 232),
    parou: taxa(22, 232),
    reunioes_sobre_qualificados: taxa(49, 80),
    indicador_qualificacao: { valor: 74.14, avaliacao: "Na meta", meta: "meta de 70%" },
    indicador_transbordo: { valor: 16.38, avaliacao: "Na meta", meta: "limite de 20%" },
    indicador_reuniao: { valor: 61.25, avaliacao: "Na meta", meta: "meta de 60% com reunião" },
    tma_segundos: 470,
    primeira_resposta: { valor: 41, avaliacao: "Na meta", meta: "alvo de 60 s" },
    csat: { valor: 4.4, avaliacao: "Na meta", meta: "alvo de 4,0" },
    notas: 97,
    satisfeitos: taxa(83, 97),
    por_origem: [
      {
        origem: "Tráfego pago · Meta Ads", leads: 150, responderam: taxa(108, 150),
        qualificados: taxa(34, 150), reunioes: 21, midia: "6800.00", custo_por_lead: "45.33",
        custo_por_qualificado: "200.00", avaliacao_resposta: "Na meta",
        avaliacao_qualificados: "Na meta", avaliacao_custo: "Na meta",
      },
      {
        origem: "Leads frios", leads: 300, responderam: taxa(36, 300), qualificados: taxa(12, 300),
        reunioes: 6, midia: null, custo_por_lead: null, custo_por_qualificado: null,
        avaliacao_resposta: "Na meta", avaliacao_qualificados: "Na meta", avaliacao_custo: null,
      },
    ],
    interesses: [{ nome: "Trocar de contador", quantidade: 82 }],
    confianca: {
      media: 0.85, respostas: 2140,
      faixas: [{ nome: "0,9 a 1,0", quantidade: 1177 }, { nome: "abaixo de 0,6", quantidade: 171 }],
      abaixo_de_0_6: taxa(171, 2140),
    },
    falhas_por_resposta: taxa(71, 2140),
    falhas_por_conversa: taxa(29, 232),
    indicador_falhas: { valor: 12.5, avaliacao: "Entre a meta e o alerta", meta: "limite de 10%" },
    termos: [{ nome: "fator r", quantidade: 19 }, { nome: "holding familiar", quantidade: 16 }],
    funil: [
      { nome: "Lead recebido ou contatado", leads: 560, saidas: [{ nome: "não responderam", quantidade: 328 }] },
      { nome: "Respondeu à IA", leads: 232, saidas: [] },
    ],
    gatilhos: [{ nome: "Perguntou o preço", quantidade: 10 }],
    descartes: [{ nome: "Porte abaixo do mínimo", quantidade: 31 }],
    tom: [{ nome: "Positivo", quantidade: 94 }, { nome: "Neutro", quantidade: 107 }],
    portes: [{ nome: "Médio", quantidade: 32 }],
    destinos: [
      { destino: "Consultoria (C2)", transbordos: 9, atendidos: 9, espera_media_min: 26, avaliacao: "Entre a meta e o alerta" },
    ],
    com_dados_da_empresa: 188,
    oportunidades: 80,
    custo_poupado: {
      calculavel: true, falta: [], conversas_concluidas: 172, custo_por_conversa: "18.75",
      bruto: "3225.00", custo_ia: "235.20", liquido: "2989.80", mensagens_sem_custo: 0,
    },
    anterior: { qualificados: 68, qualificacao_concluida: 71.3, transbordo: 17.9, tma_segundos: 505, csat: 4.2 },
    ...extra,
  };
}

describe("painel", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra os números do topo com a meta escrita, não só a cor", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel());
    render(<Sdr listas={null} />);

    expect(await screen.findByText("Leads qualificados pela IA")).toBeInTheDocument();
    expect(screen.getByText("74,1%")).toBeInTheDocument();
    expect(screen.getByText("Na meta · meta de 70%")).toBeInTheDocument();
    expect(screen.getByText("7 min 50 s")).toBeInTheDocument();
    expect(screen.getByText(/1ª resposta em 41 s · Na meta/)).toBeInTheDocument();
  });

  it("compara com o mês anterior", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel());
    render(<Sdr listas={null} />);

    expect(await screen.findByText("+12")).toBeInTheDocument();
    expect(screen.getByText("+2,8 p.p.")).toBeInTheDocument();
    expect(screen.getByText("−35 s")).toBeInTheDocument();
    expect(screen.getAllByText(/sobre agosto\/2026/).length).toBeGreaterThan(0);
  });

  it("taxa sem base aparece como frase, nunca como zero", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(
      painel({
        com_desfecho: 0,
        qualificacao_concluida: taxa(0, 0),
        transbordo: taxa(0, 0),
        indicador_qualificacao: { valor: null, avaliacao: null, meta: "meta de 70%" },
        csat: { valor: null, avaliacao: null, meta: "alvo de 4,0" },
        notas: 0,
        satisfeitos: taxa(0, 0),
        anterior: null,
      }),
    );
    render(<Sdr listas={null} />);

    expect(await screen.findAllByText("Nenhuma conversa terminou ainda")).toHaveLength(2);
    expect(screen.getByText("Nenhuma nota no mês")).toBeInTheDocument();
    expect(screen.queryByText("0,0%")).not.toBeInTheDocument();
  });

  it("custo poupado sem parâmetro diz o que falta", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(
      painel({
        custo_poupado: {
          calculavel: false, falta: ["o custo de uma hora de SDR", "a cotação do dólar"],
          conversas_concluidas: 172, custo_por_conversa: null, bruto: null, custo_ia: null,
          liquido: null, mensagens_sem_custo: 0,
        },
      }),
    );
    render(<Sdr listas={null} />);

    expect(await screen.findByText("Falta definir")).toBeInTheDocument();
    expect(screen.getByText(/o custo de uma hora de SDR, a cotação do dólar/)).toBeInTheDocument();
  });

  it("mostra a conta do custo poupado", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel());
    render(<Sdr listas={null} />);

    const conta = await screen.findByText(/172 conversas concluídas/);
    expect(conta.textContent).toMatch(/R\$\s18,75/);
    expect(conta.textContent).toMatch(/R\$\s3\.225,00/);
    expect(conta.textContent).toMatch(/R\$\s2\.989,80/);
  });

  it("o funil diz quem saiu e por quê", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel());
    render(<Sdr listas={null} />);

    expect(await screen.findByText(/328 não responderam/)).toBeInTheDocument();
  });

  it("o lead frio aparece sem mídia", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel());
    render(<Sdr listas={null} />);

    const linha = (await screen.findByRole("cell", { name: "Leads frios" })).closest("tr")!;
    expect(within(linha).getByText("sem mídia lançada")).toBeInTheDocument();
  });

  it("espera acima do alvo ganha etiqueta com a palavra", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel());
    render(<Sdr listas={null} />);

    const linha = (await screen.findByText("Consultoria (C2)")).closest("tr")!;
    expect(within(linha).getByText("Entre a meta e o alerta · alvo de 15 min")).toBeInTheDocument();
  });

  it("sem lead no mês explica de onde os dados vêm", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel({ leads: 0 }));
    render(<Sdr listas={null} />);

    expect(await screen.findByText(/Nenhum lead chegou em/)).toBeInTheDocument();
    expect(screen.getByText(/integração do WhatsApp e do e-mail/)).toBeInTheDocument();
  });

  it("vazio por filtro oferece limpar o filtro", async () => {
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel({ leads: 0 }));
    render(<Sdr listas={null} />);
    await screen.findByText(/Nenhum lead chegou em/);

    await userEvent.selectOptions(screen.getByLabelText("Origem"), "frio");

    expect(await screen.findByRole("button", { name: "Limpar filtros" })).toBeInTheDocument();
    expect(api.painelDoSdr).toHaveBeenLastCalledWith(expect.objectContaining({ origem: "frio" }));
  });

  it("erro tem tentar de novo", async () => {
    vi.mocked(api.painelDoSdr).mockRejectedValue(new ErroDaApi(0, "Não consegui falar com o servidor."));
    render(<Sdr listas={null} />);

    expect(await screen.findByText("Não consegui falar com o servidor.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tentar de novo" })).toBeInTheDocument();
  });
});

describe("custos e mídia", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.painelDoSdr).mockResolvedValue(painel());
    vi.mocked(api.parametrosDoSdr).mockResolvedValue({
      custo_hora_sdr: null, minutos_por_conversa: null, cotacao_dolar: null,
      atualizado_por: null, atualizado_em: null,
    });
    vi.mocked(api.midia).mockResolvedValue([]);
  });

  async function abrirCustos() {
    render(<Sdr listas={null} />);
    await userEvent.click(screen.getByRole("tab", { name: "Custos e mídia" }));
    await screen.findByLabelText(/custo de uma hora de SDR/i);
  }

  it("grava os parâmetros como número", async () => {
    vi.mocked(api.gravarParametrosDoSdr).mockResolvedValue({} as never);
    await abrirCustos();

    await userEvent.type(screen.getByLabelText(/custo de uma hora de SDR/i), "45.00");
    await userEvent.type(screen.getByLabelText(/minutos que um SDR/i), "25");
    await userEvent.click(screen.getByRole("button", { name: "Salvar parâmetros" }));

    await waitFor(() => expect(api.gravarParametrosDoSdr).toHaveBeenCalledOnce());
    expect(vi.mocked(api.gravarParametrosDoSdr).mock.calls[0][0]).toEqual({
      custo_hora_sdr: "45.00",
      minutos_por_conversa: 25,
      cotacao_dolar: null,
    });
  });

  it("lança o investimento do mês e só libera com canal e valor", async () => {
    vi.mocked(api.gravarMidia).mockResolvedValue({} as never);
    await abrirCustos();

    const lancar = screen.getByRole("button", { name: "Lançar investimento" });
    expect(lancar).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Canal"), "Meta Ads");
    await userEvent.type(screen.getByLabelText("Valor (R$)"), "6800");
    await userEvent.click(lancar);

    await waitFor(() => expect(api.gravarMidia).toHaveBeenCalledOnce());
    expect(vi.mocked(api.gravarMidia).mock.calls[0][0]).toMatchObject({ canal: "Meta Ads", valor: "6800" });
  });

  it("cada painel tem uma ação primária só", async () => {
    await abrirCustos();

    const parametros = screen.getByRole("region", { name: "Custo poupado" });
    const midia = screen.getByRole("region", { name: "Investimento em mídia" });
    expect(parametros.querySelectorAll(".botao-primario")).toHaveLength(1);
    expect(midia.querySelectorAll(".botao-primario")).toHaveLength(1);
  });
});
