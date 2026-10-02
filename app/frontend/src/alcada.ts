/** A alçada dos eventos de contrato, para a tela avisar antes de registrar (02/10/2026). A regra que
 * vale é a da API (`crm.domain.alcada`): esta cópia só antecipa o aviso. */

import type { ContratoDetalhe, EventoDeContrato } from "./api/tipos";

export const LIMITE_DE_REDUCAO = 0.1;
const TIPOS_COM_ALCADA: EventoDeContrato["tipo"][] = ["Contração", "Reajuste", "Aditivo"];

const percentual = (fracao: number) =>
  `${(Math.round(fracao * 1000) / 10).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`;

/** Por que o evento vai pedir aprovação, ou `null` se entra direto. */
export function motivoDaAlcada(
  contrato: Pick<ContratoDetalhe, "escopo" | "preco_mensal" | "preco_anual">,
  tipo: EventoDeContrato["tipo"],
  campos: Record<string, string>,
): string | null {
  if (!TIPOS_COM_ALCADA.includes(tipo)) return null;
  const motivos: string[] = [];
  const escopo = (campos.escopo_novo ?? "").trim();
  if (tipo === "Aditivo" && escopo && escopo !== contrato.escopo) motivos.push("aditivo que muda o escopo");
  for (const [campo, atualTexto, rotulo] of [
    ["preco_mensal_novo", contrato.preco_mensal, "preço mensal"],
    ["preco_anual_novo", contrato.preco_anual, "preço anual"],
  ] as const) {
    const novo = Number(campos[campo]);
    const atual = Number(atualTexto);
    if (!campos[campo] || !Number.isFinite(novo) || !atualTexto || !(atual > 0) || novo >= atual) continue;
    const queda = (atual - novo) / atual;
    if (queda > LIMITE_DE_REDUCAO) motivos.push(`redução de ${percentual(queda)} no ${rotulo}`);
  }
  return motivos.length ? motivos.join("; ") : null;
}
