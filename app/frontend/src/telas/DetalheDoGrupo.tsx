/** O detalhe de um grupo econômico: as propostas dele e o que já foi juntado nele.
 *
 * Existe para o reagrupamento ser auditável. Juntar dois grupos move tudo para
 * um deles e marca o outro como fundido — sem esta tela, o resultado da junção
 * só se veria de longe, na contagem da lista.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { GrupoResumo, Listas, OportunidadeResumo, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";

export function DetalheDoGrupo({
  grupo,
  listas,
  aoFechar,
}: {
  grupo: GrupoResumo;
  listas: Listas | null;
  aoFechar: () => void;
}) {
  const [aberta, definirAberta] = useState<number | null>(null);

  const propostas = usarDados<Pagina<OportunidadeResumo>>(
    () => api.oportunidades({ grupo_id: grupo.id }),
    [grupo.id],
  );

  // Os grupos fundidos continuam no banco, apontando para quem os absorveu.
  const todos = usarDados<Pagina<GrupoResumo>>(
    () => api.grupos({ incluir_fundidos: true, limite: 500 }),
    [grupo.id],
  );
  const juntados = todos.dados?.itens.filter((g) => g.fundido_em_id === grupo.id) ?? [];

  return (
    <>
      <PainelLateral
        titulo={grupo.nome}
        subtitulo="Grupo econômico"
        aoFechar={aoFechar}
      >
        <div className="secao-do-painel">
          <div className="cartao-linha">
            <Etiqueta texto={grupo.situacao} />
            <Etiqueta texto={grupo.origem} tipo="neutra" />
            {grupo.data_entrada && (
              <span className="campo-ajuda">Cliente desde {data(grupo.data_entrada)}</span>
            )}
          </div>
        </div>

        <div className="secao-do-painel">
          <h3>Propostas</h3>
          {propostas.carregando && <Carregando rotulo="Carregando as propostas" />}
          {propostas.erro && (
            <Erro mensagem={propostas.erro} aoTentarDeNovo={propostas.recarregar} />
          )}
          {!propostas.carregando && !propostas.erro && propostas.dados?.total === 0 && (
            <VazioSemDados
              titulo="Nenhuma proposta neste grupo"
              explicacao="Um grupo sem proposta costuma ser o que sobrou de uma junção."
            />
          )}
          {!propostas.carregando && (propostas.dados?.total ?? 0) > 0 && (
            <table className="mini-tabela">
              <thead>
                <tr>
                  <th scope="col">Proposta</th>
                  <th scope="col">Situação</th>
                  <th scope="col" className="tabela-numero">
                    Anual
                  </th>
                </tr>
              </thead>
              <tbody>
                {propostas.dados!.itens.map((o) => (
                  <tr key={o.id}>
                    <td>
                      <button
                        type="button"
                        className="link-de-tabela"
                        onClick={() => definirAberta(o.id)}
                      >
                        {o.nome}
                      </button>
                      <div className="campo-ajuda">
                        {[o.servico, o.tipo_servico].filter(Boolean).join(" · ") || "—"}
                        {o.data_colocacao && ` · ${data(o.data_colocacao)}`}
                      </div>
                    </td>
                    <td>
                      <Etiqueta texto={o.situacao} />
                    </td>
                    <td className="tabela-numero">{dinheiro(o.preco_anual)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {juntados.length > 0 && (
          <div className="secao-do-painel">
            <h3>Juntados neste grupo</h3>
            <p className="campo-ajuda" style={{ marginTop: 0 }}>
              Continuam no banco, marcados como fundidos. Nada foi apagado.
            </p>
            <table className="mini-tabela">
              <tbody>
                {juntados.map((g) => (
                  <tr key={g.id}>
                    <td>{g.nome}</td>
                    <td>
                      <Etiqueta texto={g.situacao} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PainelLateral>

      {aberta !== null && (
        <DetalheDaOportunidade
          id={aberta}
          listas={listas}
          aoFechar={() => definirAberta(null)}
          aoSalvar={propostas.recarregar}
        />
      )}
    </>
  );
}
