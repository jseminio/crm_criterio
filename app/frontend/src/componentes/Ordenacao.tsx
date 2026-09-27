/** Ordenação de tabela por clique no título da coluna — crescente, decrescente, depois volta ao padrão.
 *
 * Cada tela decide, por coluna, o valor que compara (`acessor`): número para dinheiro e contagens,
 * texto para nome e situação, data ISO (que já ordena como texto). `null`/`undefined` sempre vai para
 * o fim, nas duas direções — não parece um valor "menor" nem "maior", só "sem essa informação".
 */

import { useState, type ReactNode } from "react";

export type Direcao = "asc" | "desc";

export interface Ordenacao {
  coluna: string;
  direcao: Direcao;
}

export type Acessor<T> = (item: T) => string | number | null | undefined;

export function usarOrdenacao(padrao: Ordenacao | null = null) {
  const [ordenacao, definirOrdenacao] = useState(padrao);

  function alternar(coluna: string) {
    definirOrdenacao((atual) => {
      if (!atual || atual.coluna !== coluna) return { coluna, direcao: "asc" as Direcao };
      if (atual.direcao === "asc") return { coluna, direcao: "desc" as Direcao };
      return null; // terceiro clique: volta à ordem original (a que a API mandou)
    });
  }

  return { ordenacao, alternar };
}

export function ordenar<T>(itens: T[], ordenacao: Ordenacao | null, acessores: Record<string, Acessor<T>>): T[] {
  if (!ordenacao) return itens;
  const acessor = acessores[ordenacao.coluna];
  if (!acessor) return itens;
  const sinal = ordenacao.direcao === "asc" ? 1 : -1;
  return [...itens].sort((a, b) => {
    const va = acessor(a);
    const vb = acessor(b);
    const vazioA = va === null || va === undefined || va === "";
    const vazioB = vb === null || vb === undefined || vb === "";
    if (vazioA && vazioB) return 0;
    if (vazioA) return 1; // sem valor sempre por último, nas duas direções
    if (vazioB) return -1;
    if (typeof va === "number" && typeof vb === "number") return (va - vb) * sinal;
    return String(va).localeCompare(String(vb), "pt-BR", { numeric: true }) * sinal;
  });
}

export function ThOrdenavel({
  coluna,
  ordenacao,
  aoAlternar,
  numerico,
  children,
}: {
  coluna: string;
  ordenacao: Ordenacao | null;
  aoAlternar: (coluna: string) => void;
  numerico?: boolean;
  children: ReactNode;
}) {
  const ativa = ordenacao?.coluna === coluna;
  const seta = ativa ? (ordenacao!.direcao === "asc" ? "▲" : "▼") : "⇅";
  return (
    <th scope="col" className={numerico ? "tabela-numero" : undefined} aria-sort={ativa ? (ordenacao!.direcao === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" className={`th-ordenar${ativa ? " th-ordenar-ativa" : ""}`} onClick={() => aoAlternar(coluna)}>
        {children}
        <span className="th-seta" aria-hidden="true">{seta}</span>
      </button>
    </th>
  );
}
