import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderHook, act } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ThOrdenavel, ordenar, usarOrdenacao } from "./Ordenacao";

describe("ordenar", () => {
  const itens = [
    { nome: "Beta", valor: 20 },
    { nome: "Alfa", valor: null },
    { nome: "Gama", valor: 10 },
  ];
  const acessores = { nome: (i: (typeof itens)[number]) => i.nome, valor: (i: (typeof itens)[number]) => i.valor };

  it("sem ordenação, devolve a ordem original", () => {
    expect(ordenar(itens, null, acessores)).toEqual(itens);
  });

  it("crescente por texto, em pt-BR", () => {
    const r = ordenar(itens, { coluna: "nome", direcao: "asc" }, acessores);
    expect(r.map((i) => i.nome)).toEqual(["Alfa", "Beta", "Gama"]);
  });

  it("decrescente por texto", () => {
    const r = ordenar(itens, { coluna: "nome", direcao: "desc" }, acessores);
    expect(r.map((i) => i.nome)).toEqual(["Gama", "Beta", "Alfa"]);
  });

  it("numérico, com nulo sempre por último nas duas direções", () => {
    expect(ordenar(itens, { coluna: "valor", direcao: "asc" }, acessores).map((i) => i.nome)).toEqual(["Gama", "Beta", "Alfa"]);
    expect(ordenar(itens, { coluna: "valor", direcao: "desc" }, acessores).map((i) => i.nome)).toEqual(["Beta", "Gama", "Alfa"]);
  });

  it("não muda o array original", () => {
    const copia = [...itens];
    ordenar(itens, { coluna: "nome", direcao: "asc" }, acessores);
    expect(itens).toEqual(copia);
  });

  it("coluna sem acessor devolve como veio", () => {
    expect(ordenar(itens, { coluna: "outra", direcao: "asc" }, acessores)).toEqual(itens);
  });
});

describe("usarOrdenacao", () => {
  it("alterna: nenhuma → crescente → decrescente → nenhuma", () => {
    const { result } = renderHook(() => usarOrdenacao());
    expect(result.current.ordenacao).toBeNull();
    act(() => result.current.alternar("nome"));
    expect(result.current.ordenacao).toEqual({ coluna: "nome", direcao: "asc" });
    act(() => result.current.alternar("nome"));
    expect(result.current.ordenacao).toEqual({ coluna: "nome", direcao: "desc" });
    act(() => result.current.alternar("nome"));
    expect(result.current.ordenacao).toBeNull();
  });

  it("clicar noutra coluna começa de novo em crescente", () => {
    const { result } = renderHook(() => usarOrdenacao());
    act(() => result.current.alternar("nome"));
    act(() => result.current.alternar("nome"));
    act(() => result.current.alternar("valor"));
    expect(result.current.ordenacao).toEqual({ coluna: "valor", direcao: "asc" });
  });
});

describe("ThOrdenavel", () => {
  it("mostra a seta neutra quando não é a coluna ativa, e chama aoAlternar ao clicar", async () => {
    const aoAlternar = () => {};
    render(
      <table>
        <thead>
          <tr>
            <ThOrdenavel coluna="nome" ordenacao={null} aoAlternar={aoAlternar}>Nome</ThOrdenavel>
          </tr>
        </thead>
      </table>,
    );
    const cabecalho = screen.getByRole("columnheader");
    expect(cabecalho).toHaveAttribute("aria-sort", "none");
    expect(screen.getByText("⇅")).toBeInTheDocument();
  });

  it("marca aria-sort e a seta de acordo com a direção ativa", () => {
    render(
      <table>
        <thead>
          <tr>
            <ThOrdenavel coluna="nome" ordenacao={{ coluna: "nome", direcao: "desc" }} aoAlternar={() => {}}>Nome</ThOrdenavel>
          </tr>
        </thead>
      </table>,
    );
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByText("▼")).toBeInTheDocument();
  });

  it("clicar no título chama aoAlternar com a coluna", async () => {
    let chamado: string | null = null;
    render(
      <table>
        <thead>
          <tr>
            <ThOrdenavel coluna="nome" ordenacao={null} aoAlternar={(c) => (chamado = c)}>Nome</ThOrdenavel>
          </tr>
        </thead>
      </table>,
    );
    await userEvent.click(screen.getByRole("button", { name: /Nome/ }));
    expect(chamado).toBe("nome");
  });
});
