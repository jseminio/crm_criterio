/** Painel do lead › Primeiro contato (amostra aprovada por Eduardo em 04/10/2026).
 *
 * Quando a Critério falou com o lead pela primeira vez e se o que ele esperava bate com o que a peça
 * prometeu. Alimenta o Engajamento da Inteligência de Conversão: aderência = "Bate" ÷ respondidos.
 * Nada aqui é obrigatório para salvar: a pergunta não trava o fluxo. */

import type { LeadResumo, Listas } from "../api/tipos";

export interface RascunhoDoPrimeiroContato {
  primeiro_contato_em: string;
  aderencia: string;
  aderencia_sobre: string[];
  aderencia_esperava: string;
}

const SINAL: Record<string, string> = { Bate: "✓", "Em parte": "~", "Não bate": "✗" };
const AJUDA: Record<string, string> = {
  Bate: "esperava o que a peça promete",
  "Em parte": "parte da expectativa não bate",
  "Não bate": "esperava outra coisa",
};

function origemDoLead(lead: LeadResumo): string {
  return [
    lead.tipo_canal,
    lead.canal && `canal ${lead.canal}`,
    lead.campanha && `campanha “${lead.campanha}”`,
    lead.campanha_midia,
    lead.interesse && `interesse: ${lead.interesse}`,
  ].filter(Boolean).join(" · ") || "Origem não registrada";
}

export function PrimeiroContato({
  lead, listas, rascunho, aoMudar, sugerido,
}: {
  lead: LeadResumo;
  listas: Listas | null;
  rascunho: RascunhoDoPrimeiroContato;
  aoMudar: (novo: RascunhoDoPrimeiroContato) => void;
  /** O primeiro contato veio da primeira mensagem do SDR, ainda não gravado. */
  sugerido: boolean;
}) {
  const opcoes = listas?.aderencias ?? ["Bate", "Em parte", "Não bate"];
  const temas = listas?.temas_de_expectativa ?? [];
  const detalhe = rascunho.aderencia === "Em parte" || rascunho.aderencia === "Não bate";
  const mudar = (parte: Partial<RascunhoDoPrimeiroContato>) => aoMudar({ ...rascunho, ...parte });
  const alternarTema = (t: string) =>
    mudar({ aderencia_sobre: rascunho.aderencia_sobre.includes(t) ? rascunho.aderencia_sobre.filter((x) => x !== t) : [...rascunho.aderencia_sobre, t] });

  return (
    <fieldset className="primeiro-contato">
      <legend className="primeiro-contato-titulo">Primeiro contato</legend>
      <p className="primeiro-contato-origem"><strong>Veio por:</strong> {origemDoLead(lead)}</p>
      <div className="campo-bloco">
        <label className="campo-rotulo" htmlFor="e-primeiro-contato">Data e hora do 1º contato</label>
        <input id="e-primeiro-contato" type="datetime-local" className="entrada" value={rascunho.primeiro_contato_em}
          onChange={(e) => mudar({ primeiro_contato_em: e.target.value })} />
        {sugerido && (
          <p className="campo-ajuda">Preenchido pela primeira mensagem do SDR. Ajuste se o primeiro contato foi por telefone ou presencial.</p>
        )}
      </div>
      <div className="campo-bloco">
        <span className="campo-rotulo" id="e-aderencia">O que o lead esperava bate com o que a peça prometeu?</span>
        <div className="aderencia-opcoes" role="radiogroup" aria-labelledby="e-aderencia">
          {opcoes.map((o) => (
            <button key={o} type="button" role="radio" aria-checked={rascunho.aderencia === o}
              className={`aderencia-opcao${rascunho.aderencia === o ? " aderencia-opcao-escolhida" : ""}`}
              onClick={() => mudar(rascunho.aderencia === o ? { aderencia: "" } : { aderencia: o })}>
              <span aria-hidden="true">{SINAL[o] ?? ""} </span>{o}
              <small>{AJUDA[o] ?? ""}</small>
            </button>
          ))}
        </div>
      </div>
      {detalhe && (
        <>
          <div className="campo-bloco">
            <span className="campo-rotulo" id="e-aderencia-sobre">Sobre o quê? (pode marcar mais de um)</span>
            <div className="aderencia-temas" role="group" aria-labelledby="e-aderencia-sobre">
              {temas.map((t) => (
                <button key={t} type="button" aria-pressed={rascunho.aderencia_sobre.includes(t)}
                  className={`aderencia-tema${rascunho.aderencia_sobre.includes(t) ? " aderencia-tema-marcado" : ""}`}
                  onClick={() => alternarTema(t)}>
                  {rascunho.aderencia_sobre.includes(t) && <span aria-hidden="true">✓ </span>}{t}
                </button>
              ))}
            </div>
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="e-aderencia-esperava">O que ele esperava, em uma frase</label>
            <input id="e-aderencia-esperava" className="entrada" maxLength={300} value={rascunho.aderencia_esperava}
              onChange={(e) => mudar({ aderencia_esperava: e.target.value })} />
          </div>
        </>
      )}
    </fieldset>
  );
}
