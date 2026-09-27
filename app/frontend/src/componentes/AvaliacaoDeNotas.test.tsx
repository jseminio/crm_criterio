import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ClassificacaoDaCarteira, ItemDaCarteira, Listas, PorteDoGrupo } from "../api/tipos";
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
const item = (o: Partial<ItemDaCarteira> = {}): ItemDaCarteira => ({
  grupo_id: 1, grupo_nome: "Alfa", receita_mensal: "1000.00", score: "3.00", classe: "B", classe_efetiva: "B1",
  alerta_de_churn: null, em_cobranca: false, eixo_de_acao: "Sem urgência de churn", semaforo: 1, churn: 1,
  sem_contrato_ativo: false, empresas: [], porte: PORTE_VAZIO, ...o,
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

async function abrir() {
  vi.mocked(api.classificacaoDaCarteira).mockResolvedValue(resposta());
  render(<Carteira listas={LISTAS} />);
  await screen.findByText(/▸ Alfa/);
  await userEvent.click(screen.getByRole("button", { name: "Avaliar" }));
}

describe("Avaliação de complexidade, risco e disciplina por checklist", () => {
  beforeEach(() => vi.clearAllMocks());

  it("abre com nota 1 em complexidade e 5 em risco, sem nenhum fator marcado", async () => {
    await abrir();
    expect(screen.getByText(nota("Nota calculada: 1 (0 de 6 marcados)"))).toBeInTheDocument();
    expect(screen.getByText(nota("Nota calculada: 5 (0 de 5 marcados)"))).toBeInTheDocument();
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

  it("marcar fatores de risco desce a nota (0→5, 1→4 … 4-5→1)", async () => {
    await abrir();
    await userEvent.click(screen.getByLabelText(/Auto de infração/));
    expect(screen.getByText(nota("Nota calculada: 4 (1 de 5 marcados)"))).toBeInTheDocument();
  });

  it("disciplina: 3 meses no prazo e sem furo extra é nota 5; cada furo desce um ponto", async () => {
    await abrir();
    expect(screen.getByText(nota("Nota calculada: 5"))).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(/quantos o cliente entregou tudo no prazo/), "1");
    expect(screen.getByText(nota("Nota calculada: 3"))).toBeInTheDocument(); // 2 furos de mês
    await userEvent.click(screen.getByLabelText(/mais de uma cobrança/));
    expect(screen.getByText(nota("Nota calculada: 2"))).toBeInTheDocument();
  });

  it("não deixa salvar sem o nome de quem avaliou", async () => {
    await abrir();
    expect(screen.getByRole("button", { name: "Salvar avaliação" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Eduardo Luiz");
    expect(screen.getByRole("button", { name: "Salvar avaliação" })).toBeEnabled();
  });

  it("salva as três notas calculadas e o porte, com motivo descrevendo o que foi marcado", async () => {
    vi.mocked(api.editarNotasDaCarteira).mockResolvedValue({ item: item(), isc: null, avisos: [] });
    vi.mocked(api.editarPorte).mockResolvedValue(PORTE_VAZIO);
    await abrir();
    await userEvent.click(screen.getByLabelText(/Holding com consolidação/));
    await userEvent.click(screen.getByLabelText(/Auto de infração/));
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Eduardo Luiz");
    await userEvent.click(screen.getByRole("button", { name: "Salvar avaliação" }));

    expect(api.editarNotasDaCarteira).toHaveBeenCalledWith(1, {
      autor: "Eduardo Luiz",
      motivo: "Complexidade 2 (1/6: holding). Risco técnico 4 (1/5: auto de infração). Disciplina 5 (3/3 meses no prazo)",
      complexidade: 2, disciplina: 5, risco: 4,
    });
    expect(api.editarPorte).toHaveBeenCalledWith(1, {
      autor: "Eduardo Luiz", porte: undefined,
      servicos_contratados_alem_do_primeiro: 0, tem_consolidacao_de_grupo: false, e_auditada: false,
    });
    // fecha o painel e recarrega a lista depois de salvar
    await waitFor(() => expect(screen.queryByText("Avaliar complexidade, risco técnico, disciplina e porte")).toBeNull());
    expect(api.classificacaoDaCarteira).toHaveBeenCalledTimes(2);
  });

  it("porte: calcula a sugestão sob demanda e oferece usá-la", async () => {
    vi.mocked(api.sugestaoDePorte).mockResolvedValue({
      calculavel: true, pontuacao: "0.00", porte: "Micro", horas_base: 5, direcionadores_aplicados: 1,
    });
    await abrir();
    await userEvent.type(screen.getByLabelText("CNPJs no escopo"), "1");
    await userEvent.click(screen.getByRole("button", { name: "Ver sugestão" }));

    expect(api.sugestaoDePorte).toHaveBeenCalledWith({
      cnpjs_no_escopo: 1, servicos_contratados_alem_do_primeiro: 0,
      tem_consolidacao_de_grupo: false, e_auditada: false,
    });
    expect(await screen.findByText(/Sugestão da régua:/)).toHaveTextContent(
      "Sugestão da régua: Micro — pontuação 0,00, 5h base/mês, 1 de 9 direcionadores preenchidos.",
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
    await userEvent.click(screen.getByRole("button", { name: "Ver sugestão" }));
    expect(await screen.findByText("Sugestão da régua: não calculável — nenhum direcionador preenchido ainda.")).toBeInTheDocument();
    expect(screen.queryByText(/Usar sugestão/)).toBeNull();
  });

  it("mostra o erro da API sem travar a tela", async () => {
    vi.mocked(api.editarNotasDaCarteira).mockRejectedValue(new Error("falhou"));
    await abrir();
    await userEvent.type(screen.getByLabelText("Quem está avaliando"), "Eduardo Luiz");
    await userEvent.click(screen.getByRole("button", { name: "Salvar avaliação" }));
    expect(await screen.findByText("Falha ao salvar a avaliação.")).toBeInTheDocument();
  });

  it("cancelar fecha o painel sem chamar a API", async () => {
    await abrir();
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.queryByText("Avaliar complexidade, risco técnico, disciplina e porte")).toBeNull();
    expect(api.editarNotasDaCarteira).not.toHaveBeenCalled();
  });
});
