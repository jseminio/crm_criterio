/** A fila de leads: cadastro, edição de situação e conversão em oportunidade.
 *
 * O ponto mais sensível é "Convertido" — um lead só chega lá pela conversão,
 * nunca escolhido à mão, porque esse estado pressupõe a oportunidade que o
 * sustenta (ver a trava equivalente na API, corrigida em 21/09/2026).
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { LeadResumo, Listas, Pagina } from "../api/tipos";
import { Leads } from "./Leads";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: { leads: vi.fn(), criarLead: vi.fn(), editarLead: vi.fn(), converterLead: vi.fn() },
  };
});

const LISTAS: Listas = {
  situacoes: [],
  situacoes_de_lead: ["Novo", "Em contato", "Qualificado", "Convertido", "Descartado"],
  temperaturas: ["Frio", "Morno", "Quente"],
  tipos_de_canal: ["Sócios", "Parceiros"],
  tipos_de_canal_em_operacao: ["Sócios", "Parceiros"],
  motivos_de_recusa: [],
  linhas_de_servico: [],
  situacoes_de_grupo: [],
  captadores: ["EL", "BO"],
};

function lead(extra: Partial<LeadResumo> = {}): LeadResumo {
  return {
    id: 1,
    nome: "Contato da feira",
    empresa_texto: "Gama Ltda",
    email: null,
    telefone: null,
    situacao: "Novo",
    temperatura: "Morno",
    tipo_canal: "Sócios",
    canal: "Indicação",
    captador: "EL",
    interesse: null,
    campanha: null,
    campanha_midia: null,
    proxima_acao: null,
    proxima_acao_em: null,
    observacao: null,
    convertido_em_id: null,
    ...extra,
  };
}

function pagina(itens: LeadResumo[]): Pagina<LeadResumo> {
  return { total: itens.length, itens };
}

async function abrir(itens: LeadResumo[]) {
  vi.mocked(api.leads).mockResolvedValue(pagina(itens));
  render(<Leads listas={LISTAS} />);
  if (itens.length === 0) {
    await screen.findByText("Nenhum lead na fila");
  } else {
    await screen.findByText(itens[0].nome);
  }
}

describe("fila vazia", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra uma única ação primária — regra 2 do PAD-002", async () => {
    // Com a fila vazia, o botão da barra some: só resta a ação dentro do
    // próprio estado vazio, senão as duas competem pela mesma tarefa.
    await abrir([]);

    expect(screen.getAllByRole("button", { name: /cadastrar/i })).toHaveLength(1);
  });
});

describe("cadastro de lead", () => {
  beforeEach(() => vi.clearAllMocks());

  it("só o nome é exigido para salvar", async () => {
    await abrir([lead()]);

    await userEvent.click(screen.getByRole("button", { name: "Cadastrar lead" }));

    expect(screen.getByRole("button", { name: /salvar lead/i })).toBeDisabled();

    await userEvent.type(screen.getByLabelText(/nome do contato/i), "Novo contato");

    expect(screen.getByRole("button", { name: /salvar lead/i })).toBeEnabled();
  });

  it("envia só os campos preenchidos", async () => {
    vi.mocked(api.criarLead).mockResolvedValue(lead());
    await abrir([lead()]);

    await userEvent.click(screen.getByRole("button", { name: "Cadastrar lead" }));
    await userEvent.type(screen.getByLabelText(/nome do contato/i), "Fulano");
    await userEvent.click(screen.getByRole("button", { name: /salvar lead/i }));

    await waitFor(() => expect(api.criarLead).toHaveBeenCalledOnce());
    const corpo = vi.mocked(api.criarLead).mock.calls[0][0];
    expect(corpo).toEqual({ nome: "Fulano" });
  });
});

describe("edição da situação", () => {
  beforeEach(() => vi.clearAllMocks());

  it("'Convertido' nunca aparece como opção — só a conversão leva lá", async () => {
    await abrir([lead()]);

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));

    const opcoes = within(screen.getByLabelText("Situação")).getAllByRole("option");
    expect(opcoes.map((o) => o.textContent)).not.toContain("Convertido");
  });

  it("muda a situação e envia a mudança", async () => {
    vi.mocked(api.editarLead).mockResolvedValue(lead({ situacao: "Em contato" }));
    await abrir([lead()]);

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    await userEvent.selectOptions(screen.getByLabelText("Situação"), "Em contato");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(api.editarLead).toHaveBeenCalledOnce());
    const [id, mudancas] = vi.mocked(api.editarLead).mock.calls[0];
    expect(id).toBe(1);
    expect(mudancas.situacao).toBe("Em contato");
  });

  it("lead já convertido não mostra o seletor de situação", async () => {
    await abrir([lead({ convertido_em_id: 42, situacao: "Convertido" })]);

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));

    expect(screen.queryByLabelText("Situação")).not.toBeInTheDocument();
    expect(screen.getByText(/já virou oportunidade/i)).toBeInTheDocument();
  });

  it("salvar um lead convertido não manda situação — ela pertence à oportunidade", async () => {
    vi.mocked(api.editarLead).mockResolvedValue(lead({ convertido_em_id: 42 }));
    await abrir([lead({ convertido_em_id: 42, situacao: "Convertido", observacao: null })]);

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    await userEvent.type(screen.getByLabelText(/observação/i), "nota qualquer");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(api.editarLead).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarLead).mock.calls[0];
    expect(mudancas).not.toHaveProperty("situacao");
    expect(mudancas.observacao).toBe("nota qualquer");
  });
});

describe("lista", () => {
  beforeEach(() => vi.clearAllMocks());

  it("um lead não convertido tem botão de converter; um convertido, não", async () => {
    await abrir([
      lead({ id: 1, nome: "Aberto" }),
      lead({ id: 2, nome: "Fechado", convertido_em_id: 9 }),
    ]);

    const linhaAberta = screen.getByText("Aberto").closest("tr")!;
    const linhaFechada = screen.getByText("Fechado").closest("tr")!;

    expect(within(linhaAberta).getByRole("button", { name: "Converter" })).toBeInTheDocument();
    expect(within(linhaFechada).queryByRole("button", { name: "Converter" })).not.toBeInTheDocument();
    expect(within(linhaFechada).getByText("Virou oportunidade")).toBeInTheDocument();
  });
});

describe("conversão em oportunidade", () => {
  beforeEach(() => vi.clearAllMocks());

  it("pré-preenche o grupo com a empresa do lead, e envia o que foi digitado", async () => {
    vi.mocked(api.converterLead).mockResolvedValue({} as never);
    await abrir([lead({ empresa_texto: "Gama Ltda" })]);

    await userEvent.click(screen.getByRole("button", { name: "Converter" }));

    expect(screen.getByLabelText(/grupo econômico/i)).toHaveValue("Gama Ltda");

    await userEvent.type(screen.getByLabelText(/serviço/i), "BPO Contábil");
    await userEvent.click(screen.getByRole("button", { name: /converter em oportunidade/i }));

    await waitFor(() => expect(api.converterLead).toHaveBeenCalledOnce());
    const [id, dados] = vi.mocked(api.converterLead).mock.calls[0];
    expect(id).toBe(1);
    expect(dados).toEqual({ nome_do_grupo: "Gama Ltda", servico: "BPO Contábil" });
  });

  it("sem empresa informada, usa o nome do próprio lead", async () => {
    await abrir([lead({ empresa_texto: null, nome: "Fulano de Tal" })]);

    await userEvent.click(screen.getByRole("button", { name: "Converter" }));

    expect(screen.getByLabelText(/grupo econômico/i)).toHaveValue("Fulano de Tal");
  });
});
