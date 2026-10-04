/** SDR · Abordagens e conhecimento › Base de conhecimento (amostra aprovada por Eduardo em 03/10/2026).
 * Recepciona as fichas que a SDR de IA consulta: uma ficha por assunto, com o que a IA pode dizer, o
 * que nunca diz, como o lead pergunta, fonte, dono e validade. Só a ficha aprovada e dentro da
 * validade vale para a IA; o bloco Referências é consulta da equipe e nunca vai para a IA.
 * Editar uma ficha aprovada a devolve para "Em revisão" — a regra está no servidor.
 * Código editável (M1, amostra aprovada em 04/10/2026): a letra do bloco e um número; a tela sugere o
 * próximo livre, o servidor recusa repetido, e o código da carga inicial não se edita. */

import { useMemo, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { BaseDeConhecimento as Base, BlocoDaBase, EdicaoDeFicha, FichaDaBase } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { PainelLateral } from "../componentes/PainelLateral";
import { SEM_PERMISSAO, usarAcesso } from "../entrada";
import { data, dataHora } from "../formato";
import { usarDados } from "../usarDados";

const VENCIDAS = "Vencidas";

interface Rascunho {
  codigo: string;
  titulo: string;
  bloco: string;
  servico: string;
  texto: string;
  nunca_dizer: string;
  como_o_lead_pergunta: string;
  fonte: string;
  dono: string;
  depende_de_hipotese: boolean;
}

function rascunhoDe(f: FichaDaBase | null, bloco: string, sugerido: string): Rascunho {
  return {
    codigo: f ? (f.codigo ?? "") : sugerido,
    titulo: f?.titulo ?? "",
    bloco: f?.bloco ?? bloco,
    servico: f?.servico ?? "",
    texto: f?.texto ?? "",
    nunca_dizer: f?.nunca_dizer ?? "",
    como_o_lead_pergunta: f?.como_o_lead_pergunta ?? "",
    fonte: f?.fonte ?? "",
    dono: f?.dono ?? "",
    depende_de_hipotese: f?.depende_de_hipotese ?? false,
  };
}

function mudancas(antes: Rascunho, depois: Rascunho): EdicaoDeFicha {
  const saida: Record<string, unknown> = {};
  for (const chave of Object.keys(depois) as (keyof Rascunho)[]) {
    if (antes[chave] !== depois[chave]) saida[chave] = depois[chave];
  }
  return saida as EdicaoDeFicha;
}

function falha(f: unknown): string {
  return f instanceof ErroDaApi ? f.message : "Não consegui gravar. Tente de novo.";
}

function Bloco({ b, ativo, aoEscolher }: { b: BlocoDaBase; ativo: boolean; aoEscolher: () => void }) {
  return (
    <button type="button" className="base-bloco" aria-pressed={ativo} onClick={aoEscolher}>
      <span className="base-bloco-nome">{b.bloco}</span>
      {b.vai_para_a_ia ? (
        <span className="base-bloco-valor">{b.valem} de {b.total}<small> valem para a IA</small></span>
      ) : (
        <span className="base-bloco-valor">{b.total}<small> para consulta</small></span>
      )}
      <span className="base-bloco-sub">
        {b.total === 0 ? (
          <span className="texto-atencao">⚠ Sem fichas</span>
        ) : (
          [
            b.em_revisao && `${b.em_revisao} em revisão`,
            b.rascunhos && `${b.rascunhos} rascunho${b.rascunhos === 1 ? "" : "s"}`,
            !b.vai_para_a_ia && "não vai para a IA",
          ].filter(Boolean).join(" · ") || "Tudo aprovado"
        )}
        {b.vencidas > 0 && <span className="texto-atencao"> · ⚠ {b.vencidas} vencida{b.vencidas === 1 ? "" : "s"}</span>}
      </span>
    </button>
  );
}

function PainelDaFicha({
  ficha,
  blocos,
  blocoInicial,
  proximos,
  aoFechar,
  aoGravar,
}: {
  ficha: FichaDaBase | null;
  blocos: string[];
  blocoInicial: string;
  proximos: Record<string, string>;
  aoFechar: () => void;
  aoGravar: (f: FichaDaBase, recado: string) => void;
}) {
  const { pode, eu } = usarAcesso();
  const edita = pode("sdr.base");
  const aprova = pode("sdr.base_aprovar");
  const original = useMemo(
    () => rascunhoDe(ficha, blocoInicial, proximos[blocoInicial] ?? ""),
    [ficha, blocoInicial, proximos],
  );
  const [r, definirR] = useState<Rascunho>(original);
  const [aprovador, definirAprovador] = useState("");
  const [ocupado, definirOcupado] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const arquivada = ficha?.situacao === "Arquivada";
  const somenteLeitura = !edita || arquivada;
  const alterado = Object.keys(mudancas(original, r)).length > 0;
  const mudar = <K extends keyof Rascunho>(campo: K, valor: Rascunho[K]) => definirR((x) => ({ ...x, [campo]: valor }));
  const travado = ficha?.codigo_travado ?? false;
  const letra = (proximos[r.bloco] ?? "").charAt(0);
  // Trocar de bloco: se o código não começa com a letra do bloco novo, sugere o próximo livre dele.
  const mudarBloco = (bloco: string) => definirR((x) => {
    const novaLetra = (proximos[bloco] ?? "").charAt(0);
    const codigo = x.codigo && !x.codigo.toUpperCase().startsWith(novaLetra) ? (proximos[bloco] ?? "") : x.codigo;
    return { ...x, bloco, codigo: x.codigo ? codigo : x.codigo };
  });

  const fazer = async (acao: () => Promise<FichaDaBase>, recado: string) => {
    definirOcupado(true);
    definirErro(null);
    try {
      aoGravar(await acao(), recado);
    } catch (f) {
      definirErro(falha(f));
    } finally {
      definirOcupado(false);
    }
  };

  const salvar = () => fazer(
    () => (ficha ? api.alterarFicha(ficha.id, mudancas(original, r)) : api.criarFicha(r)),
    ficha?.situacao === "Aprovada" ? "Ficha salva. Como mudou, voltou para Em revisão." : "Ficha salva.",
  );
  const aprovar = () => ficha && fazer(async () => {
    if (alterado) await api.alterarFicha(ficha.id, mudancas(original, r));
    return api.aprovarFicha(ficha.id, eu.modo === "local" ? aprovador : null);
  }, "Ficha aprovada: a IA já pode usá-la.");

  const podeAprovar = ficha && !arquivada && ficha.situacao !== "Aprovada";
  const id = (campo: string) => `ficha-${campo}`;

  return (
    <PainelLateral
      titulo={ficha ? ficha.titulo : "Nova ficha"}
      subtitulo={ficha ? `${ficha.codigo ? `${ficha.codigo} · ` : ""}${ficha.bloco}` : "Começa como rascunho"}
      aoFechar={aoFechar}
      rodape={
        <div className="base-acoes">
          {podeAprovar && aprova && (
            <button type="button" className="botao botao-primario" onClick={() => void aprovar()}
              disabled={ocupado || ficha.problemas_para_aprovar.length > 0 || (eu.modo === "local" && !aprovador.trim())}>
              Aprovar
            </button>
          )}
          {edita && !arquivada && (
            <button type="button" className={`botao ${podeAprovar && aprova ? "botao-secundario" : "botao-primario"}`}
              disabled={ocupado || (ficha !== null && !alterado) || !r.titulo.trim()} onClick={() => void salvar()}>
              {ficha ? "Salvar" : "Criar ficha"}
            </button>
          )}
          {edita && ficha?.situacao === "Rascunho" && (
            <button type="button" className="botao botao-secundario" disabled={ocupado}
              onClick={() => void fazer(() => api.moverFicha(ficha.id, "revisao"), "Ficha enviada para revisão.")}>
              Enviar para revisão
            </button>
          )}
          {edita && ficha && (
            <button type="button" className="link-de-tabela empurra-direita" disabled={ocupado}
              onClick={() => void fazer(
                () => api.moverFicha(ficha.id, arquivada ? "reabrir" : "arquivar"),
                arquivada ? "Ficha reaberta como rascunho." : "Ficha arquivada: saiu da base da IA.")}>
              {arquivada ? "Reabrir" : "Arquivar"}
            </button>
          )}
        </div>
      }
    >
      <div className="formulario">
        {ficha && (
          <p className="base-situacao">
            <Etiqueta texto={ficha.situacao} />
            {ficha.vencida && <Etiqueta texto="Vencida" />}
            <span className="campo-ajuda">
              {ficha.vale_para_a_ia
                ? `Vale para a IA até ${data(ficha.validade)}. Aprovada por ${ficha.aprovada_por} em ${dataHora(ficha.aprovada_em)}.`
                : ficha.bloco === "Referências"
                  ? "Referência: consulta da equipe, não vai para a IA."
                  : ficha.vencida
                    ? `Venceu em ${data(ficha.validade)}: a IA deixou de usar. Revise e aprove de novo.`
                    : "Ainda não vale para a IA."}
            </span>
          </p>
        )}
        {!edita && <p className="campo-ajuda">{SEM_PERMISSAO}</p>}
        {arquivada && edita && <p className="campo-ajuda">Ficha arquivada: reabra para editar.</p>}

        <div className="base-codigo-titulo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor={id("codigo")}>Código</label>
            <input id={id("codigo")} className="entrada" maxLength={20} value={r.codigo}
              readOnly={somenteLeitura || travado} aria-describedby={id("codigo-ajuda")}
              onChange={(e) => mudar("codigo", e.target.value.toUpperCase())} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor={id("titulo")}>Título</label>
            <input id={id("titulo")} className="entrada" maxLength={200} value={r.titulo} readOnly={somenteLeitura}
              onChange={(e) => mudar("titulo", e.target.value)} />
          </div>
        </div>
        <span className="campo-ajuda" id={id("codigo-ajuda")}>
          {travado
            ? "Travado: código da carga inicial, não se edita. É por ele que a carga sabe que a ficha já entrou."
            : r.codigo && r.codigo === proximos[r.bloco]
              ? `Sugerido: o próximo livre em ${r.bloco}. Pode trocar. Começa sempre com ${letra}, a letra do bloco.`
              : `Começa sempre com ${letra}, a letra do bloco, seguida de número.`}
        </span>
        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor={id("bloco")}>Bloco</label>
            <select id={id("bloco")} className="selecao" value={r.bloco} disabled={somenteLeitura || travado}
              onChange={(e) => mudarBloco(e.target.value)}>
              {blocos.map((b) => <option key={b} value={b}>{b}</option>)}
            </select>
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor={id("servico")}>Serviço (se for de um só)</label>
            <input id={id("servico")} className="entrada" maxLength={120} value={r.servico} readOnly={somenteLeitura}
              placeholder="Todos" onChange={(e) => mudar("servico", e.target.value)} />
          </div>
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={id("texto")}>O que a IA pode dizer</label>
          <textarea id={id("texto")} className="entrada" rows={4} value={r.texto} readOnly={somenteLeitura}
            onChange={(e) => mudar("texto", e.target.value)} />
          <span className="campo-ajuda">De 3 a 8 linhas, um assunto só. Sem preço: a mesma trava das mensagens.</span>
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={id("nunca")}>O que a IA nunca diz</label>
          <textarea id={id("nunca")} className="entrada" rows={2} value={r.nunca_dizer} readOnly={somenteLeitura}
            onChange={(e) => mudar("nunca_dizer", e.target.value)} />
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor={id("pergunta")}>Como o lead pergunta</label>
          <textarea id={id("pergunta")} className="entrada" rows={2} value={r.como_o_lead_pergunta} readOnly={somenteLeitura}
            placeholder={'"Quanto custa?" · "Vocês atendem a minha cidade?"'}
            onChange={(e) => mudar("como_o_lead_pergunta", e.target.value)} />
        </div>
        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor={id("fonte")}>Fonte</label>
            <input id={id("fonte")} className="entrada" maxLength={300} value={r.fonte} readOnly={somenteLeitura}
              placeholder="Matriz de Objeções, 19/09/2026" onChange={(e) => mudar("fonte", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor={id("dono")}>Dono</label>
            <input id={id("dono")} className="entrada" maxLength={120} value={r.dono} readOnly={somenteLeitura}
              onChange={(e) => mudar("dono", e.target.value)} />
          </div>
        </div>
        <label className="base-marcador">
          <input type="checkbox" checked={r.depende_de_hipotese} disabled={somenteLeitura}
            onChange={(e) => mudar("depende_de_hipotese", e.target.checked)} />
          Depende de hipótese em validação (ICP, preço, fronteiras entre os produtos): vale 60 dias, não 6 meses
        </label>

        {podeAprovar && ficha.problemas_para_aprovar.length > 0 && (
          <div className="campo-ajuda" role="note">
            <strong>Antes de aprovar</strong> (salve para conferir de novo):
            <ul className="base-faltas">{ficha.problemas_para_aprovar.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        )}
        {podeAprovar && aprova && eu.modo === "local" && (
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor={id("aprovador")}>Quem aprova</label>
            <input id={id("aprovador")} className="entrada" maxLength={200} value={aprovador}
              onChange={(e) => definirAprovador(e.target.value)} />
          </div>
        )}
        {erro && <p className="estado-texto estado-erro" role="alert">✗ {erro}</p>}
      </div>
    </PainelLateral>
  );
}

export function BaseDeConhecimento() {
  const { pode } = usarAcesso();
  const edita = pode("sdr.base");
  const { dados, carregando, erro, recarregar } = usarDados<Base>(() => api.baseDoSdr(), []);
  const [bloco, definirBloco] = useState("");
  const [situacao, definirSituacao] = useState("");
  const [busca, definirBusca] = useState("");
  const [aberta, definirAberta] = useState<number | "nova" | null>(null);
  const [recado, definirRecado] = useState<string | null>(null);
  const [carregandoCarga, definirCarregandoCarga] = useState(false);
  const [erroDaCarga, definirErroDaCarga] = useState<string | null>(null);

  const visiveis = useMemo(() => {
    const termo = busca.trim().toLowerCase();
    return (dados?.fichas ?? []).filter((f) =>
      (!bloco || f.bloco === bloco)
      && (!situacao || (situacao === VENCIDAS ? f.vencida : f.situacao === situacao))
      && (!termo || [f.codigo, f.titulo, f.texto, f.nunca_dizer, f.como_o_lead_pergunta]
        .some((t) => t?.toLowerCase().includes(termo))),
    );
  }, [dados, bloco, situacao, busca]);

  if (carregando && !dados) return <Carregando rotulo="Abrindo a base de conhecimento" />;
  if (erro || !dados) return <Erro mensagem={erro ?? "Falha inesperada."} aoTentarDeNovo={recarregar} />;

  const nomesDosBlocos = dados.blocos.map((b) => b.bloco);
  const fichaAberta = typeof aberta === "number" ? dados.fichas.find((f) => f.id === aberta) ?? null : null;
  const limpar = () => { definirBloco(""); definirSituacao(""); definirBusca(""); };

  const trazerCarga = async () => {
    definirCarregandoCarga(true);
    definirErroDaCarga(null);
    try {
      const r = await api.cargaInicialDaBase();
      definirRecado(`Carga inicial: ${r.acrescentadas} fichas acrescentadas${r.ja_existiam ? `, ${r.ja_existiam} já estavam na base` : ""}.`);
      recarregar();
    } catch (f) {
      definirErroDaCarga(falha(f));
    } finally {
      definirCarregandoCarga(false);
    }
  };

  return (
    <div className="base">
      <div className="base-blocos" role="group" aria-label="Fichas por bloco">
        {dados.blocos.map((b) => (
          <Bloco key={b.bloco} b={b} ativo={bloco === b.bloco}
            aoEscolher={() => definirBloco(bloco === b.bloco ? "" : b.bloco)} />
        ))}
      </div>

      <div className="filtros">
        <div className="campo">
          <label className="campo-rotulo" htmlFor="base-bloco">Bloco</label>
          <select id="base-bloco" className="selecao" value={bloco} onChange={(e) => definirBloco(e.target.value)}>
            <option value="">Todos os blocos</option>
            {nomesDosBlocos.map((b) => <option key={b} value={b}>{b}</option>)}
          </select>
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="base-situacao">Situação</label>
          <select id="base-situacao" className="selecao" value={situacao} onChange={(e) => definirSituacao(e.target.value)}>
            <option value="">Todas as situações</option>
            {[...dados.situacoes, VENCIDAS].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div className="campo base-busca">
          <label className="campo-rotulo" htmlFor="base-busca">Buscar</label>
          <input id="base-busca" className="entrada" value={busca} placeholder="Título, texto ou como o lead pergunta"
            onChange={(e) => definirBusca(e.target.value)} />
        </div>
        {edita && (
          <button type="button" className="botao botao-primario empurra-direita" onClick={() => definirAberta("nova")}>
            Nova ficha
          </button>
        )}
      </div>

      {recado && <p className="recado" role="status">✓ {recado}</p>}

      {dados.fichas.length === 0 ? (
        <VazioSemDados
          titulo="A base ainda está vazia"
          explicacao={edita
            ? "A carga inicial traz as regras de atuação, os gatilhos de transbordo, o tom de voz, os serviços do catálogo e as referências levantadas em 03/10/2026. Tudo entra para revisão: nada nasce aprovado."
            : "Quem edita a base ainda não cadastrou fichas."}
          acao={edita ? (
            <>
              <button type="button" className="botao botao-secundario" disabled={carregandoCarga} onClick={() => void trazerCarga()}>
                {carregandoCarga ? "Trazendo…" : "Trazer a carga inicial"}
              </button>
              {erroDaCarga && <p className="estado-texto estado-erro" role="alert">✗ {erroDaCarga}</p>}
            </>
          ) : undefined}
        />
      ) : visiveis.length === 0 ? (
        <VazioPorFiltro aoLimpar={limpar} />
      ) : (
        <div className="tabela-rolagem">
          <table className="tabela">
            <thead>
              <tr><th>Ficha</th><th>Bloco</th><th>Situação</th><th>Validade</th></tr>
            </thead>
            <tbody>
              {visiveis.map((f) => (
                <tr key={f.id} className={f.id === aberta ? "linha-selecionada" : undefined}>
                  <td>
                    <button type="button" className="link-de-tabela" onClick={() => definirAberta(f.id)}>
                      {f.codigo ? `${f.codigo} · ` : ""}{f.titulo}
                    </button>
                    {f.servico && f.bloco !== "Serviços" && <span className="celula-fonte">{f.servico}</span>}
                  </td>
                  <td>{f.bloco}</td>
                  <td><Etiqueta texto={f.situacao} /></td>
                  <td>
                    {f.vencida ? <Etiqueta texto="Vencida" /> : f.validade ? data(f.validade) : <span className="sdr-fraco">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {aberta !== null && (aberta === "nova" || fichaAberta) && (
        <PainelDaFicha
          key={aberta}
          ficha={fichaAberta}
          blocos={nomesDosBlocos}
          blocoInicial={bloco || nomesDosBlocos[0]}
          proximos={dados.proximos_codigos}
          aoFechar={() => definirAberta(null)}
          aoGravar={(f, texto) => { definirRecado(texto); definirAberta(f.id); recarregar(); }}
        />
      )}
    </div>
  );
}
