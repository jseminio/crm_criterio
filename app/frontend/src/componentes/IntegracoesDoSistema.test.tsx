import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Integracoes } from "../api/tipos";
import { IntegracoesDoSistema } from "./IntegracoesDoSistema";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      integracoes: vi.fn(), salvarIntegracao: vi.fn(), testarIntegracao: vi.fn(), enviarTesteDeIntegracao: vi.fn(),
      pastasDoGranola: vi.fn(), situacaoDoGranola: vi.fn(), buscarNoGranola: vi.fn(), destinoDaNotaDoGranola: vi.fn(),
      descartarDaFilaDoGranola: vi.fn(),
    },
  };
});

const campo = (chave: string, rotulo: string, extra: object = {}) => ({
  chave, rotulo, segredo: false, origem: "vazio", valor: null, final: null, ilegivel: false,
  padrao: "", ajuda: "", exemplo: "", opcoes: [], ...extra,
});

const INTEGRACOES: Integracoes = {
  grupos: [
    {
      chave: "ia", titulo: "Inteligência artificial", testavel: true, envia_teste: false, configurado: true,
      alterado_por: "atualizador (copiado do servidor)", alterado_em: "2026-10-07T12:00:00Z",
      campos: [
        campo("anthropic.chave", "Chave da API da Anthropic", { segredo: true, origem: "tela", final: "rQAA" }),
        campo("anthropic.modelo", "Modelo da Anthropic", { origem: "padrão", valor: "claude-opus-5", padrao: "claude-opus-5" }),
      ],
    },
    {
      chave: "whatsapp", titulo: "WhatsApp (Meta)", testavel: true, envia_teste: true, configurado: false,
      alterado_por: null, alterado_em: null,
      campos: [
        campo("whatsapp.token", "Token permanente", { segredo: true }),
        campo("whatsapp.numero_id", "ID do número de telefone", { origem: "servidor", valor: "5555" }),
      ],
    },
    {
      chave: "disparo", titulo: "Disparo do lembrete e do agradecimento", testavel: false, envia_teste: false,
      configurado: true, alterado_por: null, alterado_em: null,
      campos: [campo("disparo.ligado", "Disparo ligado", { origem: "padrão", valor: "false", opcoes: ["true", "false"] })],
    },
  ],
};

/** Desde 15/10/2026 cada integração tem a sua aba: abre a aba (pelo começo do nome) e devolve o cartão. */
const cartao = async (titulo: string) => {
  const primeira = titulo === "Inteligência artificial" ? "IA" : titulo.split(" ")[0];
  const aba = (await screen.findAllByRole("tab")).find((t) => (t.textContent ?? "").startsWith(primeira));
  if (aba) await userEvent.click(aba);
  return within((await screen.findByRole("heading", { name: titulo })).closest("section")!);
};

describe("Configurações › Integrações: chaves pela tela (07/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();  // a aba escolhida fica guardada: cada teste começa na primeira
    vi.mocked(api.integracoes).mockResolvedValue(INTEGRACOES);
    vi.mocked(api.salvarIntegracao).mockResolvedValue(INTEGRACOES);
  });

  it("mostra a situação com palavra, a origem e nunca o segredo inteiro", async () => {
    render(<IntegracoesDoSistema />);
    const ia = await cartao("Inteligência artificial");
    expect(ia.getByText("Configurado")).toBeInTheDocument();
    expect(ia.getByText("rQAA")).toBeInTheDocument();
    expect(ia.getByLabelText("Chave da API da Anthropic")).toHaveValue("");
    expect(ia.getByText(/atualizador \(copiado do servidor\)/)).toBeInTheDocument();
    const whatsapp = await cartao("WhatsApp (Meta)");
    expect(whatsapp.getByText("Falta configurar")).toBeInTheDocument();
    expect(whatsapp.getByLabelText("ID do número de telefone")).toHaveValue("5555");
    expect(whatsapp.getByText(/vem do servidor/)).toBeInTheDocument();
  });

  it("salva só o que mudou e troca a chave sem mostrar a antiga", async () => {
    render(<IntegracoesDoSistema />);
    const ia = await cartao("Inteligência artificial");
    const salvar = ia.getByRole("button", { name: "Salvar" });
    expect(salvar).toBeDisabled();
    await userEvent.type(ia.getByLabelText("Chave da API da Anthropic"), "sk-ant-nova");
    await userEvent.click(salvar);
    expect(api.salvarIntegracao).toHaveBeenCalledWith("ia", { valores: { "anthropic.chave": "sk-ant-nova" }, apagar: [] });
    expect(await ia.findByText(/Salvo\. Já vale para o CRM/)).toBeInTheDocument();
  });

  it("tira a chave da tela", async () => {
    render(<IntegracoesDoSistema />);
    const ia = await cartao("Inteligência artificial");
    await userEvent.click(ia.getByRole("button", { name: "Tirar da tela" }));
    await userEvent.click(ia.getByRole("button", { name: "Salvar" }));
    expect(api.salvarIntegracao).toHaveBeenCalledWith("ia", { valores: {}, apagar: ["anthropic.chave"] });
  });

  it("testa a conexão e mostra o resultado no cartão", async () => {
    vi.mocked(api.testarIntegracao).mockResolvedValue({ ok: false, mensagem: "A Anthropic recusou a chave da API.", segundos: 0.4, em: "" });
    render(<IntegracoesDoSistema />);
    const ia = await cartao("Inteligência artificial");
    await userEvent.click(ia.getByRole("button", { name: "Testar conexão" }));
    expect(await ia.findByRole("alert")).toHaveTextContent("✗ A Anthropic recusou a chave da API. (0,4 s)");
  });

  it("envia o modelo de teste só para o número digitado", async () => {
    vi.mocked(api.enviarTesteDeIntegracao).mockResolvedValue({ ok: true, mensagem: "A Meta aceitou o modelo.", segundos: 1, em: "" });
    render(<IntegracoesDoSistema />);
    const whatsapp = await cartao("WhatsApp (Meta)");
    const enviar = whatsapp.getByRole("button", { name: "Enviar modelo de teste" });
    expect(enviar).toBeDisabled();
    await userEvent.type(whatsapp.getByLabelText("WhatsApp (Meta): enviar teste para"), "21 99999-0000");
    await userEvent.click(enviar);
    expect(api.enviarTesteDeIntegracao).toHaveBeenCalledWith("whatsapp", "21 99999-0000");
    expect(await whatsapp.findByRole("status")).toHaveTextContent("✓ A Meta aceitou o modelo.");
  });

  it("escolhe a OpenAI como principal e a Anthropic como reserva", async () => {
    vi.mocked(api.integracoes).mockResolvedValue({
      grupos: [{
        ...INTEGRACOES.grupos[0],
        campos: [
          campo("ia.principal", "IA principal", { origem: "padrão", valor: "Anthropic", opcoes: ["Anthropic", "OpenAI"] }),
          campo("ia.reserva", "IA de reserva", { origem: "padrão", valor: "Nenhuma", opcoes: ["Nenhuma", "Anthropic", "OpenAI"] }),
          campo("openai.chave", "Chave da API da OpenAI", { segredo: true }),
        ],
      }],
    });
    render(<IntegracoesDoSistema />);
    const ia = await cartao("Inteligência artificial");
    await userEvent.selectOptions(ia.getByLabelText("IA principal"), "OpenAI");
    await userEvent.selectOptions(ia.getByLabelText("IA de reserva"), "Anthropic");
    await userEvent.type(ia.getByLabelText("Chave da API da OpenAI"), "sk-proj-nova");
    await userEvent.click(ia.getByRole("button", { name: "Salvar" }));
    expect(api.salvarIntegracao).toHaveBeenCalledWith("ia", {
      valores: { "ia.principal": "OpenAI", "ia.reserva": "Anthropic", "openai.chave": "sk-proj-nova" }, apagar: [],
    });
  });

  it("liga o disparo com uma caixa, sem botão de teste", async () => {
    render(<IntegracoesDoSistema />);
    const disparo = await cartao("Disparo do lembrete e do agradecimento");
    expect(disparo.queryByRole("button", { name: "Testar conexão" })).not.toBeInTheDocument();
    await userEvent.click(disparo.getByRole("checkbox"));
    await userEvent.click(disparo.getByRole("button", { name: "Salvar" }));
    expect(api.salvarIntegracao).toHaveBeenCalledWith("disparo", { valores: { "disparo.ligado": "true" }, apagar: [] });
  });
});

describe("WhatsApp: receber as mensagens dos leads (14/10/2026)", () => {
  const COM_RECEBIMENTO: Integracoes = {
    grupos: [{
      chave: "whatsapp", titulo: "WhatsApp (Meta)", testavel: true, envia_teste: true, configurado: true,
      alterado_por: null, alterado_em: null, situacao: "⚠ Nenhuma mensagem recebida ainda.",
      campos: [
        campo("whatsapp.token", "Token permanente", { segredo: true, origem: "tela", final: "zz99" }),
        campo("whatsapp.recebimento", "Recebimento ligado", { origem: "padrão", valor: "false", opcoes: ["true", "false"] }),
        campo("whatsapp.token_verificacao", "Token de verificação", { segredo: true, origem: "tela", final: "7f3a" }),
        campo("whatsapp.app_secret", "Chave secreta do aplicativo (App Secret)", { segredo: true }),
      ],
    }],
  };

  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.integracoes).mockResolvedValue(COM_RECEBIMENTO);
    vi.mocked(api.salvarIntegracao).mockResolvedValue(COM_RECEBIMENTO);
  });

  it("mostra o endereço, a situação em texto e nunca o token salvo", async () => {
    render(<IntegracoesDoSistema />);
    const whatsapp = await cartao("WhatsApp (Meta)");
    const bloco = within(whatsapp.getByRole("group", { name: "Receber as mensagens dos leads" }));
    expect(bloco.getByLabelText("Endereço para colar na Meta (URL de retorno)"))
      .toHaveValue(`${window.location.origin}/api/whatsapp/webhook`);
    expect(bloco.getByText(/termina em/)).toHaveTextContent("7f3a");
    expect(bloco.getByLabelText("Token de verificação")).toHaveValue("");
    expect(bloco.getByRole("status")).toHaveTextContent("⚠ Nenhuma mensagem recebida ainda.");
    expect(bloco.getByText(/ninguém responde sozinho/)).toBeInTheDocument();
  });

  it("gera o token no navegador e o manda ao salvar, junto com o liga/desliga", async () => {
    render(<IntegracoesDoSistema />);
    const whatsapp = await cartao("WhatsApp (Meta)");
    await userEvent.click(whatsapp.getByRole("button", { name: "Gerar" }));
    const gerado = (whatsapp.getByLabelText("Token de verificação") as HTMLInputElement).value;
    expect(gerado).toMatch(/^crm-[0-9a-f]{32}$/);
    await userEvent.click(whatsapp.getByRole("checkbox"));
    await userEvent.type(whatsapp.getByLabelText("Chave secreta do aplicativo (App Secret)"), "segredo-do-app");
    await userEvent.click(whatsapp.getByRole("button", { name: "Salvar" }));
    expect(api.salvarIntegracao).toHaveBeenCalledWith("whatsapp", {
      valores: { "whatsapp.recebimento": "true", "whatsapp.token_verificacao": gerado, "whatsapp.app_secret": "segredo-do-app" },
      apagar: [],
    });
  });

  it("cada token gerado é diferente", async () => {
    const { gerarToken } = await import("./IntegracoesDoSistema");
    expect(gerarToken()).not.toBe(gerarToken());
  });
});

describe("Integrações em abas (15/10/2026)", () => {
  it("uma aba por integração, com a situação em sinal e texto, e o rascunho guardado ao trocar de aba", async () => {
    localStorage.clear();
    vi.mocked(api.integracoes).mockResolvedValue(INTEGRACOES as never);
    render(<IntegracoesDoSistema />);
    const abas = await screen.findAllByRole("tab");
    expect(abas.map((a) => a.textContent)).toEqual(INTEGRACOES.grupos.map(() => expect.stringMatching(/.+ [✓○]/)));
    const whatsapp = abas.find((a) => a.textContent!.startsWith("WhatsApp"))!;
    expect(whatsapp).toHaveAttribute("title", expect.stringContaining("falta configurar"));
    await userEvent.click(whatsapp);
    expect(whatsapp).toHaveAttribute("aria-selected", "true");
    const campo = screen.getByLabelText("ID do número de telefone");
    await userEvent.type(campo, "123");
    expect(whatsapp).toHaveTextContent("•");
    await userEvent.click(abas.find((a) => a.textContent!.startsWith("Disparo"))!);
    expect(screen.queryByRole("heading", { name: "WhatsApp (Meta)" })).toBeNull();
    await userEvent.click(whatsapp);
    expect(screen.getByLabelText("ID do número de telefone")).toHaveValue("5555123");
  });
});

describe("Respostas do SDR (fase 1, 23/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    vi.mocked(api.integracoes).mockResolvedValue({ grupos: [...INTEGRACOES.grupos, {
      chave: "sdr_respostas", titulo: "Respostas do SDR", testavel: false, envia_teste: false, configurado: true,
      alterado_por: null, alterado_em: null,
      situacao: "Modo supervisionado: a IA rascunha e a equipe envia. Nenhuma resposta da IA nos últimos 30 dias.",
      campos: [
        campo("sdr.modo", "Modo das respostas", { origem: "padrão", valor: "Desligado", padrao: "Desligado",
          opcoes: ["Desligado", "Supervisionado", "Automático"] }),
        campo("sdr.modelo_leve", "Modelo leve da Anthropic", { origem: "padrão", valor: "claude-haiku-4-5" }),
      ],
    }] });
    vi.mocked(api.salvarIntegracao).mockResolvedValue(INTEGRACOES);
  });

  it("aba própria com o modo, o modelo leve e a situação em texto, sem botão de teste", async () => {
    render(<IntegracoesDoSistema />);
    const c = await cartao("Respostas do SDR");
    expect(c.getByRole("status")).toHaveTextContent("Modo supervisionado: a IA rascunha e a equipe envia.");
    expect(c.queryByRole("button", { name: /Testar/ })).not.toBeInTheDocument();
    await userEvent.selectOptions(c.getByLabelText(/Modo das respostas/), "Supervisionado");
    await userEvent.click(c.getByRole("button", { name: "Salvar" }));
    expect(api.salvarIntegracao).toHaveBeenCalledWith("sdr_respostas", expect.objectContaining({
      valores: expect.objectContaining({ "sdr.modo": "Supervisionado" }),
    }));
  });
});

describe("Granola (23/10/2026)", () => {
  const GRANOLA = {
    chave: "granola", titulo: "Granola (notas das reuniões)", testavel: true, envia_teste: false, configurado: true,
    alterado_por: "Eduardo Luiz", alterado_em: "2026-10-23T14:02:00Z",
    campos: [
      campo("granola.ligado", "Busca ligada", { origem: "tela", valor: "true", opcoes: ["true", "false"] }),
      campo("granola.chave", "Chave da API do Granola", { segredo: true, origem: "tela", final: "7c1e" }),
      campo("granola.pasta_lead", "Pasta das reuniões com o lead", { origem: "padrão", valor: "Potencial Cliente", padrao: "Potencial Cliente" }),
      campo("granola.pasta_resultado", "Pasta das Reuniões de Resultado", { origem: "tela", valor: "Antiga", padrao: "Reunião de Resultado" }),
      campo("granola.desde", "Trazer notas a partir de", { exemplo: "01/10/2026" }),
    ],
  };
  const NOTA = {
    id: 5, tipo: "Reunião com o lead" as const, titulo: "Conversa inicial · Empresa Exemplo", data: "2026-10-22",
    participantes: "contato@exemplo.com.br", link: null, motivo: "Nenhum participante é contato do CRM.", resumo: "x",
    transcricao: null, chegou_em: "2026-10-22T15:00:00Z",
  };
  const SITUACAO = {
    ligada: true, proxima: "2026-10-23T17:20:00Z",
    ultima: { em: "2026-10-23T17:10:00Z", lidas: 9, novas: 3, a_usar: 2, precisam: 1, erro: null, aviso: null },
    precisam: [NOTA], oportunidades: [{ id: 8, nome: "Exemplo Alfa · BPO Financeiro" }], grupos: [],
  };

  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    localStorage.setItem("crm.integracoes.aba", "granola");
    vi.mocked(api.integracoes).mockResolvedValue({ grupos: [...INTEGRACOES.grupos, GRANOLA] } as never);
    vi.mocked(api.pastasDoGranola).mockResolvedValue(["Outras", "Potencial Cliente", "Reunião de Resultado"]);
    vi.mocked(api.situacaoDoGranola).mockResolvedValue(SITUACAO as never);
  });

  it("as pastas vêm do Granola e a que não existe mais aparece marcada", async () => {
    render(<IntegracoesDoSistema />);
    const granola = within((await screen.findByRole("heading", { name: "Granola (notas das reuniões)" })).closest("section")!);
    const lead = await granola.findByRole("combobox", { name: "Pasta das reuniões com o lead" });
    expect(lead).toHaveValue("Potencial Cliente");
    const res = granola.getByRole("combobox", { name: "Pasta das Reuniões de Resultado" });
    expect(res).toHaveValue("Antiga");
    expect(granola.getByRole("option", { name: "Antiga (não existe no Granola)" })).toBeInTheDocument();
    await userEvent.selectOptions(res, "Reunião de Resultado");
    await userEvent.click(granola.getByRole("button", { name: "Salvar" }));
    expect(api.salvarIntegracao).toHaveBeenCalledWith("granola", {
      valores: { "granola.pasta_resultado": "Reunião de Resultado" }, apagar: [] });
  });

  it("sem conseguir ler as pastas, o nome se digita", async () => {
    vi.mocked(api.pastasDoGranola).mockRejectedValue(new Error("x"));
    render(<IntegracoesDoSistema />);
    const campo = await screen.findByRole("textbox", { name: "Pasta das reuniões com o lead" });
    expect(campo).toBeInTheDocument();
    expect(await screen.findAllByText(/Não consegui ler as pastas do Granola/)).not.toHaveLength(0);
  });

  it("mostra a situação, busca agora e resolve a fila Precisa de você", async () => {
    vi.mocked(api.buscarNoGranola).mockResolvedValue({ em: "2026-10-23T17:12:00Z", lidas: 9, novas: 1, a_usar: 1, precisam: 0, erro: null, aviso: null });
    vi.mocked(api.destinoDaNotaDoGranola).mockResolvedValue({ ...SITUACAO, precisam: [] } as never);
    render(<IntegracoesDoSistema />);
    const fila = await screen.findByRole("group", { name: "Situação da busca" });
    expect(within(fila).getByRole("status")).toHaveTextContent("3 notas novas: 2 entraram sozinhas, 1 precisa de você.");
    expect(within(fila).getByText("Precisa de você (1)")).toBeInTheDocument();
    expect(within(fila).getByText(/Nenhum participante é contato do CRM/)).toBeInTheDocument();
    const aplicar = within(fila).getByRole("button", { name: "Aplicar" });
    expect(aplicar).toBeDisabled();
    await userEvent.selectOptions(within(fila).getByLabelText(/Entrar em: Conversa inicial/), "8");
    await userEvent.click(aplicar);
    expect(api.destinoDaNotaDoGranola).toHaveBeenCalledWith(5, { oportunidade_id: 8 });
    expect(await within(fila).findByText(/Nada esperando você/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Buscar agora" }));
    expect(await screen.findByText(/1 nota nova · 1 entrou sozinha, 0 precisam de você/)).toBeInTheDocument();
    expect(api.situacaoDoGranola).toHaveBeenCalledTimes(2); // a fila relê depois da busca
  });
});
