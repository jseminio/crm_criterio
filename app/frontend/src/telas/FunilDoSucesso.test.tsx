import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { FunilDoSucesso as Funil, GrupoNoFunilDoSucesso } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { FunilDoSucesso } from "./FunilDoSucesso";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      funilDoSucesso: vi.fn(), marcarItemDoSucesso: vi.fn(), concluirEtapaDoSucesso: vi.fn(),
      reunioesDoGrupo: vi.fn(), registrarReuniao: vi.fn(),
    },
  };
});

const grupo = (g: Partial<GrupoNoFunilDoSucesso> & { grupo_id: number; nome: string }): GrupoNoFunilDoSucesso => ({
  etapa: "em_curso", classe: null, itens_feitos: [], etapa_desde: null, em_curso_desde: null, situacao: null, reunioes: [], ...g,
});

const FUNIL: Funil = {
  etapas: [
    { chave: "contrato", nome: "Contrato", participantes: "Comercial & Cliente" },
    { chave: "handover", nome: "Handover", participantes: "Comercial" },
    { chave: "kickoff", nome: "Kickoff", participantes: "Gestor & Cliente" },
    { chave: "em_curso", nome: "Em curso", participantes: null },
  ],
  checklist: {
    contrato: [
      { chave: "proposta", rotulo: "Emitir a proposta comercial" },
      { chave: "contrato", rotulo: "Emitir o contrato" },
      { chave: "assinatura", rotulo: "Assinar o contrato comercial" },
    ],
    handover: [{ chave: "pontos_sensiveis", rotulo: "Apresentar os pontos sensíveis" }],
    kickoff: [{ chave: "kyc", rotulo: "Preencher o KYC" }],
  },
  tipos: [
    { chave: "mensal", nome: "Mensal", meses: 1, participantes: "Gestor & Cliente", pauta: ["Demonstrações do mês"] },
    { chave: "trimestral", nome: "Trimestral", meses: 3, participantes: "Gestor & Cliente", pauta: ["PRA e KPIs"] },
    { chave: "anual", nome: "Anual", meses: 12, participantes: "Gestor & Cliente", pauta: ["Renovação"] },
  ],
  cadencia: { A: ["mensal", "trimestral", "anual"], B: ["trimestral", "anual"], C: ["anual"] },
  grupos: [
    grupo({ grupo_id: 1, nome: "Grupo Novo", etapa: "contrato", itens_feitos: ["proposta", "contrato"] }),
    grupo({
      grupo_id: 2, nome: "Grupo Em Dia", classe: "C", situacao: "em_dia", em_curso_desde: "2026-01-10",
      reunioes: [{ tipo: "anual", ultima: "2026-05-01", proxima: "2027-05-01", atrasada: false, dias_de_atraso: null }],
    }),
    grupo({
      grupo_id: 3, nome: "Grupo Atrasado", classe: "B", situacao: "atrasada",
      reunioes: [
        { tipo: "trimestral", ultima: "2026-05-01", proxima: "2026-08-01", atrasada: true, dias_de_atraso: 62 },
        { tipo: "anual", ultima: null, proxima: null, atrasada: true, dias_de_atraso: null },
      ],
    }),
    grupo({ grupo_id: 4, nome: "Grupo Sem Classe", situacao: "sem_classe" }),
  ],
};

const eu = (permissoes: string[]) => ({
  modo: "microsoft" as const, email: "k@grupocriterio.com.br", nome: "Karine", perfil: "CS", administrador: false, permissoes,
});

const coluna = (nome: string) => screen.getByRole("region", { name: nome });

describe("Funil do Sucesso do Cliente (02/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.funilDoSucesso).mockResolvedValue(FUNIL);
    vi.mocked(api.reunioesDoGrupo).mockResolvedValue([]);
  });

  it("põe cada grupo na coluna certa, com o atraso em texto", async () => {
    render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    expect(within(coluna("Contrato")).getByText("Grupo Novo")).toBeInTheDocument();
    expect(within(coluna("Contrato")).getByText("2 de 3 itens feitos")).toBeInTheDocument();
    expect(within(coluna("Em dia")).getByText("Próxima: Anual até 01/05/2027")).toBeInTheDocument();
    const atrasada = coluna("Atrasada");
    expect(within(atrasada).getByText("⚠ Trimestral venceu em 01/08/2026 (62 d)")).toBeInTheDocument();
    expect(within(atrasada).getByText("e mais 1 reunião atrasada")).toBeInTheDocument();
    // a mais atrasada primeiro, sem classe por último
    expect(within(atrasada).getAllByRole("button").map((b) => b.querySelector(".cartao-grupo")?.textContent))
      .toEqual(["Grupo Atrasado", "Grupo Sem Classe"]);
    expect(within(atrasada).getByText(/Sem classe: avalie o Score/)).toBeInTheDocument();
    expect(within(coluna("Handover")).getByText("Nenhum grupo nesta etapa.")).toBeInTheDocument();
    expect(screen.getByText(/A: Mensal, Trimestral, Anual · B: Trimestral, Anual · C: Anual/)).toBeInTheDocument();
  });

  it("a busca filtra e, sem resultado, oferece limpar", async () => {
    render(<FunilDoSucesso />);
    fireEvent.change(await screen.findByLabelText("Buscar grupo"), { target: { value: "zzz" } });
    expect(screen.getByText("Nenhum resultado para esses filtros")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));
    expect(screen.getByText("Grupo Novo")).toBeInTheDocument();
  });

  it("sem grupo nenhum, diz como um grupo entra no funil", async () => {
    vi.mocked(api.funilDoSucesso).mockResolvedValue({ ...FUNIL, grupos: [] });
    render(<FunilDoSucesso />);
    expect(await screen.findByText("Nenhum cliente com contrato valendo")).toBeInTheDocument();
  });

  it("checklist: marca item e só conclui a etapa com tudo feito", async () => {
    vi.mocked(api.marcarItemDoSucesso).mockResolvedValue(FUNIL.grupos[0]);
    render(<FunilDoSucesso />);
    await userEvent.click(await screen.findByText("Grupo Novo"));
    const concluir = screen.getByRole("button", { name: "Concluir etapa e passar para Handover" });
    expect(concluir).toBeDisabled();
    expect(screen.getByText("· faltam 1 item")).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Assinar o contrato comercial"));
    expect(api.marcarItemDoSucesso).toHaveBeenCalledWith(1, "assinatura", true);
  });

  it("em curso: registra a reunião com a pauta do tipo já preenchida", async () => {
    vi.mocked(api.registrarReuniao).mockResolvedValue(FUNIL.grupos[2]);
    render(<FunilDoSucesso />);
    await userEvent.click(await screen.findByText("Grupo Atrasado"));
    expect(screen.getByLabelText("Tipo")).toHaveValue("trimestral"); // a primeira atrasada
    expect(screen.getByLabelText("Pauta")).toHaveValue("• PRA e KPIs");
    expect(screen.getByText("⚠ registre a primeira")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Decisões do cliente"), { target: { value: "Abrir filial em 2027" } });
    await userEvent.click(screen.getByRole("button", { name: "Registrar reunião" }));
    expect(api.registrarReuniao).toHaveBeenCalledWith(3, expect.objectContaining({
      tipo: "trimestral", participantes: "Gestor & Cliente", decisoes: "Abrir filial em 2027", dashboard: "",
    }));
    expect(await screen.findByRole("status")).toHaveTextContent("Reunião trimestral");
  });

  it("o motivo da recusa do servidor aparece", async () => {
    vi.mocked(api.registrarReuniao).mockRejectedValue(new ErroDaApi(422, "A data da reunião não pode ser futura"));
    render(<FunilDoSucesso />);
    await userEvent.click(await screen.findByText("Grupo Em Dia"));
    await userEvent.click(screen.getByRole("button", { name: "Registrar reunião" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("não pode ser futura");
  });

  it("quem só vê não tem checklist editável nem formulário", async () => {
    render(
      <ProvedorDeAcesso eu={eu(["sucesso.ver"])}>
        <FunilDoSucesso />
      </ProvedorDeAcesso>,
    );
    await userEvent.click(await screen.findByText("Grupo Novo"));
    expect(screen.getByLabelText("Assinar o contrato comercial")).toBeDisabled();
    expect(screen.queryByRole("button", { name: /Concluir etapa/ })).not.toBeInTheDocument();
  });
});
