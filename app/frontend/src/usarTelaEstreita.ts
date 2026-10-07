/** Celular ou tablet pequeno (até 768px, a mesma largura do bloco "celular" do app.css).
 *
 * Para o que o CSS sozinho não resolve — trocar o arrasto do kanban por um botão, mostrar uma
 * etapa por vez. Sem `matchMedia` (o jsdom dos testes) a resposta é "não": a tela de computador
 * continua sendo a padrão, e o teste de celular simula a largura de propósito.
 */

import { useSyncExternalStore } from "react";

export const CONSULTA_DE_TELA_ESTREITA = "(max-width: 768px)";

function lista(): MediaQueryList | null {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(CONSULTA_DE_TELA_ESTREITA)
    : null;
}

function assinar(aoMudar: () => void): () => void {
  const consulta = lista();
  if (!consulta) return () => {};
  consulta.addEventListener("change", aoMudar);
  return () => consulta.removeEventListener("change", aoMudar);
}

export function usarTelaEstreita(): boolean {
  return useSyncExternalStore(assinar, () => lista()?.matches ?? false, () => false);
}
