/** Etiqueta é onde vive a regra 4 do PAD-002: "estado nunca só por cor". */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Etiqueta } from "./Etiqueta";

describe("Etiqueta", () => {
  it("não renderiza nada sem texto — não vira uma bolinha de cor sem rótulo", () => {
    const { container } = render(<Etiqueta texto={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("mostra sempre a palavra, nunca só a cor", () => {
    render(<Etiqueta texto="Aceita" />);
    expect(screen.getByText("Aceita")).toBeInTheDocument();
  });

  it("dá o tom de ganho a Aceita", () => {
    render(<Etiqueta texto="Aceita" />);
    expect(screen.getByText("Aceita")).toHaveClass("etiqueta-ganho");
  });

  it("dá o tom de perda a Recusada e a Perdido", () => {
    render(<Etiqueta texto="Recusada" />);
    expect(screen.getByText("Recusada")).toHaveClass("etiqueta-perda");

    render(<Etiqueta texto="Perdido" />);
    expect(screen.getByText("Perdido")).toHaveClass("etiqueta-perda");
  });

  it("um valor de situação desconhecido cai no tom neutro, não quebra", () => {
    // Se o backend criar uma situação nova, a tela não pode travar — deve
    // aparecer sem cor de significado até alguém mapear o tom.
    render(<Etiqueta texto="Uma Situação Inédita" />);
    expect(screen.getByText("Uma Situação Inédita")).toHaveClass("etiqueta-neutra");
  });

  it("temperatura usa a tabela de temperatura, não a de situação", () => {
    // "Quente" não existe na tabela de situação — se o componente
    // confundisse as tabelas, cairia em neutro em vez de perda.
    render(<Etiqueta texto="Quente" tipo="temperatura" />);
    expect(screen.getByText("Quente")).toHaveClass("etiqueta-perda");
  });

  it("frio é o oposto visual de quente", () => {
    render(<Etiqueta texto="Frio" tipo="temperatura" />);
    expect(screen.getByText("Frio")).toHaveClass("etiqueta-andamento");
  });

  it("tipo neutro ignora qualquer mapeamento de cor", () => {
    // Usado para captador e canal: não é bom nem ruim, só informativo.
    render(<Etiqueta texto="Aceita" tipo="neutra" />);
    expect(screen.getByText("Aceita")).toHaveClass("etiqueta-neutra");
  });
});
