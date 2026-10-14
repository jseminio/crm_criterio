import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/cliente";
import type { Eu, ServicoNoContrato } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { ServicosEContratos } from "./ServicosEContratos";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return { ...real, api: { servicosEContratos: vi.fn(), gravarServicosEContratos: vi.fn() } };
});

const ADMIN: Eu = { modo: "microsoft", email: "e@grupocriterio.com.br", nome: "Eduardo", perfil: "Administrador", administrador: true, permissoes: [] };
const LEITURA: Eu = { ...ADMIN, perfil: "Contratos", administrador: false, permissoes: ["contratos.ver"] };

const LINHAS: ServicoNoContrato[] = [
  { servico: "Endereço Fiscal", linha: "C1", tipo: "Recorrente", parcelas: 13, temas: 0, modelo: "Recorrente padrão",
    situacao_do_modelo: "aguardando arquivo", reajuste: "IPCA em julho", modelos_possiveis: ["Recorrente padrão"],
    reajustes_possiveis: ["IPCA em julho", "Caso a caso", "Sem reajuste"], padrao: true },
  { servico: "Consultoria", linha: "C2", tipo: "Não recorrente", parcelas: null, temas: 6, modelo: "Não recorrente v1.1",
    situacao_do_modelo: "minuta v1.1 · falta a revisão do advogado", reajuste: "Caso a caso",
    modelos_possiveis: ["Não recorrente v1.1"], reajustes_possiveis: ["Caso a caso", "Sem reajuste"], padrao: true },
];

function abrir(eu: Eu) {
  render(<ProvedorDeAcesso eu={eu}><ServicosEContratos /></ProvedorDeAcesso>);
}

describe("Serviços e contratos (13/10/2026)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.servicosEContratos).mockResolvedValue(LINHAS);
  });

  it("mostra tipo, parcelas, modelo com a situação do arquivo e o reajuste", async () => {
    abrir(ADMIN);
    expect(await screen.findByText("aguardando arquivo")).toBeInTheDocument();
    expect(screen.getByText("6 temas")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Reajuste de Consultoria" })).toHaveDisplayValue("Caso a caso");
  });

  it("salva só o que mudou", async () => {
    vi.mocked(api.gravarServicosEContratos).mockResolvedValue(LINHAS);
    abrir(ADMIN);
    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Reajuste de Endereço Fiscal" }), "Sem reajuste");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));
    expect(api.gravarServicosEContratos).toHaveBeenCalledWith([
      { servico: "Endereço Fiscal", modelo: "Recorrente padrão", reajuste: "Sem reajuste" },
    ]);
    expect(await screen.findByText(/1 serviço salvo/)).toBeInTheDocument();
  });

  it("quem não tem a permissão só lê", async () => {
    abrir(LEITURA);
    await screen.findByText("aguardando arquivo");
    expect(screen.queryByRole("button", { name: "Salvar" })).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  });
});
