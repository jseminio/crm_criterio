/** Classificação da carteira (Etapa 3): classe, Score, alerta e eixo de ação por grupo, e o ISC.
 *
 * Somente leitura. Os números vêm do snapshot mais recente carregado da planilha de saúde da
 * carteira e são recalculados no CRM. Estado nunca só por cor: classe, alerta e cobrança têm texto.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { ClassificacaoDaCarteira } from "../api/tipos";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";

const um = (v: string) => Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const dois = (v: string) => Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const ALERTA: Record<string, string> = { "⚠": "⚠ Risco de churn", "⚑": "⚑ Saída a organizar" };
const PRIORIDADE = ["Cobrança", "Reter já", "Reter / vigiar", "Saída organizada", "Sem urgência"];

const rank = (eixo: string) => {
  const i = PRIORIDADE.findIndex((p) => eixo.startsWith(p));
  return i === -1 ? PRIORIDADE.length : i;
};

export function Carteira() {
  const { dados, carregando, erro, recarregar } = usarDados<ClassificacaoDaCarteira>(() => api.classificacaoDaCarteira(), []);
  const [eixo, definirEixo] = useState("");

  if (carregando && !dados) return <Carregando rotulo="Carregando a classificação" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  if (dados.itens.length === 0)
    return (
      <VazioSemDados
        titulo="Nenhuma classificação carregada"
        explicacao="Carregue a planilha de saúde da carteira com scripts/importar_classificacao.py; o ensaio mostra o que será gravado."
      />
    );

  const eixos = Array.from(new Set(dados.itens.map((i) => i.eixo_de_acao))).sort((a, b) => rank(a) - rank(b));
  const itens = dados.itens
    .filter((i) => !eixo || i.eixo_de_acao === eixo)
    .sort((a, b) => rank(a.eixo_de_acao) - rank(b.eixo_de_acao) || Number(b.receita_mensal) - Number(a.receita_mensal));
  const { isc } = dados;

  return (
    <section className="carteira" aria-label="Classificação da carteira">
      {dados.avisos.map((a) => (
        <div key={a} className="recado" role="note">{a}</div>
      ))}

      {isc && (
        <div className="carteira-topo">
          <div className="numero">
            <h3 className="numero-rotulo">ISC — índice de saúde da carteira</h3>
            <p className="numero-valor">{dois(isc.valor)} <span className="numero-nota">/ 100</span></p>
            <p className="numero-detalhe">Zona {isc.zona} · {isc.grupos} grupos · {dinheiro(isc.receita_total)}/mês</p>
            <p className="numero-nota">Referência {data(dados.referencia)} · parâmetros {dados.versao_dos_parametros}</p>
          </div>
          <div className="carteira-componentes">
            <p><strong>Classe</strong><br />{dois(isc.componente_classe)}</p>
            <p><strong>Semáforo</strong><br />{dois(isc.componente_semaforo)}</p>
            <p><strong>Churn</strong><br />{dois(isc.componente_churn)}</p>
            <p><strong>Distribuição</strong><br />{Object.entries(dados.por_classe).map(([c, n]) => `${c}: ${n}`).join(" · ")}</p>
          </div>
        </div>
      )}

      <div className="carteira-filtro">
        <label className="campo">
          <span className="campo-rotulo">Eixo de ação</span>
          <select className="selecao" value={eixo} onChange={(e) => definirEixo(e.target.value)}>
            <option value="">Todos</option>
            {eixos.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
        </label>
      </div>

      {itens.length === 0 ? (
        <VazioPorFiltro aoLimpar={() => definirEixo("")} />
      ) : (
        <table className="tabela" aria-label="Grupos classificados">
          <thead>
            <tr>
              <th>Grupo</th>
              <th className="tabela-numero">Receita/mês</th>
              <th className="tabela-numero">Score</th>
              <th>Classe</th>
              <th>Alerta</th>
              <th className="tabela-numero">Churn</th>
              <th>Eixo de ação</th>
            </tr>
          </thead>
          <tbody>
            {itens.map((i) => (
              <tr key={i.grupo_id}>
                <td>
                  {i.grupo_nome}
                  {i.sem_contrato_ativo && <span className="numero-nota"> · sem contrato ativo hoje</span>}
                </td>
                <td className="tabela-numero">{dinheiro(i.receita_mensal)}</td>
                <td className="tabela-numero">{um(i.score)}</td>
                <td>{i.classe_efetiva}{i.em_cobranca ? " · $$$ cobrança" : ""}</td>
                <td>{i.alerta_de_churn ? ALERTA[i.alerta_de_churn] ?? i.alerta_de_churn : "—"}</td>
                <td className="tabela-numero">{i.churn ?? "—"}</td>
                <td>{i.eixo_de_acao}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
