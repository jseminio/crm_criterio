/** Login com e-mail e senha (issue #89), de ponta a ponta no cliente: aqui o `fetch` é falso, mas o
 * `api`, o token no `sessionStorage` e o tratamento do 401 são os de verdade. */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { api } from "./api/cliente";
import { TrocarSenha } from "./componentes/TrocarSenha";
import { Entrada, SESSAO_EXPIROU, usarAcesso } from "./entrada";

const CHAVE = "crm.sessao";
const EU_KARINE = {
  modo: "senha", email: "karine@grupocriterio.com.br", nome: "Karine", perfil: "Comercial", administrador: false, permissoes: ["funil.ver"],
};
const daqui = (minutos: number) => new Date(Date.now() + minutos * 60_000).toISOString();

type Rota = { status: number; corpo?: unknown };
let rotas: Record<string, Rota>;
let pedidos: { url: string; metodo: string; corpo: unknown; autorizacao: string | null }[];

function responder(rota: Rota | undefined) {
  if (!rota) return new Response(JSON.stringify({ detail: "Não autenticado." }), { status: 401, headers: { "Content-Type": "application/json" } });
  if (rota.status === 204) return new Response(null, { status: 204 });
  return new Response(JSON.stringify(rota.corpo ?? {}), { status: rota.status, headers: { "Content-Type": "application/json" } });
}

beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
  pedidos = [];
  rotas = { "GET /api/acesso/entrada": { status: 200, corpo: { modo: "senha" } } };
  vi.stubGlobal("fetch", vi.fn(async (url: string, opcoes?: RequestInit) => {
    const metodo = opcoes?.method ?? "GET";
    const cabecalhos = (opcoes?.headers ?? {}) as Record<string, string>;
    pedidos.push({ url, metodo, corpo: opcoes?.body ? JSON.parse(String(opcoes.body)) : null, autorizacao: cabecalhos.Authorization ?? null });
    return responder(rotas[`${metodo} ${url}`]);
  }));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function Dentro() {
  const { eu, sair } = usarAcesso();
  return (
    <div>
      <p>{eu.nome} · {eu.perfil} · {eu.modo}</p>
      <button type="button" onClick={() => void api.listas().catch(() => undefined)}>Abrir listas</button>
      <button type="button" onClick={sair}>Sair</button>
    </div>
  );
}

function ComTrocaDeSenha() {
  const [aberta, definirAberta] = useState(false);
  return (
    <>
      <button type="button" onClick={() => definirAberta(true)}>Abrir troca</button>
      {aberta && <TrocarSenha aoFechar={() => definirAberta(false)} />}
    </>
  );
}

const montar = () => render(<Entrada><Dentro /></Entrada>);

describe("entrada com e-mail e senha", () => {
  it("modo senha mostra o formulário, com foco no e-mail, sem perguntar quem é", async () => {
    montar();
    const email = await screen.findByLabelText("E-mail");
    await waitFor(() => expect(email).toHaveFocus()); // o foco vem num efeito, depois de montar
    expect(screen.getByLabelText("Senha")).toHaveAttribute("type", "password");
    expect(screen.getByRole("button", { name: "Entrar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Microsoft/ })).toBeNull();
    expect(pedidos.map((p) => p.url)).toEqual(["/api/acesso/entrada"]);
  });

  it("a tela de entrada tem um h1 (axe: page-has-heading-one)", async () => {
    montar();
    expect(await screen.findByRole("heading", { level: 1, name: "Critério CRM" })).toHaveClass("login-marca");
  });

  it("trocar a senha guarda o token novo, e o próximo pedido já sai com ele", async () => {
    window.sessionStorage.setItem(CHAVE, JSON.stringify({ token: "tok-guardado", expira_em: daqui(30) }));
    const expiraNovo = daqui(120);
    rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
    rotas["GET /api/listas"] = { status: 200, corpo: {} };
    rotas["POST /api/acesso/senha"] = {
      status: 200,
      corpo: { token: "tok-novo", expira_em: expiraNovo, email: EU_KARINE.email, nome: "Karine", perfil: "Comercial", administrador: false },
    };
    render(<Entrada><Dentro /><ComTrocaDeSenha /></Entrada>);
    await userEvent.click(await screen.findByRole("button", { name: "Abrir troca" }));
    await userEvent.type(screen.getByLabelText("Senha atual"), "antiga-123");
    await userEvent.type(screen.getByLabelText("Senha nova"), "nova-senha-1");
    await userEvent.type(screen.getByLabelText("Repita a senha nova"), "nova-senha-1");
    await userEvent.click(screen.getByRole("button", { name: "Trocar senha" }));
    expect(await screen.findByRole("status")).toHaveTextContent("Senha trocada.");

    const troca = pedidos.find((p) => p.url === "/api/acesso/senha")!;
    expect(troca.autorizacao).toBe("Bearer tok-guardado");
    expect(troca.corpo).toEqual({ senha_atual: "antiga-123", senha_nova: "nova-senha-1" });
    expect(JSON.parse(window.sessionStorage.getItem(CHAVE)!)).toEqual({ token: "tok-novo", expira_em: expiraNovo });

    await userEvent.click(screen.getByRole("button", { name: "Abrir listas" }));
    await waitFor(() => expect(pedidos.filter((p) => p.url === "/api/listas").at(-1)?.autorizacao).toBe("Bearer tok-novo"));
    expect(screen.getByText("Karine · Comercial · senha")).toBeInTheDocument(); // continua logada
  });

  it("mostrar/ocultar a senha", async () => {
    montar();
    const senha = await screen.findByLabelText("Senha");
    await userEvent.click(screen.getByRole("button", { name: "Mostrar senha" }));
    expect(senha).toHaveAttribute("type", "text");
    await userEvent.click(screen.getByRole("button", { name: "Ocultar senha" }));
    expect(senha).toHaveAttribute("type", "password");
  });

  it("login certo guarda o token no sessionStorage, e os pedidos passam a levá-lo", async () => {
    const expira = daqui(60);
    rotas["POST /api/acesso/login"] = {
      status: 200,
      corpo: { token: "tok-123", expira_em: expira, email: EU_KARINE.email, nome: "Karine", perfil: "Comercial", administrador: false },
    };
    rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
    montar();
    await userEvent.type(await screen.findByLabelText("E-mail"), "  karine@grupocriterio.com.br ");
    await userEvent.type(screen.getByLabelText("Senha"), "segredo-123{enter}"); // Enter envia
    expect(await screen.findByText("Karine · Comercial · senha")).toBeInTheDocument();

    const login = pedidos.find((p) => p.url === "/api/acesso/login")!;
    expect(login.metodo).toBe("POST");
    expect(login.corpo).toEqual({ email: "karine@grupocriterio.com.br", senha: "segredo-123" });
    expect(JSON.parse(window.sessionStorage.getItem(CHAVE)!)).toEqual({ token: "tok-123", expira_em: expira });
    expect(window.localStorage.getItem(CHAVE)).toBeNull();
    expect(pedidos.find((p) => p.url === "/api/eu")!.autorizacao).toBe("Bearer tok-123");
  });

  it("senha errada (401) mostra o motivo do servidor e não guarda nada", async () => {
    rotas["POST /api/acesso/login"] = { status: 401, corpo: { detail: "E-mail ou senha incorretos." } };
    montar();
    await userEvent.type(await screen.findByLabelText("E-mail"), "karine@grupocriterio.com.br");
    await userEvent.type(screen.getByLabelText("Senha"), "errada-123");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou senha incorretos.");
    expect(screen.getByLabelText("Senha")).toHaveFocus();
    expect(screen.getByRole("button", { name: "Entrar" })).toBeEnabled();
    expect(window.sessionStorage.getItem(CHAVE)).toBeNull();
    expect(pedidos.some((p) => p.url === "/api/eu")).toBe(false);
  });

  it("muitas tentativas (429) mostra o aviso do servidor", async () => {
    rotas["POST /api/acesso/login"] = { status: 429, corpo: { detail: "Muitas tentativas. Espere 15 minutos e tente de novo." } };
    montar();
    await userEvent.type(await screen.findByLabelText("E-mail"), "karine@grupocriterio.com.br");
    await userEvent.type(screen.getByLabelText("Senha"), "qualquer-123{enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Muitas tentativas. Espere 15 minutos e tente de novo.");
  });

  it("conta desativada (403) mostra o motivo do servidor", async () => {
    rotas["POST /api/acesso/login"] = { status: 403, corpo: { detail: "Esta conta está sem acesso ao CRM." } };
    montar();
    await userEvent.type(await screen.findByLabelText("E-mail"), "bruno@grupocriterio.com.br");
    await userEvent.type(screen.getByLabelText("Senha"), "qualquer-123{enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Esta conta está sem acesso ao CRM.");
  });

  it("campos vazios: pede para preencher, sem ir ao servidor", async () => {
    montar();
    await userEvent.click(await screen.findByRole("button", { name: "Entrar" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Preencha o e-mail e a senha.");
    expect(screen.getByLabelText("E-mail")).toHaveFocus();
    expect(pedidos.some((p) => p.url === "/api/acesso/login")).toBe(false);
  });

  it("com sessão guardada e válida, entra direto levando o token", async () => {
    window.sessionStorage.setItem(CHAVE, JSON.stringify({ token: "tok-guardado", expira_em: daqui(30) }));
    rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
    montar();
    expect(await screen.findByText("Karine · Comercial · senha")).toBeInTheDocument();
    expect(pedidos.find((p) => p.url === "/api/eu")!.autorizacao).toBe("Bearer tok-guardado");
  });

  it("sessão guardada já vencida (expira_em): volta ao formulário com o aviso e nem pergunta quem é", async () => {
    window.sessionStorage.setItem(CHAVE, JSON.stringify({ token: "tok-velho", expira_em: daqui(-1) }));
    montar();
    expect(await screen.findByRole("alert")).toHaveTextContent(SESSAO_EXPIROU);
    expect(window.sessionStorage.getItem(CHAVE)).toBeNull();
    expect(pedidos.some((p) => p.url === "/api/eu")).toBe(false);
  });

  it("401 numa rota protegida derruba a sessão: apaga o token e volta à entrada com o aviso", async () => {
    window.sessionStorage.setItem(CHAVE, JSON.stringify({ token: "tok-guardado", expira_em: daqui(30) }));
    rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
    montar();
    await userEvent.click(await screen.findByRole("button", { name: "Abrir listas" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(SESSAO_EXPIROU);
    expect(screen.getByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.queryByText(/Karine · Comercial/)).toBeNull();
    expect(window.sessionStorage.getItem(CHAVE)).toBeNull();
    expect(pedidos.find((p) => p.url === "/api/listas")?.autorizacao).toBe("Bearer tok-guardado");
  });

  it("a sessão vence com a tela aberta: o próximo pedido nem sai com o token velho", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    try {
      window.sessionStorage.setItem(CHAVE, JSON.stringify({ token: "tok-guardado", expira_em: daqui(30) }));
      rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
      montar();
      await screen.findByText("Karine · Comercial · senha");
      vi.setSystemTime(Date.now() + 31 * 60_000);
      await userEvent.click(screen.getByRole("button", { name: "Abrir listas" }));
      expect(await screen.findByRole("alert")).toHaveTextContent(SESSAO_EXPIROU);
      expect(pedidos.find((p) => p.url === "/api/listas")?.autorizacao ?? null).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("sair apaga o token e volta ao formulário, sem aviso de sessão expirada", async () => {
    window.sessionStorage.setItem(CHAVE, JSON.stringify({ token: "tok-guardado", expira_em: daqui(30) }));
    rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
    montar();
    await userEvent.click(await screen.findByRole("button", { name: "Sair" }));
    expect(await screen.findByLabelText("E-mail")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(window.sessionStorage.getItem(CHAVE)).toBeNull();
    // Depois de sair, nenhum pedido leva o token antigo.
    await waitFor(() => expect(pedidos.filter((p) => p.autorizacao === "Bearer tok-guardado").length).toBe(1));
  });

  it("duplo clique em Entrar envia um único login e desabilita o botão enquanto espera", async () => {
    let liberar: (r: Response) => void = () => undefined;
    rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
    const base = vi.mocked(fetch).getMockImplementation()!;
    vi.stubGlobal("fetch", vi.fn((url: string, opcoes?: RequestInit) =>
      url === "/api/acesso/login" ? (pedidos.push({ url, metodo: "POST", corpo: null, autorizacao: null }), new Promise<Response>((r) => { liberar = r; })) : base(url, opcoes)));
    montar();
    await userEvent.type(await screen.findByLabelText("E-mail"), "karine@grupocriterio.com.br");
    await userEvent.type(screen.getByLabelText("Senha"), "segredo-123");
    await userEvent.dblClick(screen.getByRole("button", { name: "Entrar" }));
    expect(pedidos.filter((p) => p.url === "/api/acesso/login")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Entrando…" })).toBeDisabled();
    liberar(new Response(JSON.stringify({ token: "t", expira_em: daqui(60), email: EU_KARINE.email, nome: "Karine", perfil: "Comercial", administrador: false }), { status: 200 }));
    expect(await screen.findByText("Karine · Comercial · senha")).toBeInTheDocument();
  });

  it("a senha vai exatamente como digitada (espaços e acentos), só o e-mail é aparado", async () => {
    rotas["POST /api/acesso/login"] = { status: 401, corpo: { detail: "E-mail ou senha incorretos." } };
    montar();
    await userEvent.type(await screen.findByLabelText("E-mail"), " karine@grupocriterio.com.br ");
    await userEvent.type(screen.getByLabelText("Senha"), " Açaí  João ");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    await screen.findByRole("alert");
    expect(pedidos.find((p) => p.url === "/api/acesso/login")!.corpo).toEqual({ email: "karine@grupocriterio.com.br", senha: " Açaí  João " });
  });

  it("erro do login fica ligado aos campos (aria-describedby) para o leitor de tela", async () => {
    rotas["POST /api/acesso/login"] = { status: 401, corpo: { detail: "E-mail ou senha incorretos." } };
    montar();
    await userEvent.type(await screen.findByLabelText("E-mail"), "karine@grupocriterio.com.br");
    await userEvent.type(screen.getByLabelText("Senha"), "errada-123{enter}");
    const alerta = await screen.findByRole("alert");
    expect(screen.getByLabelText("Senha")).toHaveAttribute("aria-describedby", alerta.id);
    expect(screen.getByLabelText("E-mail")).toHaveAttribute("aria-describedby", alerta.id);
  });

  it("expira_em ilegível não derruba a sessão guardada: quem decide é o servidor (401)", async () => {
    window.sessionStorage.setItem(CHAVE, JSON.stringify({ token: "tok-guardado", expira_em: "isto-nao-e-data" }));
    rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
    montar();
    expect(await screen.findByText("Karine · Comercial · senha")).toBeInTheDocument();
    expect(pedidos.find((p) => p.url === "/api/eu")!.autorizacao).toBe("Bearer tok-guardado");
  });

  it("sessão guardada com formato estragado é descartada e pede o login", async () => {
    window.sessionStorage.setItem(CHAVE, "{não é json");
    montar();
    expect(await screen.findByLabelText("E-mail")).toBeInTheDocument();
    expect(pedidos.some((p) => p.url === "/api/eu")).toBe(false);
  });

  it("sessionStorage indisponível não derruba a entrada", async () => {
    const original = Object.getOwnPropertyDescriptor(window, "sessionStorage")!;
    Object.defineProperty(window, "sessionStorage", { configurable: true, get: () => { throw new Error("bloqueado"); } });
    try {
      rotas["POST /api/acesso/login"] = {
        status: 200,
        corpo: { token: "tok-9", expira_em: daqui(60), email: EU_KARINE.email, nome: "Karine", perfil: "Comercial", administrador: false },
      };
      rotas["GET /api/eu"] = { status: 200, corpo: EU_KARINE };
      montar();
      await userEvent.type(await screen.findByLabelText("E-mail"), "karine@grupocriterio.com.br");
      await userEvent.type(screen.getByLabelText("Senha"), "segredo-123{enter}");
      expect(await screen.findByText("Karine · Comercial · senha")).toBeInTheDocument();
      expect(pedidos.find((p) => p.url === "/api/eu")!.autorizacao).toBe("Bearer tok-9");
    } finally {
      Object.defineProperty(window, "sessionStorage", original);
    }
  });
});
