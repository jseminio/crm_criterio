/** Painel lateral — um dos três lugares onde o PAD-002 permite sombra. */

import { useEffect, type ReactNode } from "react";

export function PainelLateral({
  titulo,
  subtitulo,
  aoFechar,
  children,
  rodape,
}: {
  titulo: string;
  subtitulo?: string;
  aoFechar: () => void;
  children: ReactNode;
  rodape?: ReactNode;
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
      <aside className="painel" role="dialog" aria-modal="true" aria-label={titulo}>
        <header className="painel-cabecalho">
          <div>
            <h2 className="painel-titulo">{titulo}</h2>
            {subtitulo && <p className="painel-subtitulo">{subtitulo}</p>}
          </div>
          <button
            type="button"
            className="botao-icone"
            onClick={aoFechar}
            aria-label="Fechar painel"
          >
            ✕
          </button>
        </header>
        <div className="painel-corpo">{children}</div>
        {rodape && <footer className="painel-rodape">{rodape}</footer>}
      </aside>
    </>
  );
}
