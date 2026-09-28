import { describe, expect, it } from "vitest";
import { mesAnterior, mesAtual, nomeDoMes, pct, tempo } from "./sdrFormato";

describe("formatos do painel do SDR", () => {
  it("tempo em segundos, minutos e horas", () => {
    expect(tempo(41)).toBe("41 s");
    expect(tempo(470)).toBe("7 min 50 s");
    expect(tempo(600)).toBe("10 min");
    expect(tempo(3720)).toBe("1 h 2 min");
    expect(tempo(null)).toBeNull();
  });

  it("percentual em pt-BR e nulo sem base", () => {
    expect(pct({ numerador: 172, denominador: 232, valor: (100 * 172) / 232 })).toBe("74,1%");
    expect(pct({ numerador: 0, denominador: 0, valor: null })).toBeNull();
  });

  it("mês", () => {
    expect(nomeDoMes("2026-09")).toBe("setembro/2026");
    expect(mesAnterior("2026-01")).toBe("2025-12");
    expect(mesAnterior("2026-10")).toBe("2026-09");
    expect(mesAtual(new Date(2026, 8, 27))).toBe("2026-09");
  });
});
