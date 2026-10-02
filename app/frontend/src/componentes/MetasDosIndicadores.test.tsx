import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { Metas } from "../api/tipos";
import { MetasDosIndicadores } from "./MetasDosIndicadores";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { metas: vi.fn(), mudarMetas: vi.fn() } };
});

const METAS: Metas = {
  mrr: { meta: "400000.00", alerta: "200000.00", alterado_por: null, alterado_em: null },
  conversao: { meta: "50.00", alerta: "30.00", alterado_por: "Eduardo Luiz", alterado_em: "2026-10-02T13:15:00+00:00" },
};

describe("Configurações › Metas", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.metas).mockResolvedValue(METAS);
  });

  it("mostra os valores atuais no padrão brasileiro e de quem foi a última mudança", async () => {
    render(<MetasDosIndicadores />);
    expect(await screen.findByLabelText("Meta do MRR")).toHaveValue("400.000,00");
    expect(screen.getByLabelText("Alerta da conversão")).toHaveValue("30,00");
    expect(screen.getByText("Valor do KPI oficial, ainda não alterado")).toBeInTheDocument();
    expect(screen.getByText(/Última mudança: Eduardo Luiz/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar metas" })).toBeDisabled();
  });

  it("salva os quatro valores e avisa", async () => {
    vi.mocked(api.mudarMetas).mockResolvedValue(METAS);
    render(<MetasDosIndicadores />);
    const meta = await screen.findByLabelText("Meta do MRR");
    fireEvent.change(meta, { target: { value: "350.000,00" } });
    await userEvent.click(screen.getByRole("button", { name: "Salvar metas" }));
    expect(api.mudarMetas).toHaveBeenCalledWith({
      mrr: { meta: "350000.00", alerta: "200000.00" },
      conversao: { meta: "50.00", alerta: "30.00" },
    });
    expect(await screen.findByRole("status")).toHaveTextContent("Metas salvas");
  });

  it("o motivo da recusa do servidor aparece", async () => {
    vi.mocked(api.mudarMetas).mockRejectedValue(new ErroDaApi(422, "MRR: o alerta precisa ficar abaixo da meta"));
    render(<MetasDosIndicadores />);
    fireEvent.change(await screen.findByLabelText("Alerta do MRR"), { target: { value: "500.000" } });
    await userEvent.click(screen.getByRole("button", { name: "Salvar metas" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("o alerta precisa ficar abaixo da meta");
  });
});
