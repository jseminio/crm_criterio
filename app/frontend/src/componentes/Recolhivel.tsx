/** Seção que começa recolhida e só monta o conteúdo (e só busca os dados) depois de aberta. */

import { useState, type ReactNode } from "react";

export function Recolhivel({ titulo, resumo, children }: { titulo: string; resumo?: string; children: ReactNode }) {
  const [aberto, definirAberto] = useState(false);
  return (
    <details className="recolhivel" onToggle={(e) => definirAberto((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>
        <strong>{titulo}</strong>
        {resumo && <span className="recolhivel-resumo"> · {resumo}</span>}
      </summary>
      {aberto && <div className="recolhivel-corpo">{children}</div>}
    </details>
  );
}
