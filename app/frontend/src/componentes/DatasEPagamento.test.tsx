/** Datas e pagamento e parcelas do não recorrente (amostra aprovada por Eduardo em 28/10/2026). */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import type { ParcelaDoServico } from "../api/tipos";
import { DatasEPagamento, partesIguais, problemaNasParcelas, somarMeses } from "./DatasEPagamento";

describe("regras", () => {
  it("soma meses sem passar do último dia do mês", () => {
    expect(somarMeses("2026-12-10", 1)).toBe("2027-01-10");
    expect(somarMeses("2027-01-31", 1)).toBe("2027-02-28");
  });

  it("divide em partes iguais ao centavo; a última leva a sobra", () => {
    const p = partesIguais("1000", 3, "2026-12-10");
    expect(p.map((x) => x.valor)).toEqual(["333.33", "333.33", "333.34"]);
    expect(p.map((x) => x.vencimento)).toEqual(["2026-12-10", "2027-01-10", "2027-02-10"]);
  });

  it("só aceita parcelas que somam o total", () => {
    const p = [{ vencimento: "2026-12-10", valor: "15000" }, { vencimento: "2027-01-10", valor: "7500" }];
    expect(problemaNasParcelas(p, "30000")).toMatch(/faltam R\$\s7\.500,00/);
    expect(problemaNasParcelas([...p, { vencimento: "2027-02-10", valor: "7500" }], "30000")).toBeNull();
    expect(problemaNasParcelas([{ vencimento: "", valor: "30000" }], "30000")).toMatch(/vencimento/);
    expect(problemaNasParcelas([], null)).toBeNull();
  });
});

function Teste({ naoRecorrente = true }: { naoRecorrente?: boolean }) {
  const [parcelas, definir] = useState<ParcelaDoServico[]>([]);
  return (
    <DatasEPagamento prefixo="t" competencia="2026-11-01" inicioPagamento="2026-12-10" naoRecorrente={naoRecorrente}
      total="30000" parcelas={parcelas} aoMudarData={() => undefined} aoMudarParcelas={definir} />
  );
}

describe("na tela", () => {
  it("mostra as duas datas; o recorrente não tem parcelas", () => {
    render(<Teste naoRecorrente={false} />);
    expect(screen.getByLabelText("Data de competência")).toHaveValue("01/11/2026");
    expect(screen.getByLabelText("Início do pagamento")).toHaveValue("10/12/2026");
    expect(screen.queryByLabelText("Número de parcelas")).toBeNull();
  });

  it("o número de parcelas abre as linhas a partir do início do pagamento e confere a soma", async () => {
    render(<Teste />);
    await userEvent.type(screen.getByLabelText("Número de parcelas"), "3");
    expect(screen.getAllByRole("row")).toHaveLength(4);
    expect(document.getElementById("t-venc-2")).toHaveValue("10/02/2027");
    expect(screen.getByRole("alert")).toHaveTextContent("valor maior que zero");
    await userEvent.click(screen.getByRole("button", { name: "Dividir em partes iguais" }));
    expect(screen.getByText(/confere com o valor total/)).toBeInTheDocument();
  });

  it("valores diferentes, digitados à mão, também valem", async () => {
    render(<Teste />);
    await userEvent.type(screen.getByLabelText("Número de parcelas"), "2");
    await userEvent.type(screen.getByLabelText("Valor da 1ª parcela"), "20.000,00");
    await userEvent.type(screen.getByLabelText("Valor da 2ª parcela"), "10.000,00");
    expect(screen.getByText(/confere com o valor total/)).toBeInTheDocument();
  });
});
