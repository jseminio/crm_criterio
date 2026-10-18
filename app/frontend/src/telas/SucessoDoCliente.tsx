/** Sucesso do Cliente (aprovado por Eduardo em 02/10/2026): Saúde da carteira, Gestão de contratos, Reajuste
 * anual (13/10/2026) e Funil do Sucesso do Cliente (da assinatura do contrato às reuniões de resultado pela classe), em abas. */

import type { Listas } from "../api/tipos";
import { MenuComAbas } from "../componentes/MenuComAbas";
import { Carteira } from "./Carteira";
import { Contratos } from "./Contratos";
import { DocumentosAntigos } from "./DocumentosAntigos";
import { FunilDoSucesso } from "./FunilDoSucesso";
import { ReajusteAnual } from "./ReajusteAnual";

export type AbaDoSucesso = "saude" | "contratos" | "documentos" | "reajuste" | "funil";

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
        {
          chave: "documentos", rotulo: "Documentos antigos", permissoes: ["contratos.documentos"],
          explicacao: "Contratos, propostas e aditivos feitos fora do CRM: a IA lê, você vincula e confere.",
          conteudo: () => <DocumentosAntigos />,
        },
        {
          chave: "reajuste", rotulo: "Reajuste anual", permissoes: ["contratos.ver"],
          explicacao: "O reajuste de julho pelo IPCA: o CRM sugere, uma pessoa confirma ou altera e fica quem autorizou.",
          conteudo: () => <ReajusteAnual />,
        },
        {
          chave: "funil", rotulo: "Funil do Sucesso do Cliente", permissoes: ["sucesso.ver"],
          explicacao: "Da assinatura do contrato ao kickoff, e as reuniões de resultado que a classe do Score pede.",
          conteudo: () => <FunilDoSucesso />,
        },
      ]}
    />
  );
}
