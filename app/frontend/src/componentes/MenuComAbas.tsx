/** Um item do menu principal com abas (02/10/2026): Funil, Sucesso do Cliente e SDR. Cada aba só
 * aparece para quem tem a permissão dela; abre na aba pedida (atalho de outra tela), senão na última
 * escolhida neste navegador, senão na primeira visível. A aba ativa fica sublinhada e em negrito. */

import { useState, type ReactNode } from "react";
import { usarAcesso } from "../entrada";

export interface AbaDoMenu<C extends string> {
  chave: C;
  rotulo: string;
  /** Basta uma. */
  permissoes: string[];
  /** Uma linha que explica a aba, logo abaixo das abas. */
  explicacao?: string;
  conteudo: () => ReactNode;
}

function guardada(chave: string): string | null {
  try {
    return localStorage.getItem(chave);
  } catch {
    return null;
  }
}

export function MenuComAbas<C extends string>({
  rotulo,
  abas,
  memoria,
  abaPedida,
}: {
  /** Nome do conjunto de abas, para leitores de tela. */
  rotulo: string;
  abas: AbaDoMenu<C>[];
  /** Chave do localStorage que lembra a última aba. */
  memoria: string;
  abaPedida?: C | null;
}) {
  const { pode } = usarAcesso();
  const visiveis = abas.filter((a) => pode(...a.permissoes));
  const [escolhida, definirEscolhida] = useState<string | null>(() => abaPedida ?? guardada(memoria));
  if (visiveis.length === 0) return null;
  const aba = visiveis.find((a) => a.chave === escolhida) ?? visiveis[0];
  const escolher = (nova: C) => {
    definirEscolhida(nova);
    try {
      localStorage.setItem(memoria, nova);
    } catch {
      /* sem armazenamento: vale só nesta visita */
    }
  };

  return (
    <div style={{ display: "grid", gap: "var(--e3)" }}>
      <div className="abas" role="tablist" aria-label={rotulo}>
        {visiveis.map((a) => (
          <button key={a.chave} type="button" role="tab" className="aba" aria-selected={aba.chave === a.chave} onClick={() => escolher(a.chave)}>
            {a.rotulo}
          </button>
        ))}
      </div>
      {aba.explicacao && <p className="campo-ajuda" style={{ margin: 0 }}>{aba.explicacao}</p>}
      {aba.conteudo()}
    </div>
  );
}
