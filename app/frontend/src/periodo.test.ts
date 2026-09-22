import { describe, expect, it } from "vitest";
import { resolverPeriodo } from "./periodo";

describe("resolverPeriodo", () => {
  const meioDoAno = new Date(2026, 6, 15); // 15/07/2026, dentro do Q3

  it("este mês", () => {
    expect(resolverPeriodo("mes", meioDoAno)).toEqual({ de: "2026-07-01", ate: "2026-07-31" });
  });

  it("mês anterior", () => {
    expect(resolverPeriodo("mes_anterior", meioDoAno)).toEqual({
      de: "2026-06-01",
      ate: "2026-06-30",
    });
  });

  it("mês anterior em janeiro cai em dezembro do ano passado", () => {
    const janeiro = new Date(2026, 0, 10);
    expect(resolverPeriodo("mes_anterior", janeiro)).toEqual({
      de: "2025-12-01",
      ate: "2025-12-31",
    });
  });

  it("este trimestre", () => {
    expect(resolverPeriodo("trimestre", meioDoAno)).toEqual({
      de: "2026-07-01",
      ate: "2026-09-30",
    });
  });

  it("trimestre anterior", () => {
    expect(resolverPeriodo("trimestre_anterior", meioDoAno)).toEqual({
      de: "2026-04-01",
      ate: "2026-06-30",
    });
  });

  it("trimestre anterior no Q1 cai no Q4 do ano passado", () => {
    const fevereiro = new Date(2026, 1, 5);
    expect(resolverPeriodo("trimestre_anterior", fevereiro)).toEqual({
      de: "2025-10-01",
      ate: "2025-12-31",
    });
  });

  it("este ano", () => {
    expect(resolverPeriodo("ano", meioDoAno)).toEqual({ de: "2026-01-01", ate: "2026-12-31" });
  });

  it("ano anterior", () => {
    expect(resolverPeriodo("ano_anterior", meioDoAno)).toEqual({
      de: "2025-01-01",
      ate: "2025-12-31",
    });
  });

  it("personalizado devolve nulo — quem resolve o intervalo é a pessoa", () => {
    expect(resolverPeriodo("personalizado", meioDoAno)).toBeNull();
  });
});
