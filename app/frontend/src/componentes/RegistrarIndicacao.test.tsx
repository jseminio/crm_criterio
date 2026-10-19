/** Registrar indicação (19/10/2026): empresa nova ou da base, alerta da cláusula 2.2 e a autorização LGPD obrigatória. */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ParceiroDetalhe } from "../api/tipos";
import { RegistrarIndicacao } from "./RegistrarIndicacao";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { servicos: vi.fn(), registrarIndicacao: vi.fn(), alertasDaIndicacao: vi.fn(), empresas: vi.fn() } };
});
const m = vi.mocked(api);

const PARCEIRO = { id: 7, nome: "Ficus", nivel: "Estratégico" } as ParceiroDetalhe;

beforeEach(() => {
  vi.clearAllMocks();
  m.servicos.mockResolvedValue([{ nome: "BPO Financeiro" }] as never);
  m.registrarIndicacao.mockResolvedValue(PARCEIRO);
});

describe("Registrar indicação", () => {
  it("empresa nova só entra com a autorização do cliente", async () => {
    const aoRegistrar = vi.fn();
    render(<RegistrarIndicacao parceiro={PARCEIRO} aoFechar={() => {}} aoRegistrar={aoRegistrar} />);
    fireEvent.click(screen.getByRole("button", { name: /Cadastrar empresa nova/ }));
    fireEvent.change(screen.getByLabelText("Empresa nova"), { target: { value: "Comércio Delta" } });
    await screen.findByRole("option", { name: "BPO Financeiro" });
    fireEvent.change(screen.getByLabelText("Serviço de interesse"), { target: { value: "BPO Financeiro" } });
    const botao = screen.getByRole("button", { name: "Registrar indicação" }) as HTMLButtonElement;
    expect(botao.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText(/autorizou o contato/));
    expect(botao.disabled).toBe(false);
    fireEvent.click(botao);
    await waitFor(() => expect(aoRegistrar).toHaveBeenCalledWith(PARCEIRO));
    expect(m.registrarIndicacao).toHaveBeenCalledWith(7, expect.objectContaining({
      empresa_id: null, empresa_nova: { nome: "Comércio Delta", cnpj: null }, servico: "BPO Financeiro",
      autorizado_pelo_cliente: true,
    }));
  });
});
