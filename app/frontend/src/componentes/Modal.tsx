/** Modal centralizado (sugestão do Jesse, amostra aprovada por Eduardo em 15/10/2026): para **ler** uma composição
 * com espaço para a tabela. Edição continua no painel lateral (`PainelLateral`), que deixa ver a tela de trás.
 * Mesmo contrato do painel: título, subtítulo, rodapé; Esc, o X ou um clique fora fecham. Modal é um dos três
 * lugares onde o PAD-002 permite sombra. */

import { useEffect, useRef, type ReactNode } from "react";

export function Modal({
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
  const fechar = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    // Quem abriu com teclado continua no teclado: o foco entra no modal e volta para quem o abriu ao fechar.
    const antes = document.activeElement as HTMLElement | null;
    fechar.current?.focus();
    const aoTeclar = (evento: KeyboardEvent) => {
      if (evento.key === "Escape") aoFechar();
    };
    window.addEventListener("keydown", aoTeclar);
    return () => {
      window.removeEventListener("keydown", aoTeclar);
      antes?.focus?.();
    };
  }, [aoFechar]);

  return (
    <div className="modal-cortina" onClick={aoFechar}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={titulo} onClick={(e) => e.stopPropagation()}>
        <header className="painel-cabecalho">
          <div>
            <h2 className="painel-titulo">{titulo}</h2>
            {subtitulo && <p className="painel-subtitulo">{subtitulo}</p>}
          </div>
          <button ref={fechar} type="button" className="botao-icone" onClick={aoFechar} aria-label="Fechar">
            ✕
          </button>
        </header>
        <div className="painel-corpo">{children}</div>
        {rodape && <footer className="painel-rodape">{rodape}</footer>}
      </div>
    </div>
  );
}
