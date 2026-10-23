/** Configurações › Integrações (amostra aprovada por Eduardo em 07/10/2026): chave de IA, WhatsApp,
 * e-mail, questionário e disparo se cadastram, trocam e testam aqui, sem nada no painel do servidor.
 * Vale o que está na tela; sem valor na tela, o que veio do servidor; depois o padrão. Segredo nunca
 * volta do servidor: aparecem só os 4 últimos caracteres. A IA pode ser Anthropic ou OpenAI, com a
 * outra de reserva (07/10/2026). Desde 15/10/2026, uma aba por integração, com a situação ao lado do nome. O Granola
 * (23/10/2026) escolhe as pastas na lista do próprio Granola e mostra a busca e a fila "Precisa de você". */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { CampoDeIntegracao, GrupoDeIntegracao, Integracoes, ResultadoDoTeste } from "../api/tipos";
import { FilaDoGranola } from "./FilaDoGranola";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { Etiqueta } from "./Etiqueta";
import { Carregando, Erro } from "./estados";

/** Receber as mensagens dos leads pelo WhatsApp (fase 0 do SDR de IA, amostra aprovada em 14/10/2026). */
const DO_RECEBIMENTO = ["whatsapp.recebimento", "whatsapp.token_verificacao", "whatsapp.app_secret"];
export const CAMINHO_DO_WEBHOOK = "/api/whatsapp/webhook";

/** Um token novo, gerado no navegador: o servidor recebe ao salvar e nunca o devolve. */
export function gerarToken(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return `crm-${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}

const DE_ONDE: Record<string, string> = {
  tela: "salvo nesta tela",
  servidor: "vem do servidor; salve aqui para a tela valer",
  "padrão": "padrão do sistema",
  vazio: "não configurado",
};

/** Nome curto da aba e a linha que explica (abas aprovadas por Eduardo em 15/10/2026); grupo novo sem nome aqui
 * usa o título. */
const ABA: Record<string, { rotulo: string; explicacao: string }> = {
  ia: { rotulo: "IA", explicacao: "A chave da IA, o modelo e a IA de reserva." },
  whatsapp: { rotulo: "WhatsApp", explicacao: "O envio pela Cloud API da Meta e o recebimento das mensagens dos leads." },
  email: { rotulo: "E-mail", explicacao: "O envio de e-mail pelo Microsoft 365." },
  questionario: { rotulo: "Questionário", explicacao: "O link enviado ao lead e a busca dos questionários respondidos no site." },
  meta_ads: { rotulo: "Meta Ads", explicacao: "O gasto por campanha, os leads do formulário e a devolução das conversões." },
  google_ads: { rotulo: "Google Ads", explicacao: "O gasto por campanha, os leads do formulário e a devolução das conversões." },
  disparo: { rotulo: "Disparo", explicacao: "O envio automático do lembrete e do agradecimento do questionário." },
  sdr_respostas: {
    rotulo: "Respostas do SDR",
    explicacao: "Como a IA responde ao lead no WhatsApp: o modo, o modelo leve e os limites por conversa.",
  },
  granola: { rotulo: "Granola", explicacao: "As notas das reuniões gravadas no Granola chegam sozinhas ao CRM, sem colar." },
};
const PASTAS_DO_GRANOLA = ["granola.pasta_lead", "granola.pasta_resultado"];
const MEMORIA = "crm.integracoes.aba";

function guardada(): string | null {
  try {
    return localStorage.getItem(MEMORIA);
  } catch {
    return null;
  }
}

/** O que falta, para o título da aba ao passar o mouse. */
function oQueFalta(g: GrupoDeIntegracao): string {
  if (g.configurado) return `${g.titulo}: configurado`;
  const vazios = g.campos.filter((c) => c.origem === "vazio" || c.ilegivel).map((c) => c.rotulo);
  return `${g.titulo}: falta configurar${vazios.length ? ` (${vazios.join(", ")})` : ""}`;
}

export function IntegracoesDoSistema() {
  const { dados, carregando, erro, recarregar } = usarDados<Integracoes>(() => api.integracoes(), []);
  const [escolhida, definirEscolhida] = useState<string | null>(guardada);
  const [comRascunho, definirComRascunho] = useState<Set<string>>(new Set());
  if (carregando && !dados) return <Carregando rotulo="Abrindo as integrações" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados || dados.grupos.length === 0) return null;
  const aba = dados.grupos.find((g) => g.chave === escolhida) ?? dados.grupos[0];
  const escolher = (chave: string) => {
    definirEscolhida(chave);
    try {
      localStorage.setItem(MEMORIA, chave);
    } catch {
      /* sem armazenamento: vale só nesta visita */
    }
  };
  const marcarRascunho = (chave: string, tem: boolean) => definirComRascunho((atual) => {
    if (atual.has(chave) === tem) return atual;
    const novo = new Set(atual);
    if (tem) novo.add(chave); else novo.delete(chave);
    return novo;
  });
  return (
    <div style={{ display: "grid", gap: "var(--e3)" }}>
      <p className="campo-ajuda" style={{ margin: 0 }}>
        As chaves ficam cifradas no banco e nunca voltam para a tela: aparecem só os 4 últimos caracteres. O que
        está salvo aqui vale mais que o painel do servidor.
      </p>
      <div className="abas" role="tablist" aria-label="Integrações">
        {dados.grupos.map((g) => (
          <button key={g.chave} type="button" role="tab" className="aba" aria-selected={aba.chave === g.chave}
            title={oQueFalta(g)} onClick={() => escolher(g.chave)}>
            {ABA[g.chave]?.rotulo ?? g.titulo}{" "}
            <span className={g.configurado ? "aba-ok" : "aba-falta"} aria-label={g.configurado ? "configurado" : "falta configurar"}>
              {g.configurado ? "✓" : "○"}
            </span>
            {comRascunho.has(g.chave) && <span className="aba-rascunho" aria-label="alterações não salvas"> •</span>}
          </button>
        ))}
      </div>
      <p className="campo-ajuda" style={{ margin: 0 }}>
        {ABA[aba.chave]?.explicacao ?? aba.titulo} ✓ configurado · ○ desligado ou faltando dado (passe o mouse na aba).
      </p>
      {/* Todos ficam montados e só o da aba aparece: o que foi digitado e não salvo continua lá ao voltar. */}
      {dados.grupos.map((g) => (
        <div key={g.chave} role="tabpanel" hidden={g.chave !== aba.chave} aria-label={g.titulo}>
          <CartaoDeIntegracao grupo={g} aoSalvar={recarregar} aoMudarRascunho={(tem) => marcarRascunho(g.chave, tem)} />
        </div>
      ))}
    </div>
  );
}

function CartaoDeIntegracao({ grupo, aoSalvar, aoMudarRascunho }: {
  grupo: GrupoDeIntegracao; aoSalvar: () => void; aoMudarRascunho?: (tem: boolean) => void;
}) {
  const [rascunho, definirRascunho] = useState<Record<string, string>>({});
  const [apagar, definirApagar] = useState<string[]>([]);
  const [salvando, definirSalvando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);
  const [teste, definirTeste] = useState<ResultadoDoTeste | null>(null);
  const [testando, definirTestando] = useState(false);
  const [para, definirPara] = useState("");
  const ehGranola = grupo.chave === "granola";
  const chaveDoGranola = ehGranola ? grupo.campos.find((c) => c.chave === "granola.chave") : undefined;
  const temChave = Boolean(chaveDoGranola && chaveDoGranola.origem !== "vazio");
  const [pastas, definirPastas] = useState<string[] | null>(null);
  const [pastasFalhou, definirPastasFalhou] = useState<string | null>(null);
  const [rodada, definirRodada] = useState(0);
  useEffect(() => {
    if (!ehGranola || !temChave) return;
    let vivo = true;
    api.pastasDoGranola().then(
      (lista) => { if (vivo) { definirPastas(lista); definirPastasFalhou(null); } },
      (f) => { if (vivo) { definirPastas(null); definirPastasFalhou(f instanceof ErroDaApi ? f.message : "falha ao ler as pastas"); } },
    );
    return () => { vivo = false; };
  }, [ehGranola, temChave, chaveDoGranola?.final]);

  const valorDe = (c: CampoDeIntegracao) => rascunho[c.chave] ?? (c.segredo ? "" : (c.valor ?? ""));
  const mudar = (chave: string, valor: string) => {
    definirFeito(null);
    definirRascunho({ ...rascunho, [chave]: valor });
  };
  const mudados = grupo.campos.filter((c) =>
    c.chave in rascunho && (c.segredo ? rascunho[c.chave].trim() !== "" : rascunho[c.chave] !== (c.valor ?? "")),
  );
  const mudou = mudados.length > 0 || apagar.length > 0;
  useEffect(() => aoMudarRascunho?.(mudou), [mudou, aoMudarRascunho]);

  const salvar = async () => {
    definirSalvando(true);
    definirFalha(null);
    try {
      await api.salvarIntegracao(grupo.chave, {
        valores: Object.fromEntries(mudados.map((c) => [c.chave, rascunho[c.chave]])),
        apagar,
      });
      definirRascunho({});
      definirApagar([]);
      definirFeito("Salvo. Já vale para o CRM, sem reiniciar.");
      aoSalvar();
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  const rodar = async (acao: () => Promise<ResultadoDoTeste>) => {
    definirTestando(true);
    definirTeste(null);
    try {
      definirTeste(await acao());
    } catch (f) {
      definirTeste({ ok: false, mensagem: f instanceof ErroDaApi ? f.message : "Falha no teste.", segundos: 0, em: "" });
    } finally {
      definirTestando(false);
    }
  };

  const titulo = `integracao-${grupo.chave}`;
  return (
    <section className="numero" aria-labelledby={titulo}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--e2)", flexWrap: "wrap" }}>
        <h3 className="numero-rotulo" id={titulo} style={{ margin: 0, flex: 1 }}>{grupo.titulo}</h3>
        <Etiqueta texto={grupo.configurado ? "Configurado" : "Falta configurar"} />
      </div>
      <div style={{ display: "grid", gap: "var(--e3)", marginTop: "var(--e3)" }}>
        {grupo.campos.filter((c) => !DO_RECEBIMENTO.includes(c.chave)).map((c) => (
          <Campo key={c.chave} campo={c} valor={valorDe(c)} aoMudar={(v) => mudar(c.chave, v)}
            vaiApagar={apagar.includes(c.chave)}
            lista={PASTAS_DO_GRANOLA.includes(c.chave) ? pastas : null}
            avisoDaLista={PASTAS_DO_GRANOLA.includes(c.chave)
              ? (!temChave ? "Salve a chave para escolher na lista de pastas do Granola."
                : pastasFalhou ? `Não consegui ler as pastas do Granola (${pastasFalhou}). Digite o nome da pasta.` : null)
              : null}
            aoApagar={() => { definirFeito(null); definirApagar([...apagar, c.chave]); }} />
        ))}
        {grupo.campos.some((c) => DO_RECEBIMENTO.includes(c.chave)) && (
          <Recebimento campos={grupo.campos.filter((c) => DO_RECEBIMENTO.includes(c.chave))} situacao={grupo.situacao}
            valorDe={valorDe} aoMudar={mudar} apagar={apagar}
            aoApagar={(chave) => { definirFeito(null); definirApagar([...apagar, chave]); }} />
        )}
        {grupo.situacao && !grupo.campos.some((c) => DO_RECEBIMENTO.includes(c.chave)) && (
          <p className="campo-ajuda" role="status" style={{ margin: 0 }}>{grupo.situacao}</p>
        )}
      </div>
      <div className="perfis-acoes">
        <button type="button" className="botao botao-primario" disabled={!mudou || salvando} onClick={() => void salvar()}>
          {salvando ? "Salvando…" : "Salvar"}
        </button>
        {grupo.testavel && (
          <button type="button" className="botao" disabled={testando || mudou}
            title={mudou ? "Salve antes de testar" : undefined}
            onClick={() => void rodar(() => api.testarIntegracao(grupo.chave))}>
            {testando ? "Testando…" : "Testar conexão"}
          </button>
        )}
        {ehGranola && (
          <button type="button" className="botao" disabled={testando || mudou}
            title={mudou ? "Salve antes de buscar" : undefined}
            onClick={() => void rodar(async () => {
              const inicio = performance.now();
              try {
                const r = await api.buscarNoGranola();
                const texto = r.erro ?? [
                  `${r.novas} nota${r.novas === 1 ? " nova" : "s novas"}`,
                  r.novas ? `${r.a_usar} ${r.a_usar === 1 ? "entrou sozinha" : "entraram sozinhas"}, ${r.precisam} precisa${r.precisam === 1 ? "" : "m"} de você` : null,
                  r.aviso,
                ].filter(Boolean).join(" · ");
                return { ok: !r.erro, mensagem: texto, segundos: Math.round((performance.now() - inicio) / 100) / 10, em: r.em };
              } finally {
                definirRodada((n) => n + 1);
              }
            })}>
            Buscar agora
          </button>
        )}
        {mudou && <span className="campo-ajuda">· alterações ainda não salvas</span>}
        {grupo.alterado_em && (
          <span className="campo-ajuda">Última mudança: {grupo.alterado_por ? `${grupo.alterado_por}, ` : ""}{dataHora(grupo.alterado_em)}</span>
        )}
      </div>
      {grupo.envia_teste && (
        <div className="perfis-acoes">
          <input className="entrada" style={{ maxWidth: "18rem" }} value={para}
            aria-label={`${grupo.titulo}: enviar teste para`}
            placeholder={grupo.chave === "email" ? "seu@email.com.br" : "21 99999-9999"}
            onChange={(e) => definirPara(e.target.value)} />
          <button type="button" className="botao" disabled={testando || mudou || !para.trim()}
            onClick={() => void rodar(() => api.enviarTesteDeIntegracao(grupo.chave, para))}>
            {grupo.chave === "email" ? "Enviar e-mail de teste" : "Enviar modelo de teste"}
          </button>
          <span className="campo-ajuda">Manda uma mensagem de verdade, só para este destino.</span>
        </div>
      )}
      {teste && (
        <p className={teste.ok ? "recado" : "estado estado-erro estado-texto"} role={teste.ok ? "status" : "alert"}>
          {teste.ok ? "✓" : "✗"} {teste.mensagem}{teste.segundos ? ` (${String(teste.segundos).replace(".", ",")} s)` : ""}
        </p>
      )}
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {ehGranola && <FilaDoGranola rodada={rodada} />}
    </section>
  );
}

function BotaoCopiar({ texto, rotulo }: { texto: string; rotulo: string }) {
  const [copiado, definirCopiado] = useState(false);
  return (
    <button type="button" className="botao" aria-label={rotulo} disabled={!texto}
      onClick={() => {
        void navigator.clipboard?.writeText(texto).then(() => {
          definirCopiado(true);
          setTimeout(() => definirCopiado(false), 2000);
        }, () => definirCopiado(false));
      }}>
      {copiado ? "Copiado" : "Copiar"}
    </button>
  );
}

function Recebimento({ campos, situacao, valorDe, aoMudar, apagar, aoApagar }: {
  campos: CampoDeIntegracao[]; situacao: string | null | undefined; valorDe: (c: CampoDeIntegracao) => string;
  aoMudar: (chave: string, valor: string) => void; apagar: string[]; aoApagar: (chave: string) => void;
}) {
  const de = (chave: string) => campos.find((c) => c.chave === chave);
  const ligado = de("whatsapp.recebimento");
  const token = de("whatsapp.token_verificacao");
  const segredo = de("whatsapp.app_secret");
  const endereco = `${window.location.origin}${CAMINHO_DO_WEBHOOK}`;
  return (
    <div className="recebimento" role="group" aria-labelledby="t-recebimento">
      <strong id="t-recebimento" className="recebimento-titulo">Receber as mensagens dos leads</strong>
      <span className="campo-ajuda" style={{ margin: 0 }}>
        A Meta entrega cada mensagem do lead neste endereço do CRM. Nesta fase o CRM só recebe e mostra:{" "}
        <b>ninguém responde sozinho</b>.
      </span>
      {ligado && <Campo campo={ligado} valor={valorDe(ligado)} aoMudar={(v) => aoMudar(ligado.chave, v)}
        vaiApagar={apagar.includes(ligado.chave)} aoApagar={() => aoApagar(ligado.chave)} />}
      <div style={{ display: "grid", gap: "var(--e1)" }}>
        <label htmlFor="campo-endereco-webhook">Endereço para colar na Meta (URL de retorno)</label>
        <div className="recebimento-linha">
          <input id="campo-endereco-webhook" className="entrada" readOnly value={endereco} />
          <BotaoCopiar texto={endereco} rotulo="Copiar o endereço" />
        </div>
        <span className="campo-ajuda">
          Meta for Developers › seu app › WhatsApp › Configuração › Webhook. Assine o campo <b>messages</b>.
        </span>
      </div>
      {token && (
        <div style={{ display: "grid", gap: "var(--e1)" }}>
          <label htmlFor={`campo-${token.chave}`}>{token.rotulo}</label>
          {token.final && !valorDe(token) && !apagar.includes(token.chave) && (
            <span className="campo-ajuda">Salvo, termina em <strong>{token.final}</strong>. Gere outro só se for trocar na Meta também.</span>
          )}
          <div className="recebimento-linha">
            <input id={`campo-${token.chave}`} className="entrada" type="text" autoComplete="off" value={valorDe(token)}
              placeholder={token.final ? "Gere outro para trocar" : "Clique em Gerar"}
              onChange={(e) => aoMudar(token.chave, e.target.value)} />
            <button type="button" className="botao" onClick={() => aoMudar(token.chave, gerarToken())}>Gerar</button>
            <BotaoCopiar texto={valorDe(token)} rotulo="Copiar o token" />
          </div>
          <span className="campo-ajuda">
            Gere, cole o mesmo valor na Meta em “Verificar token” e salve aqui. Depois de salvo, o CRM mostra só os 4
            últimos caracteres, como as outras chaves.
          </span>
        </div>
      )}
      {segredo && <Campo campo={segredo} valor={valorDe(segredo)} aoMudar={(v) => aoMudar(segredo.chave, v)}
        vaiApagar={apagar.includes(segredo.chave)} aoApagar={() => aoApagar(segredo.chave)} />}
      {situacao && <p className="campo-ajuda recebimento-situacao" role="status">{situacao}</p>}
    </div>
  );
}

function Campo({ campo, valor, aoMudar, vaiApagar, aoApagar, lista = null, avisoDaLista = null }: {
  campo: CampoDeIntegracao; valor: string; aoMudar: (v: string) => void; vaiApagar: boolean; aoApagar: () => void;
  /** Opções lidas na hora (as pastas do Granola); o valor atual entra na lista mesmo se não estiver nela. */
  lista?: string[] | null;
  avisoDaLista?: string | null;
}) {
  const id = `campo-${campo.chave}`;
  const ajuda = [DE_ONDE[campo.origem], campo.ajuda, avisoDaLista].filter(Boolean).join(" · ");
  if (lista) {
    const efetivo = valor || campo.padrao;
    const opcoes = lista.includes(efetivo) || !efetivo ? lista : [efetivo, ...lista];
    return (
      <div style={{ display: "grid", gap: "var(--e1)" }}>
        <label htmlFor={id}>{campo.rotulo}</label>
        <select id={id} className="selecao" style={{ maxWidth: "18rem" }} value={efetivo} onChange={(e) => aoMudar(e.target.value)}>
          {opcoes.map((o) => (
            <option key={o} value={o}>{o}{lista.includes(o) ? "" : " (não existe no Granola)"}</option>
          ))}
        </select>
        <span className="campo-ajuda">{ajuda}</span>
      </div>
    );
  }
  if (campo.opcoes.length === 2 && campo.opcoes.includes("true")) {
    return (
      <label style={{ display: "flex", gap: "var(--e2)", alignItems: "center" }}>
        <input type="checkbox" checked={valor === "true"} onChange={(e) => aoMudar(e.target.checked ? "true" : "false")} />
        <span>{campo.rotulo}</span>
        <span className="campo-ajuda">{ajuda}</span>
      </label>
    );
  }
  if (campo.opcoes.length > 0) {
    return (
      <div style={{ display: "grid", gap: "var(--e1)" }}>
        <label htmlFor={id}>{campo.rotulo}</label>
        <select id={id} className="selecao" style={{ maxWidth: "18rem" }} value={valor} onChange={(e) => aoMudar(e.target.value)}>
          {campo.opcoes.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
        <span className="campo-ajuda">{ajuda}</span>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gap: "var(--e1)" }}>
      <label htmlFor={id}>{campo.rotulo}</label>
      {campo.segredo && campo.final && !vaiApagar && (
        <span className="campo-ajuda">
          Salva, termina em <strong>{campo.final}</strong> · {DE_ONDE[campo.origem]}
          {campo.origem === "tela" && (
            <> · <button type="button" className="botao botao-texto-perigo" onClick={aoApagar}>Tirar da tela</button></>
          )}
        </span>
      )}
      {campo.ilegivel && (
        <span className="estado estado-erro estado-texto">A chave salva não pode mais ser lida (o segredo do servidor mudou). Cadastre de novo.</span>
      )}
      {vaiApagar && <span className="campo-ajuda">Sai da tela ao salvar; volta a valer o servidor, se houver.</span>}
      <input id={id} className="entrada" type={campo.segredo ? "password" : "text"} autoComplete="off" value={valor}
        placeholder={campo.segredo ? (campo.final ? "Cole a nova para trocar" : "Cole aqui") : (campo.exemplo || campo.padrao)}
        onChange={(e) => aoMudar(e.target.value)} />
      {!campo.segredo && <span className="campo-ajuda">{ajuda}</span>}
      {campo.segredo && !campo.final && campo.ajuda && <span className="campo-ajuda">{campo.ajuda}</span>}
    </div>
  );
}
