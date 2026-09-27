import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { RevisaoDaCarteira } from "../api/tipos";
import { RevisaoMensal } from "./RevisaoMensal";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      revisoesDaCarteira: vi.fn(),
      registrarRevisaoDaCarteira: vi.fn(),
      editarMesDaRevisao: vi.fn(),
    },
  };
});

const revisao = (o: Partial<RevisaoDaCarteira> = {}): RevisaoDaCarteira => ({
  id: 1, mes_de_referencia: "2026-07-01", registrada_em: "2026-09-27T08:12:00+00:00", registrada_por: "Eduardo Luiz",
  isc_valor: "50.40", isc_zona: "atenção", componente_classe: "49.6", componente_semaforo: "42.3", componente_churn: "59.0",
  grupos: 31, receita_total: "226341.20", grupos_travados: 5, receita_travada: "93094.42", percentual_travado: "41.1",
  baseado_em_referencia: "2026-07-31", ...o,
});

describe("RevisaoMensal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date("2026-09-27T10:00:00"));
  });
  afterEach(() => vi.useRealTimers());

  it("sem revisão este mês, oferece registrar com nome obrigatório", async () => {
    vi.mocked(api.revisoesDaCarteira).mockResolvedValue([]);
    render(<RevisaoMensal />);
    expect(await screen.findByText(/Revisão de Setembro de 2026 ainda não registrada/)).toBeInTheDocument();
    const botao = screen.getByRole("button", { name: "Registrar revisão do mês" });
    expect(botao).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Quem está revisando"), "Eduardo Luiz");
    expect(botao).toBeEnabled();
  });

  it("já revisado este mês, mostra quem e quando, sem o formulário", async () => {
    vi.mocked(api.revisoesDaCarteira).mockResolvedValue([revisao({ mes_de_referencia: "2026-09-01" })]);
    render(<RevisaoMensal />);
    expect(await screen.findByText(/Revisão de Setembro de 2026 registrada por Eduardo Luiz/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar revisão do mês" })).toBeNull();
  });

  it("registra e recarrega, sem exigir mais o formulário", async () => {
    vi.mocked(api.revisoesDaCarteira).mockResolvedValueOnce([]).mockResolvedValueOnce([revisao({ mes_de_referencia: "2026-09-01" })]);
    vi.mocked(api.registrarRevisaoDaCarteira).mockResolvedValue(revisao({ mes_de_referencia: "2026-09-01" }));
    render(<RevisaoMensal />);
    await screen.findByText(/ainda não registrada/);
    await userEvent.type(screen.getByLabelText("Quem está revisando"), "Eduardo Luiz");
    await userEvent.click(screen.getByRole("button", { name: "Registrar revisão do mês" }));
    await waitFor(() => expect(api.registrarRevisaoDaCarteira).toHaveBeenCalledWith("Eduardo Luiz"));
    expect(await screen.findByText(/registrada por Eduardo Luiz/)).toBeInTheDocument();
  });

  it("mostra o erro ao registrar (ex.: já existe revisão do mês)", async () => {
    vi.mocked(api.revisoesDaCarteira).mockResolvedValue([]);
    vi.mocked(api.registrarRevisaoDaCarteira).mockRejectedValue(new ErroDaApi(409, "já existe uma revisão para 09/2026"));
    render(<RevisaoMensal />);
    await screen.findByText(/ainda não registrada/);
    await userEvent.type(screen.getByLabelText("Quem está revisando"), "Eduardo Luiz");
    await userEvent.click(screen.getByRole("button", { name: "Registrar revisão do mês" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/já existe uma revisão/);
  });

  it("abre o histórico com o gráfico e a tabela, e permite corrigir o mês de uma revisão", async () => {
    vi.mocked(api.revisoesDaCarteira).mockResolvedValue([revisao()]);
    vi.mocked(api.editarMesDaRevisao).mockResolvedValue(revisao({ mes_de_referencia: "2026-08-01" }));
    render(<RevisaoMensal />);
    await screen.findByText(/ainda não registrada/);
    await userEvent.click(screen.getByRole("button", { name: "Ver histórico de revisões" }));
    expect(screen.getByRole("img", { name: /Evolução do ISC em 1 revisão/ })).toBeInTheDocument();
    expect(screen.getByText("Julho de 2026")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Editar mês" }));
    const campoMes = screen.getByLabelText(/Novo mês para a revisão/);
    await userEvent.clear(campoMes);
    await userEvent.type(campoMes, "2026-08");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(api.editarMesDaRevisao).toHaveBeenCalledWith(1, "2026-08"));
  });

  it("histórico vazio explica que nasce com a primeira revisão", async () => {
    vi.mocked(api.revisoesDaCarteira).mockResolvedValue([]);
    render(<RevisaoMensal />);
    await screen.findByText(/ainda não registrada/);
    await userEvent.click(screen.getByRole("button", { name: "Ver histórico de revisões" }));
    expect(screen.getByText(/Registre a primeira revisão para começar o histórico/)).toBeInTheDocument();
  });
});
