import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ClassificacaoDaCarteira, ClienteNovo, ItemDaCarteira, Listas, NotasDoGrupo, PeriodoDeAvaliacao, PorteDoGrupo } from "../api/tipos";
import { Carteira } from "../telas/Carteira";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      classificacaoDaCarteira: vi.fn(),
      analiseDaCarteira: vi.fn().mockResolvedValue(null),
      gerarAnaliseDaCarteira: vi.fn(),
      revisoesDaCarteira: vi.fn().mockResolvedValue([]),
      registrarRevisaoDaCarteira: vi.fn(),
      editarMesDaRevisao: vi.fn(),
      editarNotasDaCarteira: vi.fn(),
      sugestaoDePorte: vi.fn(),
      editarPorte: vi.fn(),
      salvarRascunho: vi.fn(),
      simularCliente: vi.fn(),
      abrirPeriodo: vi.fn(),
      calcularCarteira: vi.fn(),
      editarJanela: vi.fn(),
    },
  };
});

const PORTE_VAZIO: PorteDoGrupo = {
  documentos_fiscais_mes: null, lancamentos_contabeis_mes: null, pagamentos_mes: null,
  contas_bancarias: null, conciliacoes_cartao_mes: null, empregados_clt: null,
  admissoes_desligamentos_mes: null, cnpjs_no_escopo: null, tomadores_de_servico: null,
  servicos_contratados_alem_do_primeiro: 0, tem_consolidacao_de_grupo: false, e_auditada: false,
  porte: null, porte_definido_por: null, porte_definido_em: null,
};
const LISTAS: Listas = {
  situacoes: [], situacoes_de_lead: [], temperaturas: [], tipos_de_canal: [], tipos_de_canal_em_operacao: [],
  motivos_de_recusa: [], motivos_de_encerramento: [], iniciativas_de_encerramento: [], papeis_de_contato: [],
  linhas_de_servico: [], situacoes_de_grupo: [], captadores: [],
  portes: ["Micro", "Pequeno", "Médio", "Grande", "Extra Grande"], servicos: [],
};
const NOTAS_VAZIO: NotasDoGrupo = {
  receita: "3.00", rentabilidade: "3.00", rentabilidade_planilha: "3.00", complexidade: "3.00", disciplina: "3.00", risco: "3.00",
  cross_sell: "3.00", adimplencia: "3.00", semaforo: 1, churn: 1, rentabilidade_da_planilha: false,
  atribuido_por: null, motivo: null, registrado_em: "2026-07-31T00:00:00",
};
const item = (o: Partial<ItemDaCarteira> = {}): ItemDaCarteira => ({
  grupo_id: 1, grupo_nome: "Alfa", receita_mensal: "1000.00", score: "3.00", classe: "B", classe_efetiva: "B1",
  alerta_de_churn: null, em_cobranca: false, eixo_de_acao: "Sem urgência de churn", semaforo: 1, churn: 1,
  sem_contrato_ativo: false, empresas: [], notas: NOTAS_VAZIO, porte: PORTE_VAZIO, ...o,
});
const resposta = (o: Partial<ClassificacaoDaCarteira> = {}): ClassificacaoDaCarteira => ({
  referencia: "2026-07-31", versao_dos_parametros: "v1", isc: null, retrato: null,
  por_classe: { B: 1 },
  distribuicao_por_classe: [
    { classe: "A", minimo: 15, maximo: 20, unidades: 0, percentual: "0.0", dentro_da_meta: false },
    { classe: "B", minimo: 35, maximo: 40, unidades: 1, percentual: "100.0", dentro_da_meta: false },
    { classe: "C", minimo: 40, maximo: 50, unidades: 0, percentual: "0.0", dentro_da_meta: false },
  ],
  itens: [item()], avisos: [], ...o,
});

// "Nota calculada: X (…)" tem o número dentro de um <strong>, então o texto fica partido em nós
// diferentes — o matcher padrão do Testing Library não junta os pedaços. Comparamos pelo texto
// inteiro do parágrafo.
function nota(texto: string) {
  return (_: string, elemento: Element | null) =>
    elemento?.tagName === "P" && (elemento.textContent ?? "").replace(/\s+/g, " ").trim() === texto;
}

const PERIODO: PeriodoDeAvaliacao = {
  id: 1, mes_de_referencia: "2026-10-01", aberto_em: "2026-10-01T09:00:00", aberto_por: "Eduardo Luiz",
  margem_minima: "0.6000", margem_alvo: "0.7000", calculado_em: null, calculado_por: null,
  grupos: 1, completos: 0, abas: 6, pendentes: [{ grupo_id: 1, grupo_nome: "Alfa", preenchidas: 0, abas: 6, novo: false }],
};

async function abrirComPeriodo() {
  vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({ periodo: PERIODO }));
  render(<Carteira listas={LISTAS} />);
  await screen.findByText(/▸ Alfa/);
  await userEvent.click(screen.getByRole("button", { name: "Avaliar · vazio" }));
}

async function abrir() {
  vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
  render(<Carteira listas={LISTAS} />);
  await screen.findByText(/▸ Alfa/);
  await userEvent.click(screen.getByRole("button", { name: "Avaliar" }));
}

describe("Avaliação de complexidade, risco e disciplina por checklist", () => {
  beforeEach(() => vi.clearAllMocks());

  it("abre com nota 1 em complexidade e em risco, sem nenhum fator marcado", async () => {
    await abrir();
    expect(screen.getByText(nota("Nota calculada: 1 (0 de 6 marcados)"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /^Risco técnico/ }));
    expect(screen.getByText(nota("Nota calculada: 1 (0 de 5 marcados)"))).toBeInTheDocument();
  });

  it("pré-preenche o porte com o que já foi salvo do grupo, em vez de abrir em branco", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      itens: [item({
        porte: {
          ...PORTE_VAZIO, cnpjs_no_escopo: 4, empregados_clt: 30, servicos_contratados_alem_do_primeiro: 2,
          tem_consolidacao_de_grupo: true, e_auditada: true,
          porte: "Médio", porte_definido_por: "Eduardo Luiz", porte_definido_em: "2026-09-01T10:00:00",
        },
      })],
    }));
    render(<Carteira listas={LISTAS} />);
    await screen.findByText(/▸ Alfa/);
    await userEvent.click(screen.getByRole("button", { name: "Avaliar" }));
    await userEvent.click(screen.getByRole("tab", { name: /^Porte/ }));

    expect(screen.getByLabelText("CNPJs no escopo")).toHaveValue(4);
    expect(screen.getByLabelText("Empregados CLT")).toHaveValue(30);
    expect(screen.getByLabelText("Documentos fiscais/mês")).toHaveValue(null);
    expect(screen.getByLabelText("Serviços contratados além do primeiro")).toHaveValue(2);
    expect(screen.getByLabelText("Há consolidação de grupo")).toBeChecked();
    expect(screen.getByLabelText("Empresa auditada")).toBeChecked();
    expect(screen.getByLabelText("Porte confirmado")).toHaveValue("Médio");
  });

  it("marcar fatores de complexidade sobe a nota (0→1, 1→2, 2-3→3, 4→4, 5-6→5)", async () => {
    await abrir();
    await userEvent.click(screen.getByLabelText(/Holding com consolidação/));
    expect(screen.getByText(nota("Nota calculada: 2 (1 de 6 marcados)"))).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText(/Mais de um centro de custo/));
    await userEvent.click(screen.getByLabelText(/Auditoria externa/));
    expect(screen.getByText(nota("Nota calculada: 3 (3 de 6 marcados)"))).toBeInTheDocument();
  });

  it("marcar fatores de risco sobe a nota, como na complexidade (0→1, 1→2 … 4-5→5)", async () => {
    await abrir();
    await userEvent.click(screen.getByRole("tab", { name: /^Risco técnico/ }));
    await userEvent.click(screen.getByLabelText(/Auto de infração/));
    expect(screen.getByText(nota("Nota calculada: 2 (1 de 5 marcados)"))).toBeInTheDocument();
  });

  it("disciplina: 3 meses no prazo e sem furo extra é nota 5; cada furo desce um ponto", async () => {
    await abrir();
    await userEvent.click(screen.getByRole("tab", { name: /^Disciplina/ }));
    expect(screen.getByText(nota("Nota calculada: 5"))).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(/quantos o cliente entregou tudo no prazo/), "1");
    expect(screen.getByText(nota("Nota calculada: 3"))).toBeInTheDocument(); // 2 furos de mês
    await userEvent.click(screen.getByLabelText(/mais de uma cobrança/));
    expect(screen.getByText(nota("Nota calculada: 2"))).toBeInTheDocument();
  });

  it("sem período aberto, não deixa salvar nem calcular e diz o motivo", async () => {
    await abrir();
    expect(screen.getByText(/Nenhum período de avaliação aberto/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    expect(screen.getByRole("button", { name: "Salvar rascunho" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Calcular este cliente" })).toBeDisabled();
  });

  it("com período, só libera salvar com o nome de quem avalia", async () => {
    await abrirComPeriodo();
    expect(screen.getByRole("button", { name: "Salvar rascunho" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    expect(screen.getByRole("button", { name: "Salvar rascunho" })).toBeEnabled();
  });

  it("salvar rascunho grava só as abas revistas, sem fechar o painel", async () => {
    vi.mocked(api.salvarRascunho).mockResolvedValue({
      respostas: {}, preenchidas: ["complexidade", "risco"], atualizado_em: "2026-10-02T10:00:00", atualizado_por: "Karine",
    });
    await abrirComPeriodo();
    await userEvent.click(screen.getByLabelText(/Holding com consolidação/));
    await userEvent.click(screen.getByRole("tab", { name: /^Risco técnico/ }));
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    await userEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));

    expect(api.salvarRascunho).toHaveBeenCalledWith(1, { autor: "Karine", complexidade: ["holding"], risco: [] });
    expect(api.editarNotasDaCarteira).not.toHaveBeenCalled();
    expect(await screen.findByRole("tab", { name: /^Complexidade✓ preenchida/ })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /^Disciplina· pendente/ })).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "Componentes do Score e porte" })).toBeInTheDocument();
    expect(api.classificacaoDaCarteira).toHaveBeenCalledTimes(2); // a lista recarrega para atualizar o botão Avaliar
  });

  it("calcular este cliente salva o que está na tela e mostra o resultado sem mudar a carteira", async () => {
    vi.mocked(api.salvarRascunho).mockResolvedValue({
      respostas: {}, preenchidas: ["complexidade"], atualizado_em: "2026-10-02T10:00:00", atualizado_por: "Karine",
    });
    vi.mocked(api.simularCliente).mockResolvedValue({
      pendentes: ["risco", "disciplina", "cross_sell", "inadimplencia", "porte"],
      notas_antes: { rentabilidade: "3.00" }, notas_depois: { rentabilidade: "1" }, score_antes: "3.4100", score_depois: "3.5200",
      classe_antes: "B2", classe_depois: "B2",
      rentabilidade: {
        porte: "Médio", horas: "16.80", custo_de_servir: "669.90", honorario_praticado: "1900.00", margem: "0.5374",
        honorario_calculado: "3525.79", defasagem: "-0.4611", revisao_de_honorarios: true,
      },
    });
    await abrirComPeriodo();
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    await userEvent.click(screen.getByRole("button", { name: "Calcular este cliente" }));

    expect(api.salvarRascunho).toHaveBeenCalledWith(1, { autor: "Karine", complexidade: [] });
    const resultado = await screen.findByRole("region", { name: "Resultado deste cliente" });
    expect(resultado).toHaveTextContent("A carteira não muda");
    expect(resultado).toHaveTextContent("3,41 → 3,52");
    expect(resultado).toHaveTextContent("Nota de rentabilidade (pela margem do CRM)3 → 1");
    expect(resultado).toHaveTextContent("53,7%");
    expect(resultado).toHaveTextContent("−46,1% abaixo");
    expect(resultado).toHaveTextContent("Sim, abaixo da mínima");
  });

  it("aba Porte sem porte confirmado não é salva", async () => {
    await abrirComPeriodo();
    await userEvent.click(screen.getByRole("tab", { name: /^Porte/ }));
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    await userEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));
    expect(await screen.findByText("Escolha o porte confirmado antes de salvar a aba Porte.")).toBeInTheDocument();
    expect(api.salvarRascunho).not.toHaveBeenCalled();
  });

  it("porte com justificativa vai no rascunho", async () => {
    vi.mocked(api.salvarRascunho).mockResolvedValue({
      respostas: {}, preenchidas: ["complexidade", "porte"], atualizado_em: "2026-10-02T10:00:00", atualizado_por: "Karine",
    });
    await abrirComPeriodo();
    await userEvent.click(screen.getByRole("tab", { name: /^Porte/ }));
    await userEvent.selectOptions(screen.getByLabelText("Porte confirmado"), "Médio");
    await userEvent.type(screen.getByLabelText(/^Justificativa/), "Folha em três estados.");
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    await userEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));
    expect(api.salvarRascunho).toHaveBeenCalledWith(1, expect.objectContaining({
      complexidade: [],
      porte: expect.objectContaining({ porte: "Médio", justificativa: "Folha em três estados." }),
    }));
  });

  it("porte: calcula a sugestão sob demanda e oferece usá-la", async () => {
    vi.mocked(api.sugestaoDePorte).mockResolvedValue({
      calculavel: true, pontuacao: "0.00", porte: "Micro", horas_base: 5, direcionadores_aplicados: 1,
    });
    await abrir();
    await userEvent.click(screen.getByRole("tab", { name: /^Porte/ }));
    await userEvent.type(screen.getByLabelText("CNPJs no escopo"), "1");
    await userEvent.click(screen.getByRole("button", { name: "Ver sugestão" }));

    expect(api.sugestaoDePorte).toHaveBeenCalledWith({
      cnpjs_no_escopo: 1, servicos_contratados_alem_do_primeiro: 0,
      tem_consolidacao_de_grupo: false, e_auditada: false,
    });
    expect(await screen.findByText(/Sugestão pelo questionário de porte:/)).toHaveTextContent(
      "Sugestão pelo questionário de porte: Micro — pontuação 0,00, 5h base/mês, 1 de 9 direcionadores preenchidos.",
    );

    await userEvent.click(screen.getByRole("button", { name: "Usar sugestão (Micro)" }));
    expect(screen.getByLabelText("Porte confirmado")).toHaveValue("Micro");
    // já usada: o botão de novo some
    expect(screen.queryByRole("button", { name: "Usar sugestão (Micro)" })).toBeNull();
  });

  it("porte: sem nenhum direcionador, a sugestão avisa que não dá para calcular", async () => {
    vi.mocked(api.sugestaoDePorte).mockResolvedValue({
      calculavel: false, pontuacao: null, porte: null, horas_base: null, direcionadores_aplicados: 0,
    });
    await abrir();
    await userEvent.click(screen.getByRole("tab", { name: /^Porte/ }));
    await userEvent.click(screen.getByRole("button", { name: "Ver sugestão" }));
    expect(await screen.findByText("Sugestão da régua: não calculável — nenhum direcionador preenchido ainda.")).toBeInTheDocument();
    expect(screen.queryByText(/Usar sugestão/)).toBeNull();
  });

  it("mostra o erro da API sem travar a tela", async () => {
    vi.mocked(api.salvarRascunho).mockRejectedValue(new Error("falhou"));
    await abrirComPeriodo();
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    await userEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));
    expect(await screen.findByText("Falha ao salvar o rascunho.")).toBeInTheDocument();
  });

  it("reabre com as respostas da última avaliação gravada, e não em branco", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      periodo: PERIODO,
      itens: [item({
        avaliacao: {
          registrado_em: "2026-09-29T14:30:00",
          atribuido_por: "Eduardo Luiz",
          respostas: {
            complexidade: ["holding", "auditoria"], risco: ["certificado_vencendo"], cross_sell: ["mais_de_uma_linha"],
            disciplina: { meses_no_prazo: 2, cobranca_dobrada: true, atraso_recorrente: false },
            inadimplencia: { meses_em_dia: 1, em_negociacao: true, ja_suspenso: false },
          },
        },
      })],
    }));
    render(<Carteira listas={LISTAS} />);
    await screen.findByText(/▸ Alfa/);
    await userEvent.click(screen.getByRole("button", { name: "Avaliar · vazio" }));

    expect(screen.getByText(/Os itens já marcados vêm da última avaliação \(29\/09\/2026 às 14:30, por Eduardo Luiz\)/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Holding com consolidação/)).toBeChecked();
    expect(screen.getByLabelText(/Auditoria externa/)).toBeChecked();
    expect(screen.getByText(nota("Nota calculada: 3 (2 de 6 marcados)"))).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /^Risco técnico/ }));
    expect(screen.getByLabelText(/Certificado digital vencendo/)).toBeChecked();
    await userEvent.click(screen.getByRole("tab", { name: /^Disciplina/ }));
    expect(screen.getByLabelText(/quantos o cliente entregou tudo no prazo/)).toHaveValue("2");
    expect(screen.getByLabelText(/mais de uma cobrança/)).toBeChecked();
    await userEvent.click(screen.getByRole("tab", { name: /^Adimplência/ }));
    expect(screen.getByLabelText(/quantos o cliente pagou em dia/)).toHaveValue("1");
    expect(screen.getByLabelText(/negociação ou cobrança agora/)).toBeChecked();
  });

  it("sem período e sem respostas, o aviso é o do período", async () => {
    await abrir();
    expect(screen.getByText(/Nenhum período de avaliação aberto/)).toBeInTheDocument();
  });

  it("o rascunho do período tem prioridade sobre a última avaliação", async () => {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      periodo: PERIODO,
      itens: [item({
        avaliacao: {
          registrado_em: "2026-09-29T14:30:00", atribuido_por: "Eduardo Luiz",
          respostas: {
            complexidade: ["holding"], risco: [], cross_sell: [],
            disciplina: { meses_no_prazo: 3, cobranca_dobrada: false, atraso_recorrente: false },
            inadimplencia: { meses_em_dia: 3, em_negociacao: false, ja_suspenso: false },
          },
        },
        rascunho: {
          respostas: { complexidade: ["auditoria", "regimes"] }, preenchidas: ["complexidade"],
          atualizado_em: "2026-10-02T09:00:00", atualizado_por: "Karine",
        },
      })],
    }));
    render(<Carteira listas={LISTAS} />);
    await screen.findByText(/▸ Alfa/);
    await userEvent.click(screen.getByRole("button", { name: "Avaliar · 1 de 6" }));
    expect(screen.getByText(/Rascunho salvo em 02\/10\/2026 às 09:00 por Karine/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Auditoria externa/)).toBeChecked();
    expect(screen.getByLabelText(/Holding com consolidação/)).not.toBeChecked();
    expect(screen.getByRole("tab", { name: /^Complexidade✓ preenchida/ })).toBeInTheDocument();
  });

  it("fechar o painel não chama a API", async () => {
    await abrir();
    await userEvent.click(screen.getByRole("button", { name: "Fechar painel" }));
    expect(screen.queryByRole("tablist", { name: "Componentes do Score e porte" })).toBeNull();
    expect(api.salvarRascunho).not.toHaveBeenCalled();
  });
});

describe("Avaliação de cliente novo: aba Saúde e Receita pelo porte", () => {
  beforeEach(() => vi.clearAllMocks());

  const NOVO: ClienteNovo = {
    grupo_id: 9, grupo_nome: "Zeta", desde: "2026-10-10", receita_em_contrato: "2600.00", contratos: 1,
    empresas: [], porte: PORTE_VAZIO, rascunho: null, rentabilidade_do_grupo: null,
  };

  async function abrirNovo() {
    vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta({
      itens: [], periodo: { ...PERIODO, pendentes: [{ grupo_id: 9, grupo_nome: "Zeta", preenchidas: 0, abas: 7, novo: true }] },
      novos: [NOVO],
    }));
    render(<Carteira listas={LISTAS} />);
    await screen.findByText(/▸ Zeta/);
    await userEvent.click(screen.getByRole("button", { name: "Avaliar · vazio" }));
  }

  it("tem 7 abas a preencher, com a Saúde, e a Receita diz que vem do porte", async () => {
    await abrirNovo();
    expect(screen.getByText("10/2026 · cliente novo · 0 de 7 abas preenchidas")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /^Saúde· pendente/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /^Receitapelo porte/ }));
    expect(screen.getByText(/Sem porte confirmado ainda/)).toBeInTheDocument();
  });

  it("grupo que já está na Carteira não tem a aba Saúde", async () => {
    await abrirComPeriodo();
    expect(screen.queryByRole("tab", { name: /^Saúde/ })).toBeNull();
    expect(screen.getByText("10/2026 · 0 de 6 abas preenchidas")).toBeInTheDocument();
  });

  it("só visitar a Saúde não conta; escolher semáforo e churn grava a aba", async () => {
    vi.mocked(api.salvarRascunho).mockResolvedValue({
      respostas: {}, preenchidas: ["complexidade", "saude"], atualizado_em: "2026-10-02T10:00:00", atualizado_por: "Karine",
    });
    await abrirNovo();
    await userEvent.click(screen.getByRole("tab", { name: /^Saúde/ }));
    await userEvent.click(screen.getByRole("tab", { name: /^Complexidade/ }));
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    await userEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));
    expect(api.salvarRascunho).toHaveBeenLastCalledWith(9, { autor: "Karine", complexidade: [] });

    await userEvent.click(screen.getByRole("tab", { name: /^Saúde/ }));
    await userEvent.selectOptions(screen.getByLabelText("Semáforo — saúde operacional"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Escolha o semáforo e o churn");

    await userEvent.selectOptions(screen.getByLabelText(/^Churn/), "4");
    await userEvent.click(screen.getByRole("button", { name: "Salvar rascunho" }));
    expect(api.salvarRascunho).toHaveBeenLastCalledWith(9, { autor: "Karine", complexidade: [], saude: { semaforo: 2, churn: 4 } });
  });

  it("calcular este cliente novo mostra Score só com todas as abas, sem o antes", async () => {
    vi.mocked(api.salvarRascunho).mockResolvedValue({
      respostas: {}, preenchidas: ["complexidade"], atualizado_em: "2026-10-02T10:00:00", atualizado_por: "Karine",
    });
    vi.mocked(api.simularCliente).mockResolvedValue({
      pendentes: ["risco", "disciplina", "cross_sell", "inadimplencia", "porte", "saude"], novo: true,
      notas_antes: null, notas_depois: { receita: null, rentabilidade: null, complexidade: "1" },
      score_antes: null, score_depois: null, classe_antes: null, classe_depois: null, rentabilidade: null,
    });
    await abrirNovo();
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Karine");
    await userEvent.click(screen.getByRole("button", { name: "Calcular este cliente" }));
    const resultado = await screen.findByRole("region", { name: "Resultado deste cliente" });
    expect(resultado).toHaveTextContent("— (após preencher as 7 abas)");
    expect(resultado).toHaveTextContent("cliente novo não tem nota anterior");
    expect(resultado).toHaveTextContent("Saúde");
    expect(resultado).not.toHaveTextContent("→");
  });
});
