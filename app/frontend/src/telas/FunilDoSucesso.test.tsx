import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { FunilDoSucesso as Funil, GrupoNoFunilDoSucesso } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { FunilDoSucesso, textoDasVendas } from "./FunilDoSucesso";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      funilDoSucesso: vi.fn(), marcarItemDoSucesso: vi.fn(), concluirEtapaDoSucesso: vi.fn(),
      reunioesDoGrupo: vi.fn(), registrarReuniao: vi.fn(), montarAta: vi.fn(), responsaveisPorAjuste: vi.fn(),
      servicos: vi.fn(), reunioesDaCarteira: vi.fn(), registrarReuniaoDaCarteira: vi.fn(),
    },
  };
});

const grupo = (g: Partial<GrupoNoFunilDoSucesso> & { grupo_id: number; nome: string }): GrupoNoFunilDoSucesso => ({
  etapa: "em_curso", classe: null, itens_feitos: [], etapa_desde: null, em_curso_desde: null, situacao: null, reunioes: [],
  ajustes_pendentes: 0, ajustes_atrasados: 0, ajustes_feitos: 0,
  mrr_bruto: "0", vendas_abertas: 0, vendas_por_mes: "0", vendas_em_projeto: "0", ...g,
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
    { chave: "mensal", nome: "Mensal", meses: 1, participantes: "Gestor & Cliente", pauta: ["Dashboard do mês"] },
    { chave: "trimestral", nome: "Trimestral", meses: 3, participantes: "Gestor & Cliente", pauta: ["PRA e KPIs"] },
    { chave: "semestral", nome: "Semestral", meses: 6, participantes: "Gestor & Cliente", pauta: ["Estratégia e desafios"] },
  ],
  tipos_antigos: { bimestral: "Bimestral", anual: "Anual" },
  cadencia: { A: ["mensal"], B: ["trimestral"], C: ["semestral"] },
  intencao: { A: "Reter e expandir", B: "Subir para A", C: "Entender a estratégia e vender o que falta" },
  carteira: {
    nome: "Bimestral da carteira", participantes: "Head do BPO & CEO da Critério", pauta: ["Overview da carteira"],
    ultima: "2026-08-01", proxima: "2026-10-01", atrasada: true, dias_de_atraso: 2,
  },
  grupos: [
    grupo({ grupo_id: 1, nome: "Grupo Novo", etapa: "contrato", itens_feitos: ["proposta", "contrato"] }),
    grupo({
      grupo_id: 2, nome: "Grupo Em Dia", classe: "C", situacao: "em_dia", em_curso_desde: "2026-01-10", mrr_bruto: "3000.00",
      reunioes: [{ tipo: "semestral", ultima: "2026-05-01", proxima: "2026-11-01", atrasada: false, dias_de_atraso: null }],
    }),
    grupo({
      grupo_id: 3, nome: "Grupo Atrasado", classe: "B", situacao: "atrasada", mrr_bruto: "10000.00",
      ajustes_pendentes: 2, ajustes_atrasados: 1, vendas_abertas: 2, vendas_por_mes: "4500.00", vendas_em_projeto: "14000.00",
      reunioes: [{ tipo: "trimestral", ultima: "2026-05-01", proxima: "2026-08-01", atrasada: true, dias_de_atraso: 62 }],
    }),
    grupo({
      grupo_id: 5, nome: "Grupo B Novo", classe: "B", situacao: "atrasada", mrr_bruto: "2000.00",
      reunioes: [{ tipo: "trimestral", ultima: null, proxima: null, atrasada: true, dias_de_atraso: null }],
    }),
    grupo({ grupo_id: 4, nome: "Grupo Sem Classe", situacao: "sem_classe" }),
  ],
};

const eu = (permissoes: string[]) => ({
  modo: "microsoft" as const, email: "k@grupocriterio.com.br", nome: "Karine", perfil: "CS", administrador: false, permissoes,
});

const coluna = (nome: string) => screen.getByRole("region", { name: nome });
const classe = (rotulo: RegExp) => screen.getByRole("button", { name: rotulo });

describe("Funil do Sucesso do Cliente por classe (03/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    localStorage.clear();
    vi.mocked(api.funilDoSucesso).mockResolvedValue(FUNIL);
    vi.mocked(api.reunioesDoGrupo).mockResolvedValue([]);
    vi.mocked(api.servicos).mockResolvedValue([]);
    vi.mocked(api.responsaveisPorAjuste).mockResolvedValue([
      { email: "bruno@grupocriterio.com.br", nome: "Bruno Soares", perfil: "Área técnica" },
    ]);
  });

  it("consolidado: uma coluna por etapa, a contagem de cada classe e o quadro que compara", async () => {
    render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    expect(screen.getAllByRole("region").filter((r) => r.classList.contains("coluna")).map((r) => r.getAttribute("aria-label")))
      .toEqual(["Contrato", "Handover", "Kickoff", "Mensal", "Trimestral", "Semestral"]);
    expect(classe(/^Consolidado/)).toHaveAttribute("aria-pressed", "true");
    expect(classe(/^Consolidado/)).toHaveTextContent("Consolidado5");
    expect(classe(/^Classe B/)).toHaveTextContent("Classe B2");
    expect(classe(/^Sem classe/)).toHaveTextContent("Sem classe1");
    const quadro = screen.getByRole("region", { name: "Comparativo das classes" });
    const linhaB = within(quadro).getByRole("button", { name: /B · trimestral/ }).closest("tr")!;
    // 2 clientes, MRR somado, nenhum em dia, 2 vencidas; mensal e projeto separados
    expect(Array.from(linhaB.querySelectorAll("td")).map((td) => td.textContent?.replace(/\s/g, " "))).toEqual([
      "B · trimestral", "2ver (2)", "R$ 12.000,00", "0%", "⚠ 2", "2 · ⚠ 1 atrasado", "2R$ 4.500,00/mês+ R$ 14.000,00 em projeto",
    ]);
    const linhaA = within(quadro).getByRole("button", { name: /A · mensal/ }).closest("tr")!;
    expect(linhaA.querySelectorAll("td")[3]).toHaveTextContent("—"); // sem cliente em curso, sem %
    expect(screen.getByText(/Sem classe, sem reunião cobrada/)).toBeInTheDocument();
  });

  it("o que se faz em cada etapa aparece no ⓘ, não dentro da coluna", async () => {
    render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    expect(screen.queryByText("Emitir a proposta comercial")).not.toBeInTheDocument();
    const info = within(coluna("Contrato")).getByRole("button", { name: "O que se faz em Contrato" });
    fireEvent.mouseEnter(info);
    // A dica do ⓘ da etapa (as explicações dos números também são tooltip, escondidas até o mouse passar).
    const dica = document.querySelector(".sucesso-dica")!;
    expect(dica).toHaveTextContent("Contrato · Comercial & Cliente");
    expect(dica).toHaveTextContent("Emitir a proposta comercial");
    fireEvent.mouseLeave(info);
    expect(document.querySelector(".sucesso-dica")).toBeNull();
    // no clique (celular), fica aberta até clicar de novo
    await userEvent.click(within(coluna("Semestral")).getByRole("button", { name: "O que se faz em Semestral" }));
    expect(document.querySelector(".sucesso-dica")).toHaveTextContent("Estratégia e desafios");
  });

  it("em curso, vencidas no topo com ⚠ e texto", async () => {
    render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    const trimestral = coluna("Trimestral");
    expect(within(trimestral).getByText("⚠ 2 vencidas")).toBeInTheDocument();
    expect(within(trimestral).getAllByRole("button").filter((b) => b.classList.contains("cartao"))
      .map((b) => b.querySelector(".cartao-grupo")?.textContent)).toEqual(["Grupo Atrasado", "Grupo B Novo"]);
    expect(within(trimestral).getByText("⚠ venceu em 01/08/2026 (62 d)")).toBeInTheDocument();
    expect(within(trimestral).getByText("⚠ nenhuma registrada ainda")).toBeInTheDocument();
    expect(within(trimestral).getByText("2 vendas abertas")).toBeInTheDocument();
    // colunas e cartões como no Funil comercial: a fase e o MRR da coluna embaixo do nome; o MRR no cartão
    expect(within(trimestral).getByText("Em curso · R$ 12 mil/mês")).toBeInTheDocument();
    expect(within(trimestral).getByText("R$ 10 mil/mês")).toBeInTheDocument();
    expect(within(coluna("Contrato")).getByText(/^Implantação · /)).toBeInTheDocument();
    expect(within(coluna("Mensal")).getByText("Nenhum grupo nesta etapa.")).toBeInTheDocument();
  });

  it("a classe mostra a intenção, os números dela e só a reunião dela; e é lembrada", async () => {
    const { unmount } = render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    await userEvent.click(classe(/^Classe B/));
    const intencao = screen.getByRole("region", { name: "Intenção da classe B" });
    expect(intencao).toHaveTextContent("Classe B · reunião trimestral · intenção");
    expect(intencao).toHaveTextContent("Subir para A");
    expect(intencao).toHaveTextContent(/2 clientes.*ver \(2\) · R\$ 12\.000,00 bruto · 0% das reuniões em dia · ⚠ 2 vencidas/);
    expect(screen.getAllByRole("region").filter((r) => r.classList.contains("coluna")).map((r) => r.getAttribute("aria-label")))
      .toEqual(["Contrato", "Handover", "Kickoff", "Trimestral"]);
    expect(screen.queryByText("Grupo Novo")).not.toBeInTheDocument(); // sem classe ainda, fica no consolidado
    expect(screen.queryByRole("region", { name: "Comparativo das classes" })).not.toBeInTheDocument();
    unmount();
    render(<FunilDoSucesso />);
    expect(await screen.findByRole("region", { name: "Intenção da classe B" })).toBeInTheDocument();
  });

  it("sem classe: uma coluna só, com o porquê no ⓘ", async () => {
    render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    await userEvent.click(classe(/^Sem classe/));
    expect(within(coluna("Sem classe")).getByText("Grupo Sem Classe")).toBeInTheDocument();
    expect(within(coluna("Sem classe")).getByText("⚠ sem classe")).toBeInTheDocument();
  });

  it("grade: uma linha por cliente, as mais atrasadas primeiro, e ordena pelo título", async () => {
    render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    await userEvent.click(screen.getByRole("button", { name: "☰ Grade" }));
    const grade = () => within(document.querySelector<HTMLElement>(".sucesso-grade")!);
    const nomes = () => grade().getAllByRole("row").slice(1).map((r) => r.querySelector("td")?.textContent);
    expect(nomes()).toEqual(["Grupo Atrasado", "Grupo B Novo", "Grupo Em Dia", "Grupo Novo", "Grupo Sem Classe"]);
    const atrasado = grade().getAllByRole("row")[1];
    expect(atrasado).toHaveTextContent("⚠ venceu em 01/08/2026 (62 d)");
    expect(atrasado).toHaveTextContent("2 pendentes · ⚠ 1 atrasado");
    expect(grade().getAllByRole("row")[4]).toHaveTextContent("2 de 3 itens do checklist feitos");
    await userEvent.click(grade().getByRole("button", { name: "Grupo" }));
    expect(nomes()).toEqual(["Grupo Atrasado", "Grupo B Novo", "Grupo Em Dia", "Grupo Novo", "Grupo Sem Classe"].sort((a, b) => a.localeCompare(b, "pt-BR")));
    expect(localStorage.getItem("crm.sucesso.visao")).toBe("grade");
  });

  it("vendas: mensal e projeto nunca se somam", () => {
    expect(textoDasVendas(0, 0, 0)).toBe("0");
    expect(textoDasVendas(1, 0, 45000)).toMatch(/^1 · R\$\s45\.000,00 em projeto$/);
    expect(textoDasVendas(1, 0, 0)).toBe("1");
  });

  it("a bimestral da carteira mostra o vencimento e abre o painel", async () => {
    vi.mocked(api.reunioesDaCarteira).mockResolvedValue({ devida: FUNIL.carteira, reunioes: [] });
    render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    const cartao = screen.getByRole("region", { name: "Reunião bimestral da carteira" });
    expect(cartao).toHaveTextContent("Última 01/08/2026 · ⚠ venceu em 01/10/2026 (2 d)");
    await userEvent.click(within(cartao).getByRole("button", { name: "Registrar a bimestral" }));
    expect(await screen.findByText("Bimestrais registradas")).toBeInTheDocument();
    expect(screen.getByLabelText("Correções de rota")).toBeInTheDocument();
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

  it("em curso: aberto pela coluna, registra a reunião com a pauta do tipo já preenchida", async () => {
    vi.mocked(api.registrarReuniao).mockResolvedValue(FUNIL.grupos[2]);
    render(<FunilDoSucesso />);
    await screen.findByText("Grupo Novo");
    await userEvent.click(within(coluna("Trimestral")).getByText("Grupo Atrasado"));
    expect(screen.getByText("Em curso · classe B · reunião trimestral")).toBeInTheDocument();
    expect(screen.getByLabelText("Tipo")).toHaveValue("trimestral");
    expect(screen.getByLabelText("Pauta")).toHaveValue("• PRA e KPIs");
    expect(screen.queryByRole("option", { name: "Anual" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Decisões do cliente"), { target: { value: "Abrir filial em 2027" } });
    await userEvent.click(screen.getByRole("button", { name: "Registrar reunião" }));
    expect(api.registrarReuniao).toHaveBeenCalledWith(3, expect.objectContaining({
      tipo: "trimestral", participantes: "Gestor & Cliente", decisoes: "Abrir filial em 2027", dashboard: "", ajustes: [], oportunidades: [],
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
