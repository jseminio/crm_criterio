/** A fila de leads: cadastro, edição de situação e conversão em oportunidade.
 *
 * O ponto mais sensível é "Convertido" — um lead só chega lá pela conversão,
 * nunca escolhido à mão, porque esse estado pressupõe a oportunidade que o
 * sustenta (ver a trava equivalente na API, corrigida em 21/09/2026).
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { ConversaDoSdr, LeadResumo, Listas, MensagemDoSdr, Pagina } from "../api/tipos";
import { JanelaDoWhatsapp, Leads } from "./Leads";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      leads: vi.fn(),
      criarLead: vi.fn(),
      editarLead: vi.fn(),
      converterLead: vi.fn(),
      conversasDoLead: vi.fn().mockResolvedValue([]),
      modoDasRespostas: vi.fn().mockResolvedValue({ modo: "Supervisionado" }),
      responderAoLead: vi.fn(),
      devolverParaAIA: vi.fn(),
      enviarRascunho: vi.fn(),
      descartarRascunho: vi.fn(),
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
  situacoes: [],
  situacoes_de_lead: ["Novo", "Em contato", "Qualificado", "Convertido", "Descartado"],
  temperaturas: ["Frio", "Morno", "Quente"],
  tipos_de_canal: ["Sócios", "Parceiros"],
  tipos_de_canal_em_operacao: ["Sócios", "Parceiros"],
  motivos_de_recusa: [],
  motivos_de_encerramento: [],
  iniciativas_de_encerramento: [],
  papeis_de_contato: [],
  linhas_de_servico: [],
  situacoes_de_grupo: [],
  captadores: ["EL", "BO"],
  portes: ["Micro", "Pequeno", "Médio", "Grande", "Extra Grande"],
  servicos: [],
  motivos_de_descarte: ["Porte abaixo do mínimo", "Pediu para não ser contatado"],
  aderencias: ["Bate", "Em parte", "Não bate"],
  temas_de_expectativa: ["Preço", "Serviço / escopo", "Prazo", "Porte ou segmento", "Outro"],
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
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.conversasDoLead).mockResolvedValue([]);
  });

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

  it("só o lead qualificado tem botão de converter; o convertido diz que virou oportunidade", async () => {
    await abrir([
      lead({ id: 1, nome: "Pronto", situacao: "Qualificado", porte_estimado: "Médio" }),
      lead({ id: 2, nome: "Aberto" }),
      lead({ id: 3, nome: "Fechado", convertido_em_id: 9 }),
    ]);

    const linha = (nome: string) => screen.getByText(nome).closest("tr")!;

    expect(within(linha("Pronto")).getByRole("button", { name: "Converter" })).toBeInTheDocument();
    expect(within(linha("Aberto")).queryByRole("button", { name: "Converter" })).not.toBeInTheDocument();
    expect(within(linha("Aberto")).getByText("Qualifique para converter")).toBeInTheDocument();
    expect(within(linha("Fechado")).getByText("Virou oportunidade")).toBeInTheDocument();
  });

  it("mostra o porte do qualificado e a marca de não contatar", async () => {
    await abrir([
      lead({ situacao: "Qualificado", porte_estimado: "Grande" }),
      lead({ id: 2, nome: "Saiu", situacao: "Descartado", motivo_descarte: "Pediu para não ser contatado", nao_contatar: true }),
    ]);

    expect(screen.getByText("Porte Grande")).toBeInTheDocument();
    const linhaSaiu = screen.getByText("Saiu").closest("tr")!;
    expect(within(linhaSaiu).getByText("Não contatar")).toBeInTheDocument();
    expect(within(linhaSaiu).getByText("Pediu para não ser contatado")).toBeInTheDocument();
  });

  it("filtra pela origem", async () => {
    await abrir([lead()]);

    await userEvent.selectOptions(screen.getByLabelText("Origem"), "Prospecção ativa");

    await waitFor(() =>
      expect(vi.mocked(api.leads)).toHaveBeenLastCalledWith(
        expect.objectContaining({ tipo_canal: "Prospecção ativa" }),
      ),
    );
  });
});

describe("qualificação e descarte", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.conversasDoLead).mockResolvedValue([]);
  });

  it("qualificar exige o porte antes de salvar, e envia o porte", async () => {
    vi.mocked(api.editarLead).mockResolvedValue(lead());
    await abrir([lead()]);

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    await userEvent.selectOptions(screen.getByLabelText("Situação"), "Qualificado");

    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeDisabled();
    expect(screen.getByText(/escolha o porte estimado/i)).toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("Porte estimado"), "Médio");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(api.editarLead).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarLead).mock.calls[0];
    expect(mudancas).toMatchObject({ situacao: "Qualificado", porte_estimado: "Médio" });
    expect(mudancas).not.toHaveProperty("motivo_descarte");
  });

  it("descartar exige o motivo", async () => {
    vi.mocked(api.editarLead).mockResolvedValue(lead());
    await abrir([lead()]);

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    await userEvent.selectOptions(screen.getByLabelText("Situação"), "Descartado");
    expect(screen.getByRole("button", { name: /salvar alterações/i })).toBeDisabled();

    await userEvent.selectOptions(screen.getByLabelText("Motivo do descarte"), "Porte abaixo do mínimo");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));

    await waitFor(() => expect(api.editarLead).toHaveBeenCalledOnce());
    expect(vi.mocked(api.editarLead).mock.calls[0][1]).toMatchObject({
      situacao: "Descartado",
      motivo_descarte: "Porte abaixo do mínimo",
    });
  });

  it("mostra a conversa com a IA dentro do lead", async () => {
    vi.mocked(api.conversasDoLead).mockResolvedValue([
      {
        id: 7, lead_id: 1, canal: "WhatsApp", iniciada_em: "2026-09-27T12:00:00Z",
        encerrada_em: null, desfecho: null, motivo_transbordo: null, destino_transbordo: null,
        atendida_em: null, nota: null,
        mensagens: [
          { id: 1, autor: "IA", enviada_em: "2026-09-27T12:00:05Z", texto: "Oi, aqui é da Critério",
            intencao: null, confianca: null, fallback: false, termo_nao_reconhecido: null, tom: null },
          { id: 2, autor: "Lead", enviada_em: "2026-09-27T12:01:00Z", texto: "Quero trocar de contador",
            intencao: null, confianca: null, fallback: false, termo_nao_reconhecido: null, tom: "Positivo" },
        ],
      },
    ]);
    await abrir([lead()]);

    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));

    expect(await screen.findByText("Quero trocar de contador")).toBeInTheDocument();
    expect(screen.getByText("Em andamento")).toBeInTheDocument();
    expect(api.conversasDoLead).toHaveBeenCalledWith(1);
  });
});

describe("conversão em oportunidade", () => {
  beforeEach(() => vi.clearAllMocks());

  it("pré-preenche o grupo com a empresa do lead, e envia o que foi digitado", async () => {
    vi.mocked(api.converterLead).mockResolvedValue({} as never);
    await abrir([lead({ empresa_texto: "Gama Ltda", situacao: "Qualificado", porte_estimado: "Médio" })]);

    await userEvent.click(screen.getByRole("button", { name: "Converter" }));

    expect(screen.getByLabelText(/grupo econômico/i)).toHaveValue("Gama Ltda");

    await userEvent.click(screen.getByRole("button", { name: /^Serviço/ }));
    await userEvent.click(await screen.findByRole("option", { name: "Auditoria" }));
    await userEvent.click(screen.getByRole("button", { name: "Usar este serviço" }));
    await userEvent.click(screen.getByRole("button", { name: /converter em oportunidade/i }));

    await waitFor(() => expect(api.converterLead).toHaveBeenCalledOnce());
    const [id, dados] = vi.mocked(api.converterLead).mock.calls[0];
    expect(id).toBe(1);
    expect(dados).toEqual({ nome_do_grupo: "Gama Ltda", servico: "Auditoria" });
  });

  it("sem empresa informada, usa o nome do próprio lead", async () => {
    await abrir([
      lead({ empresa_texto: null, nome: "Fulano de Tal", situacao: "Qualificado", porte_estimado: "Médio" }),
    ]);

    await userEvent.click(screen.getByRole("button", { name: "Converter" }));

    expect(screen.getByLabelText(/grupo econômico/i)).toHaveValue("Fulano de Tal");
  });

  it("primeiro contato: sugere a data do SDR, registra a aderência e o que não bateu", async () => {
    vi.mocked(api.editarLead).mockResolvedValue(lead());
    await abrir([lead({ campanha: "BPO Financeiro — Tempo para Crescer", primeiro_contato_pelo_sdr: "2026-11-03T17:20:00Z" })]);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    expect(screen.getByText(/campanha “BPO Financeiro — Tempo para Crescer”/)).toBeInTheDocument();
    expect(screen.getByLabelText("Data e hora do 1º contato")).not.toHaveValue("");
    expect(screen.getByText(/Preenchido pela primeira mensagem do SDR/)).toBeInTheDocument();
    expect(screen.queryByText(/Sobre o quê/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: /Em parte/ }));
    expect(screen.getByRole("radio", { name: /Em parte/ })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("button", { name: "Preço" }));
    await userEvent.type(screen.getByLabelText("O que ele esperava, em uma frase"), "Achou que custava menos");
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));
    await waitFor(() => expect(api.editarLead).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarLead).mock.calls[0];
    expect(mudancas.aderencia).toBe("Em parte");
    expect(mudancas.aderencia_sobre).toEqual(["Preço"]);
    expect(mudancas.aderencia_esperava).toBe("Achou que custava menos");
    expect(mudancas.primeiro_contato_em).toBe("2026-11-03T17:20:00.000Z");
  });

  it("'Bate' esconde o detalhe e não manda o que não bateu", async () => {
    vi.mocked(api.editarLead).mockResolvedValue(lead());
    await abrir([lead({ aderencia: "Não bate", aderencia_sobre: ["Prazo"], primeiro_contato_em: "2026-11-03T17:20:00Z" })]);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    expect(screen.getByRole("button", { name: /Prazo/ })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("radio", { name: /^Bate/ }));
    expect(screen.queryByText(/Sobre o quê/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /salvar alterações/i }));
    await waitFor(() => expect(api.editarLead).toHaveBeenCalledOnce());
    const [, mudancas] = vi.mocked(api.editarLead).mock.calls[0];
    expect(mudancas.aderencia).toBe("Bate");
    expect(mudancas).not.toHaveProperty("aderencia_sobre");
    expect(mudancas).not.toHaveProperty("primeiro_contato_em");
  });
});

describe("conversa do WhatsApp (14/10/2026)", () => {
  const conversa = (extra: Partial<ConversaDoSdr> = {}): ConversaDoSdr => ({
    id: 1, lead_id: 1, canal: "WhatsApp", iniciada_em: "2026-10-14T13:30:00Z", encerrada_em: null, desfecho: null,
    motivo_transbordo: null, destino_transbordo: null, atendida_em: null, nota: null,
    ultima_do_lead_em: "2026-10-14T13:34:00Z", mensagens: [], ...extra,
  });

  it("janela aberta: diz até quando e quem responde", () => {
    render(<JanelaDoWhatsapp conversa={conversa()} modo="Supervisionado" agora={new Date("2026-10-14T20:00:00Z")} />);
    const aviso = screen.getByRole("status");
    expect(aviso).toHaveTextContent("aberta até");
    expect(aviso).toHaveTextContent("Respostas da IA: supervisionadas, a equipe envia cada uma.");
  });

  it("janela fechada: avisa com sinal e texto, não só cor", () => {
    render(<JanelaDoWhatsapp conversa={conversa()} agora={new Date("2026-10-16T10:00:00Z")} />);
    expect(screen.getByRole("status")).toHaveTextContent("⚠ Janela do WhatsApp fechada desde");
  });

  it("e-mail, conversa encerrada, com a equipe ou sem mensagem do lead: sem aviso", () => {
    const { container } = render(<>
      <JanelaDoWhatsapp conversa={conversa({ canal: "E-mail" })} />
      <JanelaDoWhatsapp conversa={conversa({ equipe_desde: "2026-10-14T14:00:00Z" })} />
      <JanelaDoWhatsapp conversa={conversa({ encerrada_em: "2026-10-14T14:00:00Z" })} />
      <JanelaDoWhatsapp conversa={conversa({ ultima_do_lead_em: null })} />
    </>);
    expect(container).toBeEmptyDOMElement();
  });

  it("mostra a entrega das mensagens da Critério", async () => {
    vi.mocked(api.conversasDoLead).mockResolvedValue([conversa({ mensagens: [
      { id: 1, autor: "IA", enviada_em: "2026-10-14T13:30:00Z", texto: "Olá, Marina!", intencao: null, confianca: null,
        fallback: false, termo_nao_reconhecido: null, tom: null, entrega: "lida" },
      { id: 2, autor: "Lead", enviada_em: "2026-10-14T13:34:00Z", texto: "SAIR", intencao: null, confianca: null,
        fallback: false, termo_nao_reconhecido: null, tom: null },
    ] })]);
    await abrir([lead()]);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    expect(await screen.findByText(/✓✓ lida/)).toBeInTheDocument();
    expect(screen.getByText("SAIR")).toBeInTheDocument();
  });
});

describe("respostas do SDR de IA (fase 1, 23/10/2026)", () => {
  const agora = Date.now();
  const iso = (minutos: number) => new Date(agora - minutos * 60_000).toISOString();
  const msg = (extra: Partial<MensagemDoSdr>): MensagemDoSdr => ({
    id: 1, autor: "IA", enviada_em: iso(5), texto: "", intencao: null, confianca: null, fallback: false,
    termo_nao_reconhecido: null, tom: null, ...extra,
  });
  const conversa = (extra: Partial<ConversaDoSdr> = {}): ConversaDoSdr => ({
    id: 9, lead_id: 1, canal: "WhatsApp", iniciada_em: iso(10), encerrada_em: null, desfecho: null,
    motivo_transbordo: null, destino_transbordo: null, atendida_em: null, nota: null, ultima_do_lead_em: iso(2),
    mensagens: [], ...extra,
  });

  async function abrirComConversa(c: ConversaDoSdr) {
    vi.mocked(api.conversasDoLead).mockResolvedValue([c]);
    await abrir([lead()]);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
  }

  it("rascunho: mostra a rota e o custo e envia com o texto ajustado", async () => {
    vi.mocked(api.enviarRascunho).mockResolvedValue(conversa());
    await abrirComConversa(conversa({ mensagens: [
      msg({ id: 1, autor: "Lead", texto: "Oi, vi o anúncio", enviada_em: iso(3) }),
      msg({ id: 2, texto: "O que fez você procurar uma mudança agora?", entrega: "rascunho", rota: "leve",
            custo_usd: "0.0046", enviada_em: iso(2) }),
    ] }));
    expect(await screen.findByText(/Rascunho da IA · ainda não enviado · modelo leve · US\$ 0,005/)).toBeInTheDocument();
    expect(screen.getByText(/custo da IA US\$ 0,005/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Responder ao lead/)).not.toBeInTheDocument();  // uma ação por vez
    const caixa = screen.getByLabelText("Texto do rascunho");
    await userEvent.clear(caixa);
    await userEvent.type(caixa, "Texto ajustado.");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(api.enviarRascunho).toHaveBeenCalledWith(2, "Texto ajustado.");
  });

  it("rascunho sem mudança vai como a IA escreveu; descartar passa para a equipe", async () => {
    vi.mocked(api.enviarRascunho).mockResolvedValue(conversa());
    vi.mocked(api.descartarRascunho).mockResolvedValue(conversa());
    await abrirComConversa(conversa({ mensagens: [msg({ id: 2, texto: "Pergunta?", entrega: "rascunho", rota: "leve" })] }));
    await userEvent.click(await screen.findByRole("button", { name: "Enviar" }));
    expect(api.enviarRascunho).toHaveBeenCalledWith(2, undefined);
    await userEvent.click(screen.getByRole("button", { name: "Descartar e passar para a equipe" }));
    expect(api.descartarRascunho).toHaveBeenCalledWith(2);
  });

  it("com a equipe: diz por quê e para quem, e a equipe responde ou devolve", async () => {
    vi.mocked(api.responderAoLead).mockResolvedValue(conversa());
    vi.mocked(api.devolverParaAIA).mockResolvedValue(conversa());
    await abrirComConversa(conversa({
      desfecho: "Passou para a equipe", encerrada_em: iso(1), equipe_desde: iso(1),
      equipe_motivo: "Dúvida técnica do caso do lead", destino_transbordo: "Técnico fiscal",
      mensagens: [
        msg({ id: 1, autor: "Lead", texto: "Vale a pena eu sair do Simples Nacional?", enviada_em: iso(2) }),
        msg({ id: 2, texto: "Essa é uma análise que nossos especialistas fazem.", entrega: "entregue", rota: "leve",
              custo_usd: "0.004", enviada_em: iso(1) }),
      ],
    }));
    const faixa = await screen.findByText(/Aguardando a equipe/);
    expect(faixa.closest("p")).toHaveTextContent("Dúvida técnica do caso do lead → Técnico fiscal.");
    expect(faixa.closest("p")).toHaveTextContent("A IA não responde mais nesta conversa.");
    expect(screen.getByText("⚑ Com a equipe")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Responder ao lead/), "Olá, aqui é o Eduardo.");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(api.responderAoLead).toHaveBeenCalledWith(9, "Olá, aqui é o Eduardo.");
    await userEvent.click(screen.getByRole("button", { name: "Devolver para a IA" }));
    expect(api.devolverParaAIA).toHaveBeenCalledWith(9);
  });

  it("janela fechada: não deixa escrever, e diz por quê", async () => {
    await abrirComConversa(conversa({ equipe_desde: iso(60 * 30), ultima_do_lead_em: iso(60 * 30) }));
    expect(await screen.findByLabelText(/Responder ao lead/)).toBeDisabled();
    expect(screen.getByText(/Janela do WhatsApp fechada: só modelo aprovado/)).toBeInTheDocument();
  });

  it("conversa nova depois de devolver: a janela vem da última mensagem do lead em qualquer conversa", async () => {
    vi.mocked(api.conversasDoLead).mockResolvedValue([
      conversa({ id: 8, desfecho: "Passou para a equipe", encerrada_em: iso(5), ultima_do_lead_em: iso(6) }),
      conversa({ id: 9, iniciada_em: iso(1), ultima_do_lead_em: null }),
    ]);
    await abrir([lead()]);
    await userEvent.click(screen.getByRole("button", { name: "Abrir" }));
    expect(await screen.findByLabelText(/Responder ao lead/)).toBeEnabled();
  });

  it("resposta barrada pela trava aparece riscada, com o motivo", async () => {
    await abrirComConversa(conversa({ mensagens: [
      msg({ id: 3, texto: "São R$ 800 por mês.", entrega: "bloqueada", rota: "leve",
            observacao: "A mensagem fala de preço: a IA não informa preço, ela passa para a equipe" }),
    ] }));
    expect(await screen.findByText(/barrada pela trava, não saiu/)).toBeInTheDocument();
    expect(screen.getByText("São R$ 800 por mês.").tagName).toBe("S");
    expect(screen.getByText(/a IA não informa preço/)).toBeInTheDocument();
  });

  it("erro do servidor aparece na conversa", async () => {
    vi.mocked(api.responderAoLead).mockRejectedValue(new ErroDaApi(409, "o lead pediu para não ser contatado"));
    await abrirComConversa(conversa({ equipe_desde: iso(1) }));
    await userEvent.type(await screen.findByLabelText(/Responder ao lead/), "Oi");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("o lead pediu para não ser contatado");
  });
});
