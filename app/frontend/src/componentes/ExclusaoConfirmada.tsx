/** Botão de excluir em dois passos: o primeiro clique só mostra o aviso do que vai sumir; o
 * segundo, "Confirmar", apaga. Fica no fim do painel, longe dos botões do dia a dia, para evitar
 * exclusão por acidente (decisão de Karine em 30/09/2026).
 */

import { useState } from "react";
import { ErroDaApi } from "../api/cliente";

export function ExclusaoConfirmada({
  rotulo,
  aviso,
  bloqueio,
  aoConfirmar,
}: {
  rotulo: string;
  /** O que vai acontecer — aparece na confirmação. */
  aviso: string;
  /** Quando existe, a exclusão não é oferecida e o motivo aparece no lugar. */
  bloqueio?: string | null;
  aoConfirmar: () => Promise<void>;
}) {
  const [confirmando, definirConfirmando] = useState(false);
  const [excluindo, definirExcluindo] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  const confirmar = async () => {
    definirExcluindo(true);
    definirErro(null);
    try {
      await aoConfirmar();
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao excluir.");
      definirExcluindo(false);
    }
  };

  return (
    <div className="formulario" style={{ borderTop: "1px solid var(--borda)", paddingTop: "var(--e3)" }}>
      {bloqueio ? (
        <p className="campo-ajuda" style={{ margin: 0 }}>{bloqueio}</p>
      ) : confirmando ? (
        <div className="recado" role="alertdialog" aria-label={rotulo}>
          <strong>{rotulo}?</strong>
          <p style={{ margin: "var(--e1) 0" }}>{aviso} Não dá para desfazer.</p>
          {erro && <p role="alert" className="estado-texto">{erro}</p>}
          <div className="sugestao-acoes">
            <button type="button" className="botao botao-secundario" onClick={() => definirConfirmando(false)}>Cancelar</button>
            <button type="button" className="botao botao-perigo" disabled={excluindo} onClick={confirmar}>
              {excluindo ? "Excluindo…" : "Confirmar"}
            </button>
          </div>
        </div>
      ) : (
        <div>
          <button type="button" className="botao botao-perigo" onClick={() => definirConfirmando(true)}>{rotulo}</button>
        </div>
      )}
    </div>
  );
}
