/** NRR no ano na Saúde da carteira (aprovado por Eduardo em 18/10/2026). A base é a carteira de 31/12 do ano
 * anterior, a mesma do Churn da base: (MRR em 31/12 + expansão + reajuste − contração − churn) ÷ MRR em 31/12, só
 * com os contratos que já existiam em 31/12. É a conta da aba Receita (`crm.domain.mrr.movimento`), em 13 parcelas.
 * O NRR do mês vai junto, menor. A composição traz a ponte e cada contrato ou evento que a move. */

import { api } from "../api/cliente";
import type { CategoriaDoMovimento, ItemDoMovimento, Mrr } from "../api/tipos";
import { data, dinheiro, percentual } from "../formato";
import { usarDados } from "../usarDados";
import { LinkDoGrupo } from "./AberturaDeCard";
import { Carregando, Erro } from "./estados";
import { BotaoDeComposicao, Explicavel } from "./Indicador";
import { TabelaDeComposicao } from "./TabelaDeComposicao";

const EXPLICACAO = "(MRR em 31/12 + expansão + reajuste − contração − churn) ÷ MRR em 31/12, só com os contratos que já "
  + "existiam em 31/12. Acima de 100%, a base cresceu sozinha, sem contar cliente novo.";

const PONTE: { categoria: CategoriaDoMovimento; rotulo: string; sinal: "+" | "−" }[] = [
  { categoria: "expansao", rotulo: "Expansão", sinal: "+" },
  { categoria: "reajuste", rotulo: "Reajuste", sinal: "+" },
  { categoria: "contracao", rotulo: "Contração", sinal: "−" },
  { categoria: "churn_cliente", rotulo: "Churn: decidido pelo cliente", sinal: "−" },
  { categoria: "churn_criterio", rotulo: "Saída organizada: decidida pela Critério", sinal: "−" },
];
const ROTULO = Object.fromEntries(PONTE.map((p) => [p.categoria, p.rotulo])) as Record<CategoriaDoMovimento, string>;

/** 1º de janeiro do ano corrente: o movimento começa aí, e o MRR de partida é o de 31/12. */
export function inicioDoAno(hoje = new Date()): string {
  return `${hoje.getFullYear()}-01-01`;
}

function ComposicaoDoNrr({ de, movimento }: { de: string; movimento: Mrr["movimento"] }) {
  const { dados, carregando, erro, recarregar } = usarDados<{ itens: ItemDoMovimento[] }>(
    () => api.itensDoMovimento(de, true), [de]);
  if (carregando && !dados) return <Carregando rotulo="Buscando os contratos" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  const itens = (dados?.itens ?? []).filter((i) => i.categoria !== "novo");
  const soma = (c: CategoriaDoMovimento) => itens.filter((i) => i.categoria === c).reduce((t, i) => t + Number(i.valor), 0);
  return (
    <>
      <table className="tabela" aria-label="Ponte do NRR">
        <tbody>
          <tr><td>MRR em 31/12</td><td className="tabela-numero">{dinheiro(movimento.mrr_inicio)}</td></tr>
          {PONTE.map((p) => (
            <tr key={p.categoria}><td>{p.sinal} {p.rotulo}</td><td className="tabela-numero">{dinheiro(String(soma(p.categoria)))}</td></tr>
          ))}
          <tr className="composicao-total">
            <td>NRR · GRR {movimento.grr !== null ? percentual(movimento.grr) : "não calculável"}</td>
            <td className="tabela-numero">{movimento.nrr !== null ? percentual(movimento.nrr) : "não calculável"}</td>
          </tr>
        </tbody>
      </table>
      <p className="campo-ajuda">Cliente novo no ano não entra: ele está no MRR novo, não na retenção da base.</p>
      <h3 className="numero-rotulo">O que moveu a base ({itens.length})</h3>
      {itens.length === 0 ? <p className="numero-estado">Nenhum movimento na base desde 1º de janeiro.</p> : (
        <TabelaDeComposicao rotulo="O que moveu a base" linhas={itens} chave={(i, n) => `${i.contrato_id}-${i.categoria}-${n}`}
          colunas={[
            { titulo: "Cliente", valor: (i) => i.grupo, mostrar: (i) => <LinkDoGrupo grupoId={i.grupo_id} nome={i.grupo} /> },
            { titulo: "Movimento", valor: (i) => ROTULO[i.categoria] },
            { titulo: "Contrato", valor: (i) => i.escopo ?? `Contrato ${i.contrato_id}` },
            { titulo: "Data", valor: (i) => i.data, mostrar: (i) => (i.data ? data(i.data) : "—") },
            { titulo: "MRR", valor: (i) => (PONTE.find((p) => p.categoria === i.categoria)?.sinal === "−" ? -1 : 1) * Number(i.valor),
              mostrar: (i) => `${PONTE.find((p) => p.categoria === i.categoria)?.sinal ?? ""}\u00a0${dinheiro(i.valor)}`, numerico: true },
          ]} />
      )}
    </>
  );
}

export function NrrNoAno() {
  const de = inicioDoAno();
  const ano = usarDados<Mrr>(() => api.mrr(de), [de]);
  const mes = usarDados<Mrr>(() => api.mrr(), []);
  const m = ano.dados?.movimento;
  return (
    <div className="retrato-celula">
      <div className="retrato-chip">
        <b>{ano.erro ? "—" : !m ? "…" : m.nrr !== null ? percentual(m.nrr) : "não calculável"}</b>
        <small>
          <Explicavel texto={EXPLICACAO}>NRR no ano</Explicavel>
          <span className="retrato-nrr-mes">
            desde 31/12{mes.dados?.movimento.nrr != null ? ` · no mês ${percentual(mes.dados.movimento.nrr)}` : ""}
          </span>
        </small>
      </div>
      {m && (
        <BotaoDeComposicao rotulo="ver" composicao={{
          titulo: "NRR no ano", subtitulo: "Só os contratos que já existiam em 31/12",
          conteudo: () => <ComposicaoDoNrr de={de} movimento={m} />,
        }} />
      )}
    </div>
  );
}
