/** As lacunas do cadastro no card (amostra aprovada por Eduardo em 18/10/2026): o quadro "O que falta no cadastro" no
 * topo de todo card e a marca no próprio campo vazio, com a mesma regra da Integralidade do cadastro (obrigatório vale
 * 2, prioritário vale 1, condicional só quando se aplica). Estado nunca só por cor (PAD-002): borda tracejada, ícone e
 * texto — "!" e "Obrigatório em falta", "i" e "Prioritário em falta". */

import { useEffect, useMemo, useState } from "react";
import { api } from "../api/cliente";
import type { CadastroDaLacuna, Lacuna } from "../api/tipos";
import { usarDados } from "../usarDados";

/** O id do campo no card: único por registro, porque um card pode abrir outro por cima (grupo e oportunidade). */
export function idDaLacuna(cadastro: CadastroDaLacuna, registroId: number | null | undefined, chave: string): string {
  return `lacuna-${cadastro}-${registroId ?? "x"}-${chave}`;
}

/** As lacunas de um grupo ou de um registro. `versao` recarrega depois de salvar. */
export function usarLacunas(
  filtro: { grupo_id?: number; cadastro?: CadastroDaLacuna; registro_id?: number } | null,
  versao: unknown = 0,
) {
  const chave = filtro ? `${filtro.grupo_id ?? ""}|${filtro.cadastro ?? ""}|${filtro.registro_id ?? ""}` : "";
  const { dados, recarregar } = usarDados<Lacuna[]>(
    // Falhar aqui não impede o card: sem a resposta, o quadro só não aparece.
    () => (filtro ? Promise.resolve().then(() => api.lacunas(filtro)).then((l) => l ?? []) : Promise.resolve([])),
    [chave, versao],
  );
  return { lacunas: dados ?? null, recarregar };
}

/** A marca de cada campo do card: a classe da borda, o id para chegar nele e o aviso embaixo. */
export function marcasDeLacuna(lacunas: Lacuna[] | null, cadastro: CadastroDaLacuna, registroId: number | null | undefined) {
  const deste = new Map((lacunas ?? []).filter((l) => l.cadastro === cadastro && l.registro_id === (registroId ?? null))
    .map((l) => [l.chave, l]));
  return {
    /** Classe para o `campo-bloco`: vazio quando o campo está preenchido. */
    classe: (chave: string) => {
      const l = deste.get(chave);
      return l ? (l.obrigatorio ? "lacuna lacuna-obrigatoria" : "lacuna lacuna-prioritaria") : "";
    },
    id: (chave: string) => idDaLacuna(cadastro, registroId, chave),
    aviso: (chave: string) => {
      const l = deste.get(chave);
      return l ? <AvisoDeLacuna obrigatorio={l.obrigatorio} /> : null;
    },
    tem: (chave: string) => deste.has(chave),
  };
}

export function AvisoDeLacuna({ obrigatorio, texto }: { obrigatorio: boolean; texto?: string }) {
  return (
    <span className={`lacuna-aviso ${obrigatorio ? "lacuna-aviso-obrigatoria" : "lacuna-aviso-prioritaria"}`}>
      <span className="lacuna-icone" aria-hidden="true">{obrigatorio ? "!" : "i"}</span>
      {texto ?? (obrigatorio ? "Obrigatório em falta" : "Prioritário em falta")}
    </span>
  );
}

/** Leva até o campo e destaca por um instante: no "ir ao campo" e quando o card abre a partir da Integralidade. */
export function irAoCampo(id: string) {
  const alvo = document.getElementById(id);
  if (!alvo) return;
  const suave = !window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  alvo.scrollIntoView?.({ block: "center", behavior: suave ? "smooth" : "auto" });
  const campo = alvo.querySelector<HTMLElement>("input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled])");
  campo?.focus({ preventScroll: true });
  alvo.classList.add("lacuna-chegou");
  window.setTimeout(() => alvo.classList.remove("lacuna-chegou"), 2400);
}

/** Quando o card abre já numa lacuna: espera o campo existir (o card carrega os dados) e vai até ele uma vez. */
export function usarFocoNaLacuna(id: string | null | undefined, pronto: boolean) {
  useEffect(() => {
    if (!id || !pronto) return;
    const t = window.setTimeout(() => irAoCampo(id), 60);
    return () => window.clearTimeout(t);
  }, [id, pronto]);
}

/** O quadro no topo do card. `aoIr` decide o que "ir ao campo" faz (rolar no próprio card ou abrir o card do registro);
 * `semCampo` diz onde se preenche o que não tem campo neste card. */
export function QuadroDeLacunas({
  lacunas,
  aoIr,
  semCampo,
  comRegistro = false,
  grupoNome,
}: {
  lacunas: Lacuna[] | null;
  aoIr: (l: Lacuna) => void;
  semCampo?: (l: Lacuna) => string | null;
  /** No card do grupo, cada linha diz de que registro é a lacuna. */
  comRegistro?: boolean;
  /** Tira o nome do grupo do começo do registro: no card do grupo ele já está no título. */
  grupoNome?: string;
}) {
  const ordenadas = useMemo(() => [...(lacunas ?? [])].sort((a, b) => Number(b.obrigatorio) - Number(a.obrigatorio)), [lacunas]);
  // Muitas lacunas (o card do grupo junta todos os registros): as primeiras e um "ver todas".
  const [todas, definirTodas] = useState(false);
  const LIMITE = 5;
  const visiveis = todas ? ordenadas : ordenadas.slice(0, LIMITE);
  const doRegistro = (l: Lacuna) => {
    let sem = l.registro;
    if (grupoNome && sem.startsWith(`${grupoNome} · `)) sem = sem.slice(grupoNome.length + 3);
    if (grupoNome && sem.endsWith(` · ${grupoNome}`)) sem = sem.slice(0, -(grupoNome.length + 3));
    return sem === grupoNome || l.cadastro === "Cliente" ? l.cadastro : `${l.cadastro} · ${sem}`;
  };
  if (lacunas === null) return null;
  if (lacunas.length === 0) {
    return (
      <div className="lacunas-quadro lacunas-completo" role="note">
        <span className="lacuna-icone lacuna-icone-ok" aria-hidden="true">✓</span>Cadastro completo
      </div>
    );
  }
  const obrigatorias = lacunas.filter((l) => l.obrigatorio).length;
  const prioritarias = lacunas.length - obrigatorias;
  const partes = [
    obrigatorias ? `${obrigatorias} obrigatório${obrigatorias > 1 ? "s" : ""}` : null,
    prioritarias ? `${prioritarias} prioritário${prioritarias > 1 ? "s" : ""}` : null,
  ].filter(Boolean);
  return (
    <div className="lacunas-quadro" role="note" aria-label="O que falta no cadastro">
      <p className="lacunas-titulo">
        <span className={`lacuna-icone ${obrigatorias ? "" : "lacuna-icone-prioritaria"}`} aria-hidden="true">
          {obrigatorias ? "!" : "i"}
        </span>
        O que falta no cadastro · {partes.join(" e ")}
      </p>
      <ul className="lacunas-lista">
        {visiveis.map((l) => {
          const onde = semCampo?.(l) ?? null;
          return (
            <li key={`${l.cadastro}-${l.registro_id}-${l.chave}`}>
              <span className={`lacuna-nivel ${l.obrigatorio ? "lacuna-nivel-obrigatoria" : "lacuna-nivel-prioritaria"}`}>
                {l.obrigatorio ? "Obrigatório" : "Prioritário"}
              </span>
              <span className="lacunas-campo">
                {comRegistro && <span className="lacunas-registro">{doRegistro(l)}: </span>}
                {l.campo}
              </span>
              {onde ? (
                <span className="campo-ajuda lacunas-onde">{onde}</span>
              ) : (
                <button type="button" className="lacunas-ir" onClick={() => aoIr(l)}>ir ao campo</button>
              )}
            </li>
          );
        })}
      </ul>
      {ordenadas.length > LIMITE && (
        <button type="button" className="lacunas-ir lacunas-todas" aria-expanded={todas} onClick={() => definirTodas((t) => !t)}>
          {todas ? "Mostrar só as primeiras" : `Ver todas (${ordenadas.length})`}
        </button>
      )}
    </div>
  );
}
