/** Formatação em pt-BR — o que a tela mostra tem de bater com o PAD-002:
 * "números em R$ 1.248.300,00" e "estado nunca só por cor". */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { data, dataHora, dinheiro, dinheiroCurto, prazo } from "./formato";

describe("dinheiro", () => {
  // Intl.NumberFormat("pt-BR") insere um espaço fino sem quebra (\u00a0)
  // entre "R$" e o número — visualmente idêntico a um espaço comum, mas
  // um caractere diferente. Os literais abaixo usam o caractere real.

  it("formata no padrão do PAD-002: R$ 1.248.300,00", () => {
    expect(dinheiro(1248300)).toBe("R$ 1.248.300,00");
  });

  it("aceita valor vindo como texto, como a API devolve Decimal", () => {
    expect(dinheiro("5000.00")).toBe("R$ 5.000,00");
  });

  it("mostra travessão para ausência, não R$ 0,00", () => {
    // Diferença real: proposta de valor único não tem preço mensal, e
    // R$ 0,00 diria "grátis" em vez de "não se aplica".
    expect(dinheiro(null)).toBe("—");
    expect(dinheiro(undefined)).toBe("—");
    expect(dinheiro("")).toBe("—");
  });

  it("mostra travessão para valor que não é número", () => {
    expect(dinheiro("não é número")).toBe("—");
  });

  it("mantém duas casas mesmo em valor redondo", () => {
    expect(dinheiro(3000)).toBe("R$ 3.000,00");
  });
});

describe("dinheiroCurto", () => {
  it("abrevia milhão com uma casa decimal", () => {
    expect(dinheiroCurto(2_600_000)).toBe("R$ 2,6 mi");
  });

  it("abrevia mil sem casa decimal", () => {
    expect(dinheiroCurto(461_000)).toBe("R$ 461 mil");
  });

  it("não abrevia abaixo de mil", () => {
    expect(dinheiroCurto(850)).toBe("R$ 850,00");
  });

  it("mostra travessão para ausência", () => {
    expect(dinheiroCurto(null)).toBe("—");
  });
});

describe("data", () => {
  it("converte ISO para dd/mm/aaaa", () => {
    expect(data("2026-09-25")).toBe("25/09/2026");
  });

  it("ignora hora quando a API manda datetime", () => {
    expect(data("2026-09-25T14:30:00")).toBe("25/09/2026");
  });

  it("mostra travessão sem data", () => {
    expect(data(null)).toBe("—");
    expect(data(undefined)).toBe("—");
  });
});

describe("prazo", () => {
  // A data "hoje" muda o resultado — sem fixar o relógio, o teste passaria
  // ou falharia dependendo do dia em que rodasse.
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-22T10:00:00"));
  });
  afterEach(() => vi.useRealTimers());

  it("volta null sem data — o cartão não mostra prazo nenhum", () => {
    expect(prazo(null)).toBeNull();
  });

  it("marca atrasado com a contagem em dias", () => {
    const resultado = prazo("2026-09-19");
    expect(resultado).toEqual({ texto: "atrasado 3 d", atrasado: true });
  });

  it("diz 'hoje' no prazo do próprio dia", () => {
    expect(prazo("2026-09-22")).toEqual({ texto: "hoje", atrasado: false });
  });

  it("diz 'amanhã', não 'em 1 d'", () => {
    expect(prazo("2026-09-23")).toEqual({ texto: "amanhã", atrasado: false });
  });

  it("conta os dias à frente sem marcar como atrasado", () => {
    expect(prazo("2026-09-29")).toEqual({ texto: "em 7 d", atrasado: false });
  });
});

describe("dataHora", () => {
  it("junta data e hora com 'às'", () => {
    // A hora exata depende do fuso da máquina que roda o teste; verificamos
    // a forma, não o valor cravado.
    expect(dataHora("2026-09-21T17:35:00Z")).toMatch(/^\d{2}\/\d{2}\/\d{4} às \d{2}:\d{2}$/);
  });

  it("mostra travessão sem data", () => {
    expect(dataHora(null)).toBe("—");
  });

  it("mostra travessão para data inválida em vez de 'Invalid Date'", () => {
    expect(dataHora("isto não é uma data")).toBe("—");
  });
});
