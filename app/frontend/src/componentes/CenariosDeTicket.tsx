/** Cenários de ticket para projeção — conservador, base e otimista.
 *
 * **Hipóteses de trabalho, não meta.** O ticket comum sai dos contratos recorrentes
 * aceitos; o **atípico** (acima de 3 × a mediana) vai à parte, com a frequência
 * que Eduardo escolhe. Os valores editáveis moram só nesta tela: nada é gravado.
 * Não considera cancelamento nem o tempo até o contrato começar a faturar.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { CenariosDeTicket as Cenarios } from "../api/tipos";
import { Carregando, Erro } from "./estados";
import { paraConsulta, type EstadoDosFiltros } from "./Filtros";
import { dinheiro } from "../formato";
import { usarDados } from "../usarDados";

const num = (v: string | null) => (v === null ? 0 : Number(v));

export function CenariosDeTicket({ filtros }: { filtros: EstadoDosFiltros }) {
  const [clientes, definirClientes] = useState(20);
  const [frequencia, definirFrequencia] = useState(20);
  const { dados, carregando, erro, recarregar } = usarDados<Cenarios | null>(
    () => api.cenariosDeTicket(paraConsulta(filtros)),
    [filtros.busca, filtros.captador, filtros.tipo_canal, filtros.temperatura, filtros.servico,
      filtros.dataTipo, filtros.periodo, filtros.dataDe, filtros.dataAte],
  );

  if (carregando && dados === null) return <Carregando rotulo="Calculando os cenários" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) {
    return (
      <section className="numero numero-pendente" aria-label="Cenários de ticket">
        <h3 className="numero-rotulo">Cenários de ticket</h3>
        <p className="numero-estado">
          Não calculável — precisa de pelo menos 4 contratos recorrentes aceitos neste recorte.
        </p>
      </section>
    );
  }

  const atipicos = dados.atipicos > 0 && frequencia > 0 ? clientes / frequencia : 0;
  const comuns = clientes - atipicos;
  const cenarios = [
    { nome: "Conservador", comum: num(dados.conservador), atipico: num(dados.atipico_minimo) },
    { nome: "Base", comum: num(dados.base), atipico: num(dados.atipico_medio) },
    { nome: "Otimista", comum: num(dados.otimista), atipico: num(dados.atipico_maximo) },
  ].map((c) => {
    const total = comuns * c.comum + atipicos * c.atipico;
    return { ...c, total, porCliente: clientes > 0 ? total / clientes : 0 };
  });

  return (
    <section className="numero cenarios" aria-label="Cenários de ticket">
      <h3 className="numero-rotulo">Cenários de ticket (hipóteses de trabalho, não meta)</h3>
      <div className="cenarios-entradas">
        <label className="campo">
          <span className="campo-rotulo">Clientes novos</span>
          <input className="entrada" type="number" min={1} value={clientes} onChange={(e) => definirClientes(Math.max(1, Number(e.target.value) || 1))} />
        </label>
        <label className="campo">
          <span className="campo-rotulo">1 atípico a cada … clientes</span>
          <input className="entrada" type="number" min={1} value={frequencia} onChange={(e) => definirFrequencia(Math.max(1, Number(e.target.value) || 1))} />
        </label>
      </div>
      <table className="tabela">
        <thead>
          <tr>
            <th scope="col">Cenário</th>
            <th scope="col" className="tabela-numero">Ticket comum</th>
            <th scope="col" className="tabela-numero">Atípico</th>
            <th scope="col" className="tabela-numero">Total por mês</th>
            <th scope="col" className="tabela-numero">Total por ano</th>
            <th scope="col" className="tabela-numero">Ticket efetivo</th>
          </tr>
        </thead>
        <tbody>
          {cenarios.map((c) => (
            <tr key={c.nome}>
              <td>{c.nome}</td>
              <td className="tabela-numero">{dinheiro(c.comum)}</td>
              <td className="tabela-numero">{atipicos > 0 ? dinheiro(c.atipico) : "—"}</td>
              <td className="tabela-numero"><strong>{dinheiro(c.total)}</strong></td>
              <td className="tabela-numero">{dinheiro(c.total * 12)}</td>
              <td className="tabela-numero">{dinheiro(c.porCliente)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="numero-nota">
        Base: {dados.contratos} contratos recorrentes aceitos. Atípico = acima de{" "}
        {dinheiro(dados.limite_do_atipico)} (3 × a mediana): {dados.atipicos} contrato
        {dados.atipicos === 1 ? "" : "s"}
        {dados.atipicos > 0 && ` (${dinheiro(dados.atipico_minimo)} a ${dinheiro(dados.atipico_maximo)})`}.
        Conservador = mediana; base = média sem atípicos; otimista = terceiro quartil sem atípicos.
        Não considera cancelamento nem o tempo até faturar. Com poucos contratos, o número mexe muito.
      </p>
    </section>
  );
}
