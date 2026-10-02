import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { PendenciaDaProposta, PendenciasDaProposta } from "../api/tipos";
import { ListaDoQueFalta } from "./ListaDoQueFalta";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { novaPendencia: vi.fn(), mudarPendencia: vi.fn() } };
});

const p = (i: Partial<PendenciaDaProposta>): PendenciaDaProposta => ({
  chave: "volumes", descricao: "Volumetria: 4 de 13 volumes sem resposta", automatica: true, aberta: true,
  responsavel: null, prazo: null, dias_de_atraso: 0, feita_em: null, feita_por: null, ...i,
});

const DADOS: PendenciasDaProposta = {
  abertas: 3, atrasadas: 1, feitas: 2, revisores: ["Eduardo", "Karine"],
  itens: [
    p({ responsavel: "Karine", prazo: "2026-10-03" }),
    p({ chave: "secao-6", descricao: "Folha de pagamento e departamento pessoal: seção inteira sem resposta",
      responsavel: "Eduardo", prazo: "2026-10-01", dias_de_atraso: 1 }),
    p({ chave: "porte", descricao: "Porte confirmado", aberta: false }),
    p({ chave: "manual-5", descricao: "Pedir o balancete de agosto", automatica: false, responsavel: "Karine", prazo: "2026-10-06" }),
    p({ chave: "manual-6", descricao: "Reunião com o financeiro", automatica: false, aberta: false,
      feita_em: "2026-10-02T10:00:00", feita_por: "Karine" }),
  ],
};

describe("O que falta para a proposta", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  it("resume, põe a atrasada primeiro e diz o estado em texto", () => {
    render(<ListaDoQueFalta oportunidadeId={10} dados={DADOS} aoMudar={vi.fn()} />);
    expect(screen.getByText(/pendentes/).parentElement).toHaveTextContent("3 pendentes · 1 atrasada · 2 feitas");
    const linhas = screen.getAllByRole("listitem");
    expect(linhas[0]).toHaveTextContent("Folha de pagamento");
    expect(linhas[0]).toHaveTextContent("✗ atrasado 1 dia");
    expect(linhas[1]).toHaveTextContent("· automático");
    expect(linhas[1]).toHaveTextContent("em aberto");
    expect(screen.getByText(/não bloqueia/)).toBeInTheDocument();
    expect(screen.queryByText("Porte confirmado")).toBeNull(); // feitas ficam recolhidas
  });

  it("mostra as feitas sob pedido, com quem e quando", async () => {
    render(<ListaDoQueFalta oportunidadeId={10} dados={DADOS} aoMudar={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Mostrar as 2 feitas" }));
    expect(screen.getByText("✓ resolvido")).toBeInTheDocument();
    expect(screen.getByText("✓ feito em 02/10/2026 · Karine")).toBeInTheDocument();
  });

  it("muda responsável, marca manual como feito e adiciona item, sempre com quem está mexendo", async () => {
    const aoMudar = vi.fn();
    vi.mocked(api.mudarPendencia).mockResolvedValue(DADOS);
    vi.mocked(api.novaPendencia).mockResolvedValue(DADOS);
    render(<ListaDoQueFalta oportunidadeId={10} dados={DADOS} aoMudar={aoMudar} />);
    await userEvent.selectOptions(screen.getByLabelText("Quem está mexendo"), "Karine");
    const volumes = screen.getAllByRole("listitem")[1];
    await userEvent.selectOptions(within(volumes).getByRole("combobox"), "Eduardo");
    expect(api.mudarPendencia).toHaveBeenCalledWith(10, "volumes", { responsavel: "Eduardo", por: "Karine" });
    await userEvent.click(screen.getByRole("checkbox", { name: "Pedir o balancete de agosto: feito" }));
    expect(api.mudarPendencia).toHaveBeenLastCalledWith(10, "manual-5", { feita: true, por: "Karine" });
    expect(screen.queryByRole("checkbox", { name: /Volumetria/ })).toBeNull(); // automático não se marca
    await userEvent.type(screen.getByLabelText("Novo item do que falta"), "Pedir o contrato atual{Enter}");
    expect(api.novaPendencia).toHaveBeenCalledWith(10, { descricao: "Pedir o contrato atual", por: "Karine" });
    expect(aoMudar).toHaveBeenCalledTimes(3);
  });

  it("sem nada aberto, diz que não há pendência", () => {
    render(<ListaDoQueFalta oportunidadeId={10} dados={{ ...DADOS, abertas: 0, atrasadas: 0, itens: [] }} aoMudar={vi.fn()} />);
    expect(screen.getByText("✓ Nada pendente para esta proposta.")).toBeInTheDocument();
  });
});
