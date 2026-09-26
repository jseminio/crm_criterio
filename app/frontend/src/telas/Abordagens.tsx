/** Abordagens — a fila do agente SDR (26/09/2026, amostra aprovada por Eduardo).
 *
 * O agente prepara a ficha e o rascunho; **nada sai sem aprovação**. A tela só
 * mostra "Aprovar" como ação principal quando o rascunho está salvo e todas as
 * conferências da API estão ok — a regra mora no servidor, a tela só a exibe.
 */

import { useEffect, useMemo, useState, type ReactElement } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { AbordagemDetalhe, AbordagemResumo, Conferencia } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { data } from "../formato";
import { usarDados } from "../usarDados";

const MESES = [
  "janeiro", "fevereiro", "março", "abril", "maio", "junho",
  "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
];
const SITUACOES = [
  "A preparar", "Bloqueada", "Pesquisando", "Aguardando aprovação",
  "Aprovada", "Enviada", "Erro", "Descartada",
];
const EDITAVEIS = ["A preparar", "Bloqueada", "Aguardando aprovação", "Erro"];
/** Enquanto o agente pesquisa, a tela pergunta de novo a cada tantos ms. */
const INTERVALO_DE_ATUALIZACAO = 4000;

export function nomeDoMes(mes: string): string {
  const [ano, numero] = mes.split("-");
  return `${MESES[Number(numero) - 1]}/${ano.slice(2)}`;
}

/** O mês de hoje, se tiver contas; senão o próximo que tiver; senão o último. */
export function mesPadrao(meses: string[], hoje = new Date()): string | null {
  if (meses.length === 0) return null;
  const atual = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}`;
  return meses.includes(atual) ? atual : (meses.find((m) => m > atual) ?? meses[meses.length - 1]);
}

function mensagemDe(falha: unknown): string {
  return falha instanceof ErroDaApi ? falha.message : "Falha inesperada.";
}

function ListaDeConferencias({ conferencias }: { conferencias: Conferencia[] }) {
  return (
    <ul className="conferencias">
      {conferencias.map((c) => (
        <li key={c.regra} className={c.ok ? "conferencia-ok" : "conferencia-atencao"}>
          <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
            {c.ok ? (
              <path d="M3 8.5l3 3 7-7" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" strokeLinejoin="round" />
            ) : (
              <path d="M8 2.5l6 11H2zM8 6.5v3.2M8 11.6v.2" fill="none" stroke="currentColor"
                strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
            )}
          </svg>
          <span>
            <strong>{c.ok ? "Ok" : "Atenção"}</strong> · {c.texto}
          </span>
        </li>
      ))}
    </ul>
  );
}

interface Rascunho {
  quem_apresenta: string;
  contexto: string;
  canal: "E-mail" | "WhatsApp";
  destinatario: string;
  assunto: string;
  mensagem: string;
}

function rascunhoDe(a: AbordagemDetalhe): Rascunho {
  return {
    quem_apresenta: a.quem_apresenta ?? "",
    contexto: a.contexto ?? "",
    canal: a.canal,
    destinatario: a.destinatario ?? "",
    assunto: a.assunto ?? "",
    mensagem: a.mensagem ?? "",
  };
}

function PainelDaAbordagem({ id, aoMudar }: { id: number; aoMudar: () => void }) {
  const detalhe = usarDados(() => api.abordagem(id), [id]);
  const a = detalhe.dados;
  const [rascunho, definirRascunho] = useState<Rascunho | null>(null);
  const [instrucao, definirInstrucao] = useState("");
  const [diagnostico, definirDiagnostico] = useState("");
  const [confirmandoDescarte, definirConfirmandoDescarte] = useState(false);
  const [ocupado, definirOcupado] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  // O rascunho local recomeça quando o servidor muda a abordagem (nova versão,
  // aprovação), não a cada releitura igual.
  const assinatura = a ? `${a.id}|${a.versao}|${a.situacao}|${a.atualizado_em}` : "";
  useEffect(() => {
    if (!a) return;
    definirRascunho(rascunhoDe(a));
    definirDiagnostico(a.diagnostico_agendado_em ?? "");
    definirConfirmandoDescarte(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assinatura]);

  const pesquisando = a?.situacao === "Pesquisando";
  useEffect(() => {
    if (!pesquisando) return;
    const relogio = window.setInterval(detalhe.recarregar, INTERVALO_DE_ATUALIZACAO);
    return () => window.clearInterval(relogio);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pesquisando]);

  if (detalhe.erro && !a) {
    return (
      <aside className="abordagem-painel">
        <Erro mensagem={detalhe.erro} aoTentarDeNovo={detalhe.recarregar} />
      </aside>
    );
  }
  if (!a || !rascunho) {
    return (
      <aside className="abordagem-painel">
        <Carregando rotulo="Abrindo a conta" />
      </aside>
    );
  }

  const original = rascunhoDe(a);
  const mudancas = Object.fromEntries(
    Object.entries(rascunho).filter(([campo, valor]) => valor !== original[campo as keyof Rascunho]),
  );
  const alterado = Object.keys(mudancas).length > 0;
  const editavel = EDITAVEIS.includes(a.situacao);
  const descartavel = !["Enviada", "Descartada", "Pesquisando"].includes(a.situacao);
  const whatsapp = rascunho.canal === "WhatsApp";

  const executar = async (acao: () => Promise<unknown>) => {
    definirOcupado(true);
    definirErro(null);
    try {
      await acao();
      detalhe.recarregar();
      aoMudar();
    } catch (falha) {
      definirErro(mensagemDe(falha));
    } finally {
      definirOcupado(false);
    }
  };

  const mudar = (campo: keyof Rascunho, valor: string) =>
    definirRascunho((atual) => (atual ? { ...atual, [campo]: valor } : atual));
  const salvar = () => api.editarAbordagem(a.id, mudancas);

  let principal: ReactElement | null = null;
  const secundarias: ReactElement[] = [];
  if (a.situacao === "Aguardando aprovação") {
    principal = (
      <button type="button" className="botao botao-primario"
        disabled={ocupado || alterado || !a.pode_aprovar}
        onClick={() => executar(() => api.aprovarAbordagem(a.id))}>
        {whatsapp ? "Aprovar para envio no WhatsApp" : "Aprovar e enviar por e-mail"}
      </button>
    );
  } else if (["A preparar", "Bloqueada", "Erro"].includes(a.situacao)) {
    principal = (
      <button type="button" className="botao botao-primario"
        disabled={ocupado || !rascunho.quem_apresenta.trim()}
        onClick={() =>
          executar(async () => {
            if (alterado) await salvar();
            await api.prepararAbordagem(a.id);
          })
        }>
        {a.situacao === "Erro" ? "Tentar de novo" : "Preparar a ficha"}
      </button>
    );
  } else if (a.situacao === "Aprovada") {
    principal = (
      <button type="button" className="botao botao-primario" disabled={ocupado}
        onClick={() => executar(() => api.marcarAbordagemEnviada(a.id))}>
        Marcar como enviada
      </button>
    );
  } else if (a.situacao === "Enviada") {
    principal = (
      <button type="button" className="botao botao-primario"
        disabled={ocupado || diagnostico === (a.diagnostico_agendado_em ?? "")}
        onClick={() =>
          executar(() =>
            api.editarAbordagem(a.id, { diagnostico_agendado_em: diagnostico || null }),
          )
        }>
        Salvar o diagnóstico
      </button>
    );
  }
  if (editavel && alterado && a.situacao === "Aguardando aprovação") {
    secundarias.push(
      <button key="salvar" type="button" className="botao botao-secundario" disabled={ocupado}
        onClick={() => executar(salvar)}>
        Salvar alterações
      </button>,
    );
  }

  return (
    <aside className="abordagem-painel" aria-label={`${a.grupo_nome}: ficha e rascunho`}>
      <header className="painel-cabecalho">
        <div>
          <h2 className="painel-titulo">{a.grupo_nome}</h2>
          <p className="painel-subtitulo">
            Abordar em {nomeDoMes(a.mes)} · Quem apresenta: {a.quem_apresenta ?? "a definir"}
          </p>
        </div>
        <Etiqueta texto={a.situacao} />
      </header>

      <div className="painel-corpo">
        {erro && (
          <div className="aviso-de-movimento" role="alert">
            <span>{erro}</span>
            <button type="button" className="botao-icone" aria-label="Dispensar o aviso"
              onClick={() => definirErro(null)}>
              ✕
            </button>
          </div>
        )}

        {a.situacao === "Erro" && a.erro && (
          <div className="estado estado-erro" role="alert">
            <h3 className="estado-titulo">O agente não conseguiu preparar esta conta</h3>
            <p className="estado-texto">{a.erro}</p>
          </div>
        )}

        {pesquisando && (
          <div className="estado" role="status" aria-live="polite">
            <p className="estado-texto">
              O agente está pesquisando a conta e escrevendo o rascunho. Isso leva alguns
              minutos; a tela atualiza sozinha.
            </p>
          </div>
        )}

        <section className="abordagem-secao">
          <h3>Ficha da conta</h3>
          {a.ficha ? (
            <div className="formulario">
              <p className="ficha-linha"><strong>Na Critério:</strong> {a.ficha.historico}</p>
              <div className="ficha-linha">
                <strong>Pesquisa pública:</strong>{" "}
                {a.ficha.pesquisa.length === 0 ? (
                  "o agente não achou fatos públicos com fonte."
                ) : (
                  <ul className="ficha-fatos">
                    {a.ficha.pesquisa.map((item) => (
                      <li key={item.fato}>
                        {item.fato}{" "}
                        {item.fonte ? (
                          <a href={item.fonte} target="_blank" rel="noreferrer">fonte</a>
                        ) : (
                          <em>sem fonte</em>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <p className="ficha-linha"><strong>Quem decide:</strong> {a.ficha.quem_decide ?? "a confirmar"}</p>
            </div>
          ) : (
            <p className="campo-ajuda">A ficha aparece aqui quando o agente terminar a pesquisa.</p>
          )}
          {editavel && (
            <div className="formulario">
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ab-quem">Quem apresenta</label>
                <input id="ab-quem" className="entrada" value={rascunho.quem_apresenta}
                  onChange={(e) => mudar("quem_apresenta", e.target.value)} />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ab-contexto">
                  Histórico que não está no CRM
                </label>
                <textarea id="ab-contexto" className="entrada" rows={2} value={rascunho.contexto}
                  onChange={(e) => mudar("contexto", e.target.value)} />
              </div>
            </div>
          )}
        </section>

        <section className="abordagem-secao">
          <div className="abordagem-secao-topo">
            <h3>Rascunho da mensagem</h3>
            <div className="segmentado" role="group" aria-label="Canal">
              {(["E-mail", "WhatsApp"] as const).map((canal) => (
                <button key={canal} type="button" aria-pressed={rascunho.canal === canal}
                  disabled={!editavel} onClick={() => mudar("canal", canal)}>
                  {canal}
                </button>
              ))}
            </div>
          </div>
          <div className="formulario">
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ab-para">
                {whatsapp ? "Telefone, com DDD" : "Para"}
              </label>
              <input id="ab-para" className="entrada" value={rascunho.destinatario}
                disabled={!editavel} onChange={(e) => mudar("destinatario", e.target.value)} />
            </div>
            {!whatsapp && (
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ab-assunto">Assunto</label>
                <input id="ab-assunto" className="entrada" value={rascunho.assunto}
                  disabled={!editavel} onChange={(e) => mudar("assunto", e.target.value)} />
              </div>
            )}
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ab-mensagem">Mensagem</label>
              <textarea id="ab-mensagem" className="entrada" rows={8} value={rascunho.mensagem}
                disabled={!editavel || !a.mensagem} onChange={(e) => mudar("mensagem", e.target.value)} />
            </div>
            {a.versao > 0 && (
              <p className="campo-ajuda">
                Versão {a.versao}, gerada pelo agente. Edite à vontade antes de aprovar.
                {whatsapp &&
                  " No WhatsApp, a aprovação libera o link com o texto pronto e o envio é seu."}
              </p>
            )}
          </div>
        </section>

        {a.situacao === "Aguardando aprovação" && (
          <section className="abordagem-secao">
            <h3>Conferido antes de aprovar</h3>
            <ListaDeConferencias conferencias={a.conferencias} />
            {alterado && (
              <p className="campo-ajuda">Salve as alterações antes de aprovar: a conferência vale para o texto salvo.</p>
            )}
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ab-instrucao">Pedir outra versão ao agente</label>
              <div className="linha-de-acao">
                <input id="ab-instrucao" className="entrada" placeholder="Ex.: mais curta, sem citar a pesquisa"
                  value={instrucao} onChange={(e) => definirInstrucao(e.target.value)} />
                <button type="button" className="botao botao-secundario"
                  disabled={ocupado || instrucao.trim().length < 3}
                  onClick={() =>
                    executar(async () => {
                      await api.pedirOutraVersao(a.id, instrucao.trim());
                      definirInstrucao("");
                    })
                  }>
                  Pedir outra versão
                </button>
              </div>
            </div>
          </section>
        )}

        {a.situacao === "Aprovada" && a.link_whatsapp && (
          <section className="abordagem-secao">
            <h3>Enviar pelo WhatsApp</h3>
            <p className="campo-ajuda">Abra a conversa, confira o texto e envie. Depois marque como enviada.</p>
            <a className="botao botao-secundario" href={a.link_whatsapp} target="_blank" rel="noreferrer">
              Abrir no WhatsApp
            </a>
          </section>
        )}

        {a.situacao === "Enviada" && (
          <section className="abordagem-secao">
            <h3>Depois do envio</h3>
            <p className="campo-ajuda">Enviada em {data(a.enviada_em)}.</p>
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ab-diagnostico">Diagnóstico agendado para</label>
              <input id="ab-diagnostico" className="entrada" type="date" value={diagnostico}
                onChange={(e) => definirDiagnostico(e.target.value)} />
            </div>
          </section>
        )}
      </div>

      {(principal || secundarias.length > 0 || descartavel) && (
        <footer className="painel-rodape">
          {principal}
          {secundarias}
          {descartavel &&
            (confirmandoDescarte ? (
              <button type="button" className="botao botao-perigo" disabled={ocupado}
                onClick={() => executar(() => api.descartarAbordagem(a.id))}>
                Confirmar o descarte
              </button>
            ) : (
              <button type="button" className="botao botao-texto-perigo"
                onClick={() => definirConfirmandoDescarte(true)}>
                Descartar
              </button>
            ))}
        </footer>
      )}
    </aside>
  );
}

export function Abordagens() {
  const lista = usarDados(() => api.abordagens(), []);
  const itens: AbordagemResumo[] = useMemo(() => lista.dados?.itens ?? [], [lista.dados]);
  const meses = useMemo(() => [...new Set(itens.map((i) => i.mes))].sort(), [itens]);
  const [mesEscolhido, definirMes] = useState<string | null>(null);
  const [situacao, definirSituacao] = useState("");
  const [selecionada, definirSelecionada] = useState<number | null>(null);
  const [preparando, definirPreparando] = useState(false);
  const [aviso, definirAviso] = useState<string | null>(null);
  const [versao, definirVersao] = useState(0);

  const mes = mesEscolhido ?? mesPadrao(meses);
  const resumo = usarDados(
    () => (mes ? api.resumoDasAbordagens(mes) : Promise.resolve(null)),
    [mes, versao],
  );

  const doMes = itens.filter((i) => i.mes === mes);
  const visiveis = doMes.filter((i) => !situacao || i.situacao === situacao);
  const proxima = doMes.find((i) => i.situacao === "A preparar");

  const atualizar = () => {
    lista.recarregar();
    definirVersao((n) => n + 1);
  };

  const algumaPesquisando = itens.some((i) => i.situacao === "Pesquisando");
  useEffect(() => {
    if (!algumaPesquisando) return;
    const relogio = window.setInterval(atualizar, INTERVALO_DE_ATUALIZACAO);
    return () => window.clearInterval(relogio);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [algumaPesquisando]);

  const prepararProxima = async () => {
    if (!proxima) return;
    definirPreparando(true);
    definirAviso(null);
    try {
      await api.prepararAbordagem(proxima.id);
      definirSelecionada(proxima.id);
      atualizar();
    } catch (falha) {
      definirAviso(mensagemDe(falha));
    } finally {
      definirPreparando(false);
    }
  };

  if (lista.carregando && !lista.dados) return <Carregando rotulo="Lendo as abordagens" />;
  if (lista.erro && !lista.dados) return <Erro mensagem={lista.erro} aoTentarDeNovo={lista.recarregar} />;
  if (itens.length === 0) {
    return (
      <VazioSemDados
        titulo="Nenhuma conta na fila"
        explicacao="O agente começa quando as contas âncora do mês entram na fila, cada uma com quem a apresente. Use scripts/importar_abordagens.py com o CSV do mês."
      />
    );
  }

  const r = resumo.dados;
  return (
    <div className="abordagens">
      <section className="abordagens-fila" aria-label="Fila de abordagens">
        <div className="filtros">
          <div className="campo">
            <label className="campo-rotulo" htmlFor="ab-mes">Mês de abordagem</label>
            <select id="ab-mes" className="selecao" value={mes ?? ""}
              onChange={(e) => definirMes(e.target.value)}>
              {meses.map((m) => (
                <option key={m} value={m}>{nomeDoMes(m)}</option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label className="campo-rotulo" htmlFor="ab-situacao">Situação</label>
            <select id="ab-situacao" className="selecao" value={situacao}
              onChange={(e) => definirSituacao(e.target.value)}>
              <option value="">Todas</option>
              {SITUACOES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <button type="button" className="botao botao-secundario empurra-direita"
            disabled={!proxima || preparando} onClick={prepararProxima}>
            Preparar a próxima conta
          </button>
        </div>

        {aviso && (
          <div className="aviso-de-movimento" role="alert">
            <span>{aviso}</span>
            <button type="button" className="botao-icone" aria-label="Dispensar o aviso"
              onClick={() => definirAviso(null)}>
              ✕
            </button>
          </div>
        )}

        {visiveis.length === 0 ? (
          <VazioPorFiltro aoLimpar={() => definirSituacao("")} />
        ) : (
          <table className="tabela">
            <thead>
              <tr>
                <th>Conta</th>
                <th>Quem apresenta</th>
                <th>Situação</th>
                <th>Próximo passo</th>
              </tr>
            </thead>
            <tbody>
              {visiveis.map((i) => (
                <tr key={i.id} className={i.id === selecionada ? "linha-selecionada" : undefined}>
                  <td>
                    <button type="button" className="link-de-tabela"
                      aria-pressed={i.id === selecionada} onClick={() => definirSelecionada(i.id)}>
                      {i.grupo_nome}
                    </button>
                  </td>
                  <td>{i.quem_apresenta ?? <span className="texto-atencao">A confirmar</span>}</td>
                  <td><Etiqueta texto={i.situacao} /></td>
                  <td className="texto-medio">{i.proximo_passo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {r && (
          <div className="numeros numeros-tres">
            <div className="numero">
              <span className="numero-rotulo">Abordadas em {nomeDoMes(r.mes)}</span>
              <p className="numero-valor">{r.abordadas} de {r.na_fila}</p>
            </div>
            <div className="numero">
              <span className="numero-rotulo">Diagnósticos agendados</span>
              <p className="numero-valor">{r.diagnosticos}</p>
            </div>
            <div className="numero">
              <span className="numero-rotulo">Custo do agente nestas contas</span>
              <p className="numero-valor">
                {r.custo_usd === null
                  ? "Sem uso ainda"
                  : `US$ ${Number(r.custo_usd).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
              </p>
              <span className="numero-detalhe">
                {r.custo_parcial ? "Estimativa parcial: há modelo sem preço na tabela." : "Estimativa; confira na fatura."}
              </span>
            </div>
          </div>
        )}
      </section>

      {selecionada !== null ? (
        <PainelDaAbordagem key={selecionada} id={selecionada} aoMudar={atualizar} />
      ) : (
        <aside className="abordagem-painel abordagem-painel-vazio">
          <p className="estado-texto">Escolha uma conta na fila para ver a ficha e o rascunho.</p>
        </aside>
      )}
    </div>
  );
}
