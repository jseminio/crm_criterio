import { describe, expect, it } from "vitest";
import { detalheDaVersao, rotuloDaVersao } from "./versao";

const NO_AR = { commit: "a90b952", data_do_build: "2026-10-17" };

describe("Versão na barra lateral", () => {
  it("build com commit: data com pontos e o commit", () => {
    expect(rotuloDaVersao("2026-10-18", NO_AR)).toBe("v2026.10.18 · a90b952");
  });

  it("sem commit (ou sem resposta da API), só a data — nada inventado", () => {
    expect(rotuloDaVersao("2026-10-18", { commit: null, data_do_build: null })).toBe("v2026.10.18");
    expect(rotuloDaVersao("2026-10-18", null)).toBe("v2026.10.18");
  });

  it("no desenvolvimento, dev", () => {
    expect(rotuloDaVersao(null, NO_AR)).toBe("dev · a90b952");
    expect(rotuloDaVersao(null, null)).toBe("dev");
  });

  it("o detalhe diz de quando é cada parte", () => {
    expect(detalheDaVersao("2026-10-18", NO_AR)).toBe("Tela: build de 18/10/2026 · API: build de 17/10/2026 · commit a90b952");
    expect(detalheDaVersao(null, null)).toBe("Tela: desenvolvimento · API: sem resposta · commit desconhecido");
  });
});
