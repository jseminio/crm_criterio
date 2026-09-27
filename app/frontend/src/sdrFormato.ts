/** Formatos do painel do SDR de IA. Separados da tela para o teste usar sem
 * montar componente. */

import type { Taxa } from "./api/tipos";

export function mesAtual(hoje = new Date()): string {
  return `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}`;
}

const MESES = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];

export function nomeDoMes(mes: string): string {
  const [ano, numero] = mes.split("-").map(Number);
  return `${MESES[numero - 1]}/${ano}`;
}

export function mesAnterior(mes: string): string {
  const [ano, numero] = mes.split("-").map(Number);
  return numero === 1 ? `${ano - 1}-12` : `${ano}-${String(numero - 1).padStart(2, "0")}`;
}

export const numero = (n: number, casas = 0) =>
  n.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

/** "65,0%". Sem base, devolve null: quem chama decide a frase. */
export function pct(taxa: Taxa, casas = 1): string | null {
  return taxa.valor === null ? null : `${numero(taxa.valor, casas)}%`;
}

export function tempo(segundos: number | null): string | null {
  if (segundos === null) return null;
  const total = Math.round(segundos);
  if (total < 60) return `${total} s`;
  const minutos = Math.floor(total / 60);
  const resto = total % 60;
  if (minutos < 60) return resto ? `${minutos} min ${resto} s` : `${minutos} min`;
  return `${Math.floor(minutos / 60)} h ${minutos % 60} min`;
}
