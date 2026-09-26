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
  id: 7, grupo_id: 1, grupo_nome: "Alfa", oportunidade_id: 1, empresa_id: null, anterior_ao_crm: false, escopo: "BPO Contábil",
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
            descricao: "IPCA", motivo_categoria: null, iniciativa: null, preco_mensal_anterior: "1000.00", preco_mensal_novo: "1100.00",
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

  const MOTIVOS = ["Preço", "Migrou para concorrente", "Outro"];

  it("encerramento exige a categoria do motivo antes de liberar", async () => {
    render(<EventosDeContrato contrato={contrato()} aoRegistrar={vi.fn()} motivos={MOTIVOS} />);
    await userEvent.selectOptions(screen.getByLabelText("Registrar evento"), "Encerramento");
    expect(screen.getByRole("button", { name: /registrar encerramento/i })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Motivo do encerramento"), "Preço");
    // só a categoria não basta: falta dizer quem decidiu
    expect(screen.getByRole("button", { name: /registrar encerramento/i })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Quem decidiu encerrar?"), "Critério");
    expect(screen.getByRole("button", { name: /registrar encerramento/i })).toBeEnabled();
  });

  it("a categoria 'Outro' exige texto; as demais, não", async () => {
    render(<EventosDeContrato contrato={contrato()} aoRegistrar={vi.fn()} motivos={MOTIVOS} />);
    await userEvent.selectOptions(screen.getByLabelText("Registrar evento"), "Encerramento");
    await userEvent.selectOptions(screen.getByLabelText("Quem decidiu encerrar?"), "Cliente");
    await userEvent.selectOptions(screen.getByLabelText("Motivo do encerramento"), "Outro");
    expect(screen.getByRole("button", { name: /registrar encerramento/i })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Descreva o motivo"), "fusão com outra empresa");
    expect(screen.getByRole("button", { name: /registrar encerramento/i })).toBeEnabled();
  });

  it("envia a categoria junto do encerramento", async () => {
    vi.mocked(api.registrarEventoDeContrato).mockResolvedValue(contrato({ situacao: "Encerrado" }));
    render(<EventosDeContrato contrato={contrato()} aoRegistrar={vi.fn()} motivos={MOTIVOS} />);
    await userEvent.selectOptions(screen.getByLabelText("Registrar evento"), "Encerramento");
    await userEvent.selectOptions(screen.getByLabelText("Quem decidiu encerrar?"), "Cliente");
    await userEvent.selectOptions(screen.getByLabelText("Motivo do encerramento"), "Migrou para concorrente");
    await userEvent.click(screen.getByRole("button", { name: /registrar encerramento/i }));
    await userEvent.click(screen.getByRole("button", { name: /confirmar encerramento/i }));
    await waitFor(() => expect(api.registrarEventoDeContrato).toHaveBeenCalledWith(7, { tipo: "Encerramento", data_do_evento: null, motivo_categoria: "Migrou para concorrente", iniciativa: "Cliente" }));
  });

  it("o histórico mostra a categoria do motivo do encerramento", () => {
    render(
      <EventosDeContrato
        aoRegistrar={vi.fn()}
        contrato={contrato({
          situacao: "Encerrado",
          eventos: [{
            id: 2, tipo: "Encerramento", data_do_evento: "2026-09-20", registrado_em: "2026-09-25T15:00:00+00:00",
            descricao: "foi para outro escritório", motivo_categoria: "Migrou para concorrente", iniciativa: "Cliente",
            preco_mensal_anterior: null, preco_mensal_novo: null, preco_anual_anterior: null, preco_anual_novo: null,
            escopo_anterior: null, escopo_novo: null, data_fim_anterior: "2027-03-01", data_fim_nova: "2026-09-20",
          }],
        })}
      />,
    );
    expect(screen.getByText("Migrou para concorrente")).toBeInTheDocument();
    expect(screen.getByText("Cliente")).toBeInTheDocument(); // quem decidiu
    expect(screen.getByText("foi para outro escritório")).toBeInTheDocument();
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
