/** Datas no padrão brasileiro (dd/mm/aaaa) <-> ISO (aaaa-mm-dd), que é o que a API grava.
 * Usado pelo `CampoDeData` (01/10/2026). */

/** "2026-08-01" → "01/08/2026"; vazio ou inválido → "". */
export function isoParaBr(iso: string | null | undefined): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso ?? "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "";
}

/** "01/08/2026" → "2026-08-01"; data incompleta ou que não existe → null. */
export function brParaIso(br: string): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(br);
  if (!m) return null;
  const [d, mes, a] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const dt = new Date(a, mes - 1, d);
  if (dt.getFullYear() !== a || dt.getMonth() !== mes - 1 || dt.getDate() !== d) return null;
  return `${m[3]}-${m[2]}-${m[1]}`;
}

/** Só os dígitos, com as barras no lugar: "0108" → "01/08", "01082026" → "01/08/2026". */
export function mascarar(texto: string): string {
  const d = texto.replace(/\D/g, "").slice(0, 8);
  if (d.length <= 2) return d;
  if (d.length <= 4) return `${d.slice(0, 2)}/${d.slice(2)}`;
  return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`;
}
