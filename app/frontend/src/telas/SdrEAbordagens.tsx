/** SDR · Abordagens e conhecimento (aprovado por Eduardo em 02/10/2026): o agente SDR de prospecção
 * ativa (Abordagens), a SDR de IA que qualifica leads e, desde 03/10/2026, a base de conhecimento
 * que essa SDR consulta, em abas. */

import type { Listas } from "../api/tipos";
import { MenuComAbas } from "../componentes/MenuComAbas";
import { Abordagens } from "./Abordagens";
import { BaseDeConhecimento } from "./BaseDeConhecimento";
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
        {
          chave: "base", rotulo: "Base de conhecimento", permissoes: ["sdr.ver"],
          explicacao: "O que a SDR de IA pode dizer. Só a ficha aprovada e dentro da validade chega à IA.",
          conteudo: () => <BaseDeConhecimento />,
        },
      ]}
    />
  );
}
