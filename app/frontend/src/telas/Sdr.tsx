/** O SDR de IA: painel, fila de leads e custos — 27/09/2026.
 *
 * O painel segue a amostra aprovada por Eduardo em 27/09/2026. Tudo vem de
 * `GET /api/sdr/painel`, que calcula sobre os leads que chegaram no mês.
 * Número sem base não vira zero: a tela diz o que falta.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type {
  Contagem,
  IndicadorDoSdr,
  InvestimentoEmMidia,
  Listas,
  PainelDoSdr,
  ParametrosDoSdr,
} from "../api/tipos";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { dinheiro } from "../formato";
import { mesAnterior, mesAtual, nomeDoMes, numero, pct, tempo } from "../sdrFormato";
import { usarDados } from "../usarDados";
import { Leads } from "./Leads";

type Aba = "painel" | "leads" | "custos";

const ABAS: { chave: Aba; rotulo: string }[] = [
  { chave: "painel", rotulo: "Painel" },
  { chave: "leads", rotulo: "Leads" },
  { chave: "custos", rotulo: "Custos e mídia" },
];

export function Sdr({ listas }: { listas: Listas | null }) {
  const [aba, definirAba] = useState<Aba>("painel");
  return (
    <>
      <div className="abas sdr-abas" role="tablist" aria-label="SDR da IA">
        {ABAS.map((a) => (
          <button
            key={a.chave}
            type="button"
            role="tab"
            className="aba"
            aria-selected={aba === a.chave}
            onClick={() => definirAba(a.chave)}
          >
            {a.rotulo}
          </button>
        ))}
      </div>
      {aba === "painel" && <PainelDoSdrTela />}
      {aba === "leads" && <Leads listas={listas} />}
      {aba === "custos" && <Custos />}
    </>
  );
}

const TOM_DA_AVALIACAO: Record<string, string> = {
  "Na meta": "ganho",
  "Entre a meta e o alerta": "espera",
  "Em alerta": "perda",
};

/** Estado com palavra, nunca só cor: a etiqueta diz a avaliação e a meta. */
function Avaliacao({ indicador }: { indicador: IndicadorDoSdr | { avaliacao: string | null; meta?: string | null } }) {
  if (!indicador.avaliacao) return null;
  return (
    <span className={`etiqueta etiqueta-${TOM_DA_AVALIACAO[indicador.avaliacao] ?? "neutra"}`}>
      {indicador.avaliacao}
      {indicador.meta ? ` · ${indicador.meta}` : ""}
    </span>
  );
}

function Variacao({
  atual,
  anterior,
  mes,
  unidade,
}: {
  atual: number | null;
  anterior: number | null | undefined;
  mes: string;
  unidade: "pp" | "s" | "n" | "nota";
}) {
  if (atual === null || anterior === null || anterior === undefined) return null;
  const diferenca = atual - anterior;
  const sinal = diferenca > 0 ? "+" : diferenca < 0 ? "−" : "";
  const valor = Math.abs(diferenca);
  const texto =
    unidade === "pp"
      ? `${sinal}${numero(valor, 1)} p.p.`
      : unidade === "s"
        ? `${sinal}${tempo(valor)}`
        : unidade === "nota"
          ? `${sinal}${numero(valor, 1)}`
          : `${sinal}${numero(valor)}`;
  return (
    <span className="sdr-variacao">
      <b>{texto}</b> sobre {nomeDoMes(mesAnterior(mes))}
    </span>
  );
}

// ------------------------------------------------------------- gráficos
function Barras({
  itens,
  base,
  rotuloDaBase,
  destaque,
}: {
  itens: Contagem[];
  base: number;
  rotuloDaBase: string;
  destaque?: (nome: string) => boolean;
}) {
  const maior = Math.max(...itens.map((i) => i.quantidade), 1);
  return (
    <ul className="sdr-barras">
      {itens.map((i) => {
        const parte = base ? `${numero((100 * i.quantidade) / base)}%` : "";
        return (
          <li
            key={i.nome}
            className="sdr-barra"
            title={`${i.nome}: ${numero(i.quantidade)} ${rotuloDaBase}${parte ? `, ${parte}` : ""}`}
          >
            <span className="sdr-barra-nome">{i.nome}</span>
            <span className="sdr-barra-trilho" aria-hidden="true">
              <span
                className={`sdr-barra-fill${destaque && !destaque(i.nome) ? " sdr-barra-fraca" : ""}`}
                style={{ width: `${(100 * i.quantidade) / maior}%` }}
              />
            </span>
            <span className="sdr-barra-valor">
              {numero(i.quantidade)} <span>{parte}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function SemDado({ texto }: { texto: string }) {
  return <p className="sdr-sem-dado">{texto}</p>;
}

// ---------------------------------------------------------------- painel
function PainelDoSdrTela() {
  const [mes, definirMes] = useState(mesAtual());
  const [origem, definirOrigem] = useState("");

  const { dados, carregando, erro, recarregar } = usarDados<PainelDoSdr>(
    () => api.painelDoSdr({ mes, origem: origem || undefined }),
    [mes, origem],
  );

  return (
    <div className="sdr">
      <div className="filtros">
        <div className="campo">
          <label className="campo-rotulo" htmlFor="sdr-mes">
            Mês de chegada do lead
          </label>
          <input
            id="sdr-mes"
            type="month"
            className="entrada"
            value={mes}
            onChange={(e) => e.target.value && definirMes(e.target.value)}
          />
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="sdr-origem">
            Origem
          </label>
          <select
            id="sdr-origem"
            className="selecao"
            value={origem}
            onChange={(e) => definirOrigem(e.target.value)}
          >
            <option value="">Todas as origens</option>
            <option value="trafego_pago">Tráfego pago</option>
            <option value="frio">Leads frios</option>
          </select>
        </div>
      </div>

      {carregando && <Carregando rotulo="Calculando o painel" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {!carregando && !erro && dados && dados.leads === 0 && (
        origem ? (
          <VazioPorFiltro aoLimpar={() => definirOrigem("")} />
        ) : (
          <VazioSemDados
            titulo={`Nenhum lead chegou em ${nomeDoMes(mes)}`}
            explicacao="O painel acompanha os leads que chegaram no mês e tudo o que aconteceu com eles. As conversas entram pela integração do WhatsApp e do e-mail, ainda em preparação. Enquanto isso, os leads cadastrados na aba Leads já aparecem aqui."
          />
        )
      )}
      {!carregando && !erro && dados && dados.leads > 0 && <Conteudo painel={dados} />}
    </div>
  );
}

function Conteudo({ painel: p }: { painel: PainelDoSdr }) {
  const anterior = p.anterior;
  return (
    <>
      <section className="sdr-secao" aria-labelledby="sdr-s1">
        <div className="sdr-secao-topo">
          <h2 id="sdr-s1">Resultado do SDR</h2>
          <p>
            {numero(p.leads)} leads · {numero(p.responderam)} responderam à IA
            {p.em_andamento > 0 && ` · ${numero(p.em_andamento)} conversas em andamento`}
          </p>
        </div>
        <div className="sdr-kpis">
          <article className="sdr-bloco sdr-kpi sdr-kpi-principal">
            <span className="sdr-kpi-rotulo">Leads qualificados pela IA</span>
            <span className="sdr-kpi-valor">{numero(p.qualificados)}</span>
            <div className="sdr-linha">
              <span className="etiqueta etiqueta-neutra">
                {numero(p.reunioes)} com reunião marcada
              </span>
              <Avaliacao indicador={p.indicador_reuniao} />
            </div>
            <span className="sdr-apoio">
              {pct(p.qualificados_sobre_leads) ?? "—"} dos leads ·{" "}
              {pct(p.qualificados_sobre_responderam) ?? "sem respostas"} dos que responderam
            </span>
            <Variacao atual={p.qualificados} anterior={anterior?.qualificados} mes={p.mes} unidade="n" />
          </article>

          <article className="sdr-bloco sdr-kpi">
            <span className="sdr-kpi-rotulo">Qualificação concluída pela IA</span>
            {pct(p.qualificacao_concluida) ? (
              <span className="sdr-kpi-valor">{pct(p.qualificacao_concluida)}</span>
            ) : (
              <SemDado texto="Nenhuma conversa terminou ainda" />
            )}
            <div className="sdr-linha">
              <Avaliacao indicador={p.indicador_qualificacao} />
            </div>
            <span className="sdr-apoio">
              {numero(p.qualificacao_concluida.numerador)} de {numero(p.com_desfecho)} conversas
              terminaram com veredito da IA: {numero(p.qualificados)} qualificados e{" "}
              {numero(p.fora_do_perfil)} fora do perfil
            </span>
            <Variacao
              atual={p.qualificacao_concluida.valor}
              anterior={anterior?.qualificacao_concluida}
              mes={p.mes}
              unidade="pp"
            />
          </article>

          <article className="sdr-bloco sdr-kpi">
            <span className="sdr-kpi-rotulo">Passadas para a equipe (transbordo)</span>
            {pct(p.transbordo) ? (
              <span className="sdr-kpi-valor">{pct(p.transbordo)}</span>
            ) : (
              <SemDado texto="Nenhuma conversa terminou ainda" />
            )}
            <div className="sdr-linha">
              <Avaliacao indicador={p.indicador_transbordo} />
            </div>
            <span className="sdr-apoio">
              {numero(p.transbordo.numerador)} de {numero(p.com_desfecho)} conversas. Outras{" "}
              {numero(p.parou.numerador)} ({pct(p.parou) ?? "—"}) pararam no meio
            </span>
            <Variacao atual={p.transbordo.valor} anterior={anterior?.transbordo} mes={p.mes} unidade="pp" />
          </article>

          <article className="sdr-bloco sdr-kpi">
            <span className="sdr-kpi-rotulo">Tempo de qualificação (TMA)</span>
            {tempo(p.tma_segundos) ? (
              <span className="sdr-kpi-valor">{tempo(p.tma_segundos)}</span>
            ) : (
              <SemDado texto="A IA ainda não concluiu nenhuma conversa" />
            )}
            <div className="sdr-linha">
              {p.primeira_resposta.valor !== null && (
                <span
                  className={`etiqueta etiqueta-${TOM_DA_AVALIACAO[p.primeira_resposta.avaliacao ?? ""] ?? "neutra"}`}
                >
                  1ª resposta em {tempo(p.primeira_resposta.valor)} · {p.primeira_resposta.avaliacao}
                </span>
              )}
            </div>
            <span className="sdr-apoio">
              Média nas conversas que a IA concluiu. A 1ª resposta é a mediana para lead de tráfego
              pago, {p.primeira_resposta.meta}
            </span>
            <Variacao atual={p.tma_segundos} anterior={anterior?.tma_segundos} mes={p.mes} unidade="s" />
          </article>

          <article className="sdr-bloco sdr-kpi">
            <span className="sdr-kpi-rotulo">Nota do lead para a conversa (CSAT)</span>
            {p.csat.valor !== null ? (
              <span className="sdr-kpi-valor">
                {numero(p.csat.valor, 1)}
                <small>de 5</small>
              </span>
            ) : (
              <SemDado texto="Nenhuma nota no mês" />
            )}
            <div className="sdr-linha">
              <Avaliacao indicador={p.csat} />
            </div>
            <span className="sdr-apoio">
              {numero(p.notas)} notas
              {p.satisfeitos.valor !== null && ` · ${pct(p.satisfeitos, 0)} deram 4 ou 5`}
            </span>
            <Variacao atual={p.csat.valor} anterior={anterior?.csat} mes={p.mes} unidade="nota" />
          </article>
        </div>

        <article className="sdr-bloco">
          <div>
            <h3 className="sdr-bloco-titulo">Resultado por origem</h3>
            <p className="sdr-bloco-sub">
              O custo considera só a mídia do mês, lançada em Custos e mídia. Lead frio não tem custo
              de mídia.
            </p>
          </div>
          <PorOrigem painel={p} />
        </article>
      </section>

      <section className="sdr-secao" aria-labelledby="sdr-s2">
        <div className="sdr-secao-topo">
          <h2 id="sdr-s2">O que o lead procura e se a IA entendeu</h2>
        </div>
        <div className="sdr-grade sdr-grade-7-5">
          <article className="sdr-bloco">
            <div>
              <h3 className="sdr-bloco-titulo">O que o lead procura</h3>
              <p className="sdr-bloco-sub">Assunto reconhecido nos {numero(p.responderam)} leads que responderam</p>
            </div>
            {p.interesses.length ? (
              <Barras
                itens={p.interesses}
                base={p.responderam}
                rotuloDaBase="leads"
                destaque={(n) => n !== "Outros assuntos" && n !== "Sem assunto reconhecido"}
              />
            ) : (
              <SemDado texto="Nenhum lead respondeu no mês" />
            )}
          </article>
          <div className="sdr-coluna">
            <article className="sdr-bloco">
              <div>
                <h3 className="sdr-bloco-titulo">Confiança da IA ao responder</h3>
                <p className="sdr-bloco-sub">Distribuição das {numero(p.confianca.respostas)} respostas com confiança registrada</p>
              </div>
              {p.confianca.media !== null ? (
                <>
                  <div className="sdr-linha">
                    <span className="sdr-kpi-valor">{numero(p.confianca.media, 2)}</span>
                    <span className="sdr-apoio">média de 0 a 1</span>
                    {p.confianca.abaixo_de_0_6.numerador > 0 && (
                      <span className="etiqueta etiqueta-espera">
                        {pct(p.confianca.abaixo_de_0_6, 0)} abaixo de 0,6
                      </span>
                    )}
                  </div>
                  <Barras
                    itens={p.confianca.faixas}
                    base={p.confianca.respostas}
                    rotuloDaBase="respostas"
                    destaque={(n) => n === "abaixo de 0,6"}
                  />
                </>
              ) : (
                <SemDado texto="Nenhuma resposta da IA com confiança registrada" />
              )}
            </article>
            <article className="sdr-bloco">
              <div className="sdr-bloco-cab">
                <div>
                  <h3 className="sdr-bloco-titulo">Falhas de compreensão</h3>
                  <p className="sdr-bloco-sub">Respostas "não entendi" ou intenção padrão de erro</p>
                </div>
                <Avaliacao indicador={p.indicador_falhas} />
              </div>
              <div className="sdr-dupla">
                <div className="sdr-mini">
                  <b>{pct(p.falhas_por_resposta) ?? "—"}</b>
                  <span>
                    das respostas ({numero(p.falhas_por_resposta.numerador)} de{" "}
                    {numero(p.falhas_por_resposta.denominador)})
                  </span>
                </div>
                <div className="sdr-mini">
                  <b>{pct(p.falhas_por_conversa) ?? "—"}</b>
                  <span>
                    das conversas tiveram ao menos uma ({numero(p.falhas_por_conversa.numerador)} de{" "}
                    {numero(p.falhas_por_conversa.denominador)})
                  </span>
                </div>
              </div>
            </article>
          </div>
        </div>
        <article className="sdr-bloco">
          <div>
            <h3 className="sdr-bloco-titulo">Termos que a IA não reconheceu</h3>
            <p className="sdr-bloco-sub">
              Quanto maior, mais vezes apareceu. O número ao lado é a contagem. Cada termo é candidato
              a assunto novo no roteiro ou a sinônimo de um que já existe.
            </p>
          </div>
          {p.termos.length ? <Nuvem termos={p.termos} /> : <SemDado texto="Nenhum termo sem reconhecimento no mês" />}
        </article>
      </section>

      <section className="sdr-secao" aria-labelledby="sdr-s3">
        <div className="sdr-secao-topo">
          <h2 id="sdr-s3">Onde o lead para, sai ou pede uma pessoa</h2>
        </div>
        <div className="sdr-grade sdr-grade-7-5">
          <article className="sdr-bloco">
            <div>
              <h3 className="sdr-bloco-titulo">Funil da qualificação</h3>
              <p className="sdr-bloco-sub">Leads que chegaram a cada etapa. Entre as etapas, quem saiu e por quê.</p>
            </div>
            <Funil painel={p} />
          </article>
          <div className="sdr-coluna">
            <article className="sdr-bloco">
              <div>
                <h3 className="sdr-bloco-titulo">Por que a IA passou para a equipe</h3>
                <p className="sdr-bloco-sub">Motivo registrado em cada transbordo</p>
              </div>
              {p.gatilhos.length ? (
                <Barras itens={p.gatilhos} base={p.transbordo.numerador} rotuloDaBase="transbordos" />
              ) : (
                <SemDado texto="Nenhum transbordo no mês" />
              )}
            </article>
            <article className="sdr-bloco">
              <div>
                <h3 className="sdr-bloco-titulo">Tom do lead</h3>
                <p className="sdr-bloco-sub">Tom predominante nas mensagens do lead, por conversa</p>
              </div>
              {p.tom.length ? <TomDoLead tom={p.tom} /> : <SemDado texto="Nenhuma mensagem com tom registrado" />}
            </article>
          </div>
        </div>
        <article className="sdr-bloco">
          <div>
            <h3 className="sdr-bloco-titulo">Por que a IA descartou</h3>
            <p className="sdr-bloco-sub">
              Motivo de cada lead fora do perfil. Quem pediu para não ser contatado fica marcado "não
              contatar" no CRM.
            </p>
          </div>
          {p.descartes.length ? (
            <Barras itens={p.descartes} base={p.fora_do_perfil} rotuloDaBase="leads" />
          ) : (
            <SemDado texto="Nenhum lead fora do perfil no mês" />
          )}
        </article>
      </section>

      <section className="sdr-secao" aria-labelledby="sdr-s4">
        <div className="sdr-secao-topo">
          <h2 id="sdr-s4">O que chega ao CRM e à equipe</h2>
        </div>
        <div className="sdr-grade sdr-grade-3">
          <article className="sdr-bloco sdr-kpi">
            <h3 className="sdr-bloco-titulo">Registros no CRM</h3>
            <span className="sdr-kpi-valor">
              {numero(p.oportunidades)}
              <small>{p.oportunidades === 1 ? "oportunidade" : "oportunidades"}</small>
            </span>
            <span className="sdr-apoio">
              {numero(p.leads)} leads registrados · {numero(p.com_dados_da_empresa)} com dados da empresa
            </span>
            <div className="sdr-linha">
              <span className="etiqueta etiqueta-neutra">{numero(p.reunioes)} reuniões marcadas</span>
            </div>
          </article>
          <CustoPoupado painel={p} />
          <article className="sdr-bloco">
            <div>
              <h3 className="sdr-bloco-titulo">Porte estimado dos qualificados</h3>
              <p className="sdr-bloco-sub">
                Pela régua de porte, com o que o lead informou. Quem conduz a entrevista confirma.
              </p>
            </div>
            {p.portes.length ? (
              <Barras itens={p.portes} base={p.qualificados} rotuloDaBase="qualificados" />
            ) : (
              <SemDado texto="Nenhum lead qualificado no mês" />
            )}
          </article>
        </div>
        <article className="sdr-bloco">
          <div>
            <h3 className="sdr-bloco-titulo">Fila de transbordo por destino</h3>
            <p className="sdr-bloco-sub">
              Para quem foram os transbordos e quanto o lead esperou até a primeira mensagem da equipe
            </p>
          </div>
          <Destinos painel={p} />
        </article>
      </section>

      <Metodo />
    </>
  );
}

function PorOrigem({ painel }: { painel: PainelDoSdr }) {
  if (!painel.por_origem.length) return <SemDado texto="Nenhum lead no mês" />;
  return (
    <div className="tabela-rolagem">
      <table className="tabela sdr-tabela">
        <thead>
          <tr>
            <th scope="col">Origem</th>
            <th scope="col" className="tabela-numero">Leads</th>
            <th scope="col" className="tabela-numero">Responderam</th>
            <th scope="col" className="tabela-numero">Qualificados</th>
            <th scope="col" className="tabela-numero">Reuniões</th>
            <th scope="col" className="tabela-numero">Mídia</th>
            <th scope="col" className="tabela-numero">Custo por lead</th>
            <th scope="col" className="tabela-numero">Custo por qualificado</th>
          </tr>
        </thead>
        <tbody>
          {painel.por_origem.map((l) => (
            <tr key={l.origem} className={l.origem === "Tráfego pago · total" ? "sdr-linha-total" : undefined}>
              <td>{l.origem}</td>
              <td className="tabela-numero">{numero(l.leads)}</td>
              <td className="tabela-numero">
                {numero(l.responderam.numerador)} <span className="sdr-fraco">{pct(l.responderam) ?? ""}</span>
                {l.avaliacao_resposta && l.avaliacao_resposta !== "Na meta" && (
                  <> <Avaliacao indicador={{ avaliacao: l.avaliacao_resposta }} /></>
                )}
              </td>
              <td className="tabela-numero">
                {numero(l.qualificados.numerador)} <span className="sdr-fraco">{pct(l.qualificados) ?? ""}</span>
                {l.avaliacao_qualificados && l.avaliacao_qualificados !== "Na meta" && (
                  <> <Avaliacao indicador={{ avaliacao: l.avaliacao_qualificados }} /></>
                )}
              </td>
              <td className="tabela-numero">{numero(l.reunioes)}</td>
              <td className="tabela-numero">
                {l.midia !== null ? dinheiro(l.midia) : <span className="sdr-fraco">sem mídia lançada</span>}
              </td>
              <td className="tabela-numero">{l.custo_por_lead !== null ? dinheiro(l.custo_por_lead) : "—"}</td>
              <td className="tabela-numero">
                {l.custo_por_qualificado !== null ? dinheiro(l.custo_por_qualificado) : "—"}
                {l.avaliacao_custo && l.avaliacao_custo !== "Na meta" && (
                  <> <Avaliacao indicador={{ avaliacao: l.avaliacao_custo }} /></>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="sdr-nota">
        Os percentuais de "Responderam" e "Qualificados" são sobre os leads de cada origem. A etiqueta
        só aparece quando o número está fora da meta. "—" quer dizer sem mídia lançada ou sem
        qualificado para dividir.
      </p>
    </div>
  );
}

function Nuvem({ termos }: { termos: Contagem[] }) {
  const maior = termos[0].quantidade;
  const menor = termos[termos.length - 1].quantidade;
  return (
    <ul className="sdr-nuvem">
      {termos.map((t) => {
        const tamanho = maior === menor ? 18 : 13 + (15 * (t.quantidade - menor)) / (maior - menor);
        return (
          <li key={t.nome} style={{ fontSize: `${tamanho.toFixed(1)}px` }} title={`${t.nome}: ${t.quantidade} vezes`}>
            {t.nome}
            <sup>{t.quantidade}</sup>
          </li>
        );
      })}
    </ul>
  );
}

function Funil({ painel }: { painel: PainelDoSdr }) {
  const topo = painel.funil[0]?.leads || 1;
  return (
    <ol className="sdr-funil">
      {painel.funil.map((etapa) => {
        const saiu = etapa.saidas.reduce((s, c) => s + c.quantidade, 0);
        return (
          <li key={etapa.nome}>
            <div className="sdr-funil-etapa" title={`${etapa.nome}: ${numero(etapa.leads)} leads`}>
              <span className="sdr-barra-nome">{etapa.nome}</span>
              <span className="sdr-funil-trilho" aria-hidden="true">
                <span className="sdr-funil-fill" style={{ width: `${(100 * etapa.leads) / topo}%` }} />
              </span>
              <span className="sdr-barra-valor">
                {numero(etapa.leads)} <span>{numero((100 * etapa.leads) / topo)}%</span>
              </span>
            </div>
            {saiu > 0 && (
              <p className="sdr-funil-perda">
                <b>−{numero(saiu)}</b>{" "}
                {etapa.saidas.map((s) => `${numero(s.quantidade)} ${s.nome}`).join(" · ")}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

const CLASSE_DO_TOM: Record<string, string> = {
  Positivo: "sdr-tom-positivo",
  Neutro: "sdr-tom-neutro",
  Negativo: "sdr-tom-negativo",
};

function TomDoLead({ tom }: { tom: Contagem[] }) {
  const total = tom.reduce((s, t) => s + t.quantidade, 0);
  const parte = (t: Contagem) => `${numero((100 * t.quantidade) / total)}%`;
  return (
    <>
      <div className="sdr-empilhada" role="img" aria-label={tom.map((t) => `${t.nome} ${parte(t)}`).join(", ")}>
        {tom.map((t) => (
          <div key={t.nome} className={CLASSE_DO_TOM[t.nome]} style={{ flex: t.quantidade }} title={`${t.nome}: ${t.quantidade} conversas`} />
        ))}
      </div>
      <ul className="sdr-legenda">
        {tom.map((t) => (
          <li key={t.nome}>
            <i className={CLASSE_DO_TOM[t.nome]} aria-hidden="true" />
            {t.nome} <b>{parte(t)}</b>
          </li>
        ))}
      </ul>
    </>
  );
}

function CustoPoupado({ painel }: { painel: PainelDoSdr }) {
  const c = painel.custo_poupado;
  return (
    <article className="sdr-bloco sdr-kpi">
      <h3 className="sdr-bloco-titulo">Custo poupado no mês</h3>
      {c.liquido !== null ? (
        <>
          <span className="sdr-kpi-valor">{dinheiro(c.liquido)}</span>
          <span className="sdr-apoio">líquido, já descontado o custo da IA</span>
          <p className="sdr-conta">
            {numero(c.conversas_concluidas)} conversas concluídas × {dinheiro(c.custo_por_conversa)} ={" "}
            <b>{dinheiro(c.bruto)}</b>
            <br />− custo da IA = <b>{dinheiro(c.custo_ia)}</b>
            <br />= <b>{dinheiro(c.liquido)}</b>
          </p>
          {c.mensagens_sem_custo > 0 && (
            <span className="sdr-apoio">
              {numero(c.mensagens_sem_custo)} mensagens da IA vieram sem custo registrado e ficaram fora
              da conta.
            </span>
          )}
        </>
      ) : (
        <div className="sdr-pendente">
          <p className="sdr-pendente-estado">Falta definir</p>
          <p className="sdr-apoio">
            Para calcular, lance em Custos e mídia: {c.falta.join(", ")}.
          </p>
        </div>
      )}
    </article>
  );
}

function Destinos({ painel }: { painel: PainelDoSdr }) {
  if (!painel.destinos.length) return <SemDado texto="Nenhum transbordo no mês" />;
  const maior = painel.destinos[0].transbordos;
  const total = painel.transbordo.numerador || 1;
  return (
    <div className="tabela-rolagem">
      <table className="tabela sdr-tabela">
        <thead>
          <tr>
            <th scope="col">Destino</th>
            <th scope="col" className="tabela-numero">Transbordos</th>
            <th scope="col">
              <span className="sr">Proporção</span>
            </th>
            <th scope="col" className="tabela-numero">Espera média</th>
          </tr>
        </thead>
        <tbody>
          {painel.destinos.map((d) => (
            <tr key={d.destino}>
              <td>{d.destino}</td>
              <td className="tabela-numero">
                {numero(d.transbordos)} <span className="sdr-fraco">{numero((100 * d.transbordos) / total)}%</span>
              </td>
              <td className="sdr-barrinha" aria-hidden="true">
                <div style={{ width: `${(100 * d.transbordos) / maior}%` }} />
              </td>
              <td className="tabela-numero">
                {d.espera_media_min !== null ? `${numero(d.espera_media_min)} min` : "ninguém atendeu ainda"}
                {d.atendidos < d.transbordos && d.espera_media_min !== null && (
                  <span className="sdr-fraco"> · {numero(d.transbordos - d.atendidos)} esperando</span>
                )}{" "}
                {d.avaliacao && d.avaliacao !== "Na meta" && <Avaliacao indicador={{ avaliacao: d.avaliacao, meta: "alvo de 15 min" }} />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Metodo() {
  return (
    <details className="sdr-bloco sdr-metodo">
      <summary>Como cada número é calculado</summary>
      <dl>
        <dt>Mês</dt>
        <dd>
          O painel acompanha os leads que chegaram no mês (horário de Brasília) e tudo o que aconteceu
          com eles até agora. Por isso o funil fecha: cada lead está em uma etapa só.
        </dd>
        <dt>Leads qualificados</dt>
        <dd>Leads cuja conversa mais recente terminou com a IA enquadrando no perfil.</dd>
        <dt>Qualificação concluída pela IA</dt>
        <dd>
          Conversas que terminaram com veredito da IA (qualificado ou fora do perfil) ÷ conversas que já
          terminaram. Concluídas + transbordo + paradas no meio = 100%. As em andamento ficam fora até
          terminar.
        </dd>
        <dt>Transbordo</dt>
        <dd>Conversas passadas para uma pessoa ÷ conversas que já terminaram.</dd>
        <dt>Tempo de qualificação</dt>
        <dd>Média entre o início da conversa e o veredito, só nas que a IA concluiu.</dd>
        <dt>1ª resposta</dt>
        <dd>
          Mediana entre o registro do lead de tráfego pago no CRM e a primeira mensagem da IA. Não vale
          para lead frio, porque nele a IA fala primeiro.
        </dd>
        <dt>CSAT</dt>
        <dd>
          Média das notas de 1 a 5 dadas ao fim da conversa. O NPS fica de fora: o lead ainda não é
          cliente.
        </dd>
        <dt>Falhas de compreensão</dt>
        <dd>Respostas de fallback ÷ respostas da IA, e conversas com ao menos um fallback ÷ conversas.</dd>
        <dt>Custo por qualificado</dt>
        <dd>Mídia do mês no canal ÷ leads qualificados desse canal.</dd>
        <dt>Custo poupado</dt>
        <dd>
          Conversas concluídas pela IA × (custo da hora de SDR × minutos por conversa ÷ 60) − custo da
          IA no mês, convertido pela cotação lançada.
        </dd>
        <dt>Metas</dt>
        <dd>
          Aprovadas em 27/09/2026 como ponto de partida, para rever depois de 60 dias ou 300 leads. O
          tempo de qualificação não tem meta.
        </dd>
        <dt>Arredondamento</dt>
        <dd>
          Os percentuais são arredondados um a um, então uma lista pode somar 99% ou 101%. As contagens
          sempre fecham com o total.
        </dd>
      </dl>
    </details>
  );
}

// ------------------------------------------------------------ custos
function Custos() {
  const [mes, definirMes] = useState(mesAtual());
  return (
    <div className="sdr-grade sdr-grade-2 sdr-custos">
      <Parametros />
      <Midia mes={mes} aoTrocarMes={definirMes} />
    </div>
  );
}

function Parametros() {
  const { dados, carregando, erro, recarregar } = usarDados<ParametrosDoSdr>(() => api.parametrosDoSdr(), []);
  if (carregando) return <Carregando rotulo="Carregando os parâmetros" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  return <FormularioDeParametros atuais={dados!} aoSalvar={recarregar} />;
}

function FormularioDeParametros({ atuais, aoSalvar }: { atuais: ParametrosDoSdr; aoSalvar: () => void }) {
  const [campos, definirCampos] = useState({
    custo_hora_sdr: atuais.custo_hora_sdr ?? "",
    minutos_por_conversa: atuais.minutos_por_conversa?.toString() ?? "",
    cotacao_dolar: atuais.cotacao_dolar ?? "",
  });
  const [erro, definirErro] = useState<string | null>(null);
  const [salvo, definirSalvo] = useState(false);
  const [salvando, definirSalvando] = useState(false);
  const mudar = (campo: string, valor: string) => {
    definirSalvo(false);
    definirCampos((c) => ({ ...c, [campo]: valor }));
  };

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await api.gravarParametrosDoSdr({
        custo_hora_sdr: campos.custo_hora_sdr || null,
        minutos_por_conversa: campos.minutos_por_conversa ? Number(campos.minutos_por_conversa) : null,
        cotacao_dolar: campos.cotacao_dolar || null,
      });
      definirSalvo(true);
      aoSalvar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <section className="sdr-bloco" aria-labelledby="sdr-parametros">
      <div>
        <h3 className="sdr-bloco-titulo" id="sdr-parametros">Custo poupado</h3>
        <p className="sdr-bloco-sub">
          Sem estes três valores o painel não calcula o custo poupado. Use ponto como separador
          decimal.
        </p>
      </div>
      {erro && (
        <div className="estado estado-erro" role="alert">
          <p className="estado-texto">{erro}</p>
        </div>
      )}
      <div className="formulario">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="p-hora">Custo de uma hora de SDR (R$)</label>
          <input id="p-hora" className="entrada" inputMode="decimal" value={campos.custo_hora_sdr}
            onChange={(e) => mudar("custo_hora_sdr", e.target.value)} placeholder="45.00" />
          <p className="campo-ajuda">Salário × 1,8 de encargos ÷ 160 h. Com R$ 4.000 de salário, dá R$ 45.</p>
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="p-minutos">Minutos que um SDR levaria por conversa</label>
          <input id="p-minutos" className="entrada" inputMode="numeric" value={campos.minutos_por_conversa}
            onChange={(e) => mudar("minutos_por_conversa", e.target.value)} placeholder="25" />
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="p-dolar">Cotação do dólar (R$)</label>
          <input id="p-dolar" className="entrada" inputMode="decimal" value={campos.cotacao_dolar}
            onChange={(e) => mudar("cotacao_dolar", e.target.value)} />
          <p className="campo-ajuda">O custo da IA é medido em dólar, a cada mensagem.</p>
        </div>
      </div>
      <div className="sdr-linha">
        <button type="button" className="botao botao-primario" onClick={salvar} disabled={salvando}>
          {salvando ? "Salvando…" : "Salvar parâmetros"}
        </button>
        {salvo && <span className="etiqueta etiqueta-ganho">Salvo</span>}
      </div>
    </section>
  );
}

function Midia({ mes, aoTrocarMes }: { mes: string; aoTrocarMes: (mes: string) => void }) {
  const { dados, carregando, erro, recarregar } = usarDados<InvestimentoEmMidia[]>(() => api.midia(mes), [mes]);
  const [canal, definirCanal] = useState("");
  const [valor, definirValor] = useState("");
  const [falha, definirFalha] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);

  const salvar = async () => {
    definirSalvando(true);
    definirFalha(null);
    try {
      await api.gravarMidia({ mes, canal: canal.trim(), valor });
      definirCanal("");
      definirValor("");
      recarregar();
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <section className="sdr-bloco" aria-labelledby="sdr-midia">
      <div>
        <h3 className="sdr-bloco-titulo" id="sdr-midia">Investimento em mídia</h3>
        <p className="sdr-bloco-sub">
          Por mês e por canal de tráfego pago. O canal precisa ser escrito igual ao "Canal" dos leads
          (por exemplo, Meta Ads). Lançar de novo o mesmo canal no mesmo mês substitui o valor.
        </p>
      </div>
      <div className="campo">
        <label className="campo-rotulo" htmlFor="m-mes">Mês</label>
        <input id="m-mes" type="month" className="entrada" value={mes}
          onChange={(e) => e.target.value && aoTrocarMes(e.target.value)} />
      </div>
      {carregando && <Carregando rotulo="Carregando a mídia" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {!carregando && !erro && dados?.length === 0 && (
        <p className="campo-ajuda">Nenhum investimento lançado em {nomeDoMes(mes)}.</p>
      )}
      {!carregando && !erro && (dados?.length ?? 0) > 0 && (
        <table className="tabela sdr-tabela">
          <thead>
            <tr>
              <th scope="col">Canal</th>
              <th scope="col" className="tabela-numero">Valor</th>
            </tr>
          </thead>
          <tbody>
            {dados!.map((i) => (
              <tr key={i.id}>
                <td>{i.canal}</td>
                <td className="tabela-numero">{dinheiro(i.valor)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {falha && (
        <div className="estado estado-erro" role="alert">
          <p className="estado-texto">{falha}</p>
        </div>
      )}
      <div className="formulario-duplo">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="m-canal">Canal</label>
          <input id="m-canal" className="entrada" value={canal} onChange={(e) => definirCanal(e.target.value)} placeholder="Meta Ads" />
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="m-valor">Valor (R$)</label>
          <input id="m-valor" className="entrada" inputMode="decimal" value={valor} onChange={(e) => definirValor(e.target.value)} placeholder="6800.00" />
        </div>
      </div>
      <button type="button" className="botao botao-primario" onClick={salvar}
        disabled={salvando || !canal.trim() || !valor.trim()}>
        {salvando ? "Salvando…" : "Lançar investimento"}
      </button>
    </section>
  );
}
