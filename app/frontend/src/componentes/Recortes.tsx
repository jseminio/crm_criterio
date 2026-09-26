/** Recortes do funil por serviço, canal e captador — E5.
 *
 * Segue os mesmos filtros da faixa de números. Ticket e mediana são só dos
 * contratos **recorrentes aceitos** (preço mensal > 0); a coluna "Recorrentes"
 * diz quantos são, porque com poucos a média não diz nada.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { DimensaoDeRecorte, LinhaDeRecorte } from "../api/tipos";
import { Carregando, Erro } from "./estados";
import { paraConsulta, type EstadoDosFiltros } from "./Filtros";
import { dinheiro, percentual } from "../formato";
import { usarDados } from "../usarDados";

const DIMENSOES: { valor: DimensaoDeRecorte; rotulo: string }[] = [
  { valor: "servico", rotulo: "Serviço" },
  { valor: "tipo_canal", rotulo: "Canal" },
  { valor: "captador", rotulo: "Captador" },
];

export function Recortes({ filtros }: { filtros: EstadoDosFiltros }) {
  const [dimensao, definirDimensao] = useState<DimensaoDeRecorte>("servico");
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
              <th scope="col">{DIMENSOES.find((d) => d.valor === dimensao)!.rotulo}</th>
              <th scope="col" className="tabela-numero">Propostas</th>
              <th scope="col" className="tabela-numero">Aceitas</th>
              <th scope="col" className="tabela-numero">Conversão</th>
              <th scope="col" className="tabela-numero">Recorrentes</th>
              <th scope="col" className="tabela-numero">Mensal aceito</th>
              <th scope="col" className="tabela-numero">Ticket</th>
              <th scope="col" className="tabela-numero">Mediana</th>
            </tr>
          </thead>
          <tbody>
            {dados.map((l) => (
              <tr key={l.chave}>
                <td>{l.chave}</td>
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
