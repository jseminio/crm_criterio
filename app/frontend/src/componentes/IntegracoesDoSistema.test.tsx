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
    api: { integracoes: vi.fn(), salvarIntegracao: vi.fn(), testarIntegracao: vi.fn(), enviarTesteDeIntegracao: vi.fn() },
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

const cartao = async (titulo: string) => within((await screen.findByRole("heading", { name: titulo })).closest("section")!);

describe("Configurações › Integrações: chaves pela tela (07/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
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

  it("liga o disparo com uma caixa, sem botão de teste", async () => {
    render(<IntegracoesDoSistema />);
    const disparo = await cartao("Disparo do lembrete e do agradecimento");
    expect(disparo.queryByRole("button", { name: "Testar conexão" })).not.toBeInTheDocument();
    await userEvent.click(disparo.getByRole("checkbox"));
    await userEvent.click(disparo.getByRole("button", { name: "Salvar" }));
    expect(api.salvarIntegracao).toHaveBeenCalledWith("disparo", { valores: { "disparo.ligado": "true" }, apagar: [] });
  });
});
