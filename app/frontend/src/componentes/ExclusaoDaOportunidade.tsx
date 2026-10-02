/** "Excluir oportunidade" no fim do painel do Funil (Karine, 02/10/2026). Antes de confirmar, diz o
 * que some junto; contrato ou proposta já enviada travam e aparecem no lugar do botão. A da planilha
 * fica lembrada e a recarga não a traz de volta.
 */

import { api } from "../api/cliente";
import type { ExclusaoDeOportunidade } from "../api/tipos";
import { usarDados } from "../usarDados";
import { ExclusaoConfirmada } from "./ExclusaoConfirmada";

function aviso(nome: string, e: ExclusaoDeOportunidade): string {
  const partes: string[] = [];
  if (e.propostas.length) {
    partes.push(`${e.propostas.length === 1 ? "a proposta gerada" : "as propostas geradas"} ${e.propostas.join(", ")} (não enviada${e.propostas.length === 1 ? "" : "s"})`);
  }
  partes.push("o histórico de preço");
  let texto = `"${nome}" sai do Funil junto com ${partes.join(" e ")}.`;
  if (e.questionarios) texto += " O questionário recebido fica guardado, sem a oportunidade.";
  texto += " A empresa, o grupo e os contatos continuam.";
  if (e.da_planilha) texto += " Veio da planilha: a recarga não a traz de volta.";
  return texto;
}

export function ExclusaoDaOportunidade({
  id,
  nome,
  aoExcluir,
}: {
  id: number;
  nome: string;
  aoExcluir: () => void;
}) {
  const exame = usarDados<ExclusaoDeOportunidade>(() => api.antesDeExcluirOportunidade(id), [id]);
  if (!exame.dados) return null;
  return (
    <ExclusaoConfirmada
      rotulo="Excluir oportunidade"
      bloqueio={exame.dados.pode_excluir ? null : exame.dados.motivo}
      aviso={aviso(nome, exame.dados)}
      aoConfirmar={async () => {
        await api.excluirOportunidade(id);
        aoExcluir();
      }}
    />
  );
}
