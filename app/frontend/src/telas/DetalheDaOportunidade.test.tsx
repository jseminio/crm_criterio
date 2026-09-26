/** O painel onde a oportunidade se move pelo funil.
 *
 * Dois comportamentos aqui vêm de um defeito real, corrigido em 21/09/2026: a
 * recarga da planilha apagava a data de aceite preenchida na tela. Depois da
 * correção, a tela precisa (1) recusar marcar como aceita sem a data — a
 * mesma regra que a API aplica — e (2) avisar que a edição feita aqui
 * sobrevive à recarga, senão a garantia existe no banco e ninguém sabe dela.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Listas, OportunidadeDetalhe } from "../api/tipos";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { oportunidade: vi.fn(), editarOportunidade: vi.fn() } };
});

const LISTAS: Listas = {
  situacoes: ["Enviar proposta", "Em avaliação pela empresa", "On hold", "Aceita", "Recusada", "Perdido"],
  situacoes_de_lead: [],
  temperaturas: ["Frio", "Morno", "Quente"],
  tipos_de_canal: [],
  tipos_de_canal_em_operacao: [],
  motivos_de_recusa: ["Preço", "Concorrência"],
  motivos_de_encerramento: [],
  linhas_de_servico: [],
  situacoes_de_grupo: [],
  captadores: [],
  portes: ["Micro", "Pequeno", "Médio", "Grande", "Extra Grande"],
  servicos: [],
};

function oportunidade(extra: Partial<OportunidadeDetalhe> = {}): OportunidadeDetalhe {
  return {
    id: 1,
    nome: "Alfa BPO",
    grupo_id: 1,
    grupo_nome: "Grupo Alfa",
    situacao: "Enviar proposta",
    temperatura: "Morno",
    servico: "BPO Contábil",
    tipo_servico: "Recorrente",
    captador: "EL",
    tipo_canal: "Sócios",
    data_colocacao: "2026-03-01",
    preco_mensal: "5000.00",
    preco_anual: "65000.00",
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
    linha_planilha: 42,
    origem_da_volumetria: {},
    historico_de_preco: [],
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
    sugestao_de_porte: { calculavel: false, pontuacao: null, porte: null, horas_base: null, direcionadores_aplicados: 0 },
    ...extra,
  };
}

async function abrir(dados: OportunidadeDetalhe, aoSalvar = vi.fn()) {
  vi.mocked(api.oportunidade).mockResolvedValue(dados);
  render(
    <DetalheDaOportunidade id={dados.id} listas={LISTAS} aoFechar={() => {}} aoSalvar={aoSalvar} />,
  );
  await screen.findByLabelText("Situação");
  return aoSalvar;
}

describe("DetalheDaOportunidade", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra o estado de carregamento antes da resposta da API", () => {
    vi.mocked(api.oportunidade).mockReturnValue(new Promise(() => {})); // nunca resolve
    render(<DetalheDaOportunidade id={1} listas={LISTAS} aoFechar={() => {}} aoSalvar={() => {}} />);

    expect(screen.getByRole("status")).toHaveTextContent("Abrindo a oportunidade");
  });

  it("avisa que a edição sobrevive à recarga da planilha", async () => {
    // O comportamento existe no banco desde 21/09/2026; sem este texto a
    // pessoa não teria como saber que pode confiar na edição.
    await abrir(oportunidade());

    expect(
      screen.getByText(/a recarga da planilha não sobrescreve/i),
    ).toBeInTheDocument();
  });

  it("recusa salvar como Aceita sem a data do aceite", async () => {
    await abrir(oportunidade());

    await userEvent.selectOptions(screen.getByLabelText("Situação"), "Aceita");

    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeDisabled();
    expect(screen.getByText(/para marcar como aceita, informe a data/i)).toBeInTheDocument();
  });

  it("libera salvar assim que a data do aceite é preenchida", async () => {
    await abrir(oportunidade());

    await userEvent.selectOptions(screen.getByLabelText("Situação"), "Aceita");
    await userEvent.type(screen.getByLabelText("Data do aceite"), "2026-04-15");

    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeEnabled();
  });

  it("uma oportunidade já aceita, com data, não trava o botão", async () => {
    // Não é "Aceita sempre trava" — é "Aceita sem data trava".
    await abrir(oportunidade({ situacao: "Aceita", data_aceite: "2026-04-01" }));

    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeEnabled();
  });

  it("envia exatamente os campos que a pessoa mudou, com vazio virando null", async () => {
    vi.mocked(api.editarOportunidade).mockResolvedValue(oportunidade());
    const aoSalvar = await abrir(oportunidade());

    await userEvent.selectOptions(screen.getByLabelText("Situação"), "On hold");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledOnce());
    const [id, mudancas] = vi.mocked(api.editarOportunidade).mock.calls[0];
    expect(id).toBe(1);
    expect(mudancas.situacao).toBe("On hold");
    expect(mudancas.temperatura).toBe("Morno");
    // Campos que chegaram vazios da API viram null, não string vazia — é
    // assim que "ausência" é representada no banco.
    expect(mudancas.data_aceite).toBeNull();
    expect(mudancas.observacao).toBeNull();
    expect(aoSalvar).toHaveBeenCalledOnce();
  });

  it("mostra o erro da API sem fechar o painel, e permite tentar salvar de novo", async () => {
    vi.mocked(api.editarOportunidade).mockRejectedValue(new Error("Falha ao salvar."));
    const aoSalvar = await abrir(oportunidade());

    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Falha ao salvar."));
    expect(aoSalvar).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeEnabled();
  });

  it("preço, serviço e data de originação vêm preenchidos e editáveis — desde o E4", async () => {
    await abrir(oportunidade());

    expect(screen.getByLabelText("Serviço")).toHaveValue("BPO Contábil");
    expect(screen.getByLabelText("Tipo de serviço")).toHaveValue("Recorrente");
    expect(screen.getByLabelText("Preço mensal")).toHaveValue(5000);
    expect(screen.getByLabelText("Preço anual")).toHaveValue(65000);
    expect(screen.getByLabelText("Data de originação")).toHaveValue("2026-03-01");
  });

  it("envia preço e serviço editados junto do resto", async () => {
    vi.mocked(api.editarOportunidade).mockResolvedValue(oportunidade());
    await abrir(oportunidade());

    await userEvent.clear(screen.getByLabelText("Preço mensal"));
    await userEvent.type(screen.getByLabelText("Preço mensal"), "5500");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarOportunidade).mock.calls[0];
    expect(mudancas.preco_mensal).toBe("5500");
  });

  it("mostra o motivo só quando a situação é Recusada ou Perdido", async () => {
    await abrir(oportunidade());
    expect(screen.queryByLabelText("Motivo")).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Situação"), "Recusada");

    expect(screen.getByLabelText("Motivo")).toBeInTheDocument();
  });

  it("mostra o texto original da planilha junto do motivo", async () => {
    await abrir(
      oportunidade({ situacao: "Recusada", motivo_recusa_original: "Cliente internalizou" }),
    );

    expect(screen.getByText(/cliente internalizou/i)).toBeInTheDocument();
  });
});

describe("Volumetria e porte — a régua sugere, nunca decide (E4, 23/09/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sem direcionador nenhum preenchido, mostra que não dá para calcular", async () => {
    await abrir(oportunidade());

    expect(screen.getByText(/não calculável — nenhum direcionador preenchido/i)).toBeInTheDocument();
  });

  it("com sugestão calculável, mostra o porte e a pontuação — sem confirmar nada sozinha", async () => {
    await abrir(
      oportunidade({
        sugestao_de_porte: {
          calculavel: true,
          pontuacao: "4.00",
          porte: "Extra Grande",
          horas_base: 80,
          direcionadores_aplicados: 1,
        },
      }),
    );

    expect(screen.getByText(/sugestão da régua/i)).toHaveTextContent("Extra Grande");
    expect(screen.getByText(/sugestão da régua/i)).toHaveTextContent("4,00");
    // A sugestão não é o porte confirmado — o campo de confirmação continua
    // vazio até uma pessoa decidir.
    expect(screen.getByLabelText("Porte confirmado")).toHaveValue("");
  });

  it("o botão 'usar sugestão' copia o porte sugerido para o campo de confirmação", async () => {
    await abrir(
      oportunidade({
        sugestao_de_porte: {
          calculavel: true,
          pontuacao: "4.00",
          porte: "Extra Grande",
          horas_base: 80,
          direcionadores_aplicados: 1,
        },
      }),
    );

    await userEvent.click(screen.getByRole("button", { name: /usar sugestão/i }));

    expect(screen.getByLabelText("Porte confirmado")).toHaveValue("Extra Grande");
  });

  it("digitar um direcionador e salvar manda o número, e vazio manda null", async () => {
    vi.mocked(api.editarOportunidade).mockResolvedValue(oportunidade());
    await abrir(oportunidade());

    await userEvent.type(screen.getByLabelText("Empregados CLT"), "180");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarOportunidade).mock.calls[0];
    expect(mudancas.empregados_clt).toBe("180");
    expect(mudancas.contas_bancarias).toBeNull(); // não preenchido — fica de fora, não vira 0
  });

  it("desmarcar 'auditada' manda false explícito, não null", async () => {
    vi.mocked(api.editarOportunidade).mockResolvedValue(oportunidade());
    await abrir(oportunidade({ e_auditada: true }));

    // Já vem marcado; desmarca e salva sem mudar mais nada.
    await userEvent.click(screen.getByRole("checkbox", { name: /empresa auditada/i }));
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarOportunidade).mock.calls[0];
    expect(mudancas.e_auditada).toBe(false);
  });

  it("porte confirmado mostra quem e quando, vindo do servidor", async () => {
    await abrir(
      oportunidade({
        porte: "Grande",
        porte_definido_por: "EL",
        porte_definido_em: "2026-09-23T14:30:00Z",
      }),
    );

    expect(screen.getByText(/confirmado por EL em/i)).toBeInTheDocument();
  });
});


describe("Histórico de preço e origem da volumetria (E4, 25/09/2026)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sem mudança de preço, diz que o preço ainda não mudou", async () => {
    await abrir(oportunidade());
    expect(screen.getByText(/o preço ainda não mudou/i)).toBeInTheDocument();
  });

  it("mostra o histórico com antes, depois, motivo e origem", async () => {
    await abrir(
      oportunidade({
        historico_de_preco: [
          {
            id: 1, registrado_em: "2026-09-25T15:00:00+00:00", origem: "CRM", motivo: "reajuste anual",
            preco_mensal_anterior: "4500.00", preco_mensal_novo: "5000.00",
            preco_anual_anterior: "58500.00", preco_anual_novo: "65000.00",
          },
        ],
      }),
    );
    expect(screen.getByText(/reajuste anual/)).toBeInTheDocument();
    expect(screen.getByText(/4\.500,00.*→.*5\.000,00/)).toBeInTheDocument();
  });

  it("o campo de motivo só aparece quando o preço é alterado", async () => {
    await abrir(oportunidade());
    expect(screen.queryByLabelText(/por que o preço mudou/i)).toBeNull();
    await userEvent.clear(screen.getByLabelText("Preço mensal"));
    await userEvent.type(screen.getByLabelText("Preço mensal"), "5500");
    expect(screen.getByLabelText(/por que o preço mudou/i)).toBeInTheDocument();
  });

  it("envia o motivo junto do novo preço", async () => {
    vi.mocked(api.editarOportunidade).mockResolvedValue(oportunidade());
    await abrir(oportunidade());
    await userEvent.clear(screen.getByLabelText("Preço mensal"));
    await userEvent.type(screen.getByLabelText("Preço mensal"), "5500");
    await userEvent.type(screen.getByLabelText(/por que o preço mudou/i), "reajuste anual");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));
    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarOportunidade).mock.calls[0];
    expect(mudancas.preco_mensal).toBe("5500");
    expect(mudancas.motivo_do_preco).toBe("reajuste anual");
  });

  it("a origem só pode ser escolhida para direcionador preenchido", async () => {
    await abrir(oportunidade({ documentos_fiscais_mes: 100 }));
    expect(screen.getByLabelText("Origem de Documentos fiscais/mês")).toBeEnabled();
    expect(screen.getByLabelText("Origem de Pagamentos/mês")).toBeDisabled();
  });

  it("envia a origem como um mapa só dos campos preenchidos", async () => {
    vi.mocked(api.editarOportunidade).mockResolvedValue(oportunidade());
    await abrir(oportunidade({ documentos_fiscais_mes: 100, origem_da_volumetria: { documentos_fiscais_mes: "Entrevista" } }));
    expect(screen.getByLabelText("Origem de Documentos fiscais/mês")).toHaveValue("Entrevista");
    await userEvent.selectOptions(screen.getByLabelText("Origem de Documentos fiscais/mês"), "Questionário");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));
    await waitFor(() => expect(api.editarOportunidade).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarOportunidade).mock.calls[0];
    expect(mudancas.origem_da_volumetria).toEqual({ documentos_fiscais_mes: "Questionário" });
    expect(Object.keys(mudancas).some((k) => k.startsWith("origem_") && k !== "origem_da_volumetria")).toBe(false);
  });
});
