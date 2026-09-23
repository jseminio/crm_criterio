/** O funil em kanban — uma coluna por situação, todas sempre visíveis. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ColunaDoFunil, Listas, OportunidadeResumo } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import {
  FILTROS_VAZIOS,
  Filtros,
  paraConsulta,
  temFiltro,
  type EstadoDosFiltros,
} from "../componentes/Filtros";
import { NovaOportunidade } from "../componentes/NovaOportunidade";
import { Numeros } from "../componentes/Numeros";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { dinheiroCurto, prazo } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";

function Cartao({
  oportunidade,
  aoAbrir,
  emMovimento,
  aoComecarArrasto,
  aoTerminarArrasto,
}: {
  oportunidade: OportunidadeResumo;
  aoAbrir: () => void;
  emMovimento: boolean;
  aoComecarArrasto: (id: number) => void;
  aoTerminarArrasto: () => void;
}) {
  const quando = prazo(oportunidade.proxima_acao_em);
  return (
    <button
      type="button"
      className={`cartao ${emMovimento ? "cartao-movendo" : ""}`}
      onClick={aoAbrir}
      draggable
      onDragStart={(evento) => {
        evento.dataTransfer.effectAllowed = "move";
        // O valor em si não é lido em lugar nenhum — alguns navegadores só
        // iniciam o arrasto quando o evento carrega algum dado real.
        evento.dataTransfer.setData("text/plain", String(oportunidade.id));
        aoComecarArrasto(oportunidade.id);
      }}
      onDragEnd={aoTerminarArrasto}
    >
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
  const [situacaoDeAbertura, definirSituacaoDeAbertura] = useState<string | undefined>(undefined);
  const [arrastando, definirArrastando] = useState<number | null>(null);
  const [colunaAlvo, definirColunaAlvo] = useState<string | null>(null);
  const [movendo, definirMovendo] = useState<number | null>(null);
  const [erroDeMovimento, definirErroDeMovimento] = useState<string | null>(null);
  const [criando, definirCriando] = useState(false);

  const { dados, carregando, erro, recarregar } = usarDados<ColunaDoFunil[]>(
    () => api.funil(paraConsulta(filtros)),
    [
      filtros.busca,
      filtros.captador,
      filtros.tipo_canal,
      filtros.temperatura,
      filtros.servico,
      filtros.dataTipo,
      filtros.periodo,
      filtros.dataDe,
      filtros.dataAte,
    ],
  );

  const total = dados?.reduce((soma, coluna) => soma + coluna.quantas, 0) ?? 0;

  function abrir(id: number, comSituacao?: string) {
    definirSituacaoDeAbertura(comSituacao);
    definirAberta(id);
  }

  function fechar() {
    definirAberta(null);
    definirSituacaoDeAbertura(undefined);
  }

  async function mover(id: number, situacaoAtual: string, novaSituacao: string) {
    if (situacaoAtual === novaSituacao) return;

    // "Aceita" exige a data do aceite (regra 21/09/2026), e o cartão do
    // kanban não carrega esse campo — só o detalhe sabe se ela já existe.
    // Em vez de arriscar um PATCH que a API recusa, o drop abre o painel
    // com a situação pré-marcada: quem arrastou só confirma a data.
    if (novaSituacao === "Aceita") {
      abrir(id, novaSituacao);
      return;
    }

    definirMovendo(id);
    definirErroDeMovimento(null);
    try {
      await api.editarOportunidade(id, { situacao: novaSituacao });
      recarregar();
    } catch (falha) {
      definirErroDeMovimento(
        falha instanceof ErroDaApi ? falha.message : "Não consegui mover a oportunidade.",
      );
    } finally {
      definirMovendo(null);
    }
  }

  return (
    <>
      <Numeros filtros={filtros} />
      <Filtros
        filtros={filtros}
        aoMudar={definirFiltros}
        listas={listas}
        acao={
          <button
            type="button"
            className="botao botao-primario"
            onClick={() => definirCriando(true)}
          >
            Nova oportunidade
          </button>
        }
      />

      {erroDeMovimento && (
        <div className="aviso-de-movimento" role="alert">
          <span>{erroDeMovimento}</span>
          <button
            type="button"
            className="botao-icone"
            onClick={() => definirErroDeMovimento(null)}
            aria-label="Dispensar aviso"
          >
            ✕
          </button>
        </div>
      )}

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
            <section
              className={`coluna ${colunaAlvo === coluna.situacao ? "coluna-alvo" : ""}`}
              key={coluna.situacao}
              onDragOver={(evento) => {
                if (arrastando === null) return;
                // Sem isto o navegador recusa o drop por padrão — é assim
                // que o HTML5 marca "este elemento aceita ser alvo".
                evento.preventDefault();
                evento.dataTransfer.dropEffect = "move";
                if (colunaAlvo !== coluna.situacao) definirColunaAlvo(coluna.situacao);
              }}
              onDragLeave={() =>
                definirColunaAlvo((atual) => (atual === coluna.situacao ? null : atual))
              }
              onDrop={(evento) => {
                evento.preventDefault();
                definirColunaAlvo(null);
                if (arrastando === null) return;
                const origem = dados?.find((c) =>
                  c.oportunidades.some((o) => o.id === arrastando),
                );
                const id = arrastando;
                definirArrastando(null);
                if (origem) mover(id, origem.situacao, coluna.situacao);
              }}
            >
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
                  <Cartao
                    key={o.id}
                    oportunidade={o}
                    aoAbrir={() => abrir(o.id)}
                    emMovimento={movendo === o.id}
                    aoComecarArrasto={definirArrastando}
                    aoTerminarArrasto={() => {
                      definirArrastando(null);
                      definirColunaAlvo(null);
                    }}
                  />
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
          situacaoInicial={situacaoDeAbertura}
          aoFechar={fechar}
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
