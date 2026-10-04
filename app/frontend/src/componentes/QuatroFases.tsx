/** Inteligência de Conversão › as quatro fases do cliente (amostra aprovada por Eduardo em 03/10/2026,
 * construída em 04/10/2026): a cadeia do funil no mês com o gargalo, e um cartão por fase — Atração,
 * Engajamento, Conversão e Pós-venda — com o KPI principal, os de apoio (previsto × realizado) e o
 * ajuste. O ajuste é regra fixa do servidor, não sugestão de IA. Situação sempre com palavra e sinal. */

import { useState } from "react";
import { api } from "../api/cliente";
import type { ChaveDaSituacao, EtapaDaCadeia, FaseDoCliente, FasesDoMes, IndicadorDaFase, SituacaoDoPlano } from "../api/tipos";
import { dinheiro, dinheiroCurto, percentual } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const mesCurto = (iso: string) => `${MESES[Number(iso.slice(5, 7)) - 1]}/${iso.slice(0, 4)}`;
const SITUACAO: Record<ChaveDaSituacao, { texto: string; tom: string; sinal: string }> = {
  no_ritmo: { texto: "No ritmo", tom: "ganho", sinal: "✓" },
  atencao: { texto: "Atenção", tom: "espera", sinal: "!" },
  abaixo: { texto: "Abaixo do previsto", tom: "perda", sinal: "↓" },
};
const ORIGEM: Record<string, string> = { premissa: "premissa", historico: "histórico de 3 meses", sem_dado: "sem dado" };
const NOME_DA_TAXA: Record<string, string> = {
  lead_reuniao: "lead no ICP → reunião", reuniao_proposta: "reunião → proposta", conversao: "conversão",
};
const NUMERO_DA_FASE: Record<FaseDoCliente["chave"], string> = { atracao: "1", engajamento: "2", conversao: "3", pos_venda: "4" };

function valor(v: string | null, unidade: IndicadorDaFase["unidade"]): string {
  if (v === null) return "—";
  const n = Number(v);
  if (unidade === "reais") return dinheiro(v);
  if (unidade === "pct") return percentual(String(Math.round(n * 10) / 10));
  const texto = n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  if (unidade === "horas") return `${texto} h`;
  if (unidade === "dias") return `${texto} dias`;
  return texto;
}

function Etiqueta({ situacao, gargalo = false }: { situacao: SituacaoDoPlano | null; gargalo?: boolean }) {
  if (!situacao) return <span className="etiqueta etiqueta-neutra">Sem previsto</span>;
  const s = SITUACAO[situacao.chave];
  return (
    <span className={`etiqueta etiqueta-${s.tom}`}>
      <span aria-hidden="true">{s.sinal} </span>{s.texto}{gargalo && " · gargalo"}
    </span>
  );
}

function Barra({ previsto, realizado, tom }: { previsto: string | null; realizado: string | null; tom: string }) {
  if (previsto === null || realizado === null || Number(previsto) <= 0) return null;
  const p = Number(previsto), r = Number(realizado);
  const teto = Math.max(p, r) * 1.1;
  return (
    <div className="fase-barra" role="img" aria-label={`Realizado ${Math.round((r / p) * 100)}% do previsto`}>
      <span className={`fase-barra-feito fase-tom-${tom}`} style={{ width: `${(r / teto) * 100}%` }} />
      <span className="fase-barra-marca" style={{ left: `${(p / teto) * 100}%` }} />
    </div>
  );
}

function Cadeia({ etapas, gargalo }: { etapas: EtapaDaCadeia[]; gargalo: string | null }) {
  return (
    <ol className="cadeia" aria-label="Cadeia do funil no mês, realizado sobre previsto">
      {etapas.map((e, i) => (
        <li key={e.chave} className="cadeia-passo">
          <div className={`cadeia-etapa${e.chave === gargalo ? " cadeia-gargalo" : ""}`}>
            <span className="cadeia-rotulo">{e.rotulo}{e.chave === gargalo && " · gargalo"}</span>
            <span className="cadeia-valor">
              {e.chave === "mrr_novo" ? dinheiroCurto(e.realizado) : valor(e.realizado, "numero")}
              <span className="cadeia-previsto"> / {e.chave === "mrr_novo" ? dinheiroCurto(e.previsto) : valor(e.previsto, "numero")}</span>
            </span>
          </div>
          {i < etapas.length - 1 && (
            <span className="cadeia-seta" aria-hidden={e.taxa_realizada === null && e.taxa_prevista === null}>
              {e.taxa_realizada !== null ? percentual(e.taxa_realizada) : e.taxa_prevista !== null ? `prev. ${percentual(e.taxa_prevista)}` : ""}
              <span aria-hidden="true"> →</span>
            </span>
          )}
        </li>
      ))}
    </ol>
  );
}

function Cartao({ fase, gargalo }: { fase: FaseDoCliente; gargalo: boolean }) {
  const tom = fase.situacao ? SITUACAO[fase.situacao.chave].tom : "neutra";
  const k = fase.kpi;
  return (
    <section className={`fase${gargalo ? " fase-gargalo" : ""}`} aria-labelledby={`fase-${fase.chave}`}>
      <header className="fase-topo">
        <div>
          <h4 className="fase-titulo" id={`fase-${fase.chave}`}>{NUMERO_DA_FASE[fase.chave]} · {fase.titulo}</h4>
          <p className="fase-pergunta">{fase.pergunta}</p>
        </div>
        <Etiqueta situacao={fase.situacao} gargalo={gargalo} />
      </header>
      <div>
        <p className="fase-kpi-rotulo">{k.rotulo}</p>
        {k.realizado === null && k.previsto === null ? (
          <p className="fase-kpi-pendente">{k.nota ?? "Sem dado no mês"}</p>
        ) : (
          <p className="fase-kpi">
            {valor(k.realizado, k.unidade)}{" "}
            <span className="fase-kpi-previsto">previsto {valor(k.previsto, k.unidade)}</span>
          </p>
        )}
        <Barra previsto={k.previsto} realizado={k.realizado} tom={tom} />
      </div>
      <table className="fase-apoio">
        <thead>
          <tr><th scope="col">Apoio</th><th scope="col" className="tabela-numero">Previsto</th><th scope="col" className="tabela-numero">Realizado</th></tr>
        </thead>
        <tbody>
          {fase.apoio.map((a) => (
            <tr key={a.rotulo}>
              <td>{a.rotulo}{a.nota && <span className="fase-nota"> · {a.nota}</span>}</td>
              <td className="tabela-numero">{valor(a.previsto, a.unidade)}</td>
              <td className="tabela-numero">{valor(a.realizado, a.unidade)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="fase-ajuste"><strong>Ajuste:</strong> {fase.ajuste}</p>
    </section>
  );
}

/** Qual fase o gargalo da cadeia aponta. */
const FASE_DO_GARGALO: Record<string, FaseDoCliente["chave"]> = {
  leads_icp: "atracao", reunioes: "engajamento", propostas: "engajamento", contratos: "conversao", mrr_novo: "conversao",
};

export function QuatroFases() {
  const [mes, definirMes] = useState<string | undefined>(undefined);
  const { dados, carregando, erro, recarregar } = usarDados<FasesDoMes>(() => api.fasesDoMes(mes), [mes]);
  if (carregando && !dados) return <Carregando rotulo="Montando as quatro fases" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const faseGargalo = dados.gargalo ? FASE_DO_GARGALO[dados.gargalo] : null;
  return (
    <section className="quatro-fases" aria-labelledby="quatro-fases-titulo">
      <div className="quatro-fases-topo">
        <h3 className="plano-secao" id="quatro-fases-titulo">Cadeia do funil no mês · realizado / previsto</h3>
        <label className="quatro-fases-mes">
          <span className="campo-rotulo">Mês</span>
          <select className="entrada" value={dados.mes} onChange={(e) => definirMes(e.target.value)}>
            {dados.meses.map((m) => <option key={m} value={m}>{mesCurto(m)}</option>)}
          </select>
        </label>
      </div>
      {dados.aviso && <p className="campo-ajuda" role="note">{dados.aviso}</p>}
      <Cadeia etapas={dados.cadeia} gargalo={dados.gargalo} />
      {dados.gargalo_texto && <p className="cadeia-gargalo-texto"><span aria-hidden="true">◎ </span>{dados.gargalo_texto}</p>}
      <p className="campo-ajuda">
        Taxas do previsto: {Object.entries(dados.taxas).map(([k, t]) =>
          `${NOME_DA_TAXA[k] ?? k} ${t.valor !== null ? percentual(t.valor) : "—"} (${ORIGEM[t.origem]})`).join(" · ")}.
      </p>
      <div className="fases">
        {dados.fases.map((f) => <Cartao key={f.chave} fase={f} gargalo={f.chave === faseGargalo} />)}
      </div>
    </section>
  );
}
