/** O indicador do CRM (padrão pedido por Eduardo em 10/10/2026, para todos os indicadores):
 *
 * 1. **explicação ao passar o mouse** (ou ao focar com o teclado): como o número é calculado;
 * 2. **botão "Ver composição"**: abre o painel lateral com a lista de dados que compõem o número,
 *    cada um com o seu valor ao lado. A lista vem da mesma conta do número e soma o mesmo total.
 *
 * Estado nunca só pela cor (PAD-002): a etiqueta traz a palavra.
 */

import { useId, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { PainelLateral } from "./PainelLateral";

export type Tom = "azul" | "verde" | "ambar" | "vermelho" | "dourado" | "violeta" | "rosa" | "marinho";

export interface Composicao {
  /** Título do painel lateral. */
  titulo: string;
  subtitulo?: string;
  /** Quantos itens a lista tem, para o rótulo do botão ("Ver composição (34)"). */
  quantos?: number;
  /** O conteúdo do painel; só é montado quando a pessoa abre (carrega sob demanda). */
  conteudo: () => ReactNode;
}

export function Indicador({
  rotulo,
  destaque,
  apoio,
  etiqueta,
  tom,
  children,
  pendente = false,
  composicao,
  className = "",
}: {
  rotulo: string;
  destaque?: string;
  apoio?: ReactNode;
  etiqueta?: ReactNode;
  tom: Tom;
  /** A explicação: aparece ao passar o mouse ou ao focar o indicador. */
  children?: ReactNode;
  pendente?: boolean;
  composicao?: Composicao;
  className?: string;
}) {
  const id = useId();
  const [aberto, definirAberto] = useState(false);
  return (
    <section
      className={`numero ind ind-${tom} ${pendente ? "numero-pendente" : ""} ${className}`}
      tabIndex={0}
      aria-describedby={children ? id : undefined}
    >
      <h3 className="numero-rotulo ind-rotulo">{rotulo}</h3>
      {destaque ? <p className="numero-valor ind-valor">{destaque}</p> : <p className="ind-valor ind-valor-pendente">Não calculável</p>}
      {apoio && <p className="ind-apoio">{apoio}</p>}
      {etiqueta}
      {composicao && (
        <button type="button" className="ind-composicao" onClick={() => definirAberto(true)}>
          Ver composição{composicao.quantos !== undefined ? ` (${composicao.quantos})` : ""}
        </button>
      )}
      {children && (
        <div className="numero-detalhe ind-janela" role="tooltip" id={id}>
          {children}
        </div>
      )}
      {aberto && composicao && <PainelDaComposicao composicao={composicao} aoFechar={() => definirAberto(false)} />}
    </section>
  );
}

/** Botão "Ver composição" solto, para números que não estão num card (linha de tabela, rodapé). */
export function BotaoDeComposicao({ composicao, rotulo = "ver" }: { composicao: Composicao; rotulo?: string }) {
  const [aberto, definirAberto] = useState(false);
  return (
    <>
      <button type="button" className="ind-composicao ind-composicao-solto" onClick={() => definirAberto(true)}
        aria-label={`Ver composição: ${composicao.titulo}`}>
        {rotulo}{composicao.quantos !== undefined ? ` (${composicao.quantos})` : ""}
      </button>
      {aberto && <PainelDaComposicao composicao={composicao} aoFechar={() => definirAberto(false)} />}
    </>
  );
}

/** No `body`, fora do card: senão o foco dentro do painel manteria aberta a explicação do card. */
function PainelDaComposicao({ composicao, aoFechar }: { composicao: Composicao; aoFechar: () => void }) {
  return createPortal(
    <PainelLateral titulo={composicao.titulo} subtitulo={composicao.subtitulo} aoFechar={aoFechar}>
      <div className="composicao">{composicao.conteudo()}</div>
    </PainelLateral>,
    document.body,
  );
}
