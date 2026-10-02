import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { AjusteTecnico } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { AjustesDaAreaTecnica } from "./AjustesDaAreaTecnica";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { ajustes: vi.fn(), marcarAjusteFeito: vi.fn(), reabrirAjuste: vi.fn() } };
});

const AJUSTE: AjusteTecnico = {
  id: 9, reuniao_id: 1, reuniao_tipo: "trimestral", reuniao_data: "2026-10-01", grupo_id: 7, grupo_nome: "Rede Farma",
  descricao: "Reclassificar o frete", responsavel_email: "bruno@grupocriterio.com.br", responsavel_nome: "Bruno Soares",
  prazo: "2020-01-10", feito_em: null, feito_por: null, observacao: null,
};

const tecnico = {
  modo: "microsoft" as const, email: "bruno@grupocriterio.com.br", nome: "Bruno Soares", perfil: "Área técnica",
  administrador: false, permissoes: ["ajustes.concluir"],
};

describe("Agenda › ajustes da área técnica", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.ajustes).mockResolvedValue([AJUSTE]);
  });

  it("o técnico vê os seus, com o atraso em texto, e marca feito com observação", async () => {
    vi.mocked(api.marcarAjusteFeito).mockResolvedValue({ ...AJUSTE, feito_em: "2026-10-02T12:00:00+00:00" });
    render(<ProvedorDeAcesso eu={tecnico}><AjustesDaAreaTecnica /></ProvedorDeAcesso>);
    expect(await screen.findByText("Reclassificar o frete")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Meus ajustes · 1 pendente · ⚠ 1 atrasado/ })).toBeInTheDocument();
    expect(screen.getByText(/⚠ Prazo 10\/01\/2020 \(atrasado/)).toBeInTheDocument();
    expect(screen.getByText(/Rede Farma · reunião trimestral de 01\/10\/2026 · Bruno Soares/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Marcar feito" }));
    await userEvent.type(screen.getByLabelText("Observação sobre: Reclassificar o frete"), "Feito na DRE");
    await userEvent.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(api.marcarAjusteFeito).toHaveBeenCalledWith(9, "Feito na DRE");
    expect(await screen.findByRole("status")).toHaveTextContent("Ajuste marcado como feito");
  });

  it("aba Feitos lista os concluídos e permite reabrir", async () => {
    vi.mocked(api.ajustes).mockImplementation(async (s) =>
      s === "feitos" ? [{ ...AJUSTE, feito_em: "2026-10-02T12:00:00+00:00", feito_por: "Bruno Soares", observacao: "ok" }] : []);
    vi.mocked(api.reabrirAjuste).mockResolvedValue(AJUSTE);
    render(<ProvedorDeAcesso eu={tecnico}><AjustesDaAreaTecnica /></ProvedorDeAcesso>);
    expect(await screen.findByText(/Nenhum ajuste pendente/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Feitos" }));
    expect(await screen.findByText(/✓ Feito por Bruno Soares/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Reabrir" }));
    expect(api.reabrirAjuste).toHaveBeenCalledWith(9);
  });

  it("quem só vê não tem botão de marcar", async () => {
    render(<ProvedorDeAcesso eu={{ ...tecnico, permissoes: ["ajustes.ver"] }}><AjustesDaAreaTecnica /></ProvedorDeAcesso>);
    expect(await screen.findByRole("heading", { name: /Ajustes da área técnica/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Marcar feito" })).not.toBeInTheDocument();
  });
});
