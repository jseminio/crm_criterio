import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { EstadoDaBusca } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { EstadoDaBuscaDeQuestionarios } from "./EstadoDaBuscaDeQuestionarios";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { estadoDaBusca: vi.fn(), buscarQuestionarios: vi.fn() } };
});

const estado = (o: Partial<EstadoDaBusca> = {}): EstadoDaBusca => ({
  automatica: true, intervalo_minutos: 10, ultima_em: "2026-10-02T20:40:00Z", ultima_manual: false, novos: 1,
  erro: null, avisos: [], proxima_em: "2026-10-02T20:50:00Z", ...o,
});
const hora = (iso: string) => new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

describe("Busca automática dos questionários (02/10/2026)", () => {
  beforeEach(() => vi.resetAllMocks());

  it("mostra a última busca, o que trouxe e a próxima", async () => {
    vi.mocked(api.estadoDaBusca).mockResolvedValue(estado());
    render(<EstadoDaBuscaDeQuestionarios aoChegar={() => {}} />);
    expect(await screen.findByText(
      `Busca automática a cada 10 min · última automática às ${hora("2026-10-02T20:40:00Z")} (1 novo) · próxima às ${hora("2026-10-02T20:50:00Z")}`,
    )).toBeInTheDocument();
  });

  it("a falha aparece com o motivo, e desligada também avisa", async () => {
    vi.mocked(api.estadoDaBusca).mockResolvedValue(estado({ automatica: false, novos: 0, erro: "O Supabase recusou a chave (HTTP 401)." }));
    render(<EstadoDaBuscaDeQuestionarios aoChegar={() => {}} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("⚠ O Supabase recusou a chave (HTTP 401).");
    expect(screen.getByText(/⚠ Busca automática desligada · última automática às .* \(nada novo\)/)).toBeInTheDocument();
  });

  it("Buscar agora busca na hora e avisa a tela quando chega questionário", async () => {
    vi.mocked(api.estadoDaBusca).mockResolvedValue(estado());
    vi.mocked(api.buscarQuestionarios).mockResolvedValue({ buscado_em: "2026-10-02T20:45:00Z", novos: [{ id: 1 } as never], avisos: [] });
    const aoChegar = vi.fn();
    render(<EstadoDaBuscaDeQuestionarios aoChegar={aoChegar} />);
    await userEvent.click(await screen.findByRole("button", { name: "Buscar agora" }));
    expect(api.buscarQuestionarios).toHaveBeenCalled();
    expect(aoChegar).toHaveBeenCalled();
  });

  it("a recusa do Buscar agora aparece", async () => {
    vi.mocked(api.estadoDaBusca).mockResolvedValue(estado());
    vi.mocked(api.buscarQuestionarios).mockRejectedValue(new ErroDaApi(409, "Falta configurar a busca"));
    render(<EstadoDaBuscaDeQuestionarios aoChegar={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Buscar agora" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Falta configurar a busca");
  });

  it("quem só vê o painel não tem o botão", async () => {
    vi.mocked(api.estadoDaBusca).mockResolvedValue(estado());
    render(
      <ProvedorDeAcesso eu={{ modo: "microsoft", email: "x@grupocriterio.com.br", nome: "X", perfil: "P", administrador: false, permissoes: ["questionarios.ver"] }}>
        <EstadoDaBuscaDeQuestionarios aoChegar={() => {}} />
      </ProvedorDeAcesso>,
    );
    await screen.findByText(/Busca automática a cada 10 min/);
    expect(screen.queryByRole("button", { name: "Buscar agora" })).not.toBeInTheDocument();
  });
});
