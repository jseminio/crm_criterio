/** Abrir o card de qualquer composição de indicador (amostra aprovada por Eduardo em 18/10/2026): o nome do cliente
 * vira link e abre o card do grupo por cima da composição; na Integralidade do cadastro, "ir à lacuna" abre o card do
 * registro já no campo. Ao fechar (✕ ou Esc), a composição continua aberta no mesmo ponto. */

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import type { Listas } from "../api/tipos";
import { CardDaLacuna, CardDoGrupoPeloId, type AlvoDaLacuna } from "../telas/CardDaLacuna";

type Aberto = { tipo: "grupo"; grupoId: number } | { tipo: "lacuna"; lacuna: AlvoDaLacuna } | null;

interface Abertura {
  abrirGrupo: (grupoId: number) => void;
  abrirLacuna: (lacuna: AlvoDaLacuna) => void;
  /** Sobe a cada card fechado: quem mostra a composição recarrega (o que foi preenchido sai da lista). */
  versao: number;
}

const Contexto = createContext<Abertura | null>(null);

export function usarAberturaDeCard(): Abertura | null {
  return useContext(Contexto);
}

export function ProvedorDeCards({ listas, children }: { listas: Listas | null; children: ReactNode }) {
  const [aberto, definirAberto] = useState<Aberto>(null);
  const [versao, definirVersao] = useState(0);
  const fechar = () => { definirAberto(null); definirVersao((v) => v + 1); };

  useEffect(() => {
    if (!aberto) return;
    // Esc fecha só o card: o modal da composição e o painel lateral também escutam o Esc na `window`; parar aqui, no
    // `document`, deixa a composição aberta.
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key !== "Escape") return;
      evento.stopPropagation();
      definirAberto(null);
      definirVersao((v) => v + 1);
    };
    document.addEventListener("keydown", aoTeclar);
    return () => document.removeEventListener("keydown", aoTeclar);
  }, [aberto]);

  return (
    <Contexto.Provider value={{ abrirGrupo: (grupoId) => definirAberto({ tipo: "grupo", grupoId }),
      abrirLacuna: (lacuna) => definirAberto({ tipo: "lacuna", lacuna }), versao }}>
      {children}
      {aberto && createPortal(
        <div className="camada-do-card">
          {aberto.tipo === "grupo"
            ? <CardDoGrupoPeloId key={aberto.grupoId} grupoId={aberto.grupoId} listas={listas} aoFechar={fechar} />
            : <CardDaLacuna key={JSON.stringify(aberto.lacuna)} lacuna={aberto.lacuna} listas={listas} aoFechar={fechar} />}
        </div>,
        document.body,
      )}
    </Contexto.Provider>
  );
}

/** O nome do cliente numa composição: abre o card do grupo. Sem grupo (lead, abordagem) fica só o texto. */
export function LinkDoGrupo({ grupoId, nome }: { grupoId: number | null | undefined; nome: ReactNode }) {
  const abertura = usarAberturaDeCard();
  if (!abertura || grupoId === null || grupoId === undefined) return <>{nome}</>;
  return (
    <button type="button" className="link-do-grupo" title="Abrir o card do grupo" onClick={() => abertura.abrirGrupo(grupoId)}>
      {nome}
    </button>
  );
}
