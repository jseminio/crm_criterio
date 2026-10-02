/** Quem está preenchendo a ficha ou mexendo nas pendências (E4, 02/10/2026). Sem login (E1), a
 * pessoa escolhe o nome uma vez e o navegador lembra. Sem armazenamento, vale o primeiro da lista. */

import { useState } from "react";

const CHAVE = "crm.quem_preenche";

function lido(): string | null {
  try {
    return localStorage.getItem(CHAVE);
  } catch {
    return null;
  }
}

export function usarQuemPreenche(revisores: string[]): [string, (nome: string) => void] {
  const [escolhido, definirEscolhido] = useState<string | null>(lido);
  const atual = escolhido && revisores.includes(escolhido) ? escolhido : (revisores[0] ?? "");
  const escolher = (nome: string) => {
    definirEscolhido(nome);
    try {
      localStorage.setItem(CHAVE, nome);
    } catch {
      /* sem armazenamento: vale só nesta tela */
    }
  };
  return [atual, escolher];
}
