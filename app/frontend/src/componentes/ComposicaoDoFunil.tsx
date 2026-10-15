/** A lista que compõe um número do funil (10/10/2026): as oportunidades, com os mesmos filtros da tela e
 * da mesma conta do card. Quem entra na conta vem primeiro; o resumo no topo repete o número do card. */

import { api, type FiltrosDoFunil } from "../api/cliente";
import type { DimensaoDeRecorte, IndicadorDoFunil, ItemDaComposicao } from "../api/tipos";
import { data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";
import { TabelaDeComposicao, type ColunaDaComposicao } from "./TabelaDeComposicao";

const DIRECIONADOR: Record<string, string> = {
  documentos_fiscais_mes: "documentos fiscais", lancamentos_contabeis_mes: "lançamentos", pagamentos_mes: "pagamentos",
  contas_bancarias: "contas bancárias", conciliacoes_cartao_mes: "conciliações de cartão", empregados_clt: "empregados CLT",
  admissoes_desligamentos_mes: "admissões e desligamentos", cnpjs_no_escopo: "CNPJs no escopo",
  tomadores_de_servico: "tomadores de serviço",
};

type Coluna = ColunaDaComposicao<ItemDaComposicao>;
type I = ItemDaComposicao;

const num = (v: string | null) => (v === null ? null : Number(v));
const OPORTUNIDADE: Coluna = { titulo: "Oportunidade", valor: (i) => i.nome };
const CLIENTE: Coluna = { titulo: "Cliente", valor: (i) => i.grupo };
const SERVICO: Coluna = { titulo: "Serviço", valor: (i) => i.servico };
const SITUACAO: Coluna = { titulo: "Situação", valor: (i) => i.situacao };
const MENSAL: Coluna = { titulo: "Mensal", numerico: true, valor: (i) => num(i.valor), mostrar: (i) => (i.valor !== null ? dinheiro(i.valor) : "—") };
const ANUAL: Coluna = { titulo: "Anual", numerico: true, valor: (i) => num(i.anual), mostrar: (i) => (i.anual !== null ? dinheiro(i.anual) : "—") };
const DATA = (titulo: string, f: (i: I) => string | null | undefined): Coluna => ({ titulo, valor: f, mostrar: (i) => data(f(i)) });
const DIAS: Coluna = { titulo: "Dias", numerico: true, valor: (i) => num(i.valor), mostrar: (i) => (i.valor !== null ? String(Number(i.valor)) : "—") };

const COLUNAS: Record<IndicadorDoFunil, Coluna[]> = {
  em_aberto: [OPORTUNIDADE, CLIENTE, SERVICO, SITUACAO, MENSAL, ANUAL],
  aceitas: [OPORTUNIDADE, CLIENTE, SERVICO, DATA("Aceite", (i) => i.data_aceite), MENSAL, ANUAL],
  propostas: [OPORTUNIDADE, CLIENTE, SERVICO, SITUACAO, MENSAL, ANUAL],
  taxa_de_conversao: [OPORTUNIDADE, CLIENTE, SERVICO, { titulo: "Desfecho", valor: (i) => i.parte }, MENSAL],
  ticket_recorrente: [OPORTUNIDADE, CLIENTE, SERVICO,
    { titulo: "MRR (× 13 ÷ 12)", numerico: true, valor: (i) => num(i.valor), mostrar: (i) => dinheiro(i.valor) }],
  ciclo_medio: [OPORTUNIDADE, CLIENTE, DATA("Originação", (i) => i.data_colocacao), DATA("Envio", (i) => i.data_envio_proposta),
    DATA("Aceite", (i) => i.data_aceite),
    { ...DIAS, mostrar: (i) => (i.valor !== null ? String(Number(i.valor)) : i.parte) }],
  cobertura_proxima_acao: [OPORTUNIDADE, CLIENTE, SITUACAO,
    { titulo: "Próxima ação", valor: (i) => i.proxima_acao || null, mostrar: (i) => i.proxima_acao || "— sem próxima ação" }],
  cobertura_volumetria: [OPORTUNIDADE, CLIENTE, SITUACAO, {
    titulo: "Volumetria", valor: (i) => (i.falta.length === 0 ? "completa" : `falta: ${i.falta.map((f) => DIRECIONADOR[f] ?? f).join(", ")}`),
  }],
  dependencia_de_canal: [OPORTUNIDADE, CLIENTE, { titulo: "Canal", valor: (i) => i.parte }, { titulo: "Captador", valor: (i) => i.captador }],
  motivos_de_perda: [OPORTUNIDADE, CLIENTE, SERVICO, { titulo: "Motivo da perda", valor: (i) => i.parte }, MENSAL],
  prazo_ate_o_envio: [OPORTUNIDADE, CLIENTE, DATA("Originação", (i) => i.data_colocacao),
    { titulo: "Envio", valor: (i) => i.data_envio_proposta ?? i.parte, mostrar: (i) => (i.data_envio_proposta ? data(i.data_envio_proposta) : i.parte) },
    DIAS],
};

/** O que o resumo do topo diz, para conferir com o card. */
function resumo(indicador: IndicadorDoFunil, itens: ItemDaComposicao[]): string {
  const n = itens.length;
  const entram = itens.filter((i) => i.entra);
  const soma = (l: ItemDaComposicao[], f: (i: ItemDaComposicao) => string | null) => l.reduce((t, i) => t + Number(f(i) ?? 0), 0);
  const pct = (a: number, b: number) => (b ? `${((a / b) * 100).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%` : "—");
  switch (indicador) {
    case "em_aberto":
    case "aceitas":
    case "propostas":
      return `${n} proposta${n === 1 ? "" : "s"} · ${dinheiro(soma(itens, (i) => i.valor))} por mês · ${dinheiro(soma(itens, (i) => i.anual))} ao ano`;
    case "ticket_recorrente":
      return `${n} contrato${n === 1 ? "" : "s"} recorrente${n === 1 ? "" : "s"} · ${dinheiro(soma(itens, (i) => i.valor))} de MRR · ticket ${n ? dinheiro(soma(itens, (i) => i.valor) / n) : "—"}`;
    case "ciclo_medio":
      return `${entram.length} aceita${entram.length === 1 ? "" : "s"} na média · ${entram.length ? (soma(entram, (i) => i.valor) / entram.length).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) : "—"} dias · ${n - entram.length} fora por falta de data`;
    case "taxa_de_conversao":
      return `${entram.length} aceita${entram.length === 1 ? "" : "s"} de ${n} decidida${n === 1 ? "" : "s"} · ${pct(entram.length, n)}`;
    case "cobertura_proxima_acao":
      return `${entram.length} de ${n} em aberto com próxima ação · ${pct(entram.length, n)}`;
    case "cobertura_volumetria":
      return `${entram.length} de ${n} com a ficha de volumetria completa · ${pct(entram.length, n)}`;
    case "dependencia_de_canal":
      return `${entram.length} de ${n} da rede dos sócios · ${pct(entram.length, n)}`;
    case "prazo_ate_o_envio":
      return `${entram.length} proposta${entram.length === 1 ? "" : "s"} na média · ${entram.length ? (soma(entram, (i) => i.valor) / entram.length).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) : "—"} dias · ${n - entram.length} sem data de envio`;
    case "motivos_de_perda":
      return `${n} perdida${n === 1 ? "" : "s"} · ${n - entram.length} sem motivo informado`;
  }
}

export function ComposicaoDoFunil({ indicador, filtros, recorte }: {
  indicador: IndicadorDoFunil;
  filtros: FiltrosDoFunil;
  recorte?: { dimensao: DimensaoDeRecorte; chave: string };
}) {
  const { dados, carregando, erro, recarregar } = usarDados(
    () => api.composicaoDoFunil(indicador, filtros, recorte),
    [indicador, JSON.stringify(filtros), recorte?.dimensao, recorte?.chave],
  );
  if (carregando && !dados) return <Carregando rotulo="Buscando as oportunidades" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const itens = [...dados.itens].sort((a, b) => Number(b.entra) - Number(a.entra) || Number(b.valor ?? 0) - Number(a.valor ?? 0));
  const colunas = COLUNAS[indicador];
  if (itens.length === 0) return <p className="numero-estado">Nenhuma oportunidade nesta conta com os filtros atuais.</p>;
  return (
    <>
      <p className="composicao-linha-resumo"><strong>{resumo(indicador, itens)}</strong></p>
      <p className="numero-nota">Com os mesmos filtros da tela.</p>
      <TabelaDeComposicao rotulo="Composição do indicador" linhas={itens} colunas={colunas} chave={(i) => i.id}
        classeDaLinha={(i) => (i.entra ? undefined : "composicao-fora")} />
    </>
  );
}
