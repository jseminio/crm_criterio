/** O funil em kanban — uma coluna por situação, todas sempre visíveis. */

import { useState } from "react";
import { api } from "../api/cliente";
import type { ColunaDoFunil, Listas, OportunidadeResumo } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import {
  FILTROS_VAZIOS,
  Filtros,
  paraConsulta,
  temFiltro,
  type EstadoDosFiltros,
} from "../componentes/Filtros";
import { Numeros } from "../componentes/Numeros";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { dinheiroCurto, prazo } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";

function Cartao({
  oportunidade,
  aoAbrir,
}: {
  oportunidade: OportunidadeResumo;
  aoAbrir: () => void;
}) {
  const quando = prazo(oportunidade.proxima_acao_em);
  return (
    <button type="button" className="cartao" onClick={aoAbrir}>
      <span className="cartao-grupo">{oportunidade.grupo_nome ?? oportunidade.nome}</span>
      {oportunidade.grupo_nome && oportunidade.nome !== oportunidade.grupo_nome && (
        <span className="cartao-nome">{oportunidade.nome}</span>
      )}
      <span className="cartao-valor">
        {oportunidade.preco_mensal
          ? `${dinheiroCurto(oportunidade.preco_mensal)}/mês`
          : dinheiroCurto(oportunidade.preco_anual)}
      </span>
      <span className="cartao-linha">
        <Etiqueta texto={oportunidade.temperatura} tipo="temperatura" />
        {oportunidade.captador && <Etiqueta texto={oportunidade.captador} tipo="neutra" />}
      </span>
      {oportunidade.proxima_acao && (
        <span className={`cartao-prazo ${quando?.atrasado ? "cartao-prazo-atrasado" : ""}`}>
          {oportunidade.proxima_acao}
          {quando && ` · ${quando.texto}`}
        </span>
      )}
    </button>
  );
}

export function Funil({ listas }: { listas: Listas | null }) {
  const [filtros, definirFiltros] = useState<EstadoDosFiltros>(FILTROS_VAZIOS);
  const [aberta, definirAberta] = useState<number | null>(null);

  const { dados, carregando, erro, recarregar } = usarDados<ColunaDoFunil[]>(
    () => api.funil(paraConsulta(filtros)),
    [filtros.busca, filtros.captador, filtros.tipo_canal, filtros.temperatura],
  );

  const total = dados?.reduce((soma, coluna) => soma + coluna.quantas, 0) ?? 0;

  return (
    <>
      <Numeros filtros={filtros} />
      <Filtros filtros={filtros} aoMudar={definirFiltros} listas={listas} />

      {carregando && <Carregando rotulo="Carregando o funil" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}

      {!carregando && !erro && total === 0 && temFiltro(filtros) && (
        <VazioPorFiltro aoLimpar={() => definirFiltros(FILTROS_VAZIOS)} />
      )}

      {!carregando && !erro && total === 0 && !temFiltro(filtros) && (
        <VazioSemDados
          titulo="O funil está vazio"
          explicacao="Nenhuma oportunidade foi carregada ainda. A carga da planilha de 2026 preenche esta tela."
        />
      )}

      {!carregando && !erro && total > 0 && (
        <div className="kanban">
          {dados?.map((coluna) => (
            <section className="coluna" key={coluna.situacao}>
              <header className="coluna-topo">
                <h2 className="coluna-nome">
                  <span>{coluna.situacao}</span>
                  <span className="coluna-quantas">{coluna.quantas}</span>
                </h2>
                <p className="coluna-valor">
                  {dinheiroCurto(coluna.valor_anual)} ao ano
                </p>
              </header>
              <div className="coluna-cartoes">
                {coluna.oportunidades.map((o) => (
                  <Cartao key={o.id} oportunidade={o} aoAbrir={() => definirAberta(o.id)} />
                ))}
                {coluna.quantas === 0 && (
                  <p className="coluna-vazia">Nenhuma oportunidade nesta etapa.</p>
                )}
              </div>
            </section>
          ))}
        </div>
      )}

      {aberta !== null && (
        <DetalheDaOportunidade
          id={aberta}
          listas={listas}
          aoFechar={() => definirAberta(null)}
          aoSalvar={recarregar}
        />
      )}
    </>
  );
}
