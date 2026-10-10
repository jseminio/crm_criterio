/** "Mover para…" — a troca de etapa do kanban no celular, onde arrastar cartão não funciona bem.
 *
 * Amostra aprovada por Eduardo em 06/10/2026. É a mesma ação do arrasto no computador: quem
 * chama passa a etapa escolhida para o mesmo `mover()` do Funil, com as mesmas regras (Aceita
 * abre a ficha para a data do aceite; a etapa atual não move nada).
 */

import { useEffect } from "react";

export function FolhaMoverPara({
  nome,
  etapaAtual,
  etapas,
  aoEscolher,
  aoFechar,
}: {
  nome: string;
  etapaAtual: string;
  etapas: string[];
  aoEscolher: (etapa: string) => void;
  aoFechar: () => void;
}) {
  useEffect(() => {
    // Esc fecha: quem abriu com teclado precisa sair com teclado.
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") aoFechar();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => window.removeEventListener("keydown", aoTeclar);
  }, [aoFechar]);

  return (
    <>
      <div className="cortina" onClick={aoFechar} aria-hidden="true" />
      <div className="folha" role="dialog" aria-modal="true" aria-label="Mover para">
        <h2 className="folha-titulo">Mover para…</h2>
        <p className="folha-subtitulo">
          {nome} · hoje em "{etapaAtual}"
        </p>
        <div className="folha-opcoes">
          {etapas.map((etapa) => {
            const atual = etapa === etapaAtual;
            return (
              <button
                key={etapa}
                type="button"
                className="folha-opcao"
                aria-current={atual ? "true" : undefined}
                disabled={atual}
                onClick={() => aoEscolher(etapa)}
              >
                <span>{etapa}</span>
                {atual && <small>etapa atual</small>}
                {!atual && etapa === "Aceita" && <small>abre a ficha para a data do aceite</small>}
                {!atual && etapa === "Em avaliação pela empresa" && etapaAtual === "Enviar proposta" && (
                  <small>abre a ficha para a data de envio</small>
                )}
              </button>
            );
          })}
        </div>
        <button type="button" className="botao botao-secundario folha-cancelar" onClick={aoFechar}>
          Cancelar
        </button>
      </div>
    </>
  );
}
