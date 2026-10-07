/** Consultas de tela para o que o CSS sozinho não resolve — mostrar uma etapa do kanban por vez,
 * trocar o arrasto por um botão.
 *
 * - `usarTelaEstreita`: celular (até 768px, a mesma largura do bloco "celular" do app.css).
 * - `usarToque`: tela de toque, de qualquer largura (o tablet também não arrasta cartão direito).
 *
 * Sem `matchMedia` (o jsdom dos testes) a resposta é "não": a tela de computador continua sendo a
 * padrão, e o teste de celular simula a consulta de propósito.
 */

import { useSyncExternalStore } from "react";

export const CONSULTA_DE_TELA_ESTREITA = "(max-width: 768px)";
export const CONSULTA_DE_TOQUE = "(pointer: coarse)";

function lista(consulta: string): MediaQueryList | null {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(consulta)
    : null;
}

/** Assinatura e leitura de uma consulta, criadas uma vez por consulta (estáveis entre renderizações). */
function fonte(consulta: string) {
  return {
    assinar: (aoMudar: () => void) => {
      const l = lista(consulta);
      if (!l) return () => {};
      l.addEventListener("change", aoMudar);
      return () => l.removeEventListener("change", aoMudar);
    },
    ler: () => lista(consulta)?.matches ?? false,
  };
}

const ESTREITA = fonte(CONSULTA_DE_TELA_ESTREITA);
const TOQUE = fonte(CONSULTA_DE_TOQUE);
const NO_SERVIDOR = () => false;

export function usarTelaEstreita(): boolean {
  return useSyncExternalStore(ESTREITA.assinar, ESTREITA.ler, NO_SERVIDOR);
}

export function usarToque(): boolean {
  return useSyncExternalStore(TOQUE.assinar, TOQUE.ler, NO_SERVIDOR);
}
