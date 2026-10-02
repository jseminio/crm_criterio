/** Link de download que leva a entrada junto (E1, 02/10/2026). Sem login é o link comum de sempre;
 * com login, o clique baixa pelo `fetch` com o token e, se falhar, diz o porquê ao lado. */

import { useState, type ReactNode } from "react";
import { baixarArquivo, entradaLigada, ErroDaApi } from "../api/cliente";

export function LinkDeArquivo({
  href,
  nome,
  novaAba = false,
  className,
  title,
  children,
}: {
  href: string;
  nome?: string;
  novaAba?: boolean;
  className?: string;
  title?: string;
  children: ReactNode;
}) {
  const [erro, definirErro] = useState<string | null>(null);
  return (
    <>
      <a
        className={className}
        href={href}
        title={title}
        download={novaAba ? undefined : (nome ?? true)}
        target={novaAba ? "_blank" : undefined}
        rel={novaAba ? "noreferrer" : undefined}
        onClick={(e) => {
          if (!entradaLigada()) return;
          e.preventDefault();
          definirErro(null);
          baixarArquivo(href, nome, novaAba).catch((f) => definirErro(f instanceof ErroDaApi ? f.message : "Falha ao baixar."));
        }}
      >
        {children}
      </a>
      {erro && (
        <span className="estado-texto estado-erro" role="alert">
          {" "}✗ {erro}
        </span>
      )}
    </>
  );
}
