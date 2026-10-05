/** Campo de senha com "mostrar/ocultar" (issue #89): o login, a troca da própria senha e a senha
 * provisória que quem administra dá a uma pessoa. */

import { useState, type Ref } from "react";

/** O mesmo mínimo e o mesmo teto que o servidor exige; a tela confere antes de enviar. */
export const SENHA_MINIMA = 8;
export const SENHA_MAXIMA = 200;

/** Conta caracteres como o servidor (Python `len`: pontos de código), não unidades UTF-16: um emoji
 * vale 1, não 2. Espaços e acentos contam; a senha nunca é aparada nem normalizada. */
export function problemaDaSenha(senha: string): string | null {
  const tamanho = Array.from(senha).length;
  if (tamanho < SENHA_MINIMA) return `A senha precisa ter pelo menos ${SENHA_MINIMA} caracteres.`;
  if (tamanho > SENHA_MAXIMA) return `A senha pode ter no máximo ${SENHA_MAXIMA} caracteres.`;
  return null;
}

export function CampoDeSenha({
  id,
  valor,
  aoMudar,
  autoComplete,
  rotuloAcessivel,
  descritoPor,
  exigido = false,
  campoRef,
  dica,
}: {
  dica?: string;
  id?: string;
  valor: string;
  aoMudar: (valor: string) => void;
  autoComplete: "current-password" | "new-password";
  /** Quando não há `<label htmlFor>` visível. */
  rotuloAcessivel?: string;
  descritoPor?: string;
  exigido?: boolean;
  campoRef?: Ref<HTMLInputElement>;
}) {
  const [visivel, definirVisivel] = useState(false);
  return (
    <div className="campo-senha">
      <input
        id={id}
        ref={campoRef}
        className="entrada"
        type={visivel ? "text" : "password"}
        value={valor}
        autoComplete={autoComplete}
        aria-label={rotuloAcessivel}
        placeholder={dica}
        aria-describedby={descritoPor}
        required={exigido}
        spellCheck={false}
        autoCapitalize="none"
        onChange={(e) => aoMudar(e.target.value)}
      />
      <button
        type="button"
        className="campo-senha-ver"
        aria-controls={id}
        onClick={() => definirVisivel((v) => !v)}
      >
        {visivel ? "Ocultar senha" : "Mostrar senha"}
      </button>
    </div>
  );
}
