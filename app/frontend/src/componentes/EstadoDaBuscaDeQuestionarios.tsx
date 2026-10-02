/** A linha da busca automática no painel Questionários (aprovado por Eduardo em 02/10/2026): o CRM
 * busca sozinho a cada 10 minutos; aqui se vê a última busca, o que trouxe, a próxima e a falha, com
 * o motivo (⚠ e texto, nunca só cor). "Buscar agora" faz a mesma busca na hora. A linha se atualiza
 * sozinha a cada minuto e avisa a tela quando chega questionário novo. */

import { useEffect, useRef, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { EstadoDaBusca } from "../api/tipos";
import { usarAcesso } from "../entrada";

const hora = (iso: string) => new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });

export function EstadoDaBuscaDeQuestionarios({ aoChegar }: { aoChegar: () => void }) {
  const { pode } = usarAcesso();
  const [estado, definirEstado] = useState<EstadoDaBusca | null>(null);
  const [buscando, definirBuscando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const ultimaVista = useRef<string | null>(null);

  const ler = async () => {
    try {
      const e = await api.estadoDaBusca();
      // Busca nova com questionário novo: a tela de baixo recarrega sozinha.
      if (ultimaVista.current !== null && e.ultima_em !== ultimaVista.current && e.novos > 0) aoChegar();
      ultimaVista.current = e.ultima_em;
      definirEstado(e);
    } catch {
      /* a linha some; o painel continua */
    }
  };

  useEffect(() => {
    void ler();
    const relogio = window.setInterval(() => void ler(), 60_000);
    return () => window.clearInterval(relogio);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const buscarAgora = async () => {
    definirBuscando(true);
    definirFalha(null);
    try {
      const r = await api.buscarQuestionarios();
      if (r.novos.length) aoChegar();
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao buscar os questionários.");
    } finally {
      definirBuscando(false);
      void ler();
    }
  };

  if (!estado) return null;
  const ultima = estado.ultima_em
    ? `última ${estado.ultima_manual ? "na hora" : "automática"} às ${hora(estado.ultima_em)} (${estado.novos === 0 ? "nada novo" : `${estado.novos} novo${estado.novos === 1 ? "" : "s"}`})`
    : "ainda não buscou";
  return (
    <div className="busca-automatica" role="status">
      <p className="campo-ajuda" style={{ margin: 0 }}>
        {estado.automatica
          ? `Busca automática a cada ${estado.intervalo_minutos} min · ${ultima}${estado.proxima_em ? ` · próxima às ${hora(estado.proxima_em)}` : ""}`
          : `⚠ Busca automática desligada · ${ultima}`}
      </p>
      {pode("funil.questionarios") && (
        <button type="button" className="botao botao-secundario" disabled={buscando} onClick={() => void buscarAgora()}>
          {buscando ? "Buscando…" : "Buscar agora"}
        </button>
      )}
      {(falha ?? estado.erro) && <p className="estado-texto estado-erro busca-automatica-erro" role="alert">⚠ {falha ?? estado.erro}</p>}
      {!falha && !estado.erro && estado.avisos.map((a) => <p key={a} className="campo-ajuda busca-automatica-erro">⚠ {a}</p>)}
    </div>
  );
}
