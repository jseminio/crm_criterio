/** SDR · Abordagens e conhecimento (aprovado por Eduardo em 02/10/2026): o agente SDR de prospecção
 * ativa (Abordagens) e a SDR de IA que qualifica leads, em abas. A base de conhecimento da SDR de IA
 * vai morar aqui também, numa aba própria, quando for construída. */

import { useState } from "react";
import type { Listas } from "../api/tipos";
import { usarAcesso } from "../entrada";
import { Abordagens } from "./Abordagens";
import { Sdr } from "./Sdr";

type Aba = "abordagens" | "sdr";

const ABAS: { chave: Aba; rotulo: string; permissao: string; explicacao: string }[] = [
  {
    chave: "abordagens", rotulo: "Abordagens", permissao: "abordagens.ver",
    explicacao: "O agente SDR prepara a ficha e o rascunho. Nada sai sem a sua aprovação.",
  },
  {
    chave: "sdr", rotulo: "SDR da IA", permissao: "sdr.ver",
    explicacao: "Leads de tráfego pago e frios: quantos a IA qualificou, descartou ou passou para a equipe.",
  },
];
const CHAVE_DA_ABA = "crm.sdr.aba";

function abaGuardada(): Aba | null {
  try {
    return localStorage.getItem(CHAVE_DA_ABA) as Aba | null;
  } catch {
    return null;
  }
}

export function SdrEAbordagens({ listas }: { listas: Listas | null }) {
  const { pode } = usarAcesso();
  const visiveis = ABAS.filter((a) => pode(a.permissao));
  const [escolhida, definirEscolhida] = useState<Aba | null>(abaGuardada);
  if (visiveis.length === 0) return null;
  const aba = visiveis.find((a) => a.chave === escolhida) ?? visiveis[0];
  const escolher = (nova: Aba) => {
    definirEscolhida(nova);
    try {
      localStorage.setItem(CHAVE_DA_ABA, nova);
    } catch {
      /* sem armazenamento: vale só nesta visita */
    }
  };

  return (
    <div style={{ display: "grid", gap: "var(--e3)" }}>
      <div className="abas" role="tablist" aria-label="SDR · Abordagens e conhecimento">
        {visiveis.map((a) => (
          <button key={a.chave} type="button" role="tab" className="aba" aria-selected={aba.chave === a.chave} onClick={() => escolher(a.chave)}>
            {a.rotulo}
          </button>
        ))}
      </div>
      <p className="campo-ajuda" style={{ margin: 0 }}>{aba.explicacao}</p>
      {aba.chave === "abordagens" && <Abordagens />}
      {aba.chave === "sdr" && <Sdr listas={listas} />}
    </div>
  );
}
