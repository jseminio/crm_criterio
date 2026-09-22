/** Os quatro estados que o PAD-002 exige de toda lista: carregando, vazio sem
 * dados, vazio por filtro, erro com "tentar de novo". */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "./estados";

describe("Carregando", () => {
  it("anuncia o carregamento para leitor de tela", () => {
    render(<Carregando rotulo="Carregando o funil" />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando o funil…");
  });

  it("usa um rótulo padrão quando nenhum é passado", () => {
    render(<Carregando />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando…");
  });
});

describe("VazioSemDados", () => {
  it("explica que não há dado nenhum, distinto de filtro sem resultado", () => {
    render(
      <VazioSemDados titulo="Nenhuma oportunidade" explicacao="A base está vazia." />,
    );
    expect(screen.getByText("Nenhuma oportunidade")).toBeInTheDocument();
    expect(screen.getByText("A base está vazia.")).toBeInTheDocument();
  });

  it("mostra a ação quando fornecida, e nada quando não é", () => {
    const { rerender } = render(
      <VazioSemDados
        titulo="t"
        explicacao="e"
        acao={<button type="button">Cadastrar o primeiro</button>}
      />,
    );
    expect(screen.getByRole("button", { name: "Cadastrar o primeiro" })).toBeInTheDocument();

    rerender(<VazioSemDados titulo="t" explicacao="e" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("VazioPorFiltro", () => {
  it("é uma mensagem diferente de VazioSemDados — diz que o dado existe", () => {
    render(<VazioPorFiltro aoLimpar={() => {}} />);
    expect(screen.getByText(/existem registros na base/i)).toBeInTheDocument();
  });

  it("o botão de limpar filtros chama o callback", async () => {
    const aoLimpar = vi.fn();
    render(<VazioPorFiltro aoLimpar={aoLimpar} />);

    await userEvent.click(screen.getByRole("button", { name: "Limpar filtros" }));

    expect(aoLimpar).toHaveBeenCalledOnce();
  });
});

describe("Erro", () => {
  it("anuncia o erro como alerta para leitor de tela", () => {
    render(<Erro mensagem="Falha ao conectar." aoTentarDeNovo={() => {}} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Falha ao conectar.");
  });

  it("mostra a mensagem real do erro, não um texto genérico", () => {
    // A distinção entre "servidor fora do ar" e "servidor recusou" (ErroDaApi)
    // só ajuda quem usa se a mensagem chegar até a tela.
    render(
      <Erro
        mensagem="Não consegui falar com o servidor. Ele está no ar?"
        aoTentarDeNovo={() => {}}
      />,
    );
    expect(
      screen.getByText("Não consegui falar com o servidor. Ele está no ar?"),
    ).toBeInTheDocument();
  });

  it("o botão de tentar de novo chama o callback", async () => {
    const aoTentarDeNovo = vi.fn();
    render(<Erro mensagem="erro" aoTentarDeNovo={aoTentarDeNovo} />);

    await userEvent.click(screen.getByRole("button", { name: "Tentar de novo" }));

    expect(aoTentarDeNovo).toHaveBeenCalledOnce();
  });
});
