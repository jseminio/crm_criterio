/** Os grupos econômicos, e a fusão — o reagrupamento que Eduardo faz à mão.
 *
 * A carga formou os grupos pelo nome exato do cliente. A coluna de origem
 * mistura cliente e serviço, então o mesmo cliente aparece repartido. Esta
 * tela existe para juntar de volta, um par por vez, com o histórico intacto.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { GrupoResumo, Listas, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { usarDados } from "../usarDados";
import { DetalheDoGrupo } from "./DetalheDoGrupo";
import { SugestoesDeFusao } from "./SugestoesDeFusao";

function Fusao({
  principal,
  todos,
  aoFechar,
  aoFundir,
}: {
  principal: GrupoResumo;
  todos: GrupoResumo[];
  aoFechar: () => void;
  aoFundir: () => void;
}) {
  const [absorvidoId, definirAbsorvidoId] = useState("");
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const [confirmando, definirConfirmando] = useState(false);

  const absorvido = todos.find((g) => String(g.id) === absorvidoId);

  const fundir = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await api.fundirGrupos(principal.id, Number(absorvidoId));
      aoFundir();
      aoFechar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao fundir.");
      definirConfirmando(false);
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <PainelLateral
      titulo="Juntar grupos"
      subtitulo={`Tudo vai para ${principal.nome}`}
      aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>
            Cancelar
          </button>
          {/* Ação que mexe em muitos registros pede confirmação — regra 2. */}
          {confirmando ? (
            <button
              type="button"
              className="botao botao-primario"
              onClick={fundir}
              disabled={salvando}
            >
              {salvando ? "Juntando…" : "Confirmar, juntar agora"}
            </button>
          ) : (
            <button
              type="button"
              className="botao botao-primario"
              onClick={() => definirConfirmando(true)}
              disabled={!absorvidoId}
            >
              Juntar grupos
            </button>
          )}
        </>
      }
    >
      {erro && (
        <div className="estado estado-erro" role="alert">
          <p className="estado-texto">{erro}</p>
        </div>
      )}

      <div className="formulario">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="f-absorvido">
            Qual grupo é, na verdade, o mesmo cliente?
          </label>
          <select
            id="f-absorvido"
            className="selecao"
            value={absorvidoId}
            onChange={(e) => {
              definirAbsorvidoId(e.target.value);
              definirConfirmando(false);
            }}
          >
            <option value="">Escolha um grupo</option>
            {todos
              .filter((g) => g.id !== principal.id && g.fundido_em_id === null)
              .map((g) => (
                <option key={g.id} value={g.id}>
                  {g.nome} ({g.quantas_oportunidades} prop.)
                </option>
              ))}
          </select>
        </div>
      </div>

      {absorvido && (
        <div className="recado">
          <strong>{absorvido.nome}</strong> passa a ser parte de{" "}
          <strong>{principal.nome}</strong>. As {absorvido.quantas_oportunidades} oportunidades,
          empresas e contatos dele mudam de dono. <strong>Nada é apagado</strong>: ele continua no
          banco, marcado como fundido, apontando para cá. A data de entrada do conjunto passa a ser
          a mais antiga das duas.
        </div>
      )}
    </PainelLateral>
  );
}

export function Grupos({ listas }: { listas: Listas | null }) {
  const [busca, definirBusca] = useState("");
  const [aberto, definirAberto] = useState<GrupoResumo | null>(null);
  const [fundindo, definirFundindo] = useState<GrupoResumo | null>(null);

  const { dados, carregando, erro, recarregar } = usarDados<Pagina<GrupoResumo>>(
    () => api.grupos({ busca: busca || undefined }),
    [busca],
  );

  const comMaisDeUma = dados?.itens.filter((g) => g.quantas_oportunidades > 1).length ?? 0;

  return (
    <>
      <div className="filtros">
        <div className="campo">
          <label className="campo-rotulo" htmlFor="g-busca">
            Buscar
          </label>
          <input
            id="g-busca"
            className="entrada entrada-busca"
            placeholder="Nome do grupo"
            value={busca}
            onChange={(e) => definirBusca(e.target.value)}
          />
        </div>
      </div>

      {!carregando && !erro && (dados?.total ?? 0) > 0 && (
        <div className="recado">
          A carga formou os grupos pelo <strong>nome exato</strong> do cliente, e a coluna de
          origem mistura cliente com serviço. Por isso o mesmo cliente pode aparecer repartido em
          vários grupos. Junte-os aqui: <strong>{comMaisDeUma}</strong> grupos já têm mais de uma
          proposta e são o melhor lugar para começar.
        </div>
      )}

      <SugestoesDeFusao aoJuntar={recarregar} />

      {carregando && <Carregando rotulo="Carregando os grupos" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}

      {!carregando && !erro && dados?.total === 0 && busca !== "" && (
        <VazioPorFiltro aoLimpar={() => definirBusca("")} />
      )}
      {!carregando && !erro && dados?.total === 0 && busca === "" && (
        <VazioSemDados
          titulo="Nenhum grupo econômico"
          explicacao="A carga da planilha de 2026 cria um grupo por cliente."
        />
      )}

      {!carregando && !erro && (dados?.total ?? 0) > 0 && (
        <table className="tabela">
          <thead>
            <tr>
              <th scope="col">Grupo econômico</th>
              <th scope="col">Situação</th>
              <th scope="col">Origem</th>
              <th scope="col" className="tabela-numero">
                Propostas
              </th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {dados!.itens.map((grupo) => (
              <tr key={grupo.id}>
                <td>
                  {/* O nome é o caminho natural para o detalhe. */}
                  <button
                    type="button"
                    className="link-de-tabela"
                    onClick={() => definirAberto(grupo)}
                  >
                    {grupo.nome}
                  </button>
                </td>
                <td>
                  <Etiqueta texto={grupo.situacao} />
                </td>
                <td>
                  <Etiqueta texto={grupo.origem} tipo="neutra" />
                </td>
                <td className="tabela-numero">{grupo.quantas_oportunidades}</td>
                <td>
                  <button
                    type="button"
                    className="botao botao-secundario"
                    onClick={() => definirFundindo(grupo)}
                  >
                    Juntar outro aqui
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {aberto && (
        <DetalheDoGrupo
          grupo={aberto}
          listas={listas}
          aoFechar={() => definirAberto(null)}
        />
      )}

      {fundindo && dados && (
        <Fusao
          principal={fundindo}
          todos={dados.itens}
          aoFechar={() => definirFundindo(null)}
          aoFundir={recarregar}
        />
      )}
    </>
  );
}
