/** Sugestões de fusão: grupos que parecem ser o mesmo cliente.
 *
 * Só sugere. A fusão acontece quando **uma pessoa** clica, em dois passos
 * (regra 2: ação que mexe em muitos registros pede confirmação) — e nada é
 * apagado: o grupo absorvido continua no banco, marcado como fundido.
 * "Não é o mesmo cliente" some com a sugestão neste navegador; nada é gravado.
 * Se o navegador não deixar guardar (janela anônima, dados bloqueados), ela some
 * só até recarregar a página.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { SugestaoDeFusao } from "../api/tipos";
import { usarDados } from "../usarDados";

const CHAVE = "crm.fusoes-ignoradas";

function lerIgnoradas(): string[] {
  try {
    const lidas: unknown = JSON.parse(localStorage.getItem(CHAVE) ?? "[]");
    return Array.isArray(lidas) ? lidas.filter((c): c is string => typeof c === "string") : [];
  } catch {
    return [];
  }
}

function guardarIgnorada(chave: string) {
  try {
    localStorage.setItem(CHAVE, JSON.stringify([...lerIgnoradas(), chave]));
  } catch {
    // Sem armazenamento: a tela ainda esconde a sugestão, só não lembra depois.
  }
}

const chaveDe = (s: SugestaoDeFusao) => s.grupos.map((g) => g.id).sort((a, b) => a - b).join("-");

function Bloco({
  sugestao,
  aoIgnorar,
  aoJuntar,
}: {
  sugestao: SugestaoDeFusao;
  aoIgnorar: () => void;
  /** `falha` é `null` quando tudo foi juntado. */
  aoJuntar: (falha: string | null) => void;
}) {
  const [principalId, definirPrincipalId] = useState(sugestao.principal_id);
  const [confirmando, definirConfirmando] = useState(false);
  const [juntando, definirJuntando] = useState(false);
  const principal = sugestao.grupos.find((g) => g.id === principalId)!;
  const outros = sugestao.grupos.filter((g) => g.id !== principalId);

  const juntar = async () => {
    definirJuntando(true);
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
    // O aviso sobe para o painel: a lista recarrega, a sugestão muda de grupos
    // (ou some) e este bloco é desmontado — um aviso guardado aqui sumiria junto.
    aoJuntar(falhas.length ? `Alguns não foram juntados — ${falhas.join("; ")}` : null);
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
      <div className="sugestao-acoes">
        <button type="button" className="botao botao-secundario" onClick={aoIgnorar}>
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

export function SugestoesDeFusao({ aoJuntar, versao = 0 }: { aoJuntar: () => void; versao?: number }) {
  const { dados, recarregar } = usarDados<SugestaoDeFusao[]>(() => api.sugestoesDeFusao(), [versao]);
  const [ignoradasAgora, definirIgnoradasAgora] = useState<string[]>([]);
  const [aviso, definirAviso] = useState<string | null>(null);
  const ignoradas = [...lerIgnoradas(), ...ignoradasAgora];
  const visiveis = (dados ?? []).filter((s) => !ignoradas.includes(chaveDe(s)));
  if (visiveis.length === 0 && !aviso) return null;

  return (
    <section className="recado" aria-label="Sugestões de fusão">
      {visiveis.length > 0 && (
        <>
          <h3 className="numero-rotulo">
            {visiveis.length} {visiveis.length === 1 ? "sugestão" : "sugestões"} de grupos que parecem
            ser o mesmo cliente
          </h3>
          <p className="numero-nota">
            É só uma sugestão pelo nome. Nada é juntado sem o seu clique, e nada é apagado: o grupo
            absorvido continua no banco, marcado como fundido.
          </p>
        </>
      )}
      {aviso && <p role="alert" className="estado-texto">{aviso}</p>}
      {visiveis.length > 0 && (
        <ul className="sugestoes">
          {visiveis.map((s) => (
            <Bloco
              key={chaveDe(s)}
              sugestao={s}
              aoIgnorar={() => {
                guardarIgnorada(chaveDe(s));
                definirIgnoradasAgora((atuais) => [...atuais, chaveDe(s)]);
              }}
              aoJuntar={(falha) => {
                definirAviso(falha);
                recarregar();
                aoJuntar();
              }}
            />
          ))}
        </ul>
      )}
    </section>
  );
}
