/** Formatação em pt-BR. O PAD-002 fixa o formato de dinheiro: R$ 1.248.300,00. */

const DINHEIRO = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
});

export function dinheiro(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const numero = typeof valor === "string" ? Number(valor) : valor;
  return Number.isFinite(numero) ? DINHEIRO.format(numero) : "—";
}

/** Abrevia só em lugar apertado, como o topo da coluna do kanban. */
export function dinheiroCurto(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = typeof valor === "string" ? Number(valor) : valor;
  if (!Number.isFinite(n)) return "—";
  if (Math.abs(n) >= 1_000_000) return `R$ ${(n / 1_000_000).toFixed(1).replace(".", ",")} mi`;
  if (Math.abs(n) >= 1_000) return `R$ ${(n / 1_000).toFixed(0)} mil`;
  return DINHEIRO.format(n);
}

export function data(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

/** Quantos dias faltam, em palavra — o PAD-002 proíbe estado só por cor. */
export function prazo(iso: string | null | undefined): { texto: string; atrasado: boolean } | null {
  if (!iso) return null;
  const alvo = new Date(`${iso.slice(0, 10)}T00:00:00`);
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const dias = Math.round((alvo.getTime() - hoje.getTime()) / 86_400_000);
  if (dias < 0) return { texto: `atrasado ${Math.abs(dias)} d`, atrasado: true };
  if (dias === 0) return { texto: "hoje", atrasado: false };
  if (dias === 1) return { texto: "amanhã", atrasado: false };
  return { texto: `em ${dias} d`, atrasado: false };
}

/** "38.1" (a API devolve ponto decimal) vira "38,1%". */
export function percentual(valor: string | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  return `${valor.replace(".", ",")}%`;
}

/** "61.0" vira "61,0" — sem a unidade, que cada tela decide como encaixar. */
export function dias(valor: string | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  return valor.replace(".", ",");
}

/** Data e hora locais, em pt-BR: "21/09/2026 às 17:35". */
export function dataHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const dia = d.toLocaleDateString("pt-BR");
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  return `${dia} às ${hora}`;
}
