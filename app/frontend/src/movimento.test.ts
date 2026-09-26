/// <reference types="node" />
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

// Lido do disco: com `css: false` no vitest.config, o import `?raw` volta
// vazio, e no jsdom `import.meta.url` não é `file:`. O Vitest roda a partir
// de app/frontend.
const css = readFileSync(resolve(process.cwd(), "src/app.css"), "utf-8");

// O jsdom não avalia `@media`, então o que dá para garantir aqui é que a regra
// global de movimento reduzido existe, cobre transição e animação, e é a
// última do arquivo — nada declarado depois dela pode escapar.
const REGRA = "@media (prefers-reduced-motion: reduce)";

describe("movimento reduzido", () => {
  it("app.css tem a regra global e ela é a última do arquivo", () => {
    const inicio = css.lastIndexOf(REGRA);
    expect(inicio).toBeGreaterThan(-1);
    const bloco = css.slice(inicio);
    expect(bloco).toMatch(/\*,\s*\*::before,\s*\*::after/);
    expect(bloco).toContain("animation-duration: 0.01ms !important");
    expect(bloco).toContain("transition-duration: 0.01ms !important");
    // Depois do bloco, só pode sobrar o fechamento dele.
    expect(bloco.replace(/\s/g, "").endsWith("}}")).toBe(true);
    expect(bloco.match(/\{/g)?.length).toBe(2);
  });
});
