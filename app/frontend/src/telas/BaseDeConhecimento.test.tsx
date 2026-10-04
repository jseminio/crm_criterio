import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ErroDaApi } from "../api/cliente";
import type { BaseDeConhecimento as Base, BlocoDaBase, FichaDaBase } from "../api/tipos";
import { ProvedorDeAcesso } from "../entrada";
import { BaseDeConhecimento } from "./BaseDeConhecimento";

vi.mock("../api/cliente", async () => {
  const real = await vi.importActual<typeof import("../api/cliente")>("../api/cliente");
  return {
    ...real,
    api: {
      baseDoSdr: vi.fn(), criarFicha: vi.fn(), alterarFicha: vi.fn(), moverFicha: vi.fn(),
      aprovarFicha: vi.fn(), cargaInicialDaBase: vi.fn(),
    },
  };
});

const NOMES = ["Regras de atuação", "Transbordo", "Serviços", "Objeções", "Tom de voz", "Quem é a Critério",
  "Qualificação", "Perguntas frequentes", "Referências"];

const bloco = (nome: string, campos: Partial<BlocoDaBase> = {}): BlocoDaBase => ({
  bloco: nome, total: 0, valem: 0, em_revisao: 0, rascunhos: 0, vencidas: 0, vai_para_a_ia: nome !== "Referências", ...campos,
});

const P3: FichaDaBase = {
  id: 3, codigo: "P3", titulo: "Não opina sobre o caso concreto do lead", bloco: "Regras de atuação", servico: null,
  texto: "Vou passar a sua pergunta para eles.", nunca_dizer: "Opinião sobre regime.", como_o_lead_pergunta: null,
  fonte: "doc", dono: "Eduardo", depende_de_hipotese: false, situacao: "Em revisão", validade: null, aprovada_por: null,
  aprovada_em: null, atualizado_em: "2026-10-03T12:00:00+00:00", vencida: false, vale_para_a_ia: false, problemas_para_aprovar: [],
  codigo_travado: true,
};
const VENCIDA: FichaDaBase = {
  ...P3, id: 40, codigo: "R1", titulo: "Speed-to-lead", bloco: "Referências", situacao: "Aprovada", validade: "2026-01-01",
  vencida: true,
};
const SEM_FONTE: FichaDaBase = {
  ...P3, id: 50, codigo: null, codigo_travado: false, titulo: "Prazo de implantação", bloco: "Perguntas frequentes", situacao: "Rascunho",
  fonte: null, problemas_para_aprovar: ["Falta a fonte"],
};

function base(fichas: FichaDaBase[]): Base {
  return {
    situacoes: ["Rascunho", "Em revisão", "Aprovada", "Arquivada"],
    blocos: NOMES.map((n) => bloco(n, n === "Regras de atuação" ? { total: 12, em_revisao: 12 } : n === "Referências" ? { total: 1, vencidas: 1 } : {})),
    fichas,
    proximos_codigos: Object.fromEntries(NOMES.map((n, i) => [n, `${"PTSOVCQFR"[i]}${i === 2 ? "13" : i === 0 ? "13" : "1"}`])),
  };
}

const quem = (permissoes: string[]) => ({
  modo: "microsoft" as const, email: "k@grupocriterio.com.br", nome: "Karine", perfil: "P", administrador: false, permissoes,
});

describe("SDR › Base de conhecimento (03/10/2026)", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    vi.mocked(api.baseDoSdr).mockResolvedValue(base([P3, VENCIDA, SEM_FONTE]));
  });

  it("mostra a prontidão por bloco, com o alerta em texto, e a lista", async () => {
    render(<BaseDeConhecimento />);
    const regras = await screen.findByRole("button", { name: /Regras de atuação/ });
    expect(regras).toHaveTextContent("0 de 12 valem para a IA");
    expect(regras).toHaveTextContent("12 em revisão");
    expect(screen.getByRole("button", { name: /^Objeções/ })).toHaveTextContent("⚠ Sem fichas");
    expect(screen.getByRole("button", { name: /^Referências/ })).toHaveTextContent("não vai para a IA");
    expect(screen.getByRole("button", { name: "P3 · Não opina sobre o caso concreto do lead" })).toBeInTheDocument();
    expect(within(screen.getByRole("table")).getByText("Vencida")).toBeInTheDocument();
  });

  it("filtra por bloco clicando no cartão, por situação e pela busca", async () => {
    render(<BaseDeConhecimento />);
    await userEvent.click(await screen.findByRole("button", { name: /^Referências/ }));
    expect(screen.getAllByRole("row")).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: /^Referências/ }));
    await userEvent.selectOptions(screen.getByLabelText("Situação"), "Vencidas");
    expect(screen.getByRole("button", { name: "R1 · Speed-to-lead" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Situação"), "");
    await userEvent.type(screen.getByLabelText("Buscar"), "nada disso");
    expect(screen.getByText("Nenhum resultado para esses filtros")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));
    expect(screen.getAllByRole("row")).toHaveLength(4);
  });

  it("base vazia oferece a carga inicial a quem edita", async () => {
    vi.mocked(api.baseDoSdr).mockResolvedValueOnce(base([])).mockResolvedValue(base([P3]));
    vi.mocked(api.cargaInicialDaBase).mockResolvedValue({ acrescentadas: 46, ja_existiam: 0 });
    render(<BaseDeConhecimento />);
    expect(await screen.findByText("A base ainda está vazia")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Trazer a carga inicial" }));
    expect(await screen.findByText(/46 fichas acrescentadas/)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /^P3/ })).toBeInTheDocument();
  });

  it("quem só vê não tem carga, nova ficha nem edição", async () => {
    vi.mocked(api.baseDoSdr).mockResolvedValue(base([]));
    render(<ProvedorDeAcesso eu={quem(["sdr.ver"])}><BaseDeConhecimento /></ProvedorDeAcesso>);
    expect(await screen.findByText("Quem edita a base ainda não cadastrou fichas.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Trazer a carga inicial" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Nova ficha" })).not.toBeInTheDocument();
  });

  it("erro com tentar de novo", async () => {
    vi.mocked(api.baseDoSdr).mockRejectedValueOnce(new ErroDaApi(500, "Banco fora do ar")).mockResolvedValue(base([P3]));
    render(<BaseDeConhecimento />);
    expect(await screen.findByText("Banco fora do ar")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByRole("button", { name: /^P3/ })).toBeInTheDocument();
  });

  it("cria uma ficha nova no bloco escolhido", async () => {
    vi.mocked(api.criarFicha).mockResolvedValue({ ...SEM_FONTE, id: 60, titulo: "Atendem fora do Rio?" });
    render(<BaseDeConhecimento />);
    await userEvent.click(await screen.findByRole("button", { name: "Nova ficha" }));
    const painel = screen.getByRole("dialog", { name: "Nova ficha" });
    await userEvent.type(within(painel).getByLabelText("Título"), "Atendem fora do Rio?");
    await userEvent.selectOptions(within(painel).getByLabelText("Bloco"), "Perguntas frequentes");
    await userEvent.type(within(painel).getByLabelText("O que a IA pode dizer"), "Sim, atendemos todo o Brasil.");
    await userEvent.click(within(painel).getByRole("button", { name: "Criar ficha" }));
    expect(api.criarFicha).toHaveBeenCalledWith(expect.objectContaining({
      codigo: "F1", titulo: "Atendem fora do Rio?", bloco: "Perguntas frequentes", texto: "Sim, atendemos todo o Brasil.",
    }));
    expect(await screen.findByText("✓ Ficha salva.")).toBeInTheDocument();
  });

  it("aprovar sem login pede quem aprova e salva antes o que mudou", async () => {
    vi.mocked(api.alterarFicha).mockResolvedValue(P3);
    vi.mocked(api.aprovarFicha).mockResolvedValue({ ...P3, situacao: "Aprovada", vale_para_a_ia: true });
    render(<BaseDeConhecimento />);
    await userEvent.click(await screen.findByRole("button", { name: /^P3/ }));
    const painel = screen.getByRole("dialog");
    const aprovar = within(painel).getByRole("button", { name: "Aprovar" });
    expect(aprovar).toBeDisabled();
    await userEvent.type(within(painel).getByLabelText("Dono"), " Luiz");
    await userEvent.type(within(painel).getByLabelText("Quem aprova"), "Eduardo");
    await userEvent.click(aprovar);
    expect(api.alterarFicha).toHaveBeenCalledWith(3, { dono: "Eduardo Luiz" });
    expect(api.aprovarFicha).toHaveBeenCalledWith(3, "Eduardo");
    expect(await screen.findByText(/Ficha aprovada: a IA já pode usá-la/)).toBeInTheDocument();
  });

  it("diz o que falta para aprovar e trava o botão", async () => {
    render(<BaseDeConhecimento />);
    await userEvent.click(await screen.findByRole("button", { name: "Prazo de implantação" }));
    const painel = screen.getByRole("dialog");
    expect(within(painel).getByText("Falta a fonte")).toBeInTheDocument();
    expect(within(painel).getByRole("button", { name: "Aprovar" })).toBeDisabled();
    expect(within(painel).getByRole("button", { name: "Enviar para revisão" })).toBeInTheDocument();
  });

  it("quem edita mas não aprova não vê o botão Aprovar", async () => {
    render(<ProvedorDeAcesso eu={quem(["sdr.ver", "sdr.base"])}><BaseDeConhecimento /></ProvedorDeAcesso>);
    await userEvent.click(await screen.findByRole("button", { name: /^P3/ }));
    const painel = screen.getByRole("dialog");
    expect(within(painel).queryByRole("button", { name: "Aprovar" })).not.toBeInTheDocument();
    expect(within(painel).getByRole("button", { name: "Salvar" })).toBeInTheDocument();
  });

  it("mostra o erro do servidor no painel", async () => {
    vi.mocked(api.moverFicha).mockRejectedValue(new ErroDaApi(409, "a ficha já está arquivada"));
    render(<BaseDeConhecimento />);
    await userEvent.click(await screen.findByRole("button", { name: /^P3/ }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Arquivar" }));
    expect(await screen.findByText("✗ a ficha já está arquivada")).toBeInTheDocument();
  });

  describe("código editável (M1, 04/10/2026)", () => {
    it("ficha nova já vem com o próximo código livre, que acompanha o bloco", async () => {
      render(<BaseDeConhecimento />);
      await userEvent.click(await screen.findByRole("button", { name: "Nova ficha" }));
      const painel = screen.getByRole("dialog", { name: "Nova ficha" });
      const codigo = within(painel).getByLabelText("Código");
      expect(codigo).toHaveValue("P13");
      expect(within(painel).getByText(/Sugerido: o próximo livre em Regras de atuação/)).toBeInTheDocument();
      await userEvent.selectOptions(within(painel).getByLabelText("Bloco"), "Objeções");
      expect(codigo).toHaveValue("O1");
      await userEvent.clear(codigo);
      await userEvent.type(codigo, "o7");
      expect(codigo).toHaveValue("O7");
      expect(within(painel).getByText(/Começa sempre com O, a letra do bloco/)).toBeInTheDocument();
    });

    it("ficha da carga mostra o código travado, sem trocar bloco", async () => {
      render(<BaseDeConhecimento />);
      await userEvent.click(await screen.findByRole("button", { name: /^P3/ }));
      const painel = screen.getByRole("dialog");
      expect(within(painel).getByLabelText("Código")).toHaveAttribute("readonly");
      expect(within(painel).getByLabelText("Bloco")).toBeDisabled();
      expect(within(painel).getByText(/Travado: código da carga inicial/)).toBeInTheDocument();
    });

    it("ficha manual troca o código e mostra a recusa do servidor", async () => {
      vi.mocked(api.alterarFicha).mockRejectedValue(
        new ErroDaApi(409, 'O código F1 já é da ficha "Onde fica". Use F2, o próximo livre.'));
      render(<BaseDeConhecimento />);
      await userEvent.click(await screen.findByRole("button", { name: "Prazo de implantação" }));
      const painel = screen.getByRole("dialog");
      const codigo = within(painel).getByLabelText("Código");
      expect(codigo).not.toHaveAttribute("readonly");
      await userEvent.type(codigo, "F1");
      await userEvent.click(within(painel).getByRole("button", { name: "Salvar" }));
      expect(api.alterarFicha).toHaveBeenCalledWith(50, { codigo: "F1" });
      expect(await within(painel).findByText(/Use F2, o próximo livre/)).toBeInTheDocument();
    });
  });
});
