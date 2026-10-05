import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi, sessaoAtual } from "../api/cliente";
import { problemaDaSenha } from "./CampoDeSenha";
import { TrocarSenha } from "./TrocarSenha";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { trocarMinhaSenha: vi.fn() } };
});

async function preencher(atual: string, nova: string, repetida = nova) {
  if (atual) await userEvent.type(screen.getByLabelText("Senha atual"), atual);
  if (nova) await userEvent.type(screen.getByLabelText("Senha nova"), nova);
  if (repetida) await userEvent.type(screen.getByLabelText("Repita a senha nova"), repetida);
  await userEvent.click(screen.getByRole("button", { name: "Trocar senha" }));
}

describe("trocar a própria senha", () => {
  beforeEach(() => vi.resetAllMocks());

  it("abre como painel, com foco na senha atual", () => {
    render(<TrocarSenha aoFechar={vi.fn()} />);
    expect(screen.getByRole("dialog", { name: "Trocar senha" })).toBeInTheDocument();
    expect(screen.getByLabelText("Senha atual")).toHaveFocus();
  });

  it("senha nova curta não sai da tela", async () => {
    render(<TrocarSenha aoFechar={vi.fn()} />);
    await preencher("antiga-123", "curta");
    expect(screen.getByRole("alert")).toHaveTextContent("A senha precisa ter pelo menos 8 caracteres.");
    expect(api.trocarMinhaSenha).not.toHaveBeenCalled();
  });

  it("a repetição precisa ser igual", async () => {
    render(<TrocarSenha aoFechar={vi.fn()} />);
    await preencher("antiga-123", "nova-senha-1", "nova-senha-2");
    expect(screen.getByRole("alert")).toHaveTextContent("A senha nova e a repetição não são iguais.");
    expect(api.trocarMinhaSenha).not.toHaveBeenCalled();
  });

  it("troca, guarda o token novo que o servidor devolve e confirma", async () => {
    window.sessionStorage.setItem("crm.sessao", JSON.stringify({ token: "tok-velho", expira_em: "2099-01-01T00:00:00Z" }));
    vi.mocked(api.trocarMinhaSenha).mockResolvedValue({
      token: "tok-novo", expira_em: "2099-01-02T00:00:00Z", email: "karine@grupocriterio.com.br", nome: "Karine", perfil: "Comercial",
      administrador: false,
    });
    const aoFechar = vi.fn();
    render(<TrocarSenha aoFechar={aoFechar} />);
    await preencher("antiga-123", "nova-senha-1");
    expect(api.trocarMinhaSenha).toHaveBeenCalledWith("antiga-123", "nova-senha-1");
    expect(await screen.findByRole("status")).toHaveTextContent("Senha trocada. Você continua conectado");
    expect(JSON.parse(window.sessionStorage.getItem("crm.sessao")!)).toEqual({ token: "tok-novo", expira_em: "2099-01-02T00:00:00Z" });
    expect(sessaoAtual()?.token).toBe("tok-novo");
    await userEvent.click(screen.getByRole("button", { name: "Fechar" }));
    expect(aoFechar).toHaveBeenCalled();
  });

  it("senha atual errada (400) mostra o motivo do servidor", async () => {
    vi.mocked(api.trocarMinhaSenha).mockRejectedValue(new ErroDaApi(400, "A senha atual não confere."));
    render(<TrocarSenha aoFechar={vi.fn()} />);
    await preencher("errada-123", "nova-senha-1");
    expect(await screen.findByRole("alert")).toHaveTextContent("A senha atual não confere.");
    expect(screen.getByLabelText("Senha atual")).toBeInTheDocument();
  });
});

describe("regra da senha (a mesma do servidor: 8 a 200 caracteres, contados como Python)", () => {
  it("espaços e acentos contam; emoji vale 1 caractere", () => {
    expect(problemaDaSenha("        ")).toBeNull(); // 8 espaços
    expect(problemaDaSenha("áéíóúâêô")).toBeNull();
    expect(problemaDaSenha("😀😀😀😀")).not.toBeNull(); // 4 caracteres, não 8
    expect(problemaDaSenha("😀".repeat(8))).toBeNull();
    expect(problemaDaSenha("1234567")).not.toBeNull();
  });

  it("acima de 200 caracteres a tela recusa antes de enviar", () => {
    expect(problemaDaSenha("a".repeat(200))).toBeNull();
    expect(problemaDaSenha("a".repeat(201))).toContain("no máximo 200");
  });
});
