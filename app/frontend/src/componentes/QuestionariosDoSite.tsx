/** Questionários para proposta enviados pelos clientes no site (01/10/2026).
 *
 * "Buscar questionários" traz o que ainda não entrou; a tabela diz o que o CRM fez com cada um.
 * Quando já há oportunidade em aberto para o CNPJ, o CRM não duplica: o questionário fica
 * "precisa de você" até alguém escolher anexar ou criar nova. Estado sempre com palavra (PAD-002).
 */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { QuestionarioResumo } from "../api/tipos";
import { cnpj, dataHora } from "../formato";
import { Etiqueta } from "./Etiqueta";

const PRECISA = "Precisa de você";

function etiquetaDe(q: QuestionarioResumo): string {
  if (q.situacao === PRECISA) return "precisa de você";
  return q.cliente_novo ? "cliente novo" : "empresa já no CRM";
}

function origemDoPorte(q: QuestionarioResumo): string {
  if (!q.porte_crm) return "sem volumes informados";
  if (!q.porte_site || q.porte_site === q.porte_crm) return "igual ao do questionário";
  return `questionário dizia ${q.porte_site}: a régua do CRM vale`;
}

export function usarQuestionarios(aoMudar: () => void) {
  const [linhas, definirLinhas] = useState<QuestionarioResumo[]>([]);
  const [resumo, definirResumo] = useState<{ novos: number; avisos: string[]; buscadoEm: string } | null>(null);
  const [buscando, definirBuscando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  // Ao abrir o Funil, os que ainda precisam de alguém continuam à vista.
  useEffect(() => {
    api.questionarios()
      .then((todos) => definirLinhas(todos.filter((q) => q.situacao === PRECISA)))
      .catch(() => undefined);
  }, []);

  const buscar = async () => {
    definirBuscando(true);
    definirErro(null);
    try {
      const r = await api.buscarQuestionarios();
      definirResumo({ novos: r.novos.length, avisos: r.avisos, buscadoEm: r.buscado_em });
      definirLinhas((antes) => [...r.novos, ...antes.filter((a) => !r.novos.some((n) => n.id === a.id))]);
      if (r.novos.length) aoMudar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao buscar os questionários.");
    } finally {
      definirBuscando(false);
    }
  };

  const resolver = async (id: number, acao: "anexar" | "criar") => {
    definirErro(null);
    try {
      const atualizado = await api.resolverQuestionario(id, acao);
      definirLinhas((antes) => antes.map((q) => (q.id === id ? atualizado : q)));
      aoMudar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao resolver o questionário.");
    }
  };

  return { linhas, resumo, buscando, erro, buscar, resolver };
}

export type EstadoDosQuestionarios = ReturnType<typeof usarQuestionarios>;

export function BotaoBuscarQuestionarios({ estado }: { estado: EstadoDosQuestionarios }) {
  return (
    <button type="button" className="botao botao-secundario" onClick={estado.buscar} disabled={estado.buscando}>
      {estado.buscando ? "Buscando…" : "Buscar questionários"}
    </button>
  );
}

export function QuestionariosDoSite({ estado, aoAbrir }: { estado: EstadoDosQuestionarios; aoAbrir: (oportunidadeId: number) => void }) {
  const { linhas, resumo, erro } = estado;
  if (!resumo && !erro && linhas.length === 0) return null;
  const pendentes = linhas.filter((q) => q.situacao === PRECISA).length;
  return (
    <section className="questionarios-do-site" aria-label="Questionários do site">
      {erro && <p className="periodo-erro" role="alert">{erro}</p>}
      {resumo && (
        <p className="recado" role="status">
          {resumo.novos === 0 ? (
            <>Nenhum questionário novo no site. </>
          ) : (
            <><strong>{resumo.novos} questionário{resumo.novos > 1 ? "s" : ""} novo{resumo.novos > 1 ? "s" : ""}.</strong>{" "}</>
          )}
          {pendentes > 0 && `${pendentes} precisa${pendentes > 1 ? "m" : ""} de você. `}
          <span className="campo-ajuda">Busca de {dataHora(resumo.buscadoEm)}.</span>
        </p>
      )}
      {resumo?.avisos.map((a) => <p key={a} className="campo-ajuda">⚠ {a}</p>)}
      {linhas.length > 0 && (
        <div className="tabela-rolagem">
          <table className="tabela" aria-label="Questionários recebidos">
            <thead>
              <tr>
                <th scope="col">Recebido em</th>
                <th scope="col">Empresa e contato</th>
                <th scope="col">O que o CRM fez</th>
                <th scope="col">Porte</th>
                <th scope="col" aria-label="Ações" />
              </tr>
            </thead>
            <tbody>
              {linhas.map((q) => (
                <tr key={q.id}>
                  <td>{dataHora(q.recebido_em)}</td>
                  <td>
                    {q.razao_social}
                    <span className="celula-fonte">
                      CNPJ {cnpj(q.cnpj)} · {q.contato_nome}{q.contato_cargo ? `, ${q.contato_cargo}` : ""}
                    </span>
                  </td>
                  <td>
                    <Etiqueta texto={etiquetaDe(q)} />
                    <span className="celula-fonte">{q.o_que_fez}</span>
                  </td>
                  <td>
                    {q.porte_crm ?? "—"}
                    <span className="celula-fonte">{origemDoPorte(q)}</span>
                  </td>
                  <td>
                    {q.situacao === PRECISA ? (
                      <>
                        <button type="button" className="link-de-tabela" onClick={() => estado.resolver(q.id, "anexar")}>
                          Anexar à existente
                        </button>
                        {" · "}
                        <button type="button" className="link-de-tabela" onClick={() => estado.resolver(q.id, "criar")}>
                          Criar nova
                        </button>
                      </>
                    ) : q.oportunidade_id ? (
                      <button type="button" className="link-de-tabela" onClick={() => aoAbrir(q.oportunidade_id!)}>
                        Abrir oportunidade
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="campo-ajuda">
        A busca só lê o site; quem envia é o cliente. Questionário já importado não volta. O PDF de cada um fica
        na oportunidade, na aba "Volumetria e porte".
      </p>
    </section>
  );
}
