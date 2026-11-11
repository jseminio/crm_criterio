import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { ComparacaoDosEnvios } from "../api/tipos";
import { BotaoComparar } from "./CompararEnvios";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { enviosDaEmpresa: vi.fn(), combinarEnvios: vi.fn(), descartarEnvio: vi.fn() } };
});

const Q = { id: 2, razao_social: "XPTO Ltda", nome_fantasia: "XPTO", cnpj: "11222333000181" };

const COMPARACAO: ComparacaoDosEnvios = {
  envios: [
    { id: 1, numero: "Q-1001", recebido_em: "2026-11-03T10:12:00", contato_nome: "Ana Souza",
      chave_do_preenchedor: "11222333000181-ANA", situacao: "Importado", oportunidade_id: 40 },
    { id: 2, numero: "Q-1002", recebido_em: "2026-11-05T16:40:00", contato_nome: "Bruno Lima",
      chave_do_preenchedor: "11222333000181-BRUNO", situacao: "Precisa de você", oportunidade_id: null },
  ],
  campos: [
    { chave: "vol.empregados_clt", secao: 3, rotulo: "Empregados CLT", valores: { "1": "45", "2": "52" }, estado: "diferente", sugestao: 2 },
    { chave: "vol.notas_emitidas", secao: 3, rotulo: "Notas fiscais emitidas", valores: { "1": "300", "2": "300" }, estado: "igual", sugestao: 2 },
    { chave: "parcelamento_situacao", secao: 5, rotulo: "Se houver parcelamento", valores: { "1": "Em dia", "2": null }, estado: "completa", sugestao: 1 },
  ],
};

describe("Comparar os envios da mesma empresa (11/11/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.enviosDaEmpresa).mockResolvedValue(COMPARACAO);
  });

  it("mostra os envios lado a lado, pede escolha só no que diverge e importa a mescla escolhida", async () => {
    vi.mocked(api.combinarEnvios).mockResolvedValue({ o_que_fez: "Combinado por Eduardo a partir de Q-1001, Q-1002." } as never);
    const aoResolver = vi.fn();
    render(<BotaoComparar q={Q} aoResolver={aoResolver} />);
    await userEvent.click(screen.getByRole("button", { name: "Comparar envios" }));
    const painel = await screen.findByRole("dialog", { name: "Comparar os envios de XPTO" });
    const tabela = await within(painel).findByRole("table", { name: "Envios lado a lado" });
    expect(tabela).toHaveTextContent("Q-1001 · Ana");
    expect(tabela).toHaveTextContent("Q-1001 preenche o vazio");
    expect(within(painel).getByText(/1 campo\(s\) divergem/)).toBeInTheDocument();
    const escolha = within(painel).getByRole("radiogroup", { name: "De qual envio vem Empregados CLT" });
    expect(within(escolha).getByRole("radio", { name: "Q-1002" })).toBeChecked(); // sugere o mais novo
    await userEvent.click(within(escolha).getByRole("radio", { name: "Q-1001" }));
    await userEvent.click(within(painel).getByRole("button", { name: "Importar a mescla" }));
    expect(api.combinarEnvios).toHaveBeenCalledWith(2, { "vol.empregados_clt": 1 });
    expect(aoResolver).toHaveBeenCalledWith("Combinado por Eduardo a partir de Q-1001, Q-1002.");
  });

  it("ficar com o anterior que já virou oportunidade descarta o envio novo", async () => {
    vi.mocked(api.descartarEnvio).mockResolvedValue({ o_que_fez: "Descartado." } as never);
    render(<BotaoComparar q={Q} aoResolver={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Comparar envios" }));
    const painel = await screen.findByRole("dialog", { name: "Comparar os envios de XPTO" });
    await within(painel).findByRole("table", { name: "Envios lado a lado" });
    await userEvent.click(within(painel).getByRole("button", { name: "Usar só o Q-1001" }));
    expect(api.descartarEnvio).toHaveBeenCalledWith(2);
    expect(api.combinarEnvios).not.toHaveBeenCalled();
  });

  it("usar só o novo leva todos os campos que divergem dele", async () => {
    vi.mocked(api.combinarEnvios).mockResolvedValue({ o_que_fez: "ok" } as never);
    render(<BotaoComparar q={Q} aoResolver={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Comparar envios" }));
    const painel = await screen.findByRole("dialog", { name: "Comparar os envios de XPTO" });
    await within(painel).findByRole("table", { name: "Envios lado a lado" });
    await userEvent.click(within(painel).getByRole("button", { name: "Usar só o Q-1002" }));
    expect(api.combinarEnvios).toHaveBeenCalledWith(2, { "vol.empregados_clt": 2 });
  });
});
