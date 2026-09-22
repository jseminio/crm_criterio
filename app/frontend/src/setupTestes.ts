/** Carregado antes de cada arquivo de teste — matchers do jest-dom
 * (toBeInTheDocument, toBeDisabled) e a limpeza automática do DOM entre
 * testes, para um teste não ver o que o anterior deixou montado. */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
