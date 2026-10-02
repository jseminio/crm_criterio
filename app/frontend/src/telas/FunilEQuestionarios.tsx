/** Funil com abas (aprovado por Eduardo em 02/10/2026): Oportunidades (o funil de sempre) e
 * Questionários (o que chegou pelo site, do recebimento à proposta). */

import type { Listas } from "../api/tipos";
import { MenuComAbas } from "../componentes/MenuComAbas";
import { Funil } from "./Funil";
import { Questionarios } from "./Questionarios";

export function FunilEQuestionarios({ listas }: { listas: Listas | null }) {
  return (
    <MenuComAbas
      rotulo="Funil comercial"
      memoria="crm.funil.aba"
      abas={[
        {
          chave: "oportunidades", rotulo: "Oportunidades", permissoes: ["funil.ver"],
          conteudo: () => <Funil listas={listas} />,
        },
        {
          chave: "questionarios", rotulo: "Questionários", permissoes: ["questionarios.ver"],
          explicacao: "Tudo o que chegou pelo questionário do site, do recebimento à proposta.",
          conteudo: () => <Questionarios listas={listas} />,
        },
      ]}
    />
  );
}
