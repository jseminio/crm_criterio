/** O MRR dos contratos registrados no CRM, e o que o moveu no período.
 *
 * O KPI oficial de MRR é a receita da carteira inteira. Sem a carteira anterior ao CRM
 * carregada, o número é **parcial**, a tela diz isso e **não compara com a meta**. Com ela,
 * compara com a meta (R$ 400 mil) e o alerta (R$ 200 mil), com ícone e texto (02/10/2026).
 * Churn vem separado por quem decidiu: cliente (churn) e Critério (saída organizada).
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { Mrr } from "../api/tipos";
import { Carregando, Erro } from "../componentes/estados";
import { data, dinheiro, percentual } from "../formato";
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

function Linha({ rotulo, valor, sinal, nota }: { rotulo: string; valor: string; sinal?: "+" | "−"; nota?: string }) {
  return (
    <tr>
      <td>
        {rotulo}
        {nota && <span className="numero-nota"> · {nota}</span>}
      </td>
      <td className="tabela-numero">
        {sinal && Number(valor) !== 0 ? `${sinal} ` : ""}
        {dinheiro(valor)}
      </td>
    </tr>
  );
}

export function Receita() {
  const [periodo, definirPeriodo] = useState<Periodo>("mes");
  const { dados, carregando, erro, recarregar } = usarDados<Mrr>(() => api.mrr(inicioDoPeriodo(periodo)), [periodo]);

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
          <p className="numero-valor">{dinheiro(atual.valor)}</p>
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
          <Linha rotulo="MRR no início" valor={m.mrr_inicio} />
          <Linha rotulo="Novos contratos" valor={m.novo} sinal="+" nota="assinados no período" />
          <Linha rotulo="Expansão" valor={m.expansao} sinal="+" />
          <Linha rotulo="Reajuste" valor={m.reajuste} sinal="+" />
          <Linha rotulo="Contração" valor={m.contracao} sinal="−" />
          <Linha rotulo="Churn: decidido pelo cliente" valor={m.churn_cliente} sinal="−" />
          <Linha rotulo="Saída organizada: decidida pela Critério" valor={m.churn_criterio} sinal="−" />
          <tr>
            <td><strong>MRR no fim</strong></td>
            <td className="tabela-numero"><strong>{dinheiro(m.mrr_fim)}</strong></td>
          </tr>
        </tbody>
      </table>

      <div className="receita-retencao">
        <p>
          <strong>NRR</strong> {m.nrr !== null ? percentual(m.nrr) : "não calculável"}
          {" · "}
          <strong>GRR</strong> {m.grr !== null ? percentual(m.grr) : "não calculável"}
        </p>
        <p className="numero-nota">
          {m.nrr === null
            ? "Sem MRR no início do período, não há o que medir (e nunca vira 0%). "
            : ""}
          Só contam contratos que já existiam no início do período. Contração inclui qualquer queda de preço.
        </p>
      </div>
    </section>
  );
}
