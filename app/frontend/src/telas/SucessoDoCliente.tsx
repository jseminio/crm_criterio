/** Sucesso do Cliente (aprovado por Eduardo em 02/10/2026): Saúde da carteira e Gestão de contratos,
 * em abas. O Funil do Sucesso do Cliente (comercial, onboarding e as reuniões pelo Score) entra aqui
 * como terceira aba quando for construído. */

import type { Listas } from "../api/tipos";
import { MenuComAbas } from "../componentes/MenuComAbas";
import { Carteira } from "./Carteira";
import { Contratos } from "./Contratos";

export type AbaDoSucesso = "saude" | "contratos";

export function SucessoDoCliente({ listas, abaPedida = null }: { listas: Listas | null; abaPedida?: AbaDoSucesso | null }) {
  return (
    <MenuComAbas
      rotulo="Sucesso do Cliente"
      memoria="crm.sucesso.aba"
      abaPedida={abaPedida}
      abas={[
        {
          chave: "saude", rotulo: "Saúde da carteira", permissoes: ["carteira.ver"],
          explicacao: "Classe, Score e eixo de ação por grupo, e o índice de saúde (ISC).",
          conteudo: () => <Carteira listas={listas} />,
        },
        {
          chave: "contratos", rotulo: "Gestão de contratos", permissoes: ["contratos.ver"],
          explicacao: "O MRR da carteira contra a meta, os contratos e os eventos de cada um.",
          conteudo: () => <Contratos listas={listas} />,
        },
      ]}
    />
  );
}
