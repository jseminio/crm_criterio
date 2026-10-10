/** MRR atual da carteira (10/10/2026): contratado × recebido, explicação ao passar o mouse e o botão
 * "Ver composição" com cada cliente e os seus valores. Situação sempre em palavra (PAD-002). */

import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { MrrDaCarteira as Carteira } from "../api/tipos";
import { MrrDaCarteira } from "./MrrDaCarteira";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { mrrDaCarteira: vi.fn() } };
});

const carteira = (o: Partial<Carteira> = {}): Carteira => ({
  competencia: "2026-10", mrr: "279099.19", contratos: 62, grupos: 34, suspenso: "0.00", sem_preco_mensal: 0,
  meta: "433333.33", alerta: "216666.67", esperado: "257629.97", recebido: "0.00", recebido_fora: "0.00",
  mes_importado: false, importado_em: null, importado_por: null, grupos_registrados: 0,
  itens: [
    { grupo_id: 1, grupo: "Inbel", contratos: 7, mrr: "48452.95", esperado: "44725.80", recebido: "0.00", situacao: "Sem registro",
      itens: [{ id: 10, escopo: "Contábil", empresa: "Inbel Ltda", parte: "somado", mrr: "20000.00", esperado: "18461.54" }] },
    { grupo_id: 2, grupo: "Grupo MR", contratos: 3, mrr: "43972.32", esperado: "40589.82", recebido: "0.00", situacao: "Sem registro", itens: [] },
  ],
  ...o,
});

describe("MRR atual da carteira", () => {
  beforeEach(() => vi.clearAllMocks());

  it("mostra o contratado, a meta e o recebido sem registro quando a planilha do mês não veio", async () => {
    vi.mocked(api.mrrDaCarteira).mockResolvedValue(carteira());
    render(<MrrDaCarteira />);
    expect(await screen.findByText("MRR atual da carteira")).toBeInTheDocument();
    expect(screen.getByText(/62 contratos · 34 grupos · 64,4% da meta/)).toBeInTheDocument();
    expect(screen.getByText(/Recebido em out\/2026: sem registro/)).toBeInTheDocument();
  });

  it("a explicação do cálculo fica na janela ligada ao card (mouse ou Tab)", async () => {
    vi.mocked(api.mrrDaCarteira).mockResolvedValue(carteira());
    render(<MrrDaCarteira />);
    const card = (await screen.findByText("MRR atual da carteira")).closest("section")!;
    const janela = document.getElementById(card.getAttribute("aria-describedby")!)!;
    expect(janela).toHaveAttribute("role", "tooltip");
    expect(janela.textContent).toMatch(/× 13 ÷ 12/);
    expect(janela.textContent).toMatch(/não muda com os filtros do funil/);
  });

  it("Ver composição abre a lista de clientes com os valores e o total igual ao card", async () => {
    vi.mocked(api.mrrDaCarteira).mockResolvedValue(carteira());
    render(<MrrDaCarteira />);
    fireEvent.click(await screen.findByRole("button", { name: "Ver composição (2)" }));
    const painel = await screen.findByRole("dialog", { name: "MRR atual da carteira" });
    const tabela = within(painel).getByRole("table", { name: "Composição do MRR da carteira" });
    expect(within(tabela).getByText(/Inbel/)).toBeInTheDocument();
    expect(within(tabela).getByText("R$ 48.452,95")).toBeInTheDocument();
    expect(within(tabela).getAllByText("Sem registro")).toHaveLength(2);
    expect(within(tabela).getAllByText("R$ 279.099,19").length).toBeGreaterThan(0);
    // Clicar no cliente abre os contratos dele.
    fireEvent.click(within(tabela).getByRole("button", { name: /Inbel/ }));
    expect(within(tabela).getByText(/Contábil · Inbel Ltda/)).toBeInTheDocument();
  });

  it("com a planilha importada, mostra recebido contra o esperado e a situação em palavra", async () => {
    vi.mocked(api.mrrDaCarteira).mockResolvedValue(carteira({
      mes_importado: true, recebido: "44725.80", grupos_registrados: 1, importado_em: "2026-10-10T12:00:00Z", importado_por: "Eduardo Luiz",
      itens: [
        { grupo_id: 1, grupo: "Inbel", contratos: 7, mrr: "48452.95", esperado: "44725.80", recebido: "44725.80", situacao: "Em dia", itens: [] },
        { grupo_id: 2, grupo: "Grupo MR", contratos: 3, mrr: "43972.32", esperado: "40589.82", recebido: "0.00", situacao: "Em aberto", itens: [] },
      ],
    }));
    render(<MrrDaCarteira />);
    expect(await screen.findByText(/Recebido em out\/2026: R\$ 45 mil de R\$ 258 mil/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Ver composição/ }));
    const painel = await screen.findByRole("dialog");
    expect(within(painel).getByText("Em dia")).toBeInTheDocument();
    expect(within(painel).getByText("Em aberto")).toBeInTheDocument();
    expect(within(painel).getByText(/por Eduardo Luiz/)).toBeInTheDocument();
  });
});
