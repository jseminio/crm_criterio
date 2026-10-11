/** O que foi digitado na aba Proposta e ainda não virou PowerPoint fica guardado neste navegador, por
 * oportunidade: trocar de aba, salvar a oportunidade (que fecha o painel) ou recarregar a página não perde
 * nada. Some ao gerar. Navegador sem armazenamento (janela anônima) só não guarda: a tela funciona igual.
 *
 * A aba Granola (11/10/2026) também escreve aqui: aplicar a contextualização da reunião troca a do
 * rascunho guardado, para a aba Proposta abrir já com ela. */

import type { EntradaDaProposta } from "./api/tipos";

export type Guardado = { entrada: EntradaDaProposta; salvo_em: string };
const chaveDoRascunho = (id: number) => `crm.proposta.rascunho.${id}`;

export function lerRascunho(id: number): Guardado | null {
  try {
    const bruto = localStorage.getItem(chaveDoRascunho(id));
    return bruto ? (JSON.parse(bruto) as Guardado) : null;
  } catch {
    return null;
  }
}

export function guardarRascunho(id: number, entrada: EntradaDaProposta) {
  try {
    localStorage.setItem(chaveDoRascunho(id), JSON.stringify({ entrada, salvo_em: new Date().toISOString() }));
  } catch {
    /* sem armazenamento: segue sem guardar */
  }
}

export function apagarRascunho(id: number) {
  try {
    localStorage.removeItem(chaveDoRascunho(id));
  } catch {
    /* idem */
  }
}

/** Troca só a contextualização do rascunho guardado, se houver um; sem rascunho, a API já devolve a da
 * reunião. */
export function trocarContextualizacaoGuardada(id: number, contextualizacao: string) {
  const guardado = lerRascunho(id);
  if (guardado) guardarRascunho(id, { ...guardado.entrada, contextualizacao });
}
