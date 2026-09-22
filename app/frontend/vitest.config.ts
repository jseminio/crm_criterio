/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTestes.ts"],
    css: false,
    // Um processo só, sem paralelismo. Numa máquina sob carga (é o caso desta:
    // dois núcleos, vários apps abertos), abrir vários workers ao mesmo tempo
    // faz o próprio Vitest estourar o tempo de inicialização e falhar antes de
    // rodar um teste sequer — não é defeito do teste, é concorrência demais
    // para a máquina.
    pool: "forks",
    maxWorkers: 1,
    minWorkers: 1,
    testTimeout: 15000,
    // Reaproveita o processo entre arquivos em vez de abrir um por arquivo —
    // metade do tempo numa máquina sob carga. Seguro aqui porque cada teste já
    // limpa o que monta (afterEach com cleanup) e zera os mocks da API
    // (beforeEach com vi.clearAllMocks); testado que não vaza estado.
    isolate: false,
  },
});
