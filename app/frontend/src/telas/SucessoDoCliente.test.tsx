import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProvedorDeAcesso } from "../entrada";
import { FunilEQuestionarios } from "./FunilEQuestionarios";
import { SucessoDoCliente } from "./SucessoDoCliente";

vi.mock("./Carteira", () => ({ Carteira: () => <p>tela da saúde da carteira</p> }));
vi.mock("./Contratos", () => ({ Contratos: () => <p>tela de contratos</p> }));
vi.mock("./FunilDoSucesso", () => ({ FunilDoSucesso: () => <p>tela do funil do sucesso</p> }));
vi.mock("./Funil", () => ({ Funil: () => <p>tela do funil</p> }));
vi.mock("./Questionarios", () => ({ Questionarios: () => <p>tela de questionários</p> }));

const eu = (permissoes: string[]) => ({
  modo: "microsoft" as const, email: "k@grupocriterio.com.br", nome: "Karine", perfil: "Comercial", administrador: false, permissoes,
});

describe("Sucesso do Cliente (02/10/2026)", () => {
  beforeEach(() => localStorage.clear());

  it("junta Saúde da carteira, Gestão de contratos e o Funil do Sucesso em abas, nessa ordem", () => {
    render(<SucessoDoCliente listas={null} />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(
      ["Saúde da carteira", "Gestão de contratos", "Funil do Sucesso do Cliente"]);
    expect(screen.getByText("tela da saúde da carteira")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Gestão de contratos" }));
    expect(screen.getByText("tela de contratos")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Funil do Sucesso do Cliente" }));
    expect(screen.getByText("tela do funil do sucesso")).toBeInTheDocument();
  });

  it("o atalho da Agenda abre direto em Gestão de contratos", () => {
    render(<SucessoDoCliente listas={null} abaPedida="contratos" />);
    expect(screen.getByRole("tab", { name: "Gestão de contratos" })).toHaveAttribute("aria-selected", "true");
  });

  it("quem vê contratos mas não a carteira vê só Gestão de contratos", () => {
    render(
      <ProvedorDeAcesso eu={eu(["contratos.ver", "funil.ver"])}>
        <SucessoDoCliente listas={null} />
      </ProvedorDeAcesso>,
    );
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Gestão de contratos"]);
  });
});

describe("Funil em abas (02/10/2026)", () => {
  beforeEach(() => localStorage.clear());

  it("Oportunidades, Questionários e Inteligência de Conversão, lembrando a última aba", () => {
    const { unmount } = render(<FunilEQuestionarios listas={null} />);
    expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["Oportunidades", "Questionários", "Inteligência de Conversão"]);
    expect(screen.getByText("tela do funil")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Questionários" }));
    expect(screen.getByText("tela de questionários")).toBeInTheDocument();
    unmount();
    render(<FunilEQuestionarios listas={null} />);
    expect(screen.getByRole("tab", { name: "Questionários" })).toHaveAttribute("aria-selected", "true");
  });
});
