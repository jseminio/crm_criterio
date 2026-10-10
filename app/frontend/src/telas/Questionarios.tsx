/** Questionários (amostra aprovada por Eduardo em 02/10/2026): tudo o que chegou pelo questionário do
 * site, do recebimento à proposta, num lugar só. A situação vem da oportunidade: nada se digita duas
 * vezes. Ao clicar numa linha, as respostas do cliente abrem por seção, sem precisar do PDF. */

import { Fragment, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { LinhaDoPainel, Listas, PainelDeQuestionarios, SecaoDeRespostas, SituacaoDoPainel } from "../api/tipos";
import { EstadoDaBuscaDeQuestionarios } from "../componentes/EstadoDaBuscaDeQuestionarios";
import { LinkDeArquivo } from "../componentes/LinkDeArquivo";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { usarAcesso } from "../entrada";
import { cnpj, data, dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";
import { BotaoDeComposicao, Explicavel } from "../componentes/Indicador";

/** Os questionários do período que compõem um número do topo (10/10/2026), com os filtros de serviço e porte
 * (a situação escolhida na lista não muda os números, então aqui também não). */
function QuestionariosDaConta({ filtros, entra, comDias = false }: {
  filtros: { dias: number | null; servico?: string; porte?: string }; entra: (l: LinhaDoPainel) => boolean; comDias?: boolean;
}) {
  const { dados, carregando, erro, recarregar } = usarDados<PainelDeQuestionarios>(
    () => api.painelDeQuestionarios({ ...filtros, situacao: "" }), [filtros.dias, filtros.servico, filtros.porte]);
  if (carregando && !dados) return <Carregando rotulo="Buscando os questionários" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  const itens = (dados?.itens ?? []).filter(entra);
  if (itens.length === 0) return <p className="numero-estado">Nenhum questionário nesta conta no período.</p>;
  const dias = (l: LinhaDoPainel) =>
    l.proposta_enviada_em ? Math.round((new Date(`${l.proposta_enviada_em}T12:00:00`).getTime() - new Date(l.recebido_em).getTime()) / 86400000) : null;
  return (
    <table className="tabela" aria-label="Questionários na conta">
      <thead><tr><th>Empresa</th><th>Recebido</th><th>Situação</th>{comDias ? <th className="tabela-numero">Dias até a proposta</th> : <th>Proposta</th>}</tr></thead>
      <tbody>
        {itens.map((l) => (
          <tr key={l.id}><td>{l.nome_fantasia || l.razao_social}</td><td>{data(l.recebido_em)}</td>
            <td>{l.situacao_do_painel.replaceAll("_", " ")}{l.dias_uteis_aguardando ? ` · ${l.dias_uteis_aguardando} dias úteis` : ""}</td>
            {comDias ? <td className="tabela-numero">{dias(l) ?? "—"}</td> : <td>{l.proposta_enviada_em ? `enviada ${data(l.proposta_enviada_em)}` : "—"}</td>}</tr>
        ))}
      </tbody>
    </table>
  );
}

const PERIODOS: { dias: number; rotulo: string; antes: string }[] = [
  { dias: 30, rotulo: "Últimos 30 dias", antes: "30 dias anteriores" },
  { dias: 90, rotulo: "Últimos 90 dias", antes: "90 dias anteriores" },
  { dias: 365, rotulo: "Últimos 12 meses", antes: "12 meses anteriores" },
  { dias: 0, rotulo: "Desde o primeiro", antes: "" },
];

const SITUACOES: { chave: SituacaoDoPainel; rotulo: string }[] = [
  { chave: "precisa_de_voce", rotulo: "Precisa de você" },
  { chave: "aguardando_proposta", rotulo: "Aguardando proposta" },
  { chave: "proposta_enviada", rotulo: "Proposta enviada" },
  { chave: "em_espera", rotulo: "Em espera" },
  { chave: "aceita", rotulo: "Aceita" },
  { chave: "perdida", rotulo: "Perdida" },
];

/** Ícone e texto, nunca só a cor (PAD-002). */
function Situacao({ l }: { l: LinhaDoPainel }) {
  switch (l.situacao_do_painel) {
    case "precisa_de_voce":
      return <span className="etiqueta etiqueta-perda">! precisa de você</span>;
    case "aguardando_proposta": {
      const d = l.dias_uteis_aguardando ?? 0;
      return <span className="etiqueta etiqueta-espera">⏳ aguardando proposta · {d} dia{d === 1 ? "" : "s"} út{d === 1 ? "il" : "eis"}</span>;
    }
    case "proposta_enviada":
      return <span className="etiqueta etiqueta-andamento">↗ proposta enviada{l.proposta_numero ? ` · ${l.proposta_numero}` : ""}</span>;
    case "em_espera":
      return <span className="etiqueta etiqueta-neutra">‖ em espera</span>;
    case "aceita":
      return <span className="etiqueta etiqueta-ganho">✓ aceita</span>;
    case "perdida":
      return <span className="etiqueta etiqueta-neutra">✗ perdida{l.motivo_da_perda ? ` · ${l.motivo_da_perda.toLowerCase()}` : ""}</span>;
  }
}

function Respostas({ id, nome }: { id: number; nome: string }) {
  const { dados, carregando, erro, recarregar } = usarDados<SecaoDeRespostas[]>(() => api.respostasDoQuestionario(id), [id]);
  if (carregando && !dados) return <Carregando rotulo="Abrindo as respostas" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados || dados.length === 0) return <p className="campo-ajuda">O questionário chegou sem respostas além da identificação.</p>;
  return (
    <div className="questionario-respostas" aria-label={`Respostas de ${nome}`}>
      {dados.map((s) => (
        <section key={s.numero} className="questionario-secao">
          <h4>{s.numero} · {s.titulo}</h4>
          <dl>
            {s.respostas.map((r) => (
              <Fragment key={r.rotulo}>
                <dt>{r.rotulo}</dt>
                <dd>{r.valor}</dd>
              </Fragment>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}

function Acoes({ l, aoAbrir, aoResolver }: { l: LinhaDoPainel; aoAbrir: (id: number) => void; aoResolver: () => void }) {
  const { pode } = usarAcesso();
  const [erro, definirErro] = useState<string | null>(null);
  const resolver = (acao: "anexar" | "criar") =>
    api.resolverQuestionario(l.id, acao).then(aoResolver).catch((f) => definirErro(f instanceof ErroDaApi ? f.message : "Falha ao resolver."));
  const pdf = l.tem_pdf && <LinkDeArquivo className="link-de-tabela" href={`/api/questionarios/${l.id}/pdf`} novaAba>PDF</LinkDeArquivo>;
  if (l.situacao_do_painel === "precisa_de_voce") {
    return (
      <span className="questionario-acoes">
        {pode("funil.questionarios") ? (
          <>
            <button type="button" className="link-de-tabela" onClick={(e) => { e.stopPropagation(); void resolver("anexar"); }}>Anexar à existente</button>
            {" · "}
            <button type="button" className="link-de-tabela" onClick={(e) => { e.stopPropagation(); void resolver("criar"); }}>Criar nova</button>
          </>
        ) : (
          <span className="campo-ajuda">quem busca questionários resolve</span>
        )}
        {pdf && <> · {pdf}</>}
        {erro && <span className="estado-texto estado-erro" role="alert"> ✗ {erro}</span>}
      </span>
    );
  }
  return (
    <span className="questionario-acoes">
      {l.oportunidade_id !== null && pode("funil.ver") && (
        <button type="button" className="link-de-tabela" onClick={(e) => { e.stopPropagation(); aoAbrir(l.oportunidade_id!); }}>
          Abrir oportunidade
        </button>
      )}
      {pdf && <>{l.oportunidade_id !== null && pode("funil.ver") ? " · " : ""}{pdf}</>}
    </span>
  );
}

export function Questionarios({ listas }: { listas: Listas | null }) {
  const [dias, definirDias] = useState(30);
  const [servico, definirServico] = useState("");
  const [porte, definirPorte] = useState("");
  const [situacao, definirSituacao] = useState<SituacaoDoPainel | "">("");
  const [aberta, definirAberta] = useState<number | null>(null);
  const [oportunidade, definirOportunidade] = useState<number | null>(null);
  const { dados, carregando, erro, recarregar } = usarDados<PainelDeQuestionarios>(
    () => api.painelDeQuestionarios({ dias, servico, porte, situacao }),
    [dias, servico, porte, situacao],
  );
  // As opções dos filtros vêm do que chegou (o período inteiro, sem os outros filtros).
  const { dados: todos } = usarDados<PainelDeQuestionarios>(() => api.painelDeQuestionarios({ dias: 0 }), []);
  const servicos = [...new Set((todos?.itens ?? []).flatMap((l) => l.servicos))].sort();
  const portes = [...new Set((todos?.itens ?? []).map((l) => l.porte_crm).filter((p): p is string => !!p))].sort();
  const periodo = PERIODOS.find((p) => p.dias === dias)!;
  const filtrado = !!(servico || porte || situacao);

  if (carregando && !dados) return <Carregando rotulo="Abrindo os questionários" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const n = dados.numeros;
  const media = n.media_de_dias_ate_a_proposta;
  const filtrosDaConta = { dias, servico: servico || undefined, porte: porte || undefined };
  const ver = (titulo: string, quantos: number, entra: (l: LinhaDoPainel) => boolean, comDias = false) => (
    <BotaoDeComposicao rotulo="ver" composicao={{ titulo, subtitulo: periodo.rotulo, quantos,
      conteudo: () => <QuestionariosDaConta filtros={filtrosDaConta} entra={entra} comDias={comDias} /> }} />
  );
  const enviado = (l: LinhaDoPainel) => l.proposta_enviada_em !== null || l.situacao_do_painel === "proposta_enviada" || l.situacao_do_painel === "aceita";

  return (
    <div className="questionarios">
      <EstadoDaBuscaDeQuestionarios aoChegar={recarregar} />
      <div className="questionarios-numeros">
        <div className="numero">
          <div className="numero-rotulo">
            <Explicavel texto="Questionários do site recebidos no período, com os filtros de serviço e porte.">Recebidos · {periodo.rotulo.toLowerCase()}</Explicavel>
            {ver("Recebidos", n.recebidos, () => true)}
          </div>
          <div className="numero-valor">{n.recebidos}</div>
          <div className="numero-detalhe">{n.recebidos_antes !== null ? `${periodo.antes}: ${n.recebidos_antes}` : "desde o primeiro questionário"}</div>
        </div>
        <div className="numero">
          <div className="numero-rotulo">
            <Explicavel texto="Recebidos no período cuja proposta ainda não foi enviada; conta os dias úteis de espera (alerta acima de 5).">Aguardando proposta</Explicavel>
            {ver("Aguardando proposta", n.aguardando, (l) => l.situacao_do_painel === "aguardando_proposta")}
          </div>
          <div className="numero-valor">{n.aguardando}</div>
          <div className="numero-detalhe">
            {n.aguardando_atrasados > 0 ? `⚠ ${n.aguardando_atrasados} há mais de 5 dias úteis` : "nenhum há mais de 5 dias úteis"}
          </div>
        </div>
        <div className="numero">
          <div className="numero-rotulo">
            <Explicavel texto="Recebidos no período cuja proposta já foi enviada (ou aceita), sobre todos os recebidos.">Viraram proposta enviada</Explicavel>
            {ver("Viraram proposta enviada", n.enviados, enviado)}
          </div>
          <div className="numero-valor">{n.enviados} de {n.recebidos}</div>
          <div className="numero-detalhe">
            {n.recebidos > 0 ? `${Math.round((n.enviados / n.recebidos) * 100)}% no período` : "nenhum recebido no período"}
          </div>
        </div>
        <div className="numero">
          <div className="numero-rotulo">
            <Explicavel texto="Média de dias corridos entre o recebimento do questionário e o envio da proposta, nos que já foram enviados.">Do questionário à proposta</Explicavel>
            {ver("Do questionário à proposta", n.enviados, (l) => l.proposta_enviada_em !== null, true)}
          </div>
          <div className="numero-valor">{media !== null ? `${Number(media).toLocaleString("pt-BR")} dia${Number(media) === 1 ? "" : "s"}` : "—"}</div>
          <div className="numero-detalhe">{media !== null ? "média dos enviados" : "nenhuma proposta enviada ainda"}</div>
        </div>
        <div className="numero">
          <div className="numero-rotulo">
            <Explicavel texto="Questionários de grupo que já tinha oportunidade aberta: alguém decide se junta ou abre outra.">Precisam de você</Explicavel>
            {ver("Precisam de você", n.precisam_de_voce, (l) => l.situacao_do_painel === "precisa_de_voce")}
          </div>
          <div className="numero-valor">{n.precisam_de_voce}</div>
          <div className="numero-detalhe">já havia oportunidade aberta no grupo</div>
        </div>
      </div>

      <div className="questionarios-filtros" aria-label="Filtros">
        <select className="selecao" aria-label="Período" value={dias} onChange={(e) => definirDias(Number(e.target.value))}>
          {PERIODOS.map((p) => <option key={p.dias} value={p.dias}>{p.rotulo}</option>)}
        </select>
        <select className="selecao" aria-label="Serviço" value={servico} onChange={(e) => definirServico(e.target.value)}>
          <option value="">Todos os serviços</option>
          {servicos.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="selecao" aria-label="Porte" value={porte} onChange={(e) => definirPorte(e.target.value)}>
          <option value="">Todos os portes</option>
          {portes.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="selecao" aria-label="Situação" value={situacao} onChange={(e) => definirSituacao(e.target.value as SituacaoDoPainel | "")}>
          <option value="">Todas as situações</option>
          {SITUACOES.map((s) => <option key={s.chave} value={s.chave}>{s.rotulo}</option>)}
        </select>
      </div>

      {dados.itens.length === 0 ? (
        filtrado ? (
          <VazioPorFiltro aoLimpar={() => { definirServico(""); definirPorte(""); definirSituacao(""); }} />
        ) : (
          <VazioSemDados
            titulo="Nenhum questionário no período"
            explicacao="O CRM busca os questionários do site sozinho, a cada 10 minutos. Escolha um período maior para ver os anteriores."
          />
        )
      ) : (
        <>
          <p className="campo-ajuda">
            {dados.itens.length} questionário{dados.itens.length === 1 ? "" : "s"}. Clique numa linha para ler as respostas por seção.
          </p>
          <div className="tabela-rolagem">
            <table className="tabela questionarios-tabela" aria-label="Questionários">
              <thead>
                <tr>
                  <th scope="col">Recebido</th>
                  <th scope="col">Empresa</th>
                  <th scope="col">Contato</th>
                  <th scope="col">Serviços</th>
                  <th scope="col">Porte</th>
                  <th scope="col">Situação</th>
                  <th scope="col"><span className="visualmente-oculto">Ações</span></th>
                </tr>
              </thead>
              <tbody>
                {dados.itens.map((l) => (
                  <Fragment key={l.id}>
                    <tr
                      className={`linha-clicavel${aberta === l.id ? " linha-aberta" : ""}`}
                      tabIndex={0}
                      aria-expanded={aberta === l.id}
                      onClick={() => definirAberta(aberta === l.id ? null : l.id)}
                      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); definirAberta(aberta === l.id ? null : l.id); } }}
                    >
                      <td className="celula-numero">{dataHora(l.recebido_em)}</td>
                      <td>
                        {l.nome_fantasia || l.razao_social}
                        <span className="celula-fonte sem-quebra">CNPJ {cnpj(l.cnpj)}</span>
                      </td>
                      <td>
                        {l.contato_nome}
                        {l.contato_cargo && <span className="celula-fonte">{l.contato_cargo}</span>}
                      </td>
                      <td>{l.servicos.join(", ") || "—"}</td>
                      <td>
                        {l.porte_crm ?? "—"}
                        {l.porte_site && l.porte_crm && l.porte_site !== l.porte_crm && (
                          <span className="celula-fonte">régua do CRM · o site dizia {l.porte_site}</span>
                        )}
                      </td>
                      <td>
                        <Situacao l={l} />
                        {l.proposta_enviada_em && <span className="celula-fonte">enviada em {data(l.proposta_enviada_em)}</span>}
                      </td>
                      <td><Acoes l={l} aoAbrir={definirOportunidade} aoResolver={recarregar} /></td>
                    </tr>
                    {aberta === l.id && (
                      <tr className="linha-detalhe">
                        <td colSpan={7}><Respostas id={l.id} nome={l.nome_fantasia || l.razao_social} /></td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {oportunidade !== null && (
        <DetalheDaOportunidade id={oportunidade} listas={listas} aoFechar={() => definirOportunidade(null)} aoSalvar={recarregar} />
      )}
    </div>
  );
}
