/** Funil comercial › Inteligência de Conversão (aprovado por Eduardo em 03/10/2026), Entrega 1.
 *
 * A meta é acréscimo **líquido** sobre a receita atual. A tela mostra, de cima para baixo: a meta
 * (realizado × previsto × alerta), o acumulado contra os três cenários, o plano por motor com o
 * ajuste, os cenários, as premissas e os cenários de ticket por serviço (vieram da aba
 * Oportunidades). Uma ação primária: "Editar premissas", só para o Administrador. O ajuste é regra
 * fixa do servidor, não sugestão de IA. Regras em `crm.domain.plano_de_mrr`.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type {
  CenariosDoServico, ChaveDaSituacao, ContratoPrevistoDoPlano, ItemDoRealizado, NomeDoCenario, PlanoDeMrr, PremissasDoPlano,
  SituacaoDoPlano,
} from "../api/tipos";
import { CampoDeValor } from "../componentes/CampoDeValor";
import { KpisDaLideranca } from "../componentes/KpisDaLideranca";
import { BotaoDeComposicao, Explicavel } from "../componentes/Indicador";
import { ComposicaoDoFunil } from "../componentes/ComposicaoDoFunil";
import { Carregando, Erro } from "../componentes/estados";
import { PainelLateral } from "../componentes/PainelLateral";
import { QuatroFases } from "../componentes/QuatroFases";
import { Recolhivel } from "../componentes/Recolhivel";
import { usarAcesso } from "../entrada";
import { data, dataHora, dinheiro, dinheiroCurto, percentual } from "../formato";
import { usarDados } from "../usarDados";

const NOME_DO_CENARIO: Record<NomeDoCenario, string> = { alerta: "Alerta", previsto: "Previsto", otimista: "Otimista" };
const PAPEL_DO_CENARIO: Record<NomeDoCenario, string> = {
  alerta: "abaixo dele, o ajuste entra em ação",
  previsto: "o compromisso",
  otimista: "o alvo de esforço",
};
const SITUACAO: Record<ChaveDaSituacao, { texto: string; tom: string; sinal: string }> = {
  no_ritmo: { texto: "No ritmo", tom: "ganho", sinal: "✓" },
  atencao: { texto: "Atenção", tom: "espera", sinal: "!" },
  abaixo: { texto: "Abaixo do previsto", tom: "perda", sinal: "↓" },
};
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

/** As premissas opcionais das quatro fases: [campo, rótulo, sufixo]. */
const TAXAS_E_ALVOS = [
  ["taxa_lead_reuniao_pct", "Lead no ICP → reunião", "%"],
  ["taxa_reuniao_proposta_pct", "Reunião → proposta", "%"],
  ["taxa_conversao_pct", "Conversão", "%"],
  ["icp_alvo_pct", "Leads dentro do ICP", "%"],
  ["aderencia_alvo_pct", "Aderência da promessa", "%"],
  ["indicacoes_por_mes", "Leads por indicação/mês", ""],
  ["primeiro_contato_horas", "1º contato em até", " h"],
  ["ciclo_alvo_dias", "Ciclo de venda", " dias"],
] as const satisfies readonly (readonly [keyof PremissasDoPlano, string, string])[];

const n = (v: string | null | undefined) => (v === null || v === undefined ? 0 : Number(v));
const mesCurto = (iso: string) => `${MESES[Number(iso.slice(5, 7)) - 1]}/${iso.slice(2, 4)}`;
const numeroBr = (v: string | number) => Number(v).toLocaleString("pt-BR", { maximumFractionDigits: 2 });

function Situacao({ situacao }: { situacao: SituacaoDoPlano | null }) {
  if (!situacao) return <span className="etiqueta etiqueta-neutra">Sem previsto ainda</span>;
  const s = SITUACAO[situacao.chave];
  return (
    <span className={`etiqueta etiqueta-${s.tom}`}>
      <span aria-hidden="true">{s.sinal} </span>{s.texto}{situacao.percentual && ` · ${percentual(situacao.percentual)}`}
    </span>
  );
}

// ---------------------------------------------------------------- composição do realizado (10/10/2026)

const LINHA_DO_PLANO: Record<ItemDoRealizado["linha"], string> = {
  bpo: "Novo BPO Financeiro", contabil: "Novo contábil", escada: "Escada (upgrade de BPO)", perdas: "Churn e contração",
  outros: "Reajuste e expansão contábil",
};
const CATEGORIA: Record<string, string> = {
  novo: "contrato novo", expansao: "expansão", reajuste: "reajuste", contracao: "contração",
  churn_cliente: "churn (cliente)", churn_criterio: "saída (Critério)",
};

/** Cada contrato ou evento que soma ao realizado, com o valor com sinal; `linha` filtra um motor. */
function ComposicaoDoRealizado({ linha }: { linha?: ItemDoRealizado["linha"] }) {
  const { dados, carregando, erro, recarregar } = usarDados<ItemDoRealizado[]>(() => api.realizadoDoPlano(), []);
  if (carregando && !dados) return <Carregando rotulo="Buscando os contratos" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  const itens = (dados ?? []).filter((i) => !linha || i.linha === linha);
  if (itens.length === 0) return <p className="numero-estado">Nenhum contrato ou evento nesta conta ainda.</p>;
  const total = itens.reduce((t, i) => t + n(i.valor), 0);
  return (
    <table className="tabela" aria-label="Composição do realizado">
      <thead><tr><th>Data</th><th>Cliente</th><th>Contrato</th>{!linha && <th>Linha do plano</th>}<th>O quê</th><th className="tabela-numero">MRR</th></tr></thead>
      <tbody>
        {itens.map((i, k) => (
          <tr key={k}>
            <td>{data(i.data)}</td><td>{i.grupo}</td><td>{i.escopo ?? `Contrato ${i.contrato_id}`}</td>
            {!linha && <td>{LINHA_DO_PLANO[i.linha]}</td>}
            <td>{CATEGORIA[i.categoria] ?? i.categoria}</td>
            <td className="tabela-numero">{n(i.valor) < 0 ? "− " : ""}{dinheiro(Math.abs(n(i.valor)))}</td>
          </tr>
        ))}
        <tr className="composicao-total"><td>Total</td><td /><td />{!linha && <td />}<td />
          <td className="tabela-numero">{total < 0 ? "− " : ""}{dinheiro(Math.abs(total))}</td></tr>
      </tbody>
    </table>
  );
}

/** O mês a mês do cenário: o que soma até o líquido do card. */
function ComposicaoDoCenario({ plano, nome }: { plano: PlanoDeMrr; nome: NomeDoCenario }) {
  const c = plano.cenarios.find((x) => x.nome === nome)!;
  return (
    <>
      <p className="composicao-linha-resumo">
        <strong>{dinheiro(c.liquido)}</strong> = partida {dinheiro(plano.premissas.ponto_de_partida)} + mês a mês abaixo
      </p>
      <table className="tabela" aria-label={`Cenário ${NOME_DO_CENARIO[nome]} mês a mês`}>
        <thead><tr><th>Mês</th><th className="tabela-numero">Contábil</th><th className="tabela-numero">BPO</th>
          <th className="tabela-numero">Escada</th><th className="tabela-numero">Churn</th><th className="tabela-numero">Acumulado</th></tr></thead>
        <tbody>
          {c.linhas.map((l) => (
            <tr key={l.mes}>
              <td>{mesCurto(l.mes)}</td><td className="tabela-numero">{dinheiro(l.contabil)}</td>
              <td className="tabela-numero">{dinheiro(l.bpo)}</td><td className="tabela-numero">{dinheiro(l.escada)}</td>
              <td className="tabela-numero">− {dinheiro(l.churn)}</td><td className="tabela-numero">{dinheiro(l.acumulado)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="numero-nota">Projeção pelas premissas do plano (veja Premissas, abaixo). Não é dado realizado.</p>
    </>
  );
}

// ---------------------------------------------------------------- meta

function BlocoDaMeta({ plano }: { plano: PlanoDeMrr }) {
  const { meta, premissas } = plano;
  const alvo = n(meta.meta_liquida);
  const largura = (v: string) => `${Math.max(0, Math.min(100, (n(v) / alvo) * 100))}%`;
  return (
    <section className="plano-meta" aria-labelledby="plano-meta-titulo">
      <div className="plano-meta-topo">
        <div>
          <h3 className="numero-rotulo" id="plano-meta-titulo">
            Acréscimo líquido sobre a receita · meta de {dinheiroCurto(meta.meta_liquida)} até {data(premissas.fim)}
          </h3>
          <p className="plano-meta-valor">
            <Explicavel texto={<>Soma do MRR (× 13 ÷ 12) que entrou desde {data(premissas.inicio)}: contratos novos de BPO e
              contábeis, a escada (expansão de BPO), reajustes e expansões, menos churn e contração. É o mesmo movimento do MRR,
              separado pelos motores do plano.</>}>
              {dinheiro(meta.realizado)}
            </Explicavel>{" "}
            <BotaoDeComposicao rotulo="ver composição" composicao={{
              titulo: "Realizado do plano de MRR", subtitulo: `Cada contrato e evento desde ${data(premissas.inicio)}`,
              conteudo: () => <ComposicaoDoRealizado />,
            }} />{" "}
            <span className="plano-meta-detalhe">realizado · previsto até hoje {dinheiro(meta.previsto_ate_hoje)}</span>
          </p>
        </div>
        <Situacao situacao={meta.situacao} />
      </div>
      <div className="plano-barra" role="img"
        aria-label={`${percentual(meta.percentual_da_meta)} da meta; o previsto até hoje é ${dinheiro(meta.previsto_ate_hoje)}`}>
        <span className="plano-barra-feito" style={{ width: largura(meta.realizado) }} />
        <span className="plano-barra-marca" style={{ left: largura(meta.previsto_ate_hoje) }} title="Previsto até hoje" />
      </div>
      <div className="plano-meta-rodape">
        <span>{percentual(meta.percentual_da_meta)} da meta</span>
        <span>
          Marca = previsto até hoje · {meta.meses_restantes} {meta.meses_restantes === 1 ? "mês restante" : "meses restantes"}
          {meta.ritmo_necessario !== null && ` · ritmo necessário ${dinheiro(meta.ritmo_necessario)}/mês`}
        </span>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------- gráfico

const COR_DO_CENARIO: Record<NomeDoCenario, string> = { alerta: "plano-serie-alerta", previsto: "plano-serie-previsto", otimista: "plano-serie-otimista" };

function GraficoAcumulado({ plano }: { plano: PlanoDeMrr }) {
  const { premissas, cenarios, realizado, meta } = plano;
  const meses: string[] = [];
  for (let d = new Date(`${premissas.inicio.slice(0, 7)}-01T00:00:00`); d <= new Date(`${premissas.fim}T00:00:00`); d.setMonth(d.getMonth() + 1)) {
    meses.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`);
  }
  const indice = (iso: string) => meses.indexOf(`${iso.slice(0, 7)}-01`);
  const partida = indice(premissas.inicio_da_projecao) - 1;
  const series = cenarios.map((c) => ({
    nome: c.nome,
    pontos: [
      ...(partida >= 0 ? [[partida, n(premissas.ponto_de_partida)] as const] : []),
      ...c.linhas.map((l) => [indice(l.mes), n(l.acumulado)] as const),
    ],
    final: c.liquido,
  }));
  const pontosReais = realizado.map((l) => [indice(l.mes), n(l.acumulado)] as const);
  const maximo = Math.max(n(meta.meta_liquida), ...cenarios.map((c) => n(c.liquido)), ...pontosReais.map(([, v]) => v)) * 1.05;
  const minimo = Math.min(0, ...pontosReais.map(([, v]) => v));
  const W = 760, H = 260, esq = 84, dir = 150, cima = 16, baixo = 32;
  const x = (i: number) => esq + (i / Math.max(1, meses.length - 1)) * (W - esq - dir);
  const y = (v: number) => cima + (1 - (v - minimo) / (maximo - minimo || 1)) * (H - cima - baixo);
  const linha = (pts: readonly (readonly [number, number])[]) => pts.map(([i, v]) => `${x(i)},${y(v)}`).join(" ");
  const grades = [0, 0.25, 0.5, 0.75, 1].map((f) => minimo + f * (maximo - minimo));

  return (
    <figure className="plano-grafico">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Acréscimo líquido acumulado: realizado contra os cenários alerta, previsto e otimista">
        {grades.map((v) => (
          <g key={v}>
            <line x1={esq} x2={W - dir} y1={y(v)} y2={y(v)} className="plano-grade" />
            <text x={esq - 8} y={y(v) + 4} textAnchor="end" className="plano-eixo">{dinheiroCurto(v)}</text>
          </g>
        ))}
        {meses.map((m, i) => (
          <text key={m} x={x(i)} y={H - 10} textAnchor="middle" className="plano-eixo">{mesCurto(m)}</text>
        ))}
        <line x1={esq} x2={W - dir} y1={y(n(meta.meta_liquida))} y2={y(n(meta.meta_liquida))} className="plano-meta-linha" />
        <text x={esq + 4} y={y(n(meta.meta_liquida)) - 6} className="plano-eixo">Meta {dinheiroCurto(meta.meta_liquida)}</text>
        {series.map((s) => (
          <g key={s.nome}>
            <polyline points={linha(s.pontos)} className={`plano-serie ${COR_DO_CENARIO[s.nome]}`} />
            {s.pontos.length > 0 && (
              <text x={x(s.pontos[s.pontos.length - 1][0]) + 8} y={y(s.pontos[s.pontos.length - 1][1]) + 4} className="plano-rotulo">
                {NOME_DO_CENARIO[s.nome]} {dinheiroCurto(s.final)}
              </text>
            )}
          </g>
        ))}
        {pontosReais.length > 0 && <polyline points={linha(pontosReais)} className="plano-serie plano-serie-realizado" />}
        {pontosReais.map(([i, v]) => <circle key={i} cx={x(i)} cy={y(v)} r={3.5} className="plano-ponto-realizado" />)}
      </svg>
      <figcaption className="plano-legenda">
        <span><i className="plano-chave plano-serie-realizado" aria-hidden="true" /> Realizado</span>
        <span><i className="plano-chave plano-serie-previsto" aria-hidden="true" /> Previsto</span>
        <span><i className="plano-chave plano-serie-alerta" aria-hidden="true" /> Alerta</span>
        <span><i className="plano-chave plano-serie-otimista" aria-hidden="true" /> Otimista</span>
      </figcaption>
      <details className="plano-tabela-equivalente">
        <summary>Ver o gráfico em tabela</summary>
        <table className="mini-tabela">
          <thead>
            <tr>
              <th scope="col">Mês</th>
              <th scope="col" className="tabela-numero">Realizado</th>
              {cenarios.map((c) => <th key={c.nome} scope="col" className="tabela-numero">{NOME_DO_CENARIO[c.nome]}</th>)}
            </tr>
          </thead>
          <tbody>
            {meses.map((m) => {
              const real = realizado.find((l) => l.mes.slice(0, 7) === m.slice(0, 7));
              return (
                <tr key={m}>
                  <td>{mesCurto(m)}</td>
                  <td className="tabela-numero">{real ? dinheiro(real.acumulado) : "—"}</td>
                  {cenarios.map((c) => {
                    const l = c.linhas.find((x) => x.mes.slice(0, 7) === m.slice(0, 7));
                    return <td key={c.nome} className="tabela-numero">{l ? dinheiro(l.acumulado) : "—"}</td>;
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </details>
    </figure>
  );
}

// ---------------------------------------------------------------- motores e cenários

function PlanoPorMotor({ plano }: { plano: PlanoDeMrr }) {
  return (
    <section aria-labelledby="plano-motores-titulo">
      <h3 className="plano-secao" id="plano-motores-titulo">Por motor · previsto (cenário previsto) × realizado</h3>
      <div className="tabela-rolagem">
        <table className="tabela" aria-labelledby="plano-motores-titulo">
          <thead>
            <tr>
              <th scope="col">Motor</th>
              <th scope="col" className="tabela-numero">Previsto no plano</th>
              <th scope="col" className="tabela-numero">Previsto até hoje</th>
              <th scope="col" className="tabela-numero">Realizado</th>
              <th scope="col">Situação</th>
              <th scope="col">Ajuste</th>
            </tr>
          </thead>
          <tbody>
            {plano.motores.map((m) => (
              <tr key={m.motor}>
                <td><strong>{m.rotulo}</strong></td>
                <td className="tabela-numero">{m.motor === "perdas" && m.previsto_no_plano ? "− " : ""}{dinheiro(m.previsto_no_plano)}</td>
                <td className="tabela-numero">{dinheiro(m.previsto_ate_hoje)}</td>
                <td className="tabela-numero">
                  {m.motor === "perdas" && n(m.realizado) > 0 ? "− " : ""}{dinheiro(m.realizado)}
                  {n(m.realizado) !== 0 && (
                    <BotaoDeComposicao rotulo="ver" composicao={{
                      titulo: m.rotulo, subtitulo: "Contratos e eventos que compõem o realizado do motor",
                      conteudo: () => <ComposicaoDoRealizado linha={m.motor} />,
                    }} />
                  )}
                </td>
                <td>{m.motor === "outros" ? <span className="etiqueta etiqueta-neutra">Fora do plano</span> : <Situacao situacao={m.situacao} />}</td>
                <td className="plano-ajuste">{m.ajuste}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Cenarios({ plano }: { plano: PlanoDeMrr }) {
  return (
    <section aria-labelledby="plano-cenarios-titulo">
      <h3 className="plano-secao" id="plano-cenarios-titulo">Cenários até {data(plano.premissas.fim)} · líquido de churn</h3>
      <div className="plano-cenarios">
        {plano.cenarios.map((c) => (
          <div key={c.nome} className={`numero plano-cenario plano-cenario-${c.nome}`}>
            <span className="numero-rotulo">
              <Explicavel texto={<>Projeção até {data(plano.premissas.fim)} pelas premissas do cenário: BPO, contábil e escada
                somados mês a mês, menos o churn sobre o MRR de partida, a partir de {dinheiro(plano.premissas.ponto_de_partida)} já
                realizados. Não é dado realizado.</>}>
                {NOME_DO_CENARIO[c.nome]} · {PAPEL_DO_CENARIO[c.nome]}
              </Explicavel>
            </span>
            <p className="numero-valor">{dinheiro(c.liquido)}</p>
            <p className="numero-detalhe">
              {percentual(c.percentual_da_meta)} da meta · BPO {dinheiroCurto(c.bpo)} + contábil {dinheiroCurto(c.contabil)} +
              escada {dinheiroCurto(c.escada)} − churn {dinheiroCurto(c.churn)}
            </p>
            <BotaoDeComposicao rotulo="Ver composição" composicao={{
              titulo: `Cenário ${NOME_DO_CENARIO[c.nome].toLowerCase()}`, subtitulo: "Mês a mês até o fim do prazo",
              quantos: c.linhas.length, conteudo: () => <ComposicaoDoCenario plano={plano} nome={c.nome} />,
            }} />
          </div>
        ))}
      </div>
    </section>
  );
}

function Premissas({ plano }: { plano: PlanoDeMrr }) {
  const p = plano.premissas;
  const cen = (c: NomeDoCenario) =>
    `${NOME_DO_CENARIO[c]}: ${numeroBr(p[c].bpo_por_mes)} BPO/mês, ticket contábil ${dinheiro(p[c].ticket_contabil)}${p[c].com_contratos_previstos ? ", com os contratos previstos" : ""}`;
  return (
    <section aria-labelledby="plano-premissas-titulo">
      <h3 className="plano-secao" id="plano-premissas-titulo">Premissas</h3>
      <ul className="plano-premissas">
        <li>Meta: +{dinheiro(p.meta_liquida)} líquidos de {data(p.inicio)} a {data(p.fim)}</li>
        <li>Projeção a partir de {mesCurto(p.inicio_da_projecao)}, com {dinheiro(p.ponto_de_partida)} já realizados</li>
        <li>MRR de partida (base do churn): {dinheiro(p.mrr_de_partida)} · churn de {numeroBr(p.churn_anual_pct)}% ao ano</li>
        <li>BPO Financeiro: entrada a {dinheiro(p.bpo_ticket)}, teto da célula de {numeroBr(p.bpo_teto)}/mês</li>
        <li>Contábil: {numeroBr(p.contabil_vagas)} vagas de onboarding/mês; o atípico ocupa {numeroBr(p.atipico_vagas)}</li>
        <li>
          Escada a cada {p.escada_prazo_meses} meses: {numeroBr(p.plus_pct)}% sobem para o BPO Plus (+{dinheiro(p.plus_acrescimo)}) e{" "}
          {numeroBr(p.cfo_pct)}% deles para o CFO as a Service (+{dinheiro(p.cfo_acrescimo)})
        </li>
        <li>{cen("alerta")}</li>
        <li>{cen("previsto")}</li>
        <li>{cen("otimista")}</li>
        <li>
          Contratos previstos:{" "}
          {p.contratos_previstos.length === 0 ? "nenhum" : p.contratos_previstos
            .map((c) => `${c.descricao} (${mesCurto(c.mes)}, ${dinheiro(c.valor)}${c.atipico ? ", atípico" : ""})`).join(" · ")}
        </li>
        <li>
          Quatro fases: {TAXAS_E_ALVOS.map(([k, rotulo, sufixo]) =>
            `${rotulo} ${p[k] ? `${numeroBr(p[k] as string)}${sufixo}` : "pelo histórico"}`).join(" · ")}
        </li>
      </ul>
      <p className="campo-ajuda">
        {p.alterado_em ? `Última mudança: ${p.alterado_por ? `${p.alterado_por}, ` : ""}${dataHora(p.alterado_em)}.` : "Premissas de 03/10/2026, ainda não alteradas."}{" "}
        Só o Administrador muda; cada mudança fica no histórico de alterações.
      </p>
    </section>
  );
}

// ---------------------------------------------------------------- cenários de ticket por serviço

function CenariosDeTicketPorServico() {
  const { dados, carregando, erro, recarregar } = usarDados<CenariosDoServico[]>(() => api.cenariosPorServico(), []);
  if (carregando && !dados) return <Carregando rotulo="Calculando os cenários" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados || dados.length === 0) {
    return <p className="estado estado-texto">Ainda não há contrato recorrente aceito para calcular cenários.</p>;
  }
  return (
    <div className="tabela-rolagem">
      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">Serviço</th>
            <th scope="col" className="tabela-numero">Recorrentes</th>
            <th scope="col" className="tabela-numero">Conservador</th>
            <th scope="col" className="tabela-numero">Base</th>
            <th scope="col" className="tabela-numero">Otimista</th>
            <th scope="col">Atípicos (acima de 3 × a mediana)</th>
          </tr>
        </thead>
        <tbody>
          {dados.map((s) => (
            <tr key={s.servico}>
              <td><strong>{s.servico}</strong></td>
              <td className="tabela-numero">
                {s.contratos_recorrentes}
                {s.servico !== "Sem serviço" && <BotaoDeComposicao rotulo="ver" composicao={{
                  titulo: `Recorrentes aceitos · ${s.servico}`, subtitulo: "Os contratos que formam os cenários (MRR, × 13 ÷ 12)",
                  quantos: s.contratos_recorrentes,
                  conteudo: () => <ComposicaoDoFunil indicador="ticket_recorrente" filtros={{ servico: [s.servico] }} />,
                }} />}
              </td>
              {s.base === null ? (
                <td colSpan={4} className="numero-nota">Sem base: precisa de pelo menos 4 contratos recorrentes aceitos.</td>
              ) : (
                <>
                  <td className="tabela-numero">{dinheiro(s.conservador)}</td>
                  <td className="tabela-numero">{dinheiro(s.base)}</td>
                  <td className="tabela-numero">{dinheiro(s.otimista)}</td>
                  <td>
                    {s.atipicos === 0
                      ? `nenhum acima de ${dinheiro(s.limite_do_atipico)}`
                      : `${s.atipicos} acima de ${dinheiro(s.limite_do_atipico)} (${dinheiro(s.atipico_minimo)} a ${dinheiro(s.atipico_maximo)})`}
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="numero-nota">
        Hipóteses de trabalho, não meta. Conservador = mediana sem atípicos; base = média sem atípicos; otimista = terceiro
        quartil sem atípicos. Por serviço, para que o ticket do BPO Financeiro não vire "atípico" do contábil.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------- edição

type Rascunho = PremissasDoPlano;

function deDados(p: PlanoDeMrr["premissas"]): Rascunho {
  const { alterado_por: _por, alterado_em: _em, ...resto } = p;
  return structuredClone(resto);
}

function CampoNumero({ rotulo, value, aoMudar, ajuda, erro }: {
  rotulo: string; value: string | number; aoMudar: (v: string) => void; ajuda?: string; erro?: string | null;
}) {
  return (
    <label className="campo">
      <span className="campo-rotulo">{rotulo}</span>
      <input className={`entrada${erro ? " entrada-com-erro" : ""}`} type="number" min={0} step="any" value={value}
        aria-invalid={erro ? true : undefined} onChange={(e) => aoMudar(e.target.value)} />
      {erro && <span className="campo-erro">{erro}</span>}
      {ajuda && <span className="campo-ajuda">{ajuda}</span>}
    </label>
  );
}

function CampoDinheiro({ rotulo, value, aoMudar, erro }: { rotulo: string; value: string; aoMudar: (v: string) => void; erro?: string | null }) {
  return (
    <label className="campo">
      <span className="campo-rotulo">{rotulo}</span>
      <CampoDeValor value={value} aoMudar={(v) => aoMudar(v ?? "")} aria-label={rotulo}
        className={`entrada${erro ? " entrada-com-erro" : ""}`} />
      {erro && <span className="campo-erro">{erro}</span>}
    </label>
  );
}

function CampoData({ rotulo, value, aoMudar, tipo = "date" }: { rotulo: string; value: string; aoMudar: (v: string) => void; tipo?: "date" | "month" }) {
  return (
    <label className="campo">
      <span className="campo-rotulo">{rotulo}</span>
      <input className="entrada" type={tipo} value={tipo === "month" ? value.slice(0, 7) : value}
        onChange={(e) => aoMudar(tipo === "month" ? `${e.target.value}-01` : e.target.value)} />
    </label>
  );
}

const ABAS_DAS_PREMISSAS = [
  ["meta", "Meta", "A meta é acréscimo líquido sobre a receita: venda nova e escada menos churn."],
  ["motores", "Motores", "BPO Financeiro é o motor de volume, com onboarding próprio; o contábil é limitado pelas vagas de onboarding."],
  ["escada", "Escada", "BPO Financeiro → BPO Plus → CFO as a Service, um degrau a cada prazo."],
  ["cenarios", "Cenários", "Os três cenários lado a lado, para comparar."],
  ["fases", "Quatro fases", "Deixe vazio para o previsto usar a taxa histórica do CRM (três meses fechados)."],
  ["previstos", "Contratos previstos", "O pipeline contábil que o plano já conta. Sem nome de cliente: descreva o contrato para quem edita o plano."],
] as const;
type AbaDasPremissas = (typeof ABAS_DAS_PREMISSAS)[number][0];

const vazio = (v: string | number | null | undefined) => v === "" || v === null || v === undefined;
const FALTA = "Preencha o valor";

/** Os campos obrigatórios que estão vazios, por aba: o painel mostra "! n" na aba e marca o campo. */
function errosDasPremissas(r: Rascunho): Record<AbaDasPremissas, Record<string, string>> {
  const de = (pares: [string, string | number | null | undefined][]) =>
    Object.fromEntries(pares.filter(([, v]) => vazio(v)).map(([k]) => [k, FALTA]));
  const previstos: Record<string, string> = {};
  r.contratos_previstos.forEach((c, i) => {
    if (!c.descricao.trim()) previstos[`descricao-${i}`] = "Descreva o contrato";
    if (vazio(c.valor)) previstos[`valor-${i}`] = FALTA;
  });
  return {
    meta: de([["meta_liquida", r.meta_liquida], ["ponto_de_partida", r.ponto_de_partida], ["mrr_de_partida", r.mrr_de_partida],
      ["churn_anual_pct", r.churn_anual_pct]]),
    motores: de([["bpo_ticket", r.bpo_ticket], ["bpo_teto", r.bpo_teto], ["contabil_vagas", r.contabil_vagas], ["atipico_vagas", r.atipico_vagas]]),
    escada: de([["escada_prazo_meses", r.escada_prazo_meses], ["plus_pct", r.plus_pct], ["plus_acrescimo", r.plus_acrescimo],
      ["cfo_pct", r.cfo_pct], ["cfo_acrescimo", r.cfo_acrescimo]]),
    cenarios: de((["alerta", "previsto", "otimista"] as const).flatMap((c) => [
      [`${c}.bpo_por_mes`, r[c].bpo_por_mes], [`${c}.ticket_contabil`, r[c].ticket_contabil]] as [string, string][])),
    fases: {},
    previstos,
  };
}

function EditarPremissas({ plano, aoFechar, aoSalvar }: { plano: PlanoDeMrr; aoFechar: () => void; aoSalvar: (novo: PlanoDeMrr) => void }) {
  const [r, definir] = useState<Rascunho>(() => deDados(plano.premissas));
  const [aba, definirAba] = useState<AbaDasPremissas>("meta");
  const [salvando, definirSalvando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const mudar = <K extends keyof Rascunho>(k: K, v: Rascunho[K]) => definir((x) => ({ ...x, [k]: v }));
  const mudarCenario = (c: NomeDoCenario, campo: keyof Rascunho["alerta"], v: string | boolean) =>
    definir((x) => ({ ...x, [c]: { ...x[c], [campo]: v } }));
  const mudarPrevisto = (i: number, campo: keyof ContratoPrevistoDoPlano, v: string | boolean) =>
    definir((x) => ({ ...x, contratos_previstos: x.contratos_previstos.map((c, j) => (j === i ? { ...c, [campo]: v } : c)) }));
  const erros = errosDasPremissas(r);
  const total = Object.values(erros).reduce((n, e) => n + Object.keys(e).length, 0);
  const e = erros[aba] as Record<string, string>;
  const explicacao = ABAS_DAS_PREMISSAS.find(([k]) => k === aba)?.[2];

  const salvar = async () => {
    definirSalvando(true);
    definirFalha(null);
    try {
      aoSalvar(await api.mudarPlanoDeMrr({ ...r, escada_prazo_meses: Number(r.escada_prazo_meses) }));
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Não foi possível salvar as premissas. Confira os valores e tente de novo.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <PainelLateral
      titulo="Editar premissas do plano"
      subtitulo="Cada mudança fica no histórico de alterações."
      aoFechar={aoFechar}
      rodape={
        <div className="perfis-acoes">
          <button type="button" className="botao botao-primario" disabled={salvando || total > 0} onClick={() => void salvar()}>
            {salvando ? "Salvando…" : "Salvar premissas"}
          </button>
          <button type="button" className="botao" onClick={aoFechar}>Cancelar</button>
          <span className="campo-ajuda">
            {total > 0
              ? `Corrija ${total} ${total === 1 ? "campo" : "campos"}: veja o "!" nas abas.`
              : "Salva as seis abas juntas."}
          </span>
        </div>
      }
    >
      <div className="abas premissas-abas" role="tablist" aria-label="Premissas do plano">
        {ABAS_DAS_PREMISSAS.map(([k, rotulo]) => {
          const n = Object.keys(erros[k]).length;
          return (
            <button key={k} type="button" role="tab" id={`premissas-aba-${k}`} aria-selected={aba === k}
              aria-controls="premissas-conteudo" className="aba" onClick={() => definirAba(k)}>
              {rotulo}
              {n > 0 && <span className="premissas-alerta" aria-label={`${n} ${n === 1 ? "campo" : "campos"} a corrigir`}>! {n}</span>}
            </button>
          );
        })}
      </div>
      <div className="plano-form" role="tabpanel" id="premissas-conteudo" aria-labelledby={`premissas-aba-${aba}`}>
        {explicacao && <p className="campo-ajuda">{explicacao}</p>}
        {aba === "meta" && (
          <div className="premissas-grade">
            <CampoDinheiro rotulo="Meta líquida (R$/mês)" value={r.meta_liquida} aoMudar={(v) => mudar("meta_liquida", v)} erro={e.meta_liquida} />
            <CampoNumero rotulo="Churn ao ano (%)" value={r.churn_anual_pct} aoMudar={(v) => mudar("churn_anual_pct", v)} erro={e.churn_anual_pct} />
            <CampoData rotulo="Início do realizado" tipo="month" value={r.inicio} aoMudar={(v) => mudar("inicio", v)} />
            <CampoData rotulo="Fim do prazo" value={r.fim} aoMudar={(v) => mudar("fim", v)} />
            <CampoData rotulo="Primeiro mês projetado" tipo="month" value={r.inicio_da_projecao} aoMudar={(v) => mudar("inicio_da_projecao", v)} />
            <CampoDinheiro rotulo="Já realizado antes da projeção (R$/mês)" value={r.ponto_de_partida} aoMudar={(v) => mudar("ponto_de_partida", v)} erro={e.ponto_de_partida} />
            <CampoDinheiro rotulo="MRR de partida, base do churn (R$/mês)" value={r.mrr_de_partida} aoMudar={(v) => mudar("mrr_de_partida", v)} erro={e.mrr_de_partida} />
          </div>
        )}
        {aba === "motores" && (
          <div className="premissas-grade">
            <CampoDinheiro rotulo="Entrada do BPO Financeiro (R$/mês)" value={r.bpo_ticket} aoMudar={(v) => mudar("bpo_ticket", v)} erro={e.bpo_ticket} />
            <CampoNumero rotulo="Teto da célula (clientes novos/mês)" value={r.bpo_teto} aoMudar={(v) => mudar("bpo_teto", v)} erro={e.bpo_teto} />
            <CampoNumero rotulo="Vagas de onboarding contábil/mês" value={r.contabil_vagas} aoMudar={(v) => mudar("contabil_vagas", v)} erro={e.contabil_vagas} />
            <CampoNumero rotulo="Vagas que um atípico ocupa" value={r.atipico_vagas} aoMudar={(v) => mudar("atipico_vagas", v)} erro={e.atipico_vagas} />
          </div>
        )}
        {aba === "escada" && (
          <div className="premissas-grade">
            <CampoNumero rotulo="Prazo de cada degrau (meses)" value={r.escada_prazo_meses} aoMudar={(v) => mudar("escada_prazo_meses", v === "" ? ("" as unknown as number) : Number(v))} erro={e.escada_prazo_meses} />
            <span />
            <CampoNumero rotulo="Sobem para o BPO Plus (%)" value={r.plus_pct} aoMudar={(v) => mudar("plus_pct", v)} erro={e.plus_pct} />
            <CampoDinheiro rotulo="Acréscimo do BPO Plus (R$/mês)" value={r.plus_acrescimo} aoMudar={(v) => mudar("plus_acrescimo", v)} erro={e.plus_acrescimo} />
            <CampoNumero rotulo="Desses, sobem para o CFO as a Service (%)" value={r.cfo_pct} aoMudar={(v) => mudar("cfo_pct", v)} erro={e.cfo_pct} />
            <CampoDinheiro rotulo="Acréscimo do CFO as a Service (R$/mês)" value={r.cfo_acrescimo} aoMudar={(v) => mudar("cfo_acrescimo", v)} erro={e.cfo_acrescimo} />
          </div>
        )}
        {aba === "cenarios" && (
          <div className="premissas-cenarios">
            {(["alerta", "previsto", "otimista"] as const).map((c) => (
              <fieldset key={c} className={`premissas-cenario premissas-cenario-${c}`}>
                <legend>{NOME_DO_CENARIO[c]}</legend>
                <CampoNumero rotulo="BPO Fin. novos/mês" value={r[c].bpo_por_mes} aoMudar={(v) => mudarCenario(c, "bpo_por_mes", v)} erro={e[`${c}.bpo_por_mes`]} />
                <CampoDinheiro rotulo="Ticket contábil (R$)" value={r[c].ticket_contabil} aoMudar={(v) => mudarCenario(c, "ticket_contabil", v)} erro={e[`${c}.ticket_contabil`]} />
                <label className="campo-marcar">
                  <input type="checkbox" checked={r[c].com_contratos_previstos} onChange={(ev) => mudarCenario(c, "com_contratos_previstos", ev.target.checked)} />
                  Conta o pipeline
                </label>
              </fieldset>
            ))}
          </div>
        )}
        {aba === "fases" && (
          <div className="premissas-grade">
            {TAXAS_E_ALVOS.map(([k, rotulo, sufixo]) => (
              <CampoNumero key={k} rotulo={`${rotulo}${sufixo ? ` (${sufixo.trim()})` : ""}`} value={r[k] ?? ""}
                aoMudar={(v) => mudar(k, v === "" ? null : v)} />
            ))}
          </div>
        )}
        {aba === "previstos" && (
          <>
            {r.contratos_previstos.length === 0 && <p className="campo-ajuda">Nenhum contrato previsto no plano.</p>}
            {r.contratos_previstos.map((c, i) => (
              <div key={i} className="plano-previsto">
                <label className="campo">
                  <span className="campo-rotulo">Descrição</span>
                  <input className={`entrada${e[`descricao-${i}`] ? " entrada-com-erro" : ""}`} value={c.descricao} maxLength={120}
                    aria-invalid={e[`descricao-${i}`] ? true : undefined} onChange={(ev) => mudarPrevisto(i, "descricao", ev.target.value)} />
                  {e[`descricao-${i}`] && <span className="campo-erro">{e[`descricao-${i}`]}</span>}
                </label>
                <CampoData rotulo="Mês" tipo="month" value={c.mes} aoMudar={(v) => mudarPrevisto(i, "mes", v)} />
                <CampoDinheiro rotulo="Valor (R$/mês)" value={c.valor} aoMudar={(v) => mudarPrevisto(i, "valor", v)} erro={e[`valor-${i}`]} />
                <label className="campo-marcar">
                  <input type="checkbox" checked={c.atipico} onChange={(ev) => mudarPrevisto(i, "atipico", ev.target.checked)} />
                  Atípico
                </label>
                <button type="button" className="botao" onClick={() => definir((x) => ({ ...x, contratos_previstos: x.contratos_previstos.filter((_, j) => j !== i) }))}>
                  Tirar do plano
                </button>
              </div>
            ))}
            <button type="button" className="botao"
              onClick={() => definir((x) => ({
                ...x,
                contratos_previstos: [...x.contratos_previstos, { descricao: "", mes: x.inicio_da_projecao, valor: "", atipico: false }],
              }))}>
              Acrescentar contrato previsto
            </button>
          </>
        )}
      </div>
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
    </PainelLateral>
  );
}

// ---------------------------------------------------------------- tela

export function InteligenciaDeConversao() {
  const { pode, eu } = usarAcesso();
  const { dados, carregando, erro, recarregar } = usarDados<PlanoDeMrr>(() => api.planoDeMrr(), []);
  const [salvo, definirSalvo] = useState<PlanoDeMrr | null>(null);
  const [editando, definirEditando] = useState(false);
  const [recado, definirRecado] = useState<string | null>(null);
  const plano = salvo ?? dados;

  if (carregando && !plano) return <Carregando rotulo="Montando o plano de MRR" />;
  if (erro && !plano) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!plano) return null;

  return (
    <div className="plano">
      {/* KPIs da liderança (09/10/2026): só o Administrador. */}
      {eu.administrador && <KpisDaLideranca />}
      <div className="plano-cabecalho">
        <div>
          <h2 className="plano-titulo">Plano de MRR</h2>
          <p className="campo-ajuda">
            Meta medida em acréscimo líquido: venda nova e escada menos churn e contração. Situação: no ritmo com 100% ou
            mais do previsto, atenção de 90% a 99%, abaixo com menos de 90%.
          </p>
        </div>
        {pode("configuracoes.metas") && (
          <button type="button" className="botao botao-primario" onClick={() => { definirRecado(null); definirEditando(true); }}>
            Editar premissas
          </button>
        )}
      </div>
      {recado && <p className="recado" role="status">✓ {recado}</p>}
      {plano.aviso && <p className="aviso-de-movimento" role="note">{plano.aviso}</p>}
      <BlocoDaMeta plano={plano} />
      <QuatroFases key={plano.premissas.alterado_em ?? "padrao"} />
      <GraficoAcumulado plano={plano} />
      <PlanoPorMotor plano={plano} />
      <Cenarios plano={plano} />
      <Premissas plano={plano} />
      <Recolhivel titulo="Cenários de ticket por serviço" resumo="conservador, base e otimista · vieram da aba Oportunidades">
        <CenariosDeTicketPorServico />
      </Recolhivel>
      {editando && (
        <EditarPremissas
          plano={plano}
          aoFechar={() => definirEditando(false)}
          aoSalvar={(novo) => {
            definirSalvo(novo);
            definirEditando(false);
            definirRecado("Premissas salvas. O previsto e o ajuste já usam os valores novos.");
          }}
        />
      )}
    </div>
  );
}
