/** Preço anual de serviço recorrente: mensal × parcelas. Pedido de Karine
 * em 30/09/2026; o servidor refaz a mesma conta. */

/** Mensal × parcelas em centavos inteiros — evita 0,1 + 0,2 no preço. */
export function precoPelasParcelas(mensal: string, parcelas: string): string {
  const centavos = Math.round(Number(mensal) * 100);
  const vezes = Number(parcelas);
  if (mensal === "" || parcelas === "" || !Number.isFinite(centavos) || !Number.isInteger(vezes) || vezes < 1) {
    return "";
  }
  return ((centavos * vezes) / 100).toFixed(2);
}
