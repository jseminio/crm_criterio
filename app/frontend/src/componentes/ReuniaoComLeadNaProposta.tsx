/** A reunião com o lead alimenta a proposta (amostra aprovada por Eduardo em 10/10/2026).
 *
 * Cola-se o **resumo** da nota do Granola feita com o template [Potencial Cliente]; a IA sugere a
 * contextualização e os campos do perfil que a reunião trouxe, cada um com a frase de onde saiu. Nada
 * muda na proposta até "Aplicar": a pessoa escolhe entre a sugestão e o texto atual e marca os campos.
 * O questionário prevalece: campo que diverge vem desmarcado, com ⚠. Do lead guarda-se só o resumo,
 * com a ciência de que a reunião foi gravada. Quando houver a API do Granola, o campo de colar vira
 * "Buscar no Granola" e o resto não muda.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { AbaDaProposta, ReuniaoComLead, SugestaoDoContexto, TipoDeMatriz } from "../api/tipos";
import { data } from "../formato";
import { CampoDeData } from "./CampoDeData";

/** O mesmo mínimo do servidor: menos que isso não é um resumo de reunião. */
export const MINIMO_DO_RESUMO = 80;

const hoje = () => new Date().toLocaleDateString("sv");

type Campos = { data: string; participantes: string; link: string; resumo: string; ciencia: boolean };
const VAZIO = (): Campos => ({ data: hoje(), participantes: "", link: "", resumo: "", ciencia: false });

function Guardada({ r, aoColarOutra, podeEditar }: { r: ReuniaoComLead; aoColarOutra: () => void; podeEditar: boolean }) {
  const [vendo, definirVendo] = useState(false);
  return (
    <div className="reuniao-lead-guardada">
      <div className="reuniao-lead-linha">
        <span className="etiqueta etiqueta-ganho">✓ Reunião guardada</span>
        <span>
          {data(r.data)}
          {r.participantes ? ` · ${r.participantes}` : ""} · resumo guardado · ciência da gravação ✓
          {r.link_do_granola && (
            <>
              {" · "}
              <a href={r.link_do_granola} target="_blank" rel="noreferrer">nota no Granola</a>
            </>
          )}
        </span>
        <button type="button" className="link-de-tabela" aria-expanded={vendo} onClick={() => definirVendo((v) => !v)}>
          {vendo ? "Esconder o resumo" : "Ver o resumo"}
        </button>
        {podeEditar && (
          <button type="button" className="link-de-tabela" onClick={aoColarOutra}>Colar outra reunião</button>
        )}
      </div>
      {vendo && <pre className="reuniao-lead-resumo">{r.resumo_do_granola}</pre>}
    </div>
  );
}

export function ReuniaoComLeadNaProposta({
  oportunidadeId,
  matriz,
  aba,
  contextualizacaoAtual,
  podeEditar,
  aoAplicar,
}: {
  oportunidadeId: number;
  matriz: TipoDeMatriz;
  aba: AbaDaProposta;
  contextualizacaoAtual: string;
  podeEditar: boolean;
  /** A aba nova (perfil já com a reunião) e a contextualização escolhida; `null` mantém a atual. */
  aoAplicar: (aba: AbaDaProposta, contextualizacao: string | null) => void;
}) {
  const reunioes = aba.reunioes_com_o_lead ?? [];
  const [colando, definirColando] = useState(reunioes.length === 0);
  const [campos, definirCampos] = useState<Campos>(VAZIO);
  const [sugestao, definirSugestao] = useState<SugestaoDoContexto | null>(null);
  const [usarSugestao, definirUsarSugestao] = useState(true);
  const [marcados, definirMarcados] = useState<Set<string>>(new Set());
  const [ocupado, definirOcupado] = useState<"sugerindo" | "aplicando" | null>(null);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  const mudar = <K extends keyof Campos>(campo: K, valor: Campos[K]) => definirCampos((c) => ({ ...c, [campo]: valor }));
  const curto = campos.resumo.trim().length < MINIMO_DO_RESUMO;

  const sugerir = async () => {
    definirOcupado("sugerindo");
    definirFalha(null);
    definirFeito(null);
    try {
      const s = await api.sugerirContextoDaReuniao(oportunidadeId, {
        matriz, data: campos.data, participantes: campos.participantes || undefined, resumo: campos.resumo,
      });
      definirSugestao(s);
      definirUsarSugestao(s.contextualizacao.trim() !== "");
      definirMarcados(new Set(s.perfil.filter((p) => !p.diverge).map((p) => p.campo)));
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui sugerir. Tente de novo.");
    } finally {
      definirOcupado(null);
    }
  };

  const aplicar = async () => {
    if (!sugestao) return;
    definirOcupado("aplicando");
    definirFalha(null);
    const contextualizacao = usarSugestao && sugestao.contextualizacao.trim() ? sugestao.contextualizacao : null;
    try {
      const nova = await api.guardarReuniaoComLead(oportunidadeId, {
        data: campos.data, participantes: campos.participantes || undefined, link_do_granola: campos.link || undefined,
        resumo: campos.resumo, ciencia_da_gravacao: campos.ciencia, contextualizacao,
        perfil: Object.fromEntries(sugestao.perfil.filter((p) => marcados.has(p.campo)).map((p) => [p.campo, p.valor])),
      });
      definirSugestao(null);
      definirCampos(VAZIO());
      definirColando(false);
      definirFeito("Reunião guardada e aplicada à proposta. Revise a contextualização e o perfil abaixo.");
      aoAplicar(nova, contextualizacao);
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui guardar a reunião. Tente de novo.");
    } finally {
      definirOcupado(null);
    }
  };

  const alternar = (campo: string) =>
    definirMarcados((m) => {
      const n = new Set(m);
      if (n.has(campo)) n.delete(campo);
      else n.add(campo);
      return n;
    });

  return (
    <div className="reuniao-lead">
      {reunioes.length > 0 && (
        <Guardada r={reunioes[0]} podeEditar={podeEditar} aoColarOutra={() => { definirColando(true); definirFeito(null); }} />
      )}
      {feito && <p className="recado" role="status">✓ {feito}</p>}

      {colando && podeEditar && (
        <fieldset className="reuniao-lead-colar">
          <legend>Reunião com o lead (Granola)</legend>
          <p className="campo-ajuda">
            Cole o <strong>resumo</strong> da nota feita com o template [Potencial Cliente]. Não cole a transcrição: do
            lead, o CRM guarda só o resumo.
          </p>
          <div className="proposta-grade">
            <div className="campo">
              <label className="campo-rotulo" htmlFor="rl-data">Data da reunião</label>
              <CampoDeData id="rl-data" value={campos.data} aoMudar={(v) => mudar("data", v)} />
            </div>
            <label className="campo">
              <span className="campo-rotulo">Participantes</span>
              <input className="entrada" maxLength={300} placeholder="Ex.: Ana (sócia), Carlos (financeiro)"
                value={campos.participantes} onChange={(e) => mudar("participantes", e.target.value)} />
            </label>
            <label className="campo">
              <span className="campo-rotulo">Link da nota no Granola (opcional)</span>
              <input className="entrada" maxLength={400} placeholder="https://notes.granola.ai/…"
                value={campos.link} onChange={(e) => mudar("link", e.target.value)} />
            </label>
          </div>
          <label className="campo">
            <span className="campo-rotulo">Resumo da nota [Potencial Cliente]</span>
            <textarea className="entrada" rows={6} maxLength={30000} value={campos.resumo}
              onChange={(e) => mudar("resumo", e.target.value)} />
          </label>
          <label className="reuniao-lead-ciencia">
            <input type="checkbox" checked={campos.ciencia} onChange={(e) => mudar("ciencia", e.target.checked)} />
            <span>
              O lead foi avisado de que a reunião foi gravada <span className="campo-ajuda">(obrigatório para guardar)</span>
            </span>
          </label>
          <div className="proposta-acoes">
            <button type="button" className="botao botao-secundario" disabled={curto || ocupado !== null}
              onClick={() => void sugerir()}>
              {ocupado === "sugerindo" ? "Lendo a reunião…" : "Sugerir contexto e perfil com a IA"}
            </button>
            <span className="campo-ajuda">
              {ocupado === "sugerindo"
                ? "· pode levar até um minuto"
                : curto
                  ? `· cole o resumo inteiro (mínimo de ${MINIMO_DO_RESUMO} caracteres)`
                  : "· a IA só sugere; nada muda na proposta até você aplicar"}
            </span>
            {reunioes.length > 0 && !sugestao && (
              <button type="button" className="link-de-tabela" onClick={() => { definirColando(false); definirCampos(VAZIO()); }}>
                cancelar
              </button>
            )}
          </div>
        </fieldset>
      )}

      {sugestao && (
        <div className="reuniao-lead-sugestao" aria-label="Sugestão da IA">
          <h4><span className="etiqueta etiqueta-andamento">Sugestão da IA</span> Contextualização</h4>
          {sugestao.contextualizacao.trim() ? (
            <div className="reuniao-lead-compara">
              <label className="reuniao-lead-opcao">
                <input type="radio" name="rl-contexto" checked={usarSugestao} onChange={() => definirUsarSugestao(true)} />
                <span>
                  <strong>Usar a sugestão da reunião</strong>
                  <span className="reuniao-lead-texto">{sugestao.contextualizacao}</span>
                </span>
              </label>
              <label className="reuniao-lead-opcao">
                <input type="radio" name="rl-contexto" checked={!usarSugestao} onChange={() => definirUsarSugestao(false)} />
                <span>
                  <strong>Manter a atual</strong>
                  <span className="reuniao-lead-texto campo-ajuda">{contextualizacaoAtual}</span>
                </span>
              </label>
            </div>
          ) : (
            <p className="campo-ajuda">A reunião não trouxe o bastante para uma contextualização: fica a atual.</p>
          )}

          <h4><span className="etiqueta etiqueta-andamento">Sugestão da IA</span> Perfil do cliente</h4>
          {sugestao.perfil.length === 0 ? (
            <p className="campo-ajuda">A reunião não informou nenhum campo do perfil.</p>
          ) : (
            <table className="tabela reuniao-lead-perfil">
              <thead>
                <tr><th scope="col">Usar</th><th scope="col">Campo</th><th scope="col">Hoje</th><th scope="col">Na reunião</th></tr>
              </thead>
              <tbody>
                {sugestao.perfil.map((p) => (
                  <tr key={p.campo}>
                    <td>
                      <input type="checkbox" aria-label={`Usar ${p.rotulo} da reunião`} checked={marcados.has(p.campo)}
                        onChange={() => alternar(p.campo)} />
                    </td>
                    <td>{p.rotulo}</td>
                    <td className={p.atual === "N/D" ? "campo-ajuda" : undefined}>{p.atual}</td>
                    <td>
                      {p.diverge && <span className="etiqueta etiqueta-espera">⚠ diverge</span>} {p.valor}
                      {p.trecho && <span className="celula-fonte">“{p.trecho}”</span>}
                      {p.diverge && <span className="celula-fonte">O que já está prevalece; marque só se a reunião estiver certa.</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {sugestao.nao_apareceu.length > 0 && (
            <p className="campo-ajuda"><strong>Não apareceu na reunião:</strong> {sugestao.nao_apareceu.join(", ")}. Seguem como estão.</p>
          )}
          {sugestao.para_a_carta.length > 0 && (
            <>
              <p className="campo-ajuda"><strong>Para a carta, se quiser usar:</strong></p>
              <ul className="reuniao-lead-carta">
                {sugestao.para_a_carta.map((i) => <li key={i}>{i}</li>)}
              </ul>
            </>
          )}

          <div className="proposta-acoes">
            <button type="button" className="botao botao-secundario" disabled={!campos.ciencia || ocupado !== null}
              onClick={() => void aplicar()}>
              {ocupado === "aplicando" ? "Aplicando…" : "Aplicar à proposta"}
            </button>
            <button type="button" className="link-de-tabela" disabled={ocupado !== null} onClick={() => definirSugestao(null)}>
              Descartar a sugestão
            </button>
            <span className="campo-ajuda">
              {!campos.ciencia
                ? "· marque, acima, que o lead foi avisado da gravação"
                : sugestao.custo_usd
                  ? `· custo estimado US$ ${sugestao.custo_usd.replace(".", ",")}`
                  : ""}
            </span>
          </div>
        </div>
      )}
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
    </div>
  );
}
