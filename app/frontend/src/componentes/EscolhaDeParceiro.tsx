/** O parceiro que indicou, escolhido na lista do Funil de Parceiros (19/10/2026, pedido de Eduardo): quando o tipo de
 * canal é Parceiros ou Advogados, o Canal deixa de ser texto solto e liga a indicação ao parceiro. Quem não está na
 * lista ainda pode ser escrito; esse texto aparece na conferência do Funil de Parceiros para ser ligado depois. */

import { useState } from "react";
import { api } from "../api/cliente";
import { usarDados } from "../usarDados";

export const CANAIS_DE_PARCEIRO = ["Parceiros", "Advogados"];

const FORA_DA_LISTA = "fora";

export function EscolhaDeParceiro({ id, parceiroId, canal, aoMudar }: {
  id: string;
  parceiroId: string;
  canal: string;
  /** O id do parceiro ("" quando não está na lista) e o texto do canal. */
  aoMudar: (parceiroId: string, canal: string) => void;
}) {
  const { dados: parceiros, carregando, erro } = usarDados(() => api.nomesDosParceiros(), []);
  const [foraDaLista, definirForaDaLista] = useState(parceiroId === "" && canal !== "");
  const valor = parceiroId !== "" ? parceiroId : foraDaLista ? FORA_DA_LISTA : "";
  return (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={id}>Parceiro que indicou</label>
      <select id={id} className="selecao" value={valor} disabled={carregando}
        onChange={(e) => {
          const escolha = e.target.value;
          if (escolha === FORA_DA_LISTA) {
            definirForaDaLista(true);
            aoMudar("", parceiroId !== "" ? "" : canal);
            return;
          }
          definirForaDaLista(false);
          const p = parceiros?.find((x) => String(x.id) === escolha);
          aoMudar(escolha, p?.nome ?? "");
        }}>
        <option value="">{carregando ? "Carregando os parceiros…" : "Escolha o parceiro"}</option>
        {(parceiros ?? []).map((p) => (
          <option key={p.id} value={String(p.id)}>{p.nome}{p.tipo ? ` · ${p.tipo}` : ""}</option>
        ))}
        <option value={FORA_DA_LISTA}>Não está na lista</option>
      </select>
      {erro && <p className="campo-ajuda">Não consegui carregar os parceiros: {erro}</p>}
      {foraDaLista && (
        <>
          <input id={`${id}-texto`} className="entrada" aria-label="Nome de quem indicou" placeholder="Nome de quem indicou"
            value={canal} onChange={(e) => aoMudar("", e.target.value)} style={{ marginTop: "var(--e2)" }} />
          <p className="campo-ajuda">
            Cadastre o parceiro no Funil de Parceiros: este nome aparece lá na conferência das indicações antigas.
          </p>
        </>
      )}
    </div>
  );
}
