import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { ContratoDetalhe } from "../api/tipos";
import { EventosDeContrato } from "./EventosDeContrato";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { registrarEventoDeContrato: vi.fn() } };
});

const contrato = (o: Partial<ContratoDetalhe> = {}): ContratoDetalhe => ({
  id: 7, grupo_id: 1, grupo_nome: "Alfa", oportunidade_id: 1, escopo: "BPO Contábil",
  preco_mensal: "1000.00", preco_anual: "12000.00", data_inicio: "2026-03-01", data_fim: "2027-03-01",
  situacao: "Ativo", signatario: null, documento_assinado: null, observacao: null, eventos: [], ...o,
});

describe("EventosDeContrato", () => {
  beforeEach(() => vi.clearAllMocks());

  it("antes da assinatura não deixa registrar e explica que a vigência começa nela", () => {
    render(<EventosDeContrato contrato={contrato({ situacao: "Aguardando assinatura" })} aoRegistrar={vi.fn()} />);
    expect(screen.getByText(/a vigência começa na assinatura/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/registrar evento/i)).toBeNull();
  });

  it("contrato encerrado não recebe mais eventos", () => {
    render(<EventosDeContrato contrato={contrato({ situacao: "Encerrado" })} aoRegistrar={vi.fn()} />);
    expect(screen.getByText(/não recebe mais eventos/i)).toBeInTheDocument();
  });

  it("mostra o histórico com o antes e o depois", () => {
    render(
      <EventosDeContrato
        aoRegistrar={vi.fn()}
        contrato={contrato({
          eventos: [{
            id: 1, tipo: "Reajuste", data_do_evento: "2026-09-01", registrado_em: "2026-09-25T15:00:00+00:00",
            descricao: "IPCA", preco_mensal_anterior: "1000.00", preco_mensal_novo: "1100.00",
            preco_anual_anterior: null, preco_anual_novo: null, escopo_anterior: null, escopo_novo: null,
            data_fim_anterior: null, data_fim_nova: null,
          }],
        })}
      />,
    );
    expect(screen.getByText(/1\.000,00.*→.*1\.100,00/)).toBeInTheDocument();
    expect(screen.getByText("IPCA")).toBeInTheDocument();
  });

  it("registra em dois passos e só chama a API depois de confirmar", async () => {
    vi.mocked(api.registrarEventoDeContrato).mockResolvedValue(contrato({ preco_mensal: "1100.00" }));
    const aoRegistrar = vi.fn();
    render(<EventosDeContrato contrato={contrato()} aoRegistrar={aoRegistrar} />);
    const botao = screen.getByRole("button", { name: /registrar reajuste/i });
    expect(botao).toBeDisabled(); // sem novo preço
    await userEvent.type(screen.getByLabelText("Novo preço mensal"), "1100");
    await userEvent.click(screen.getByRole("button", { name: /registrar reajuste/i }));
    expect(api.registrarEventoDeContrato).not.toHaveBeenCalled();
    expect(screen.getByText(/não se edita nem se apaga/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /confirmar reajuste/i }));
    await waitFor(() => expect(api.registrarEventoDeContrato).toHaveBeenCalledWith(7, { tipo: "Reajuste", data_do_evento: null, preco_mensal_novo: "1100" }));
    await waitFor(() => expect(aoRegistrar).toHaveBeenCalled());
  });

  it("encerramento exige o motivo antes de liberar", async () => {
    render(<EventosDeContrato contrato={contrato()} aoRegistrar={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Registrar evento"), "Encerramento");
    expect(screen.getByRole("button", { name: /registrar encerramento/i })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Motivo do encerramento"), "migrou de contador");
    expect(screen.getByRole("button", { name: /registrar encerramento/i })).toBeEnabled();
  });

  it("renovação pede a nova data de fim", async () => {
    render(<EventosDeContrato contrato={contrato()} aoRegistrar={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Registrar evento"), "Renovação");
    expect(screen.getByRole("button", { name: /registrar renovação/i })).toBeDisabled();
    expect(screen.getByText(/termina em/i)).toBeInTheDocument();
  });

  it("mostra o erro da API sem perder o que foi digitado", async () => {
    vi.mocked(api.registrarEventoDeContrato).mockRejectedValue(new ErroDaApi(422, "Expansão aumenta o valor."));
    render(<EventosDeContrato contrato={contrato()} aoRegistrar={vi.fn()} />);
    await userEvent.selectOptions(screen.getByLabelText("Registrar evento"), "Expansão");
    await userEvent.type(screen.getByLabelText("Novo preço mensal"), "900");
    await userEvent.click(screen.getByRole("button", { name: /registrar expansão/i }));
    await userEvent.click(screen.getByRole("button", { name: /confirmar expansão/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Expansão aumenta o valor.");
    expect(screen.getByLabelText("Novo preço mensal")).toHaveValue(900);
  });
});
