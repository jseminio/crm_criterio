/** Mesclar o questionário com uma oportunidade aberta (amostra aprovada por Eduardo em 15/10/2026): o card aberto a
 * partir do lead recebe o questionário em vez de ganhar uma duplicada. Sugestões do CRM primeiro, com o motivo; busca
 * livre entre as abertas; a prévia diz o que vai para o card, a fusão de grupos e a duplicada. "Mesclar" confirma. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { OportunidadeResumo, PreviaDaMescla, SugestaoDeMescla } from "../api/tipos";
import { cnpj, data, dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";
import { PainelLateral } from "./PainelLateral";

const ABERTAS = ["Enviar proposta", "Em avaliação pela empresa", "On hold"];

export interface QuestionarioParaMesclar {
  id: number;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj: string;
  recebido_em: string;
  /** A oportunidade que o CRM já achou (regra D ou mesmo CNPJ), para vir marcada. */
  oportunidade_em_aberto_id: number | null;
}

function Opcao({ id, titulo, detalhe, escolhida, aoEscolher }: {
  id: number; titulo: string; detalhe: string; escolhida: boolean; aoEscolher: (id: number) => void;
}) {
  return (
    <label className={`mescla-opcao ${escolhida ? "mescla-opcao-escolhida" : ""}`}>
      <input type="radio" name="mescla-destino" checked={escolhida} onChange={() => aoEscolher(id)} />
      <span><strong>{titulo}</strong><span className="celula-fonte">{detalhe}</span></span>
    </label>
  );
}

function Previa({ p, trocar, aoTrocar, excluir, aoExcluir }: {
  p: PreviaDaMescla; trocar: Set<string>; aoTrocar: (campo: string) => void; excluir: boolean; aoExcluir: (v: boolean) => void;
}) {
  if (p.recusa) return <p className="estado-texto estado-erro" role="alert">✗ {p.recusa}</p>;
  return (
    <>
      <h3 className="numero-rotulo">O que vai para o card</h3>
      {p.campos.length === 0 ? <p className="numero-estado">O questionário não traz nada novo para este card.</p> : (
        <table className="tabela" aria-label="O que vai para o card">
          <thead><tr><th>Campo</th><th>No card</th><th>No questionário</th><th>Fica</th></tr></thead>
          <tbody>
            {p.campos.map((c) => (
              <tr key={c.campo}>
                <td>{c.rotulo}</td>
                <td>{c.no_card ?? "—"}</td>
                <td>{c.campo === "empresa_id" ? cnpj(c.no_questionario) : c.no_questionario}</td>
                <td>
                  {c.acao === "preenche" && <span className="mescla-preenche">preenche</span>}
                  {c.acao === "igual" && "igual"}
                  {c.acao === "fica" && "fica o do card"}
                  {c.acao === "diferente" && (
                    <label className="mescla-troca">
                      <input type="checkbox" checked={trocar.has(c.campo)} onChange={() => aoTrocar(c.campo)} />
                      {trocar.has(c.campo) ? `usar ${c.no_questionario}` : `diferente: fica ${c.no_card}`}
                    </label>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="campo-ajuda">Preço, captador, temperatura, serviço e datas do vendedor nunca mudam.</p>
      <div className="mescla-grupos">
        {p.cnpj_novo_no_grupo && <p>O CNPJ será cadastrado no grupo “{p.cnpj_novo_no_grupo}”, o do card.</p>}
        {p.fusao_de && (
          <p>O grupo “{p.fusao_de}”, criado pelo questionário, será <strong>fundido</strong> no grupo “{p.fusao_em}”
            (empresa e contato vão junto). Pode ser desfeito em Grupos › Fusões feitas.</p>
        )}
        {p.duplicada_id !== null && (p.duplicada_recusa ? (
          <p>A oportunidade “{p.duplicada_nome}” fica: {p.duplicada_recusa}</p>
        ) : (
          <label className="mescla-troca">
            <input type="checkbox" checked={excluir} onChange={(e) => aoExcluir(e.target.checked)} />
            Excluir a oportunidade “{p.duplicada_nome}” que o questionário criou
            {p.duplicada_intocada ? " (ninguém mexeu nela)" : " — atenção: alguém já mexeu nela"}
          </label>
        ))}
      </div>
    </>
  );
}

export function MesclarQuestionario({ q, aoFechar, aoMesclar }: {
  q: QuestionarioParaMesclar; aoFechar: () => void; aoMesclar: (texto: string) => void;
}) {
  const sugestoes = usarDados<SugestaoDeMescla[]>(() => api.sugestoesDeMescla(q.id), [q.id]);
  const [busca, definirBusca] = useState("");
  const [achadas, definirAchadas] = useState<OportunidadeResumo[]>([]);
  const [destino, definirDestino] = useState<number | null>(q.oportunidade_em_aberto_id);
  const [previa, definirPrevia] = useState<PreviaDaMescla | null>(null);
  const [trocar, definirTrocar] = useState<Set<string>>(new Set());
  const [excluir, definirExcluir] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const [mesclando, definirMesclando] = useState(false);

  useEffect(() => {
    if (destino === null && sugestoes.dados && sugestoes.dados.length > 0) definirDestino(sugestoes.dados[0].oportunidade_id);
  }, [sugestoes.dados, destino]);

  useEffect(() => {
    const termo = busca.trim();
    if (termo.length < 3) { definirAchadas([]); return; }
    const t = setTimeout(() => {
      api.oportunidades({ busca: termo, situacao: ABERTAS }).then((r) => definirAchadas(r.itens.slice(0, 8))).catch(() => definirAchadas([]));
    }, 300);
    return () => clearTimeout(t);
  }, [busca]);

  useEffect(() => {
    definirPrevia(null);
    definirTrocar(new Set());
    if (destino === null) return;
    let vivo = true;
    api.previaDaMescla(q.id, destino).then((p) => {
      if (!vivo) return;
      definirPrevia(p);
      definirExcluir(p.duplicada_intocada && !p.duplicada_recusa);
    }).catch((f) => vivo && definirErro(f instanceof ErroDaApi ? f.message : "Falha ao montar a prévia."));
    return () => { vivo = false; };
  }, [q.id, destino]);

  const alternar = (campo: string) => definirTrocar((atual) => {
    const novo = new Set(atual);
    if (novo.has(campo)) novo.delete(campo); else novo.add(campo);
    return novo;
  });

  async function mesclar() {
    if (destino === null) return;
    definirErro(null);
    definirMesclando(true);
    try {
      const r = await api.mesclarQuestionario(q.id, {
        oportunidade_id: destino, usar_do_questionario: [...trocar], excluir_duplicada: excluir,
      });
      aoMesclar(r.o_que_fez);
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao mesclar.");
    } finally {
      definirMesclando(false);
    }
  }

  const sugeridas = new Set((sugestoes.dados ?? []).map((s) => s.oportunidade_id));
  const pode = destino !== null && previa !== null && !previa.recusa && !mesclando;
  return (
    <PainelLateral
      titulo="Mesclar o questionário com uma oportunidade"
      subtitulo={`${q.nome_fantasia || q.razao_social} · CNPJ ${cnpj(q.cnpj)} · recebido em ${dataHora(q.recebido_em)}`}
      aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>Cancelar</button>
          <button type="button" className="botao botao-primario" onClick={() => void mesclar()} disabled={!pode}>
            {mesclando ? "Mesclando…" : "Mesclar"}
          </button>
        </>
      }
    >
      <h3 className="numero-rotulo">Sugestões do CRM</h3>
      {sugestoes.carregando && <Carregando rotulo="Procurando a oportunidade deste questionário" />}
      {sugestoes.erro && <Erro mensagem={sugestoes.erro} aoTentarDeNovo={sugestoes.recarregar} />}
      {sugestoes.dados && sugestoes.dados.length === 0 && (
        <p className="numero-estado">O CRM não achou nenhuma provável. Busque abaixo.</p>
      )}
      <div className="mescla-opcoes" role="radiogroup" aria-label="Oportunidade de destino">
        {(sugestoes.dados ?? []).map((s) => (
          <Opcao key={s.oportunidade_id} id={s.oportunidade_id} escolhida={destino === s.oportunidade_id} aoEscolher={definirDestino}
            titulo={`${s.grupo_nome ?? "?"} · ${s.servico ?? s.nome}`}
            detalhe={`${s.situacao}${s.captador ? ` · captador ${s.captador}` : ""}${s.data_colocacao ? ` · aberta em ${data(s.data_colocacao)}` : ""} · ${s.motivo}`} />
        ))}
        {achadas.filter((o) => !sugeridas.has(o.id)).map((o) => (
          <Opcao key={o.id} id={o.id} escolhida={destino === o.id} aoEscolher={definirDestino}
            titulo={`${o.grupo_nome ?? "?"} · ${o.servico ?? o.nome}`}
            detalhe={`${o.situacao}${o.captador ? ` · captador ${o.captador}` : ""} · da busca`} />
        ))}
      </div>
      <label className="campo-rotulo" htmlFor="mescla-busca">Buscar outra oportunidade aberta</label>
      <input id="mescla-busca" className="entrada entrada-busca" type="search" value={busca}
        onChange={(e) => definirBusca(e.target.value)} placeholder="Grupo, CNPJ, contato ou proposta" />
      {destino !== null && !previa && !erro && <Carregando rotulo="Montando a prévia" />}
      {previa && <Previa p={previa} trocar={trocar} aoTrocar={alternar} excluir={excluir} aoExcluir={definirExcluir} />}
      {erro && <p className="estado-texto estado-erro" role="alert">✗ {erro}</p>}
    </PainelLateral>
  );
}

/** O botão que abre o painel; serve à lista de questionários, à Agenda e ao Funil. */
export function BotaoMesclar({ q, aoMesclar, classe = "link-de-tabela" }: {
  q: QuestionarioParaMesclar; aoMesclar: (texto: string) => void; classe?: string;
}) {
  const [aberto, definirAberto] = useState(false);
  return (
    <>
      <button type="button" className={classe} onClick={(e) => { e.stopPropagation(); definirAberto(true); }}>
        Mesclar com existente
      </button>
      {aberto && (
        <MesclarQuestionario q={q} aoFechar={() => definirAberto(false)}
          aoMesclar={(texto) => { definirAberto(false); aoMesclar(texto); }} />
      )}
    </>
  );
}
