import { describe, expect, it } from "vitest";
import { motivoDaAlcada } from "./alcada";

const c = { escopo: "BPO Contábil", preco_mensal: "4800.00", preco_anual: null };

describe("alçada antecipada na tela (a regra que vale é a da API)", () => {
  it("contração até 10% entra direto; acima pede aprovação, com o percentual", () => {
    expect(motivoDaAlcada(c, "Contração", { preco_mensal_novo: "4320" })).toBeNull();
    expect(motivoDaAlcada(c, "Contração", { preco_mensal_novo: "3900" })).toBe("redução de 18,8% no preço mensal");
  });

  it("reajuste para cima e expansão entram direto", () => {
    expect(motivoDaAlcada(c, "Reajuste", { preco_mensal_novo: "6000" })).toBeNull();
    expect(motivoDaAlcada(c, "Expansão", { preco_mensal_novo: "100" })).toBeNull();
  });

  it("aditivo que muda o escopo pede aprovação; o mesmo escopo, não", () => {
    expect(motivoDaAlcada(c, "Aditivo", { escopo_novo: "BPO Full" })).toBe("aditivo que muda o escopo");
    expect(motivoDaAlcada(c, "Aditivo", { escopo_novo: "BPO Contábil" })).toBeNull();
  });
});
