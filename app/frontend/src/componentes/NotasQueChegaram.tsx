/** As notas que chegaram sozinhas do Granola para esta oportunidade ou este cliente (23/10/2026). "Usar" só
 * preenche o formulário: nada é guardado até a pessoa aplicar ou registrar, como na nota colada. */

import type { NotaDoGranola } from "../api/tipos";
import { data } from "../formato";

export function NotasQueChegaram({ notas, emUso, aoUsar, aoDescartar, ocupado = false }: {
  notas: NotaDoGranola[];
  /** A nota que está no formulário agora. */
  emUso: number | null;
  aoUsar: (n: NotaDoGranola) => void;
  aoDescartar: (n: NotaDoGranola) => void;
  ocupado?: boolean;
}) {
  if (notas.length === 0) return null;
  return (
    <div className="recado granola-chegou" role="group" aria-labelledby="t-granola-chegou">
      <strong id="t-granola-chegou">Chegou do Granola ({notas.length})</strong>
      {notas.map((n) => (
        <div key={n.id} className="granola-chegou-linha">
          <span className="etiqueta etiqueta-andamento">{emUso === n.id ? "No formulário" : "A usar"}</span>
          <strong>{n.titulo}</strong>
          <span>{data(n.data)}</span>
          {n.participantes && <span className="campo-ajuda" style={{ margin: 0 }}>{n.participantes}</span>}
          {n.link && <a className="campo-ajuda" href={n.link} target="_blank" rel="noreferrer">nota no Granola</a>}
          <button type="button" className="botao" disabled={ocupado || emUso === n.id} onClick={() => aoUsar(n)}>
            Usar esta nota
          </button>
          <button type="button" className="botao botao-texto-perigo" disabled={ocupado}
            onClick={() => {
              if (window.confirm(`Descartar a nota “${n.titulo}”? O conteúdo sai do CRM e a nota não volta na busca.`)) aoDescartar(n);
            }}>
            Descartar
          </button>
        </div>
      ))}
    </div>
  );
}
