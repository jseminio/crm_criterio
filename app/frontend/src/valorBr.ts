/** Valores em reais no padrão brasileiro ("3.287,38") <-> o texto decimal que a API grava
 * ("3287.38"). Usado pelo `CampoDeValor` (02/10/2026): o `<input type="number">` recusava a
 * vírgula e a proposta voltava com "Erro 422". */

/** "3287.38" → "3.287,38"; "2500" → "2.500"; vazio ou inválido → "". */
export function apiParaBr(api: string | null | undefined): string {
  const m = /^(\d+)(?:\.(\d{1,2}))?$/.exec(api ?? "");
  if (!m) return "";
  const inteiro = m[1].replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return m[2] === undefined ? inteiro : `${inteiro},${m[2].padEnd(2, "0")}`;
}

/** "3.287,38" → "3287.38"; "2500" → "2500"; "2.500" → "2500"; vazio → "";
 * "3287.38" (ponto decimal) → "3287.38"; mais de duas casas, duas vírgulas ou letra → null (inválido). */
export function brParaApi(br: string): string | null {
  const t = br.trim().replace(/^R\$\s*/i, "");
  if (t === "") return "";
  // "3287.38": ponto seguido de 1 ou 2 dígitos só pode ser decimal (o jeito do computador, que
  // a tela pedia antes). Com 3 dígitos ("2.500") é milhar, como se escreve no Brasil.
  const decimalComPonto = /^(\d+)\.(\d{1,2})$/.exec(t);
  if (decimalComPonto) return `${decimalComPonto[1].replace(/^0+(?=\d)/, "")}.${decimalComPonto[2]}`;
  const m = /^(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?$/.exec(t);
  if (!m) return null;
  const inteiro = m[1].replace(/\./g, "").replace(/^0+(?=\d)/, "");
  return m[2] === undefined ? inteiro : `${inteiro}.${m[2]}`;
}
