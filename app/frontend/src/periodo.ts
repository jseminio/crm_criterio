/** Os atalhos de período do filtro de data, pedidos por Eduardo em
 * 22/09/2026 para comparar um recorte de tempo (ex.: um teste de
 * prospecção) contra o resto da carteira.
 *
 * Resolve cada atalho para um intervalo De/Até concreto, calculado no
 * navegador — a API só recebe datas prontas, nunca o nome do atalho. Isso
 * mantém "o que significa 'último trimestre'" numa função só, testável sem
 * banco.
 */

export type Preset =
  | "mes"
  | "mes_anterior"
  | "trimestre"
  | "trimestre_anterior"
  | "ano"
  | "ano_anterior"
  | "personalizado";

export const PRESETS: { valor: Preset; rotulo: string }[] = [
  { valor: "mes", rotulo: "Este mês" },
  { valor: "mes_anterior", rotulo: "Mês anterior" },
  { valor: "trimestre", rotulo: "Este trimestre" },
  { valor: "trimestre_anterior", rotulo: "Trimestre anterior" },
  { valor: "ano", rotulo: "Este ano" },
  { valor: "ano_anterior", rotulo: "Ano anterior" },
  { valor: "personalizado", rotulo: "Personalizado" },
];

/** "2026-07-01", nunca via `toISOString` — que é UTC e desloca o dia perto
 * da meia-noite local. */
function paraISO(d: Date): string {
  const ano = d.getFullYear();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}

/** Primeiro e último dia do mês. `mes` pode vir fora de 0–11 (ex.: -1, 12) —
 * o `Date` do JavaScript normaliza sozinho, rolando o ano. É assim que "mês
 * anterior" em janeiro cai em dezembro do ano passado sem tratar o caso à
 * parte. */
function primeiroEUltimoDoMes(ano: number, mes: number): [Date, Date] {
  return [new Date(ano, mes, 1), new Date(ano, mes + 1, 0)];
}

/** Mesma normalização do `Date`, aplicada ao trimestre: `mes` fora de 0–11
 * ainda aponta pro trimestre certo do ano certo. */
function primeiroEUltimoDoTrimestre(ano: number, mes: number): [Date, Date] {
  const mesInicio = Math.floor(mes / 3) * 3;
  return [new Date(ano, mesInicio, 1), new Date(ano, mesInicio + 3, 0)];
}

export function resolverPeriodo(
  preset: Preset,
  hoje: Date = new Date(),
): { de: string; ate: string } | null {
  const ano = hoje.getFullYear();
  const mes = hoje.getMonth();

  switch (preset) {
    case "mes": {
      const [de, ate] = primeiroEUltimoDoMes(ano, mes);
      return { de: paraISO(de), ate: paraISO(ate) };
    }
    case "mes_anterior": {
      const [de, ate] = primeiroEUltimoDoMes(ano, mes - 1);
      return { de: paraISO(de), ate: paraISO(ate) };
    }
    case "trimestre": {
      const [de, ate] = primeiroEUltimoDoTrimestre(ano, mes);
      return { de: paraISO(de), ate: paraISO(ate) };
    }
    case "trimestre_anterior": {
      const [de, ate] = primeiroEUltimoDoTrimestre(ano, mes - 3);
      return { de: paraISO(de), ate: paraISO(ate) };
    }
    case "ano":
      return { de: paraISO(new Date(ano, 0, 1)), ate: paraISO(new Date(ano, 11, 31)) };
    case "ano_anterior":
      return { de: paraISO(new Date(ano - 1, 0, 1)), ate: paraISO(new Date(ano - 1, 11, 31)) };
    case "personalizado":
      return null;
  }
}
