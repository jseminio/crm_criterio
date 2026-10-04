/** Prévia do bruto da proposta: líquido ÷ (1 − alíquota), ao múltiplo de R$ 50 mais próximo
 * (aprovado por Eduardo em 01/10/2026). O valor que vale é o que a API grava ao gerar; a regra é a
 * mesma de `crm.proposta.conta.bruto_de`. */
export function brutoPrevio(liquido: number, imposto: number): number {
  return Math.round(liquido / (1 - imposto) / 50) * 50;
}

/** Horas de consulta por ano (Eduardo, 03/10/2026): 50% do 13º honorário (Contábil + DP, líquidos)
 * ÷ R$ 350 por hora, ao inteiro mais próximo; Contábil fica com 70% e DP com o resto. Sem DP, tudo é
 * Contábil. A mesma regra de `crm.proposta.conta.horas_de_consulta`, que vale ao gerar. */
export function horasDeConsulta(
  contabil: number,
  dp: number,
  valorDaHora = 350,
): { total: number; contabil: number; dp: number | null; base: number } {
  const temDp = dp > 0;
  const base = (contabil + (temDp ? dp : 0)) / 2;
  const total = Math.round(base / valorDaHora);
  if (!temDp) return { total, contabil: total, dp: null, base };
  const horasContabil = Math.round((total * 7) / 10);
  return { total, contabil: horasContabil, dp: total - horasContabil, base };
}
