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
  linhas_de_servico: [],
  situacoes_de_grupo: [],
  captadores: [],
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

  it("não deixa editar preço, serviço ou datas de origem — só mostra", async () => {
    // A regra de contrato: enquanto a planilha roda em paralelo, ela é a
    // fonte desses campos. Não pode existir campo editável para eles aqui.
    await abrir(oportunidade());

    expect(screen.queryByLabelText(/preço/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/serviço/i)).not.toBeInTheDocument();
    // O texto real tem um espaço fino sem quebra (\u00a0) depois de "R$", mas
    // o normalizador do Testing Library o reduz a espaço comum antes de
    // comparar — por isso a consulta usa o espaço comum, não o caractere real.
    expect(screen.getByText("R$ 5.000,00")).toBeInTheDocument();
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
