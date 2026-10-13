/** KPIs da liderança (amostra aprovada por Eduardo em 09/10/2026; churn no ano em 13/10/2026): os indicadores da planilha
 * "CRITÉRIO — KPIs de mercado", mês a mês, em MRR com 13 parcelas. Só o Administrador vê. Cada card diz o
 * que entrou na conta e, quando falta registro, o que falta — "sem dado" nunca vira zero. */

import { useState } from "react";
import { api } from "../api/cliente";
import type { ItemDoKpi, KpiDaLideranca, KpisDaLideranca as Kpis } from "../api/tipos";
import { Indicador, type Tom } from "./Indicador";
import { dinheiro, percentual } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
  "novembro", "dezembro"];

/** Os últimos 12 meses, do atual para trás, como "2026-10". */
export function ultimosMeses(hoje = new Date()): { valor: string; rotulo: string }[] {
  return Array.from({ length: 12 }, (_, i) => {
    const d = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1);
    return { valor: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`, rotulo: `${MESES[d.getMonth()]} de ${d.getFullYear()}` };
  });
}

function valorDoKpi(k: KpiDaLideranca): string {
  if (k.valor === null) return "sem dado";
  return k.unidade === "R$" ? dinheiro(k.valor) : percentual(k.valor);
}

const texto = (v: string | number | null | undefined) => (v === null || v === undefined ? "—" : String(v));

function Detalhe({ k }: { k: KpiDaLideranca }) {
  const x = k.extras;
  if (k.chave === "ticket") {
    return (
      <div style={{ display: "grid", gap: "var(--e1)" }}>
        <p className="campo-ajuda" style={{ margin: 0 }}>
          No mês: por grupo <strong>{dinheiro(texto(x.mes_por_grupo))}</strong> · por CNPJ{" "}
          <strong>{dinheiro(texto(x.mes_por_cnpj))}</strong> ({texto(x.mes_grupos)} grupo(s), {texto(x.mes_cnpjs)} CNPJ(s))
        </p>
        <p className="campo-ajuda" style={{ margin: 0 }}>
          No ano: por grupo <strong>{dinheiro(texto(x.ano_por_grupo))}</strong> (mediana {dinheiro(texto(x.ano_mediana_por_grupo))}) ·
          por CNPJ <strong>{dinheiro(texto(x.ano_por_cnpj))}</strong> (mediana {dinheiro(texto(x.ano_mediana_por_cnpj))})
        </p>
      </div>
    );
  }
  if (k.chave === "upsell") {
    return (
      <div style={{ display: "grid", gap: "var(--e1)" }}>
        <p className="campo-ajuda" style={{ margin: 0 }}>
          Recorrente: <strong>{dinheiro(texto(x.recorrente))}</strong>/mês ({percentual(x.recorrente_pct as string | null)})
        </p>
        <p className="campo-ajuda" style={{ margin: 0 }}>
          Não recorrente: <strong>{dinheiro(texto(x.nao_recorrente))}</strong> ({percentual(x.nao_recorrente_pct as string | null)})
        </p>
      </div>
    );
  }
  if (k.chave === "integralidade") {
    const cadastros = [["Oportunidade", "oportunidade"], ["Contrato", "contrato"], ["Encerramento", "encerramento"],
      ["Cliente", "cliente"], ["Empresa (CNPJ)", "empresa"], ["Contato", "contato"]] as const;
    return (
      <div style={{ display: "grid", gap: "var(--e1)" }}>
        <ul className="integralidade-barras" aria-label="Pendente por cadastro">
          {cadastros.map(([rotulo, chave]) => {
            const v = x[`pendente_${chave}`];
            const n = v === null || v === undefined ? null : Number(v);
            return (
              <li key={chave}>
                <span>{rotulo}</span>
                <span className="integralidade-trilho" aria-hidden="true">
                  <span className="integralidade-barra" style={{ width: `${n ?? 0}%` }} />
                </span>
                <span className="tabela-numero">{n === null ? "—" : percentual(String(v))}</span>
              </li>
            );
          })}
        </ul>
        <p className="campo-ajuda" style={{ margin: 0 }}>Obrigatório vale 2, prioritário vale 1.</p>
        <p className="campo-ajuda" style={{ margin: 0 }}>
          Legado (antes do corte): {x.legado_pct === null || x.legado_pct === undefined ? "—" : percentual(String(x.legado_pct))} pendente
        </p>
      </div>
    );
  }
  if (k.chave === "churn_novos") {
    return (
      <div style={{ display: "grid", gap: "var(--e1)" }}>
        <p className="campo-ajuda" style={{ margin: 0 }}>
          Tempo médio como cliente: {x.tempo_medio_meses === null || x.tempo_medio_meses === undefined
            ? "—" : `${String(x.tempo_medio_meses).replace(".", ",")} meses`}
        </p>
        <p className="campo-ajuda" style={{ margin: 0 }}>Sinal de venda ou implantação, não de retenção.</p>
      </div>
    );
  }
  return null;
}

const TOM: Record<string, Tom> = {
  mrr_novo: "verde", ticket: "dourado", upsell: "violeta", churn: "vermelho", churn_novos: "vermelho", cobertura: "azul", integralidade: "marinho",
};
const NO_ANO = new Set(["churn", "churn_novos"]);

/** A lista que compõe o KPI: quem entra na conta primeiro, quem ficou fora (a base, os sem reunião) depois. */
function ComposicaoDoKpi({ k }: { k: KpiDaLideranca }) {
  const entram = k.itens.filter((i) => i.entra);
  const fora = k.itens.filter((i) => !i.entra);
  const comValor = k.itens.some((i) => Number(i.valor) > 0);
  const totalDe = (itens: ItemDoKpi[]) => itens.reduce((t, i) => t + Number(i.valor), 0);
  const tabela = (itens: ItemDoKpi[], rotulo: string) => (
    <table className="tabela" aria-label={rotulo}>
      <thead><tr><th>Cliente</th><th>O quê</th>{comValor && <th className="tabela-numero">Valor</th>}</tr></thead>
      <tbody>
        {itens.map((i, n) => (
          <tr key={n}><td>{i.grupo}</td><td>{i.detalhe}</td>{comValor && <td className="tabela-numero">{dinheiro(i.valor)}</td>}</tr>
        ))}
        {comValor && itens.length > 0 && itens.every((i) => i.entra) && (
          <tr className="composicao-total"><td>Total</td><td />
            <td className="tabela-numero">{dinheiro(totalDe(itens))}</td></tr>
        )}
      </tbody>
    </table>
  );
  const secoes = [...new Set(k.itens.map((i) => i.secao).filter((x): x is string => !!x))];
  if (secoes.length > 0) {
    return (
      <>
        <p className="composicao-linha-resumo">
          {visoesDoChurn(k)
            ? visoesDoChurn(k)!.map((v) => <span key={v.rotulo}>{v.rotulo}: <strong>{v.valor}</strong> ({v.apoio}) · </span>)
            : <><strong>{valorDoKpi(k)}</strong> · </>}
          {k.resumo}
        </p>
        {secoes.map((secao) => {
          const itens = k.itens.filter((i) => i.secao === secao);
          return (
            <div key={secao}>
              <h3 className="numero-rotulo">{secao} ({itens.length})</h3>
              {tabela(itens, secao)}
            </div>
          );
        })}
        {entram.length === 0 && <p className="numero-estado">Nada entrou na conta no ano.</p>}
      </>
    );
  }
  return (
    <>
      <p className="composicao-linha-resumo"><strong>{valorDoKpi(k)}</strong> · {k.resumo}</p>
      {entram.length > 0 ? tabela(entram, "Entram na conta") : <p className="numero-estado">Nada entrou na conta no mês.</p>}
      {fora.length > 0 && (
        <>
          <h3 className="numero-rotulo">Ficaram fora da conta ({fora.length})</h3>
          {tabela(fora, "Ficaram fora da conta")}
        </>
      )}
    </>
  );
}

/** Duas visões no mesmo card (13/10/2026): o churn por grupos e por faturamento; a integralidade do cadastro,
 * o pendente e os obrigatórios em falta. */
function visoesDoChurn(k: KpiDaLideranca) {
  const x = k.extras;
  if (k.chave === "integralidade") {
    return [
      { rotulo: "Pendente", valor: valorDoKpi(k), apoio: `${texto(x.pontos_pendentes)} de ${texto(x.pontos_devidos)} pontos` },
      { rotulo: "Obrigatórios em falta", valor: texto(x.obrigatorios_em_falta), apoio: `e ${texto(x.prioritarios_em_falta)} prioritários` },
    ];
  }
  if (!NO_ANO.has(k.chave)) return undefined;
  return [
    { rotulo: "Por grupos", valor: valorDoKpi(k), apoio: `${texto(x.grupos_perdidos)} de ${texto(x.grupos)} grupos` },
    { rotulo: "Por faturamento", valor: x.faturamento_pct === null || x.faturamento_pct === undefined ? "sem dado" : percentual(String(x.faturamento_pct)),
      apoio: `${dinheiro(texto(x.mrr_perdido))} de ${dinheiro(texto(x.mrr_de_partida))}/mês` },
  ];
}

function Cartao({ k }: { k: KpiDaLideranca }) {
  return (
    <Indicador
      rotulo={k.titulo}
      tom={TOM[k.chave] ?? "marinho"}
      destaque={valorDoKpi(k)}
      valores={visoesDoChurn(k)}
      pendente={k.valor === null}
      apoio={<>{k.resumo}{k.meta && <><br />Meta: {k.meta}</>}</>}
      etiqueta={
        <>
          <Detalhe k={k} />
          {k.falta.map((f) => (
            <p key={f} className="aviso-de-movimento" role="note" style={{ margin: "var(--e1) 0 0" }}>Falta: {f}</p>
          ))}
        </>
      }
      composicao={k.itens.length > 0 ? {
        titulo: k.titulo, subtitulo: NO_ANO.has(k.chave) ? "O que compõe o indicador no ano, até o fim do mês" : "O que compõe o indicador no mês", quantos: k.itens.length,
        conteudo: () => <ComposicaoDoKpi k={k} />,
      } : undefined}
    >
      <p>{k.explicacao}</p>
      {k.meta && <p>Meta: {k.meta}</p>}
    </Indicador>
  );
}

export function KpisDaLideranca() {
  const meses = ultimosMeses();
  const [mes, definirMes] = useState(meses[0].valor);
  const { dados, carregando, erro, recarregar } = usarDados<Kpis>(() => api.kpisDaLideranca(mes), [mes]);
  return (
    <section aria-labelledby="kpis-titulo" style={{ display: "grid", gap: "var(--e3)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: "var(--e2)", flexWrap: "wrap" }}>
        <h2 className="plano-titulo" id="kpis-titulo" style={{ flex: 1, margin: 0 }}>KPIs da liderança</h2>
        <select className="selecao" aria-label="Mês dos KPIs" value={mes} onChange={(e) => definirMes(e.target.value)}>
          {meses.map((m) => <option key={m.valor} value={m.valor}>{m.rotulo}</option>)}
        </select>
      </div>
      <p className="campo-ajuda" style={{ margin: 0 }}>
        Só o Administrador vê. Valores em MRR: a parcela × 13 ÷ 12. "Falta" diz o que registrar para o KPI valer.
      </p>
      {carregando && !dados && <Carregando rotulo="Calculando os KPIs" />}
      {erro && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {dados && (
        <div className="numeros numeros-kpis">
          {dados.kpis.map((k) => <Cartao key={k.chave} k={k} />)}
        </div>
      )}
    </section>
  );
}
