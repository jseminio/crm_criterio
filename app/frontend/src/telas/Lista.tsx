/** O funil em lista, para quem precisa comparar e ordenar. */

import { useState } from "react";
import { api } from "../api/cliente";
import type { Listas, OportunidadeResumo, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import {
  FILTROS_VAZIOS,
  Filtros,
  paraConsulta,
  temFiltro,
  type EstadoDosFiltros,
} from "../componentes/Filtros";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { NovaOportunidade } from "../componentes/NovaOportunidade";
import { data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";

export function Lista({ listas }: { listas: Listas | null }) {
  const [filtros, definirFiltros] = useState<EstadoDosFiltros>(FILTROS_VAZIOS);
  const [situacao, definirSituacao] = useState("");
  const [aberta, definirAberta] = useState<number | null>(null);
  const [criando, definirCriando] = useState(false);

  const { dados, carregando, erro, recarregar } = usarDados<Pagina<OportunidadeResumo>>(
    () =>
      api.oportunidades({
        ...paraConsulta(filtros),
        situacao: situacao ? [situacao] : undefined,
      }),
    [
      filtros.busca,
      filtros.captador,
      filtros.tipo_canal,
      filtros.temperatura,
      filtros.dataTipo,
      filtros.periodo,
      filtros.dataDe,
      filtros.dataAte,
      situacao,
    ],
  );

  const filtrando = temFiltro(filtros) || situacao !== "";
  const limpar = () => {
    definirFiltros(FILTROS_VAZIOS);
    definirSituacao("");
  };

  return (
    <>
      <Filtros
        filtros={filtros}
        aoMudar={definirFiltros}
        listas={listas}
        acao={
          <>
            <div className="campo">
              <label className="campo-rotulo" htmlFor="filtro-situacao">
                Situação
              </label>
              <select
                id="filtro-situacao"
                className="selecao"
                value={situacao}
                onChange={(e) => definirSituacao(e.target.value)}
              >
                <option value="">Todas</option>
                {listas?.situacoes.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="button"
              className="botao botao-primario"
              onClick={() => definirCriando(true)}
            >
              Nova oportunidade
            </button>
          </>
        }
      />

      {carregando && <Carregando rotulo="Carregando as oportunidades" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}

      {!carregando && !erro && dados?.total === 0 && filtrando && (
        <VazioPorFiltro aoLimpar={limpar} />
      )}
      {!carregando && !erro && dados?.total === 0 && !filtrando && (
        <VazioSemDados
          titulo="Nenhuma oportunidade"
          explicacao="A base está vazia. A carga da planilha de 2026 preenche esta tela."
        />
      )}

      {!carregando && !erro && (dados?.total ?? 0) > 0 && (
        <>
          <p style={{ color: "var(--texto-medio)", marginTop: 0 }}>
            {dados!.total} oportunidade{dados!.total === 1 ? "" : "s"}
          </p>
          <table className="tabela">
            <thead>
              <tr>
                <th scope="col">Cliente</th>
                <th scope="col">Oportunidade</th>
                <th scope="col">Situação</th>
                <th scope="col">Temperatura</th>
                <th scope="col">Captador</th>
                <th scope="col">Originação</th>
                <th scope="col" className="tabela-numero">
                  Mensal
                </th>
                <th scope="col" className="tabela-numero">
                  Anual
                </th>
              </tr>
            </thead>
            <tbody>
              {dados!.itens.map((o) => (
                <tr
                  key={o.id}
                  className="tabela-clicavel"
                  onClick={() => definirAberta(o.id)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && definirAberta(o.id)}
                >
                  <td>{o.grupo_nome ?? "—"}</td>
                  <td>{o.nome}</td>
                  <td>
                    <Etiqueta texto={o.situacao} />
                  </td>
                  <td>
                    <Etiqueta texto={o.temperatura} tipo="temperatura" />
                  </td>
                  <td>{o.captador ?? "—"}</td>
                  <td>{data(o.data_colocacao)}</td>
                  <td className="tabela-numero">{dinheiro(o.preco_mensal)}</td>
                  <td className="tabela-numero">{dinheiro(o.preco_anual)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {aberta !== null && (
        <DetalheDaOportunidade
          id={aberta}
          listas={listas}
          aoFechar={() => definirAberta(null)}
          aoSalvar={recarregar}
        />
      )}

      {criando && (
        <NovaOportunidade
          listas={listas}
          aoFechar={() => definirCriando(false)}
          aoCriar={recarregar}
        />
      )}
    </>
  );
}
