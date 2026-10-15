import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { TabelaDeComposicao } from "./TabelaDeComposicao";
import { dinheiro, data } from "../formato";

type L = { nome: string; mrr: number | null; quando: string | null };
const LINHAS: L[] = [
  { nome: "Beta", mrr: 1200, quando: "2026-05-01" },
  { nome: "Alfa", mrr: null, quando: "2026-10-08" },
  { nome: "Gama", mrr: 12000, quando: null },
];

function Tabela() {
  return (
    <TabelaDeComposicao rotulo="Teste" linhas={LINHAS} chave={(l) => l.nome}
      colunas={[
        { titulo: "Cliente", valor: (l) => l.nome },
        { titulo: "Data", valor: (l) => l.quando, mostrar: (l) => data(l.quando) },
        { titulo: "MRR", valor: (l) => l.mrr, mostrar: (l) => (l.mrr === null ? "—" : dinheiro(l.mrr)), numerico: true },
      ]}
      rodape={<tr className="composicao-total"><td>Total</td><td /><td>{dinheiro(13200)}</td></tr>} />
  );
}

const nomes = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);

describe("Tabela de composição com ordenação pelo título (15/10/2026)", () => {
  it("ordena número e data, vazio sempre por último e o total fixo no fim", async () => {
    render(<Tabela />);
    expect(nomes()).toEqual(["Beta", "Alfa", "Gama", "Total"]);  // a ordem original, a que veio
    const mrr = screen.getByRole("button", { name: /MRR/ });
    await userEvent.click(mrr);
    expect(nomes()).toEqual(["Beta", "Gama", "Alfa", "Total"]);  // 1.200 < 12.000; sem MRR por último
    await userEvent.click(mrr);
    expect(nomes()).toEqual(["Gama", "Beta", "Alfa", "Total"]);
    expect(screen.getByRole("columnheader", { name: /MRR/ })).toHaveAttribute("aria-sort", "descending");
    await userEvent.click(mrr);
    expect(nomes()).toEqual(["Beta", "Alfa", "Gama", "Total"]);  // terceiro clique: volta
    await userEvent.click(screen.getByRole("button", { name: /Data/ }));
    expect(nomes()).toEqual(["Beta", "Alfa", "Gama", "Total"]);  // 01/05 < 08/10; sem data por último
    await userEvent.click(screen.getByRole("button", { name: /Cliente/ }));
    expect(nomes()).toEqual(["Alfa", "Beta", "Gama", "Total"]);
  });
});
