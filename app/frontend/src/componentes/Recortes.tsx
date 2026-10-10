/** Recortes do funil por serviço, canal e captador — E5.
 *
 * Segue os mesmos filtros da faixa de números. Ticket e mediana são só dos
 * contratos **recorrentes aceitos** (preço mensal > 0); a coluna "Recorrentes"
 * diz quantos são, porque com poucos a média não diz nada.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { DimensaoDeRecorte, LinhaDeRecorte } from "../api/tipos";
import { ThOrdenavel, ordenar, usarOrdenacao } from "./Ordenacao";
import { Carregando, Erro } from "./estados";
import { paraConsulta, type EstadoDosFiltros } from "./Filtros";
import { dinheiro, percentual } from "../formato";
import { usarDados } from "../usarDados";
import { BotaoDeComposicao } from "./Indicador";
import { ComposicaoDoFunil } from "./ComposicaoDoFunil";

const DIMENSOES: { valor: DimensaoDeRecorte; rotulo: string }[] = [
  { valor: "servico", rotulo: "Serviço" },
  { valor: "tipo_canal", rotulo: "Canal" },
  { valor: "captador", rotulo: "Captador" },
];

export function Recortes({ filtros }: { filtros: EstadoDosFiltros }) {
  const [dimensao, definirDimensao] = useState<DimensaoDeRecorte>("servico");
  const { ordenacao, alternar: alternarOrdenacao } = usarOrdenacao();
  const { dados, carregando, erro, recarregar } = usarDados<LinhaDeRecorte[]>(
    () => api.recortes(dimensao, paraConsulta(filtros)),
    [dimensao, filtros.busca, filtros.captador, filtros.tipo_canal, filtros.temperatura,
      filtros.servico, filtros.dataTipo, filtros.periodo, filtros.dataDe, filtros.dataAte],
  );

  return (
    <section className="numero recortes" aria-label="Recortes do funil">
      <div className="recortes-topo">
        <h3 className="numero-rotulo">Recortes do funil</h3>
        <label className="campo">
          <span className="campo-rotulo">Cortar por</span>
          <select className="selecao" value={dimensao} onChange={(e) => definirDimensao(e.target.value as DimensaoDeRecorte)}>
            {DIMENSOES.map((d) => (
              <option key={d.valor} value={d.valor}>{d.rotulo}</option>
            ))}
          </select>
        </label>
      </div>
      {carregando && !dados && <Carregando rotulo="Calculando os recortes" />}
      {erro && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {dados && (
        <table className="tabela">
          <thead>
            <tr>
              <ThOrdenavel coluna="chave" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>
                {DIMENSOES.find((d) => d.valor === dimensao)!.rotulo}
              </ThOrdenavel>
              <ThOrdenavel coluna="propostas" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Propostas</ThOrdenavel>
              <ThOrdenavel coluna="aceitas" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Aceitas</ThOrdenavel>
              <ThOrdenavel coluna="conversao" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Conversão</ThOrdenavel>
              <ThOrdenavel coluna="recorrentes" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Recorrentes</ThOrdenavel>
              <ThOrdenavel coluna="mensal" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Mensal aceito</ThOrdenavel>
              <ThOrdenavel coluna="ticket" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Ticket</ThOrdenavel>
              <ThOrdenavel coluna="mediana" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Mediana</ThOrdenavel>
            </tr>
          </thead>
          <tbody>
            {ordenar(dados, ordenacao, {
              chave: (l) => l.chave,
              propostas: (l) => l.propostas,
              aceitas: (l) => l.aceitas,
              conversao: (l) => (l.conversao ? Number(l.conversao) : null),
              recorrentes: (l) => l.recorrentes,
              mensal: (l) => (l.recorrentes ? Number(l.valor_mensal) : null),
              ticket: (l) => (l.ticket_medio ? Number(l.ticket_medio) : null),
              mediana: (l) => (l.mediana ? Number(l.mediana) : null),
            }).map((l) => (
              <tr key={l.chave}>
                <td>
                  {l.chave}
                  <BotaoDeComposicao rotulo="ver" composicao={{
                    titulo: `${DIMENSOES.find((d) => d.valor === dimensao)!.rotulo}: ${l.chave}`,
                    subtitulo: "Propostas desta linha, com os filtros da tela", quantos: l.propostas,
                    conteudo: () => <ComposicaoDoFunil indicador="propostas" filtros={paraConsulta(filtros)} recorte={{ dimensao, chave: l.chave }} />,
                  }} />
                </td>
                <td className="tabela-numero">{l.propostas}</td>
                <td className="tabela-numero">{l.aceitas}</td>
                <td className="tabela-numero">{l.conversao ? percentual(l.conversao) : "—"}</td>
                <td className="tabela-numero">{l.recorrentes}</td>
                <td className="tabela-numero">{l.recorrentes ? dinheiro(l.valor_mensal) : "—"}</td>
                <td className="tabela-numero">{l.ticket_medio ? dinheiro(l.ticket_medio) : "—"}</td>
                <td className="tabela-numero">{l.mediana ? dinheiro(l.mediana) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="numero-nota">
        Ticket e mediana são só dos contratos aceitos com preço mensal; consultoria de valor único
        não entra. Com poucos recorrentes, a média engana.
      </p>
    </section>
  );
}
