/** Funil com abas (aprovado por Eduardo em 02/10/2026): Oportunidades (o funil de sempre),
 * Questionários (o que chegou pelo site, do recebimento à proposta) e, desde 03/10/2026,
 * Inteligência de Conversão (o plano de MRR: previsto, realizado e ajuste). */

import type { Listas } from "../api/tipos";
import { MenuComAbas } from "../componentes/MenuComAbas";
import { Funil } from "./Funil";
import { InteligenciaDeConversao } from "./InteligenciaDeConversao";
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
        {
          chave: "inteligencia", rotulo: "Inteligência de Conversão", permissoes: ["funil.ver"],
          explicacao: "A meta de MRR líquido: previsto, realizado e o ajuste para chegar lá, por motor.",
          conteudo: () => <InteligenciaDeConversao />,
        },
      ]}
    />
  );
}
