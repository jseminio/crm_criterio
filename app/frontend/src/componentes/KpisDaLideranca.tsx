/** KPIs da liderança (amostra aprovada por Eduardo em 09/10/2026): os cinco indicadores da planilha
 * "CRITÉRIO — KPIs de mercado", mês a mês, em MRR com 13 parcelas. Só o Administrador vê. Cada card diz o
 * que entrou na conta e, quando falta registro, o que falta — "sem dado" nunca vira zero. */

import { useState } from "react";
import { api } from "../api/cliente";
import type { KpiDaLideranca, KpisDaLideranca as Kpis } from "../api/tipos";
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
  return null;
}

function Cartao({ k }: { k: KpiDaLideranca }) {
  return (
    <section className={k.valor === null ? "numero numero-pendente" : "numero"} aria-labelledby={`kpi-${k.chave}`}>
      <h3 className="numero-rotulo" id={`kpi-${k.chave}`}>{k.titulo}</h3>
      <p className="numero-valor" style={{ margin: "var(--e1) 0" }}>{valorDoKpi(k)}</p>
      <p className="campo-ajuda" style={{ margin: 0 }}>{k.resumo}</p>
      <Detalhe k={k} />
      {k.meta && <p className="campo-ajuda" style={{ margin: "var(--e1) 0 0" }}>Meta: {k.meta}</p>}
      {k.falta.map((f) => (
        <p key={f} className="aviso-de-movimento" role="note" style={{ margin: "var(--e1) 0 0" }}>Falta: {f}</p>
      ))}
      {k.itens.length > 0 && (
        <details style={{ marginTop: "var(--e2)" }}>
          <summary className="campo-ajuda">Ver o que entrou na conta ({k.itens.length})</summary>
          <ul style={{ margin: "var(--e1) 0 0", paddingLeft: "1.2rem" }}>
            {k.itens.map((i, n) => (
              <li key={n} className="campo-ajuda">
                {i.grupo} · {i.detalhe}{Number(i.valor) > 0 ? ` · ${dinheiro(i.valor)}` : ""}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
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
        <div style={{ display: "grid", gap: "var(--e3)", gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))" }}>
          {dados.kpis.map((k) => <Cartao key={k.chave} k={k} />)}
        </div>
      )}
    </section>
  );
}
