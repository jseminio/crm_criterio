/** O MRR dos contratos registrados no CRM, e o que o moveu no período.
 *
 * O KPI oficial de MRR é a receita da carteira inteira. Sem a carteira anterior ao CRM
 * carregada, o número é **parcial**, a tela diz isso e **não compara com a meta**. Com ela,
 * compara com a meta e o alerta de Configurações › Metas, com ícone e texto (02/10/2026; em 13 parcelas desde 10/10).
 * Churn vem separado por quem decidiu: cliente (churn) e Critério (saída organizada).
 *
 * Padrão dos indicadores (10/10/2026): cada número tem "Ver composição", que abre a lista do que o
 * compõe — o MRR por cliente, e cada contrato ou evento de cada linha do movimento.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { CategoriaDoMovimento, ItemDoMovimento, Mrr } from "../api/tipos";
import { BotaoDeComposicao, Explicavel } from "../componentes/Indicador";
import { ComposicaoDaCarteira } from "../componentes/MrrDaCarteira";
import { Carregando, Erro } from "../componentes/estados";
import { aliquota, data, dinheiro, percentual } from "../formato";
import { usarDados } from "../usarDados";

type Periodo = "mes" | "trimestre" | "ano";
const ROTULOS: Record<Periodo, string> = { mes: "Mês atual", trimestre: "Últimos 3 meses", ano: "Ano até hoje" };

/** Data ISO local (sem fuso), para não deslocar um dia perto da meia-noite. */
function iso(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function inicioDoPeriodo(p: Periodo, hoje = new Date()): string {
  if (p === "mes") return iso(new Date(hoje.getFullYear(), hoje.getMonth(), 1));
  if (p === "trimestre") return iso(new Date(hoje.getFullYear(), hoje.getMonth() - 2, 1));
  return iso(new Date(hoje.getFullYear(), 0, 1));
}

const SITUACAO_DA_META = {
  na_meta: ["✓ Na meta", "ganho"],
  entre: ["Entre o alerta e a meta", "espera"],
  abaixo_do_alerta: ["⚠ Abaixo do alerta", "perda"],
} as const;

const ROTULO_DA_CATEGORIA: Record<CategoriaDoMovimento, string> = {
  novo: "Novos contratos", expansao: "Expansão", reajuste: "Reajuste", contracao: "Contração",
  churn_cliente: "Churn: decidido pelo cliente", churn_criterio: "Saída organizada: decidida pela Critério",
};

/** A lista de uma linha do movimento: cada contrato (novo) ou evento, com cliente, data e valor. */
function ItensDaLinha({ de, categoria }: { de: string; categoria: CategoriaDoMovimento }) {
  const { dados, carregando, erro, recarregar } = usarDados<{ itens: ItemDoMovimento[] }>(() => api.itensDoMovimento(de), [de]);
  if (carregando && !dados) return <Carregando rotulo="Buscando os contratos" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  const itens = (dados?.itens ?? []).filter((i) => i.categoria === categoria);
  if (itens.length === 0) return <p className="numero-estado">Nada nesta linha no período.</p>;
  const total = itens.reduce((t, i) => t + Number(i.valor), 0);
  return (
    <table className="tabela" aria-label={ROTULO_DA_CATEGORIA[categoria]}>
      <thead><tr><th>Cliente</th><th>Contrato</th><th>Data</th><th className="tabela-numero">MRR</th></tr></thead>
      <tbody>
        {itens.map((i, n) => (
          <tr key={n}>
            <td>{i.grupo}</td>
            <td>{i.escopo ?? `Contrato ${i.contrato_id}`}</td>
            <td>{i.data ? data(i.data) : "—"}</td>
            <td className="tabela-numero">{dinheiro(i.valor)}</td>
          </tr>
        ))}
        <tr className="composicao-total"><td>Total</td><td /><td /><td className="tabela-numero">{dinheiro(total)}</td></tr>
      </tbody>
    </table>
  );
}

/** Motivos de churn no período (10/10/2026): os encerramentos do movimento, por motivo (lista aprovada). */
function MotivosDeChurn({ de }: { de: string }) {
  const { dados } = usarDados<{ itens: ItemDoMovimento[] }>(() => api.itensDoMovimento(de), [de]);
  const saidas = (dados?.itens ?? []).filter((i) => i.categoria === "churn_cliente" || i.categoria === "churn_criterio");
  if (!dados) return null;
  const porMotivo = new Map<string, { n: number; valor: number }>();
  for (const i of saidas) {
    const m = i.motivo ?? "Sem motivo informado";
    const atual = porMotivo.get(m) ?? { n: 0, valor: 0 };
    porMotivo.set(m, { n: atual.n + 1, valor: atual.valor + Number(i.valor) });
  }
  const linhas = [...porMotivo.entries()].sort((a, b) => b[1].valor - a[1].valor);
  return (
    <div className="receita-retencao">
      <p>
        <Explicavel texto="Os contratos que saíram no período (saída efetiva), agrupados pelo motivo do encerramento — a lista aprovada em 10/10/2026. Valor em MRR (× 13 ÷ 12).">
          <strong>Motivos de churn</strong>
        </Explicavel>{" "}
        {linhas.length === 0 ? "nenhuma saída no período" : linhas.map(([m, x]) => `${m}: ${x.n} (${dinheiro(x.valor)})`).join(" · ")}
        {saidas.length > 0 && (
          <BotaoDeComposicao rotulo="ver composição" composicao={{
            titulo: "Motivos de churn", subtitulo: `Saídas desde ${data(de)}`, quantos: saidas.length,
            conteudo: () => (
              <table className="tabela" aria-label="Saídas por motivo">
                <thead><tr><th>Cliente</th><th>Contrato</th><th>Saída</th><th>Quem decidiu</th><th>Motivo</th><th className="tabela-numero">MRR</th></tr></thead>
                <tbody>
                  {saidas.map((i, n) => (
                    <tr key={n}><td>{i.grupo}</td><td>{i.escopo ?? `Contrato ${i.contrato_id}`}</td><td>{data(i.data)}</td>
                      <td>{i.iniciativa ?? "—"}</td><td>{i.motivo ?? "Sem motivo informado"}</td><td className="tabela-numero">{dinheiro(i.valor)}</td></tr>
                  ))}
                </tbody>
              </table>
            ),
          }} />
        )}
      </p>
    </div>
  );
}

function Linha({ rotulo, valor, sinal, nota, categoria, de, explicacao }: {
  rotulo: string; valor: string; sinal?: "+" | "−"; nota?: string; categoria?: CategoriaDoMovimento; de?: string; explicacao?: string;
}) {
  return (
    <tr>
      <td title={explicacao}>
        {rotulo}
        {nota && <span className="numero-nota"> · {nota}</span>}
        {categoria && de && Number(valor) !== 0 && (
          <BotaoDeComposicao rotulo="ver composição" composicao={{
            titulo: ROTULO_DA_CATEGORIA[categoria], subtitulo: `Desde ${data(de)}`,
            conteudo: () => <ItensDaLinha de={de} categoria={categoria} />,
          }} />
        )}
      </td>
      <td className="tabela-numero">
        {sinal && Number(valor) !== 0 ? `${sinal} ` : ""}
        {dinheiro(valor)}
      </td>
    </tr>
  );
}

/** `versao` muda quando um contrato é salvo ou recebe evento: o MRR é recalculado na hora. */
export function Receita({ versao = 0 }: { versao?: number }) {
  const [periodo, definirPeriodo] = useState<Periodo>("mes");
  const { dados, carregando, erro, recarregar } = usarDados<Mrr>(() => api.mrr(inicioDoPeriodo(periodo)), [periodo, versao]);

  if (carregando && !dados) return <Carregando rotulo="Calculando o MRR" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const { atual, movimento: m } = dados;

  return (
    <section className="numero receita" aria-label={dados.cobertura_completa ? "MRR da carteira" : "MRR dos contratos registrados"}>
      <div className="recado" role="note">
        <strong>{dados.cobertura_completa ? "Confira a fonte." : "MRR parcial."}</strong> {dados.aviso}
      </div>

      <div className="receita-topo">
        <div>
          <h3 className="numero-rotulo">{dados.cobertura_completa ? "MRR da carteira" : "MRR dos contratos registrados"}</h3>
          <p className="numero-valor" title="Soma da parcela mensal dos contratos ativos, em bruto, × 13 ÷ 12 (13 parcelas no ano).">
            {dinheiro(atual.valor)}
            <BotaoDeComposicao rotulo="ver composição" composicao={{
              titulo: "MRR atual da carteira", subtitulo: "Contratado e recebido por cliente", quantos: atual.grupos,
              conteudo: () => <ComposicaoDaCarteira />,
            }} />
          </p>
          {dados.contra_a_meta && (
            <p className="receita-meta">
              <span className={`etiqueta etiqueta-${SITUACAO_DA_META[dados.contra_a_meta][1]}`}>
                {SITUACAO_DA_META[dados.contra_a_meta][0]}
              </span>{" "}
              {dados.contra_a_meta === "na_meta"
                ? `meta de ${dinheiro(dados.meta)} atingida`
                : `falta ${dinheiro(dados.falta_para_a_meta)} para a meta de ${dinheiro(dados.meta)} · alerta abaixo de ${dinheiro(dados.alerta)}`}
            </p>
          )}
          <div className="numero-detalhe">
            <p>
              {atual.contratos} contrato{atual.contratos === 1 ? "" : "s"} ativo{atual.contratos === 1 ? "" : "s"}
              {atual.suspenso_contratos > 0 && ` · ${dinheiro(atual.suspenso_valor)} em ${atual.suspenso_contratos} suspenso${atual.suspenso_contratos === 1 ? "" : "s"}`}
            </p>
            {atual.ticket_por_grupo !== null && (
              <p>
                Ticket médio por grupo <strong>{dinheiro(atual.ticket_por_grupo)}</strong>
                {" · "}mediana <strong>{dinheiro(atual.mediana_por_grupo)}</strong>
                {" · "}{atual.grupos} grupo{atual.grupos === 1 ? "" : "s"}
              </p>
            )}
            {(dados.contratos_liquidos > 0 || dados.contratos_sem_base > 0) && (
              <p className="numero-nota">
                Somado em bruto
                {dados.contratos_liquidos > 0 &&
                  `: ${dados.contratos_liquidos} contrato${dados.contratos_liquidos === 1 ? " líquido entrou" : "s líquidos entraram"} com o imposto de ${aliquota(dados.imposto)}`}
                {dados.contratos_sem_base > 0 &&
                  ` · ⚠ ${dados.contratos_sem_base} sem bruto ou líquido informado, ${dados.contratos_sem_base === 1 ? "somado como está" : "somados como estão"} (marque em cada contrato)`}
                .
              </p>
            )}
            {atual.sem_preco_mensal > 0 && (
              <p className="numero-nota">
                {atual.sem_preco_mensal} contrato{atual.sem_preco_mensal === 1 ? "" : "s"} sem preço mensal ficou de fora da soma.
              </p>
            )}
            {atual.ticket_por_grupo !== null && (
              <p className="numero-nota">
                Receita média por grupo, na carteira inteira (não é venda nova). Empresas do mesmo grupo
                contam como um; a mediana vai junto porque poucos grupos grandes puxam a média.
              </p>
            )}
            {dados.contratos_registrados === 0 && (
              <p className="numero-estado">Nenhum contrato registrado ainda: o MRR aparece quando o primeiro for ativado.</p>
            )}
          </div>
        </div>
        <label className="campo">
          <span className="campo-rotulo">Período</span>
          <select className="selecao" value={periodo} onChange={(e) => definirPeriodo(e.target.value as Periodo)}>
            {(Object.keys(ROTULOS) as Periodo[]).map((p) => <option key={p} value={p}>{ROTULOS[p]}</option>)}
          </select>
        </label>
      </div>

      <table className="tabela" aria-label="Movimento do MRR">
        <caption className="numero-nota" style={{ textAlign: "left" }}>
          De {data(m.de)} a {data(m.ate)}
        </caption>
        <tbody>
          <Linha rotulo="MRR no início" valor={m.mrr_inicio} explicacao="O MRR de hoje menos tudo o que se moveu desde o início do período." />
          <Linha rotulo="Novos contratos" valor={m.novo} sinal="+" nota="assinados no período" categoria="novo" de={m.de}
            explicacao="Preço mensal na assinatura dos contratos assinados no período, × 13 ÷ 12." />
          <Linha rotulo="Expansão" valor={m.expansao} sinal="+" categoria="expansao" de={m.de}
            explicacao="Aumento de preço por Expansão ou Aditivo no período." />
          <Linha rotulo="Reajuste" valor={m.reajuste} sinal="+" categoria="reajuste" de={m.de}
            explicacao="Aumento de preço por Reajuste no período." />
          <Linha rotulo="Contração" valor={m.contracao} sinal="−" categoria="contracao" de={m.de}
            explicacao="Qualquer queda de preço no período (a Correção de lançamento não conta)." />
          <Linha rotulo="Churn: decidido pelo cliente" valor={m.churn_cliente} sinal="−" categoria="churn_cliente" de={m.de}
            explicacao="Contratos encerrados no período por decisão do cliente, pelo valor que tinham." />
          <Linha rotulo="Saída organizada: decidida pela Critério" valor={m.churn_criterio} sinal="−" categoria="churn_criterio" de={m.de}
            explicacao="Contratos encerrados no período por decisão da Critério, pelo valor que tinham." />
          <tr>
            <td><strong>MRR no fim</strong></td>
            <td className="tabela-numero"><strong>{dinheiro(m.mrr_fim)}</strong></td>
          </tr>
        </tbody>
      </table>

      <div className="receita-retencao">
        <p>
          <strong title="(MRR no início + expansão + reajuste − contração − churn) ÷ MRR no início, só com contratos que já existiam no início.">NRR</strong>{" "}
          {m.nrr !== null ? percentual(m.nrr) : "não calculável"}
          {" · "}
          <strong title="(MRR no início − contração − churn) ÷ MRR no início, só com contratos que já existiam no início.">GRR</strong>{" "}
          {m.grr !== null ? percentual(m.grr) : "não calculável"}
        </p>
        <p className="numero-nota">
          {m.nrr === null
            ? "Sem MRR no início do período, não há o que medir (e nunca vira 0%). "
            : ""}
          Só contam contratos que já existiam no início do período. Contração inclui qualquer queda de preço.
        </p>
      </div>
      <MotivosDeChurn de={m.de} />
    </section>
  );
}
