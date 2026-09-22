/** Carregado antes de cada arquivo de teste — matchers do jest-dom
 * (toBeInTheDocument, toBeDisabled) e a limpeza automática do DOM entre
 * testes, para um teste não ver o que o anterior deixou montado. */

import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());

// O padrão do Testing Library é 1 s para um `waitFor` desistir. Numa máquina
// sob carga alta — aconteceu aqui, load average acima de 300 num Mac de dois
// núcleos — 1 s some antes do React terminar de assentar uma atualização, e o
// teste falha por lentidão da máquina, não por defeito do componente. 5 s dá
// folga sem esconder um `waitFor` que de fato nunca resolveria.
configure({ asyncUtilTimeout: 5000 });
