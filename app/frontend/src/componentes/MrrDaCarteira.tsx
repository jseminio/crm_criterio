/** MRR atual da carteira inteira, contratado × recebido (pedido de Eduardo em 10/10/2026).
 *
 * É o KPI oficial de MRR: a carteira inteira, em bruto, parcela × 13 ÷ 12. **Não muda com os filtros
 * do funil.** O recebido vem da planilha importada em Gestão de contratos (só o Administrador) e se
 * compara com o esperado do mês: a parcela, sem o 13 ÷ 12 (em dezembro, a 13ª).
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { GrupoDaCarteira, MrrDaCarteira as Carteira, SituacaoDoRecebido } from "../api/tipos";
import { dataHora, dinheiro, dinheiroCurto } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";
import { Indicador } from "./Indicador";

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
  "novembro", "dezembro"];

export function mesCurto(competencia: string): string {
  const [ano, mes] = competencia.split("-");
  return `${MESES[Number(mes) - 1]}/${ano}`;
}

function mesLongo(competencia: string): string {
  return MESES_LONGOS[Number(competencia.split("-")[1]) - 1];
}

/** Os últimos 12 meses, do atual para trás, como "AAAA-MM". */
function ultimosMeses(hoje = new Date()): string[] {
  return Array.from({ length: 12 }, (_, i) => {
    const d = new Date(hoje.getFullYear(), hoje.getMonth() - i, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
}

const TOM_DA_SITUACAO: Record<SituacaoDoRecebido, string> = {
  "Em dia": "ganho", Parcial: "espera", "Em aberto": "perda", "Sem registro": "neutra",
};

function pct(parte: string | number, todo: string | number): string {
  const t = Number(todo);
  return t > 0 ? `${((Number(parte) / t) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%` : "—";
}

/** O card do funil. */
export function MrrDaCarteira() {
  const { dados, carregando, erro, recarregar } = usarDados<Carteira>(() => api.mrrDaCarteira(), []);
  if (carregando && !dados) return <Carregando rotulo="Somando a carteira" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const mes = mesCurto(dados.competencia);
  return (
    <Indicador
      rotulo="MRR atual da carteira"
      tom="marinho"
      className="ind-mrr"
      destaque={dinheiro(dados.mrr)}
      apoio={
        <>
          {dados.contratos} contratos · {dados.grupos} grupos · {pct(dados.mrr, dados.meta)} da meta
          <br />
          Recebido em {mes}:{" "}
          {dados.mes_importado ? `${dinheiroCurto(dados.recebido)} de ${dinheiroCurto(dados.esperado)}` : "sem registro"}
        </>
      }
      composicao={{
        titulo: "MRR atual da carteira",
        subtitulo: "Contratado e recebido por cliente",
        quantos: dados.itens.length,
        conteudo: () => <ComposicaoDaCarteira inicial={dados} />,
      }}
    >
      <ExplicacaoDoMrr dados={dados} />
    </Indicador>
  );
}

export function ExplicacaoDoMrr({ dados }: { dados: Carteira }) {
  return (
    <>
      <p><strong>Contratado:</strong> {dinheiro(dados.mrr)} por mês. Soma da parcela mensal dos {dados.contratos} contratos
        ativos, em bruto, × 13 ÷ 12 (13 parcelas no ano). Carteira inteira: não muda com os filtros do funil.</p>
      <p><strong>Recebido:</strong> o que entrou no caixa na competência, pela planilha importada em Gestão de contratos.
        Compara com o esperado do mês: a parcela, sem o 13 ÷ 12 (em dezembro conta a 13ª).</p>
      <p>Meta {dinheiro(dados.meta)} · alerta {dinheiro(dados.alerta)} (Configurações › Metas).</p>
      {Number(dados.suspenso) > 0 && <p>{dinheiro(dados.suspenso)} em contratos suspensos ficam à parte.</p>}
      {dados.sem_preco_mensal > 0 && <p>{dados.sem_preco_mensal} contrato(s) sem preço mensal ficaram fora da soma.</p>}
    </>
  );
}

/** A lista do painel: um cliente por linha, do maior MRR para o menor; clicar abre os contratos. */
export function ComposicaoDaCarteira({ inicial }: { inicial?: Carteira }) {
  const meses = ultimosMeses();
  const [competencia, definirCompetencia] = useState(inicial?.competencia ?? meses[0]);
  const [abertos, definirAbertos] = useState<Set<number>>(new Set());
  const { dados, carregando, erro, recarregar } = usarDados<Carteira>(
    () => (inicial && competencia === inicial.competencia ? Promise.resolve(inicial) : api.mrrDaCarteira(competencia)),
    [competencia],
  );

  const alternar = (id: number) =>
    definirAbertos((atual) => {
      const novo = new Set(atual);
      if (novo.has(id)) novo.delete(id);
      else novo.add(id);
      return novo;
    });

  return (
    <>
      <label className="campo">
        <span className="campo-rotulo">Competência do recebido</span>
        <select className="selecao" value={competencia} onChange={(e) => definirCompetencia(e.target.value)}>
          {meses.map((m) => <option key={m} value={m}>{mesCurto(m)}</option>)}
        </select>
      </label>
      {carregando && !dados && <Carregando rotulo="Somando a carteira" />}
      {erro && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {dados && (
        <>
          <div className="composicao-resumo">
            <div><span className="numero-rotulo">Contratado (MRR)</span><strong>{dinheiro(dados.mrr)}</strong>
              <span className="numero-nota">{dados.contratos} contratos · {dados.grupos} grupos</span></div>
            <div><span className="numero-rotulo">Esperado em {mesLongo(dados.competencia)}</span><strong>{dinheiro(dados.esperado)}</strong>
              <span className="numero-nota">parcela, sem o 13 ÷ 12</span></div>
            <div><span className="numero-rotulo">Recebido em {mesLongo(dados.competencia)}</span>
              <strong>{dados.mes_importado ? dinheiro(dados.recebido) : "Sem registro"}</strong>
              <span className="numero-nota">
                {dados.mes_importado
                  ? `${pct(dados.recebido, dados.esperado)} do esperado · ${dados.grupos_registrados} clientes na planilha`
                  : "a planilha do mês ainda não foi importada"}
              </span></div>
          </div>
          {dados.mes_importado && dados.importado_em && (
            <p className="numero-nota">Planilha importada em {dataHora(dados.importado_em)}{dados.importado_por ? ` por ${dados.importado_por}` : ""}.</p>
          )}
          {Number(dados.recebido_fora) > 0 && (
            <p className="numero-nota">
              {dinheiro(dados.recebido_fora)} recebidos de clientes sem parcela esperada no mês (pontual ou contrato encerrado)
              ficam fora da comparação.
            </p>
          )}
          <table className="tabela" aria-label="Composição do MRR da carteira">
            <thead>
              <tr>
                <th>Cliente</th>
                <th className="tabela-numero">Contratos</th>
                <th className="tabela-numero">MRR contratado</th>
                <th className="tabela-numero">Esperado</th>
                <th className="tabela-numero">Recebido</th>
                <th>Situação</th>
              </tr>
            </thead>
            <tbody>
              {dados.itens.map((g) => <LinhaDoGrupo key={g.grupo_id} g={g} aberto={abertos.has(g.grupo_id)} aoAlternar={alternar} importado={dados.mes_importado} />)}
              <tr className="composicao-total">
                <td>Total</td>
                <td className="tabela-numero">{dados.contratos}</td>
                <td className="tabela-numero">{dinheiro(dados.mrr)}</td>
                <td className="tabela-numero">{dinheiro(dados.esperado)}</td>
                <td className="tabela-numero">{dados.mes_importado ? dinheiro(dados.recebido) : "—"}</td>
                <td />
              </tr>
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

const PARTE: Record<string, string> = {
  somado: "no MRR", suspenso: "suspenso, à parte", sem_preco: "sem preço mensal, fora da soma",
  encerrado: "encerrado depois do mês",
};

function LinhaDoGrupo({ g, aberto, aoAlternar, importado }: {
  g: GrupoDaCarteira; aberto: boolean; aoAlternar: (id: number) => void; importado: boolean;
}) {
  return (
    <>
      <tr>
        <td>
          <button type="button" className="link-de-tabela" aria-expanded={aberto} onClick={() => aoAlternar(g.grupo_id)}>
            {aberto ? "▾" : "▸"} {g.grupo}
          </button>
        </td>
        <td className="tabela-numero">{g.contratos}</td>
        <td className="tabela-numero">{dinheiro(g.mrr)}</td>
        <td className="tabela-numero">{Number(g.esperado) > 0 ? dinheiro(g.esperado) : "—"}</td>
        <td className="tabela-numero">{importado || Number(g.recebido) > 0 ? dinheiro(g.recebido) : "—"}</td>
        <td>
          {g.situacao
            ? <span className={`etiqueta etiqueta-${TOM_DA_SITUACAO[g.situacao]}`}>{g.situacao}</span>
            : <span className="numero-nota">sem parcela no mês</span>}
        </td>
      </tr>
      {aberto && g.itens.map((c) => (
        <tr key={c.id} className="composicao-sub">
          <td>{c.escopo ?? "Contrato"} {c.empresa ? `· ${c.empresa}` : ""} <span className="numero-nota">({PARTE[c.parte]})</span></td>
          <td />
          <td className="tabela-numero">{c.mrr !== null ? dinheiro(c.mrr) : "—"}</td>
          <td className="tabela-numero">{Number(c.esperado) > 0 ? dinheiro(c.esperado) : "—"}</td>
          <td />
          <td />
        </tr>
      ))}
    </>
  );
}
