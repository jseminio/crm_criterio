/** Propostas em aberto · visão gerencial (amostra aprovada por Eduardo em 14/10/2026), para a war room com o Bruno:
 * o quadro por etapa com o mensalizado (com a 13ª) aberto por temperatura, a conversão, as enviadas no mês e o
 * On hold há mais de 60 dias. "Copiar para enviar" leva o quadro em texto; "Baixar planilha", o Excel. */

import { useState } from "react";
import { api } from "../api/cliente";
import type { LinhaDoQuadroDePropostas, PropostaAberta, QuadroDePropostas } from "../api/tipos";
import { data, dinheiro, percentual } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";
import { BotaoDeComposicao, Explicavel, Indicador } from "./Indicador";

const COLUNAS: { chave: keyof LinhaDoQuadroDePropostas; rotulo: string; classe?: string }[] = [
  { chave: "anual", rotulo: "Valor anual" },
  { chave: "mensalizado", rotulo: "Mensalizado" },
  { chave: "quente", rotulo: "Quente", classe: "quadro-quente" },
  { chave: "morno", rotulo: "Morno", classe: "quadro-morno" },
  { chave: "frio", rotulo: "Frio", classe: "quadro-frio" },
  { chave: "sem_classificacao", rotulo: "Sem class." },
];

const valor = (v: string) => (Number(v) === 0 ? "—" : dinheiro(v));

/** O quadro em texto, para colar no e-mail ou no WhatsApp. */
export function quadroEmTexto(q: QuadroDePropostas): string {
  const linha = (l: LinhaDoQuadroDePropostas) =>
    `${l.etapa}: ${l.quantas} · ${dinheiro(l.anual)} ao ano · ${dinheiro(l.mensalizado)}/mês ` +
    `(quente ${dinheiro(l.quente)}, morno ${dinheiro(l.morno)}, frio ${dinheiro(l.frio)}, sem class. ${dinheiro(l.sem_classificacao)})`;
  const conv = (c: QuadroDePropostas["conversao_do_ano"]) =>
    `${c.rotulo}: ${c.percentual === null ? "sem dado" : percentual(c.percentual)} (${c.aceitas} aceitas / ${c.decididas} decididas)`;
  return [
    `Propostas em aberto · visão gerencial · ${data(q.hoje)}`,
    "",
    ...q.linhas.map(linha),
    linha(q.total),
    "Mensalizado: recorrente pela parcela × 13 ÷ 12; pontual pelo valor único ÷ 12.",
    "",
    conv(q.conversao_do_ano),
    conv(q.conversao_12_meses),
    `Enviadas em ${q.mes_das_enviadas}: ${q.enviadas_no_mes} · ${dinheiro(q.enviadas_no_mes_em_aberto)} ainda em aberto`,
    `On hold há mais de 60 dias: ${q.on_hold_antigas} · ${dinheiro(q.on_hold_antigas_mensalizado)}/mês`,
    "",
    "O que o quadro mostra:",
    ...q.resumo.map((f) => `- ${f}`),
  ].join("\n");
}

function ListaDePropostas({ propostas, comOnHold = false }: { propostas: PropostaAberta[]; comOnHold?: boolean }) {
  if (propostas.length === 0) return <p className="numero-estado">Nenhuma proposta.</p>;
  const total = propostas.reduce((t, p) => t + Number(p.mensalizado), 0);
  return (
    <table className="tabela" aria-label="Propostas">
      <thead>
        <tr>
          <th>Grupo</th><th>Proposta</th><th>Temperatura</th>
          {comOnHold && <th>Em On hold desde</th>}
          <th className="tabela-numero">Mensalizado</th>
        </tr>
      </thead>
      <tbody>
        {propostas.map((p) => (
          <tr key={p.id}>
            <td>{p.grupo}</td>
            <td>{p.servico ?? p.nome}{p.captador ? ` · ${p.captador}` : ""}</td>
            <td>{p.temperatura ?? "sem class."}</td>
            {comOnHold && (
              <td>{data(p.em_on_hold_desde)}{p.dias_em_on_hold !== null && ` · ${p.dias_em_on_hold} dias`}
                {p.on_hold_pela_originacao && <span className="numero-nota"> (pela originação)</span>}</td>
            )}
            <td className="tabela-numero">{dinheiro(p.mensalizado)}</td>
          </tr>
        ))}
        <tr className="composicao-total"><td>Total</td><td /><td />{comOnHold && <td />}
          <td className="tabela-numero">{dinheiro(total)}</td></tr>
      </tbody>
    </table>
  );
}

export function PropostasEmAberto() {
  const { dados: q, carregando, erro, recarregar } = usarDados<QuadroDePropostas>(() => api.propostasEmAberto(), []);
  const [recado, definirRecado] = useState<string | null>(null);

  async function copiar() {
    if (!q) return;
    try {
      await navigator.clipboard.writeText(quadroEmTexto(q));
      definirRecado("Quadro copiado: é só colar no e-mail ou no WhatsApp.");
    } catch {
      definirRecado("O navegador não deixou copiar. Use \"Baixar planilha\".");
    }
  }

  async function baixar() {
    try {
      await api.baixarPropostasEmAberto();
    } catch {
      definirRecado("Não foi possível baixar a planilha agora. Tente de novo.");
    }
  }

  if (carregando && !q) return <Carregando rotulo="Montando o quadro das propostas em aberto" />;
  if (erro && !q) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!q) return null;

  const daEtapa = (etapa: string) => q.propostas.filter((p) => p.etapa === etapa);
  const antigas = q.propostas.filter((p) => p.dias_em_on_hold !== null && p.dias_em_on_hold > 60);

  return (
    <section className="quadro-propostas" aria-labelledby="quadro-propostas-titulo">
      <div className="plano-cabecalho">
        <div>
          <h2 className="plano-titulo" id="quadro-propostas-titulo">Propostas em aberto · visão gerencial</h2>
          <p className="campo-ajuda">
            Hoje, {data(q.hoje)}. Mensalizado com a 13ª: recorrente pela parcela × 13 ÷ 12; consultoria e legalização
            pelo valor único ÷ 12. As colunas de temperatura somam o mensalizado da linha.
          </p>
        </div>
        <div style={{ display: "flex", gap: "var(--e2)", flexWrap: "wrap" }}>
          <button type="button" className="botao botao-secundario" onClick={copiar}>Copiar para enviar</button>
          <button type="button" className="botao botao-secundario" onClick={baixar}>Baixar planilha</button>
        </div>
      </div>
      {recado && <p className="recado" role="status">{recado}</p>}

      <div className="tabela-rolavel">
        <table className="tabela quadro-tabela">
          <thead>
            <tr>
              <th>Etapa</th>
              <th className="tabela-numero">Qtd</th>
              {COLUNAS.map((c) => <th key={c.chave} className="tabela-numero">{c.rotulo}</th>)}
            </tr>
          </thead>
          <tbody>
            {[...q.linhas, q.total].map((l) => {
              const total = l === q.total;
              return (
                <tr key={l.etapa} className={total ? "composicao-total" : undefined}>
                  <td>
                    {l.etapa}{" "}
                    <BotaoDeComposicao composicao={{
                      titulo: l.etapa, subtitulo: "As propostas da linha, com o mensalizado de cada uma",
                      quantos: l.quantas,
                      conteudo: () => <ListaDePropostas propostas={total ? q.propostas : daEtapa(l.etapa)}
                        comOnHold={l.etapa === "On hold"} />,
                    }} />
                  </td>
                  <td className="tabela-numero">{l.quantas}</td>
                  {COLUNAS.map((c) => (
                    <td key={c.chave} className={`tabela-numero ${c.classe ?? ""}`}>
                      {c.chave === "mensalizado" ? (
                        <Explicavel texto={`Recorrente ${dinheiro(l.recorrente)} + pontual ${dinheiro(l.pontual)}`}>
                          {dinheiro(l.mensalizado)}
                        </Explicavel>
                      ) : valor(String(l[c.chave]))}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="numeros numeros-quadro">
        {[q.conversao_do_ano, q.conversao_12_meses].map((c) => (
          <Indicador key={c.rotulo} rotulo={c.rotulo} tom="azul"
            destaque={c.percentual === null ? undefined : percentual(c.percentual)}
            apoio={`${c.aceitas} aceitas / ${c.decididas} decididas`}>
            <p>Aceitas ÷ decididas (aceitas e perdidas), pela data de originação: a mesma regra da conversão do Funil.</p>
          </Indicador>
        ))}
        <Indicador rotulo={`Enviadas em ${q.mes_das_enviadas}`} tom="verde" destaque={String(q.enviadas_no_mes)}
          apoio={`${dinheiro(q.enviadas_no_mes_em_aberto)} ainda em aberto`}>
          <p>Propostas com a data de envio no mês corrente; o valor é o anual das que seguem em aberto.</p>
        </Indicador>
        <Indicador rotulo="On hold há mais de 60 dias" tom="ambar" destaque={String(q.on_hold_antigas)}
          apoio={`${dinheiro(q.on_hold_antigas_mensalizado)}/mês`}
          composicao={{ titulo: "On hold há mais de 60 dias", subtitulo: "Desde quando cada uma está parada",
            quantos: antigas.length, conteudo: () => <ListaDePropostas propostas={antigas} comOnHold /> }}>
          <p>A entrada em On hold é a última mudança de situação para On hold no histórico; sem registro (carga ou
            antes do histórico), vale a data de originação.</p>
        </Indicador>
      </div>

      <div className="quadro-resumo" role="note">
        <strong>O que o quadro mostra:</strong>
        <ul>{q.resumo.map((f) => <li key={f}>{f}</li>)}</ul>
      </div>
    </section>
  );
}
