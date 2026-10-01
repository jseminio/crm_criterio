/** Prévia do bruto da proposta: líquido ÷ (1 − alíquota), ao múltiplo de R$ 50 mais próximo
 * (aprovado por Eduardo em 01/10/2026). O valor que vale é o que a API grava ao gerar; a regra é a
 * mesma de `crm.proposta.conta.bruto_de`. */
export function brutoPrevio(liquido: number, imposto: number): number {
  return Math.round(liquido / (1 - imposto) / 50) * 50;
}
