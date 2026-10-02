import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "./api/cliente";
import { Entrada, usarAcesso } from "./entrada";

const msal = vi.hoisted(() => ({ contas: [] as unknown[], loginRedirect: vi.fn() }));

vi.mock("@azure/msal-browser", () => ({
  InteractionRequiredAuthError: class extends Error {},
  PublicClientApplication: class {
    initialize = async () => undefined;
    handleRedirectPromise = async () => null;
    getAllAccounts = () => msal.contas;
    setActiveAccount = () => undefined;
    acquireTokenSilent = async () => ({ accessToken: "token" });
    loginRedirect = msal.loginRedirect;
  },
}));

vi.mock("./api/cliente", async () => {
  const real = await vi.importActual<typeof import("./api/cliente")>("./api/cliente");
  return { ...real, api: { entrada: vi.fn(), eu: vi.fn() } };
});

function QuemSou() {
  const { eu, pode } = usarAcesso();
  return (
    <p>
      {eu.nome ?? "sem nome"} · {eu.perfil} · converter: {pode("funil.converter") ? "sim" : "não"}
    </p>
  );
}

const MICROSOFT = { modo: "microsoft" as const, tenant_id: "t", client_id: "c", escopo: "api://c/acesso" };

describe("entrada no CRM", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    msal.contas = [];
  });

  it("sem a Microsoft configurada, segue sem login como antes", async () => {
    vi.mocked(api.entrada).mockResolvedValue({ modo: "local", tenant_id: null, client_id: null, escopo: null });
    vi.mocked(api.eu).mockResolvedValue({ modo: "local", email: null, nome: null, perfil: "Sem login", administrador: true, permissoes: [] });
    render(<Entrada><QuemSou /></Entrada>);
    expect(await screen.findByText("sem nome · Sem login · converter: sim")).toBeInTheDocument();
  });

  it("com a Microsoft e sem conta, mostra só o botão de entrar", async () => {
    vi.mocked(api.entrada).mockResolvedValue(MICROSOFT);
    render(<Entrada><QuemSou /></Entrada>);
    expect(await screen.findByRole("button", { name: "Entrar com a conta Microsoft" })).toBeInTheDocument();
    expect(screen.queryByText(/converter/)).toBeNull();
    expect(api.eu).not.toHaveBeenCalled();
  });

  it("com conta, o perfil decide o que pode", async () => {
    msal.contas = [{ username: "karine@grupocriterio.com.br" }];
    vi.mocked(api.entrada).mockResolvedValue(MICROSOFT);
    vi.mocked(api.eu).mockResolvedValue({
      modo: "microsoft", email: "karine@grupocriterio.com.br", nome: "Karine", perfil: "Comercial", administrador: false,
      permissoes: ["funil.ver"],
    });
    render(<Entrada><QuemSou /></Entrada>);
    expect(await screen.findByText("Karine · Comercial · converter: não")).toBeInTheDocument();
  });

  it("conta sem perfil no CRM vê o motivo e pode entrar com outra", async () => {
    msal.contas = [{ username: "bruno@grupocriterio.com.br" }];
    vi.mocked(api.entrada).mockResolvedValue(MICROSOFT);
    vi.mocked(api.eu).mockRejectedValue(new ErroDaApi(403, "A conta bruno@grupocriterio.com.br ainda não tem perfil no CRM."));
    render(<Entrada><QuemSou /></Entrada>);
    expect(await screen.findByRole("alert")).toHaveTextContent("ainda não tem perfil no CRM");
    expect(screen.getByRole("button", { name: "Entrar com outra conta" })).toBeInTheDocument();
  });
});
