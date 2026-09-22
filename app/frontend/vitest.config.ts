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
    // NÃO usar `isolate: false`. Pareceu seguro em 21/09/2026 (rodou limpo
    // várias vezes) e virou instabilidade real em 22/09/2026, assim que um
    // quarto arquivo passou a mockar `../api/cliente` com um formato
    // diferente dos outros três: `isolate: false` reaproveita o registro de
    // módulos entre arquivos do mesmo processo, e o `vi.mock` de um arquivo
    // às vezes vazava para o teste seguinte — em ~1 de cada 3 rodadas, sem
    // padrão fixo. Teste instável é pior que teste lento: ensina a ignorar
    // falha. `maxWorkers: 1` sozinho já resolve o problema de inicialização
    // sob carga; isolamento entre arquivos continua ligado (o padrão).
  },
});
