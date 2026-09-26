/** Sugestões de fusão: grupos que parecem ser o mesmo cliente.
 *
 * Só sugere. A fusão acontece quando **uma pessoa** clica, em dois passos
 * (regra 2: ação que mexe em muitos registros pede confirmação) — e nada é
 * apagado: o grupo absorvido continua no banco, marcado como fundido.
 * "Não é o mesmo cliente" some com a sugestão neste navegador; nada é gravado.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { SugestaoDeFusao } from "../api/tipos";
import { usarDados } from "../usarDados";

const CHAVE = "crm.fusoes-ignoradas";

function lerIgnoradas(): string[] {
  try {
    return JSON.parse(localStorage.getItem(CHAVE) ?? "[]");
  } catch {
    return [];
  }
}

const chaveDe = (s: SugestaoDeFusao) => s.grupos.map((g) => g.id).sort((a, b) => a - b).join("-");

function Bloco({ sugestao, aoResolver }: { sugestao: SugestaoDeFusao; aoResolver: () => void }) {
  const [principalId, definirPrincipalId] = useState(sugestao.principal_id);
  const [confirmando, definirConfirmando] = useState(false);
  const [juntando, definirJuntando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const principal = sugestao.grupos.find((g) => g.id === principalId)!;
  const outros = sugestao.grupos.filter((g) => g.id !== principalId);

  const juntar = async () => {
    definirJuntando(true);
    definirErro(null);
    const falhas: string[] = [];
    for (const g of outros) {
      try {
        await api.fundirGrupos(principalId, g.id);
      } catch (f) {
        falhas.push(`${g.nome}: ${f instanceof ErroDaApi ? f.message : "falhou"}`);
      }
    }
    definirJuntando(false);
    definirConfirmando(false);
    if (falhas.length) definirErro(`Alguns não foram juntados — ${falhas.join("; ")}`);
    aoResolver();
  };

  return (
    <li className="sugestao">
      <div className="sugestao-cabeca">
        <span className={`etiqueta etiqueta-${sugestao.confianca === "alta" ? "ganho" : "espera"}`}>
          Confiança {sugestao.confianca}
        </span>
        <span className="numero-nota">{sugestao.motivo}</span>
      </div>
      <fieldset className="sugestao-grupos">
        <legend className="campo-rotulo">Junte tudo em qual grupo?</legend>
        {sugestao.grupos.map((g) => (
          <label key={g.id} className="sugestao-opcao">
            <input
              type="radio"
              name={`principal-${chaveDe(sugestao)}`}
              checked={principalId === g.id}
              onChange={() => {
                definirPrincipalId(g.id);
                definirConfirmando(false);
              }}
            />{" "}
            {g.nome} <span className="numero-nota">({g.quantas_oportunidades} prop.)</span>
          </label>
        ))}
      </fieldset>
      {erro && <p role="alert" className="estado-texto">{erro}</p>}
      <div className="sugestao-acoes">
        <button type="button" className="botao botao-secundario" onClick={() => {
          localStorage.setItem(CHAVE, JSON.stringify([...lerIgnoradas(), chaveDe(sugestao)]));
          aoResolver();
        }}>
          Não é o mesmo cliente
        </button>
        {confirmando ? (
          <button type="button" className="botao botao-primario" onClick={juntar} disabled={juntando}>
            {juntando ? "Juntando…" : `Confirmar: juntar ${outros.length} em ${principal.nome}`}
          </button>
        ) : (
          <button type="button" className="botao botao-primario" onClick={() => definirConfirmando(true)}>
            Juntar {sugestao.grupos.length} grupos
          </button>
        )}
      </div>
    </li>
  );
}

export function SugestoesDeFusao({ aoJuntar }: { aoJuntar: () => void }) {
  const { dados, recarregar } = usarDados<SugestaoDeFusao[]>(() => api.sugestoesDeFusao(), []);
  const [, forcar] = useState(0);
  const ignoradas = lerIgnoradas();
  const visiveis = (dados ?? []).filter((s) => !ignoradas.includes(chaveDe(s)));
  if (visiveis.length === 0) return null;

  return (
    <section className="recado" aria-label="Sugestões de fusão">
      <h3 className="numero-rotulo">
        {visiveis.length} sugestõe{visiveis.length === 1 ? "" : "s"} de grupos que parecem ser o mesmo cliente
      </h3>
      <p className="numero-nota">
        É só uma sugestão pelo nome. Nada é juntado sem o seu clique, e nada é apagado: o grupo
        absorvido continua no banco, marcado como fundido.
      </p>
      <ul className="sugestoes">
        {visiveis.map((s) => (
          <Bloco
            key={chaveDe(s)}
            sugestao={s}
            aoResolver={() => {
              forcar((n) => n + 1);
              recarregar();
              aoJuntar();
            }}
          />
        ))}
      </ul>
    </section>
  );
}
