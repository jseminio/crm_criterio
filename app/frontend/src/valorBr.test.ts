import { describe, expect, it } from "vitest";
import { apiParaBr, brParaApi } from "./valorBr";

describe("valores no padrão brasileiro", () => {
  it("da API para a tela", () => {
    expect(apiParaBr("3287.38")).toBe("3.287,38");
    expect(apiParaBr("2500")).toBe("2.500");
    expect(apiParaBr("2500.5")).toBe("2.500,50");
    expect(apiParaBr("7000.00")).toBe("7.000,00");
    expect(apiParaBr("1234567.89")).toBe("1.234.567,89");
    expect(apiParaBr(null)).toBe("");
    expect(apiParaBr("abc")).toBe("");
  });

  it("da tela para a API", () => {
    expect(brParaApi("3.287,38")).toBe("3287.38");
    expect(brParaApi("3287,38")).toBe("3287.38");
    expect(brParaApi("3287")).toBe("3287");
    expect(brParaApi("2.500")).toBe("2500");
    expect(brParaApi("R$ 1.000,5")).toBe("1000.5");
    expect(brParaApi("")).toBe("");
    expect(brParaApi("3287.38")).toBe("3287.38"); // ponto decimal, como a tela pedia antes
    expect(brParaApi("32.8")).toBe("32.8");
  });

  it("o que não dá para ler é recusado, não adivinhado", () => {
    expect(brParaApi("3,2,1")).toBeNull();
    expect(brParaApi("3287,385")).toBeNull();
    expect(brParaApi("abc")).toBeNull();
    expect(brParaApi("1.2.3")).toBeNull();
    expect(brParaApi("2.500,385")).toBeNull();
  });
});
