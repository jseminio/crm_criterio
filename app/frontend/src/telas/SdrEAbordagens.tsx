/** SDR · Abordagens e conhecimento (aprovado por Eduardo em 02/10/2026): o agente SDR de prospecção
 * ativa (Abordagens) e a SDR de IA que qualifica leads, em abas. A base de conhecimento da SDR de IA
 * vai morar aqui também, numa aba própria, quando for construída. */

import type { Listas } from "../api/tipos";
import { MenuComAbas } from "../componentes/MenuComAbas";
import { Abordagens } from "./Abordagens";
import { Sdr } from "./Sdr";

export function SdrEAbordagens({ listas }: { listas: Listas | null }) {
  return (
    <MenuComAbas
      rotulo="SDR · Abordagens e conhecimento"
      memoria="crm.sdr.aba"
      abas={[
        {
          chave: "abordagens", rotulo: "Abordagens", permissoes: ["abordagens.ver"],
          explicacao: "O agente SDR prepara a ficha e o rascunho. Nada sai sem a sua aprovação.",
          conteudo: () => <Abordagens />,
        },
        {
          chave: "sdr", rotulo: "SDR da IA", permissoes: ["sdr.ver"],
          explicacao: "Leads de tráfego pago e frios: quantos a IA qualificou, descartou ou passou para a equipe.",
          conteudo: () => <Sdr listas={listas} />,
        },
      ]}
    />
  );
}
