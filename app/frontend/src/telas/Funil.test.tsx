/** O funil em kanban, com o arrasto entre colunas.
 *
 * Três comportamentos verificados de ponta a ponta no navegador (21/09/2026,
 * contra a API e o PostgreSQL reais) e aqui de novo, como regressão: mover
 * para uma coluna comum grava direto; mover para "Aceita" abre o painel em
 * vez de arriscar um PATCH que a API recusaria (o cartão não carrega
 * `data_aceite`); soltar na própria coluna não faz nada.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ColunaDoFunil, Indicadores, Listas, OportunidadeDetalhe } from "../api/tipos";
import { Funil } from "./Funil";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      funil: vi.fn(), indicadores: vi.fn(), oportunidade: vi.fn(), editarOportunidade: vi.fn(),
      antesDeExcluirOportunidade: vi.fn().mockResolvedValue({ pode_excluir: true, motivo: null, propostas: [], questionarios: 0, da_planilha: false }),
      excluirOportunidade: vi.fn(),
      recortes: vi.fn().mockResolvedValue([]), cenariosDeTicket: vi.fn().mockResolvedValue(null),
      oportunidades: vi.fn(), questionarios: vi.fn().mockResolvedValue([]),
      questionarioDaOportunidade: vi.fn().mockResolvedValue(null),
      enderecoDaExportacaoDoFunil: real.api.enderecoDaExportacaoDoFunil,
      servicos: vi.fn().mockResolvedValue([
        { nome: "BPO Contábil e Fiscal", nome_por_extenso: null, linha: "C1", recorrente: true,
          para_quem: "Empresa que terceiriza contabilidade e fiscal.", perguntas: [{ texto: "CNPJs no escopo", direcionador: "cnpjs_no_escopo" }],
          fora_do_perfil: ["MEI"], transbordo: "Comercial · BPO (C1)", nomes_antigos: ["BPO Contábil"], rascunho: true, temas: [] },
        { nome: "Auditoria", nome_por_extenso: null, linha: "C2", recorrente: false,
          para_quem: "Auditoria das demonstrações.", perguntas: [{ texto: "Exercício a auditar", direcionador: null }],
          fora_do_perfil: [], transbordo: "Consultoria (C2)", nomes_antigos: [], rascunho: true, temas: [] },
      ]),
    },
  };
});

const LISTAS: Listas = {
  situacoes: ["Enviar proposta", "On hold", "Aceita"],
  situacoes_de_lead: [],
  temperaturas: ["Frio", "Morno", "Quente"],
  tipos_de_canal: [],
  tipos_de_canal_em_operacao: [],
  motivos_de_recusa: [],
  motivos_de_encerramento: [],
  iniciativas_de_encerramento: [],
  papeis_de_contato: [],
  linhas_de_servico: [],
  situacoes_de_grupo: [],
  captadores: [],
  portes: [],
  servicos: [],
};

const INDICADORES_VAZIOS: Indicadores = {
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
  ticket_recorrente: { quantas: 0, clientes: 0, valor_mensal: "0", ticket_medio: null, mediana: null, maior_valor: null, participacao_do_maior: null, calculavel: false },
};

function coluna(situacao: string, oportunidades: ColunaDoFunil["oportunidades"]): ColunaDoFunil {
  return { situacao, quantas: oportunidades.length, valor_mensal: "0", valor_anual: "0", oportunidades };
}

function oportunidade(id: number, nome: string): ColunaDoFunil["oportunidades"][number] {
  return {
    id,
    nome,
    grupo_id: id,
    grupo_nome: nome,
    situacao: "Enviar proposta",
    temperatura: "Morno",
    servico: null,
    tipo_servico: null,
    captador: null,
    tipo_canal: null,
    data_colocacao: null,
    preco_mensal: null,
    preco_anual: null,
    proxima_acao: null,
    proxima_acao_em: null,
  };
}

/** Um `dataTransfer` mínimo — só o que os manipuladores realmente tocam. */
function dataTransfer() {
  return { setData: vi.fn(), effectAllowed: "", dropEffect: "" };
}

async function abrir(colunas: ColunaDoFunil[]) {
  vi.mocked(api.funil).mockResolvedValue(colunas);
  vi.mocked(api.indicadores).mockResolvedValue(INDICADORES_VAZIOS);
  render(<Funil listas={LISTAS} />);
  await screen.findByText(colunas[0].situacao);
}

function encontrarCartao(nome: string) {
  return screen.getByText(nome).closest(".cartao")!;
}

function encontrarColuna(situacao: string) {
  return screen.getByText(situacao).closest(".coluna")!;
}

describe("arrasto no kanban", () => {
  beforeEach(() => vi.clearAllMocks());

  it("soltar numa coluna comum grava a nova situação e recarrega", async () => {
    vi.mocked(api.editarOportunidade).mockResolvedValue({} as OportunidadeDetalhe);
    await abrir([
      coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")]),
      coluna("On hold", []),
    ]);

    const dt = dataTransfer();
    fireEvent.dragStart(encontrarCartao("Alfa BPO"), { dataTransfer: dt });
    fireEvent.dragOver(encontrarColuna("On hold"), { dataTransfer: dt });
    fireEvent.drop(encontrarColuna("On hold"), { dataTransfer: dt });

    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledOnce());
    expect(api.editarOportunidade).toHaveBeenCalledWith(1, { situacao: "On hold" });
    // Depois de gravar, o funil é recarregado — uma segunda chamada a /api/funil.
    await waitFor(() => expect(api.funil).toHaveBeenCalledTimes(2));
  });

  it("soltar em 'Aceita' abre o painel em vez de gravar direto", async () => {
    vi.mocked(api.oportunidade).mockResolvedValue({
      id: 1,
      nome: "Alfa BPO",
      grupo_id: 1,
      grupo_nome: "Alfa BPO",
      situacao: "Enviar proposta",
      temperatura: null,
      servico: null,
      tipo_servico: null,
      captador: null,
      tipo_canal: null,
      data_colocacao: null,
      preco_mensal: null,
      preco_anual: null,
      proxima_acao: null,
      proxima_acao_em: null,
      canal: null,
      linha_servico: null,
      data_aceite: null,
      motivo_recusa: null,
      motivo_recusa_original: null,
      valor_mensalizado: null,
      observacao: null,
      origem: "Carga 2026",
      linha_planilha: null,
      complexidade: null,
      risco_tecnico: null,
      documentos_fiscais_mes: null,
      lancamentos_contabeis_mes: null,
      pagamentos_mes: null,
      contas_bancarias: null,
      conciliacoes_cartao_mes: null,
      empregados_clt: null,
      admissoes_desligamentos_mes: null,
      cnpjs_no_escopo: null,
      tomadores_de_servico: null,
      servicos_contratados_alem_do_primeiro: 0,
      tem_consolidacao_de_grupo: false,
      e_auditada: false,
      porte: null,
      porte_definido_por: null,
      porte_definido_em: null,
      origem_da_volumetria: {},
      historico_de_preco: [],
      sugestao_de_porte: { calculavel: false, pontuacao: null, porte: null, horas_base: null, direcionadores_aplicados: 0 },
    });
    await abrir([
      coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")]),
      coluna("Aceita", []),
    ]);

    const dt = dataTransfer();
    fireEvent.dragStart(encontrarCartao("Alfa BPO"), { dataTransfer: dt });
    fireEvent.dragOver(encontrarColuna("Aceita"), { dataTransfer: dt });
    fireEvent.drop(encontrarColuna("Aceita"), { dataTransfer: dt });

    // O painel abre com a situação já em "Aceita" — é a mesma trava que
    // desabilita salvar sem a data, sem duplicar a regra aqui.
    await waitFor(() => expect(screen.getByLabelText("Situação")).toHaveValue("Aceita"));
    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeDisabled();
    expect(api.editarOportunidade).not.toHaveBeenCalled();
  });

  it("soltar na própria coluna não faz nada", async () => {
    await abrir([coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")])]);

    const dt = dataTransfer();
    fireEvent.dragStart(encontrarCartao("Alfa BPO"), { dataTransfer: dt });
    fireEvent.dragOver(encontrarColuna("Enviar proposta"), { dataTransfer: dt });
    fireEvent.drop(encontrarColuna("Enviar proposta"), { dataTransfer: dt });

    // Nada para esperar assincronamente — a ausência de chamada é o resultado.
    await new Promise((r) => setTimeout(r, 50));
    expect(api.editarOportunidade).not.toHaveBeenCalled();
    expect(api.funil).toHaveBeenCalledTimes(1); // só a carga inicial
  });

  it("uma falha ao gravar mostra um aviso dispensável, sem travar a tela", async () => {
    vi.mocked(api.editarOportunidade).mockRejectedValue(new Error("Não consegui mover a oportunidade."));
    await abrir([
      coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")]),
      coluna("On hold", []),
    ]);

    const dt = dataTransfer();
    fireEvent.dragStart(encontrarCartao("Alfa BPO"), { dataTransfer: dt });
    fireEvent.dragOver(encontrarColuna("On hold"), { dataTransfer: dt });
    fireEvent.drop(encontrarColuna("On hold"), { dataTransfer: dt });

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent("Não consegui mover a oportunidade.");

    fireEvent.click(screen.getByRole("button", { name: /dispensar aviso/i }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    // A falha não deve ter disparado uma recarga — o cartão continua onde
    // estava, e o teste confirma que ninguém chamou /api/funil de novo.
    expect(api.funil).toHaveBeenCalledTimes(1);
  });
});

describe("fusão Kanban/Grade (27/09/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("abre no Kanban por padrão, sem o filtro Situação", async () => {
    await abrir([coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")])]);
    expect(screen.getByRole("button", { name: "▦ Kanban" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByLabelText("Situação")).toBeNull();
  });

  it("troca para Grade: busca as oportunidades e mostra a tabela, com o filtro Situação", async () => {
    await abrir([coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")])]);
    vi.mocked(api.oportunidades).mockResolvedValue({
      total: 1,
      itens: [{ ...oportunidade(1, "Alfa BPO"), situacao: "Enviar proposta" }],
    });

    await fireEvent.click(screen.getByRole("button", { name: "☰ Grade" }));

    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.getByLabelText("Situação")).toBeInTheDocument();
    expect(screen.getByText("1 oportunidade")).toBeInTheDocument();
    expect(api.oportunidades).toHaveBeenCalledWith(expect.objectContaining({ situacao: undefined }));
    // Kanban não chamou de novo: cada visão busca só quando está ativa.
    expect(api.funil).toHaveBeenCalledTimes(1);
  });

  it("na Grade, filtrar por situação manda o filtro para a API", async () => {
    await abrir([coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")])]);
    vi.mocked(api.oportunidades).mockResolvedValue({ total: 0, itens: [] });
    await fireEvent.click(screen.getByRole("button", { name: "☰ Grade" }));
    await screen.findByLabelText("Situação");

    fireEvent.change(screen.getByLabelText("Situação"), { target: { value: "On hold" } });

    await waitFor(() =>
      expect(api.oportunidades).toHaveBeenLastCalledWith(expect.objectContaining({ situacao: ["On hold"] })),
    );
  });

  it("'Exportar para Excel' só aparece na Grade", async () => {
    await abrir([coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")])]);
    expect(screen.queryByRole("link", { name: "Exportar para Excel" })).toBeNull();

    vi.mocked(api.oportunidades).mockResolvedValue({ total: 0, itens: [] });
    await fireEvent.click(screen.getByRole("button", { name: "☰ Grade" }));

    expect(await screen.findByRole("link", { name: "Exportar para Excel" })).toHaveAttribute(
      "href",
      "/api/oportunidades/exportar",
    );
  });

  it("o link de exportação leva os filtros da Grade, inclusive a situação", async () => {
    await abrir([coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")])]);
    vi.mocked(api.oportunidades).mockResolvedValue({ total: 0, itens: [] });
    await fireEvent.click(screen.getByRole("button", { name: "☰ Grade" }));
    await screen.findByLabelText("Situação");

    fireEvent.change(screen.getByLabelText("Situação"), { target: { value: "On hold" } });

    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Exportar para Excel" })).toHaveAttribute(
        "href",
        "/api/oportunidades/exportar?situacao=On+hold",
      ),
    );
  });

  it("clicar numa linha da Grade abre o painel de detalhe", async () => {
    await abrir([coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")])]);
    vi.mocked(api.oportunidades).mockResolvedValue({
      total: 1,
      itens: [{ ...oportunidade(1, "Alfa BPO"), situacao: "Enviar proposta" }],
    });
    vi.mocked(api.oportunidade).mockResolvedValue({
      id: 1, nome: "Alfa BPO", grupo_id: 1, grupo_nome: "Alfa BPO", situacao: "Enviar proposta",
      temperatura: "Morno", servico: null, tipo_servico: null, captador: null, tipo_canal: null,
      data_colocacao: null, preco_mensal: null, preco_anual: null, proxima_acao: null, proxima_acao_em: null,
      canal: null, motivo_recusa: null, motivo_recusa_original: null, data_aceite: null, observacao: null,
      historico_de_preco: [], complexidade: null, risco_tecnico: null, documentos_fiscais_mes: null,
      lancamentos_contabeis_mes: null, pagamentos_mes: null, contas_bancarias: null, conciliacoes_cartao_mes: null,
      empregados_clt: null, admissoes_desligamentos_mes: null, cnpjs_no_escopo: null, tomadores_de_servico: null,
      servicos_contratados_alem_do_primeiro: 0, tem_consolidacao_de_grupo: false, e_auditada: false,
      porte: null, porte_definido_por: null, porte_definido_em: null, sugestao_de_porte: null,
      origem_da_volumetria: {}, linha_planilha: null,
      linha_servico: null, valor_mensalizado: null, origem: "CRM",
    } as OportunidadeDetalhe);

    await fireEvent.click(screen.getByRole("button", { name: "☰ Grade" }));
    await fireEvent.click((await screen.findAllByText("Alfa BPO"))[0]);

    expect(await screen.findByLabelText("Situação")).toBeInTheDocument();
    expect(api.oportunidade).toHaveBeenCalledWith(1);
  });

  it("voltar para Kanban busca de novo (a visão só troca de aba, não guarda cache) e mostra o Kanban certo", async () => {
    await abrir([coluna("Enviar proposta", [oportunidade(1, "Alfa BPO")])]);
    vi.mocked(api.oportunidades).mockResolvedValue({
      total: 1,
      itens: [{ ...oportunidade(1, "Alfa BPO"), situacao: "Enviar proposta" }],
    });
    await fireEvent.click(screen.getByRole("button", { name: "☰ Grade" }));
    await screen.findByRole("table");

    await fireEvent.click(screen.getByRole("button", { name: "▦ Kanban" }));

    expect(await screen.findByRole("button", { name: "▦ Kanban" })).toHaveAttribute("aria-pressed", "true");
    await waitFor(() => expect(api.funil).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole("table")).toBeNull();
  });
});
