/** Configurações › Integrações › Granola (amostra aprovada por Eduardo em 23/10/2026): a situação da busca e a
 * fila "Precisa de você", com as notas em que nenhum participante casou com um contato do CRM (ou casou com mais de
 * um). A pessoa escolhe onde a nota entra, ou descarta: descartada, o resumo e a transcrição saem do CRM. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { NotaDoGranola, SituacaoDoGranola } from "../api/tipos";
import { data, dataHora } from "../formato";
import { Carregando, Erro } from "./estados";

function hora(iso: string): string {
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function FilaDoGranola({ rodada = 0 }: { rodada?: number }) {
  const [situacao, definirSituacao] = useState<SituacaoDoGranola | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [escolhas, definirEscolhas] = useState<Record<number, string>>({});
  const [ocupada, definirOcupada] = useState<number | null>(null);
  const [falha, definirFalha] = useState<string | null>(null);

  const carregar = () => {
    definirErro(null);
    api.situacaoDoGranola().then(definirSituacao, (f) =>
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao abrir a busca do Granola."));
  };
  useEffect(carregar, [rodada]);

  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={carregar} />;
  if (!situacao) return <Carregando rotulo="Abrindo a busca do Granola" />;

  const agir = async (n: NotaDoGranola, acao: () => Promise<SituacaoDoGranola>) => {
    definirOcupada(n.id);
    definirFalha(null);
    try {
      definirSituacao(await acao());
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Não consegui. Tente de novo.");
    } finally {
      definirOcupada(null);
    }
  };
  const aplicar = (n: NotaDoGranola) => {
    const id = Number(escolhas[n.id]);
    void agir(n, () => api.destinoDaNotaDoGranola(n.id, n.tipo === "Reunião com o lead" ? { oportunidade_id: id } : { grupo_id: id }));
  };
  const descartar = (n: NotaDoGranola) => {
    if (window.confirm(`Descartar a nota “${n.titulo}”? O resumo e a transcrição saem do CRM e a nota não volta na busca.`)) {
      void agir(n, () => api.descartarDaFilaDoGranola(n.id));
    }
  };

  const u = situacao.ultima;
  let linha: string;
  if (!situacao.ligada) linha = "Busca desligada: ligue e salve a chave para as notas chegarem sozinhas.";
  else if (!u) linha = "A primeira busca roda em instantes.";
  else if (u.erro) linha = `Última busca: ${dataHora(u.em)} · ✗ ${u.erro}`;
  else linha = `Última busca: ${dataHora(u.em)}${situacao.proxima ? ` · próxima às ${hora(situacao.proxima)}` : ""} · ${
    u.novas === 0 ? "nenhuma nota nova" : `${u.novas} nota${u.novas === 1 ? " nova" : "s novas"}: ${u.a_usar} ${
      u.a_usar === 1 ? "entrou sozinha" : "entraram sozinhas"}, ${u.precisam} precisa${u.precisam === 1 ? "" : "m"} de você`}.`;

  return (
    <div className="granola-situacao" role="group" aria-labelledby="t-granola-situacao">
      <strong id="t-granola-situacao" className="recebimento-titulo">Situação da busca</strong>
      <span className="campo-ajuda" role="status" style={{ margin: 0 }}>{linha}</span>
      {u?.aviso && <span className="campo-ajuda" style={{ margin: 0 }}>⚠ {u.aviso}</span>}

      <strong className="recebimento-titulo">Precisa de você ({situacao.precisam.length})</strong>
      {situacao.precisam.length === 0 ? (
        <span className="campo-ajuda" style={{ margin: 0 }}>Nada esperando você. Toda nota que chegou achou o seu lugar.</span>
      ) : (
        <>
          <span className="campo-ajuda" style={{ margin: 0 }}>
            O CRM não achou um lugar só para estas notas pelos participantes. Escolha onde cada uma entra ou descarte.
          </span>
          <div className="granola-fila-rolagem">
          <table className="tabela granola-fila">
            <thead>
              <tr><th scope="col">Reunião</th><th scope="col">Data</th><th scope="col">Participantes</th><th scope="col">Entrar em</th></tr>
            </thead>
            <tbody>
              {situacao.precisam.map((n) => {
                const lead = n.tipo === "Reunião com o lead";
                const opcoes = lead ? situacao.oportunidades : situacao.grupos;
                return (
                  <tr key={n.id}>
                    <td>
                      {n.titulo}
                      <span className="campo-ajuda" style={{ display: "block", margin: 0 }}>{n.tipo} · {n.motivo}</span>
                    </td>
                    <td className="sem-quebra">{data(n.data)}</td>
                    <td>{n.participantes ?? "—"}</td>
                    <td>
                      <div className="granola-fila-escolha">
                        <select className="selecao" aria-label={`Entrar em: ${n.titulo}`} value={escolhas[n.id] ?? ""}
                          onChange={(e) => definirEscolhas((x) => ({ ...x, [n.id]: e.target.value }))}>
                          <option value="">{lead ? "Escolha a oportunidade…" : "Escolha o cliente…"}</option>
                          {opcoes.map((o) => <option key={o.id} value={o.id}>{o.nome}</option>)}
                        </select>
                        <span className="acoes">
                          <button type="button" className="botao" disabled={!escolhas[n.id] || ocupada === n.id} onClick={() => aplicar(n)}>
                            Aplicar
                          </button>{" "}
                          <button type="button" className="botao botao-texto-perigo" disabled={ocupada === n.id} onClick={() => descartar(n)}>
                            Descartar
                          </button>
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
        </>
      )}
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
    </div>
  );
}
