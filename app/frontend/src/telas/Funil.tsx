/** O funil comercial — Kanban (uma coluna por situação) ou Grade (tabela), a mesma base.
 *
 * Fusão de 27/09/2026: a tela Oportunidades virou a visão "Grade" desta mesma tela, porque as duas
 * mostravam a mesma coisa em formatos diferentes. O botão Kanban/Grade fica na barra de filtros; o
 * filtro "Situação" só faz sentido na Grade (no Kanban, todas as situações já ficam visíveis juntas).
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ColunaDoFunil, Listas, OportunidadeResumo, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import {
  FILTROS_VAZIOS,
  Filtros,
  paraConsulta,
  temFiltro,
  type EstadoDosFiltros,
} from "../componentes/Filtros";
import { NovaOportunidade } from "../componentes/NovaOportunidade";
import { BotaoBuscarQuestionarios, QuestionariosDoSite, usarQuestionarios } from "../componentes/QuestionariosDoSite";
import { CenariosDeTicket } from "../componentes/CenariosDeTicket";
import { Numeros } from "../componentes/Numeros";
import { Recolhivel } from "../componentes/Recolhivel";
import { Recortes } from "../componentes/Recortes";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { data, dinheiro, dinheiroCurto, prazo } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";

type Visao = "kanban" | "grade";

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
  const [visao, definirVisao] = useState<Visao>("kanban");
  const [filtros, definirFiltros] = useState<EstadoDosFiltros>(FILTROS_VAZIOS);
  const [situacao, definirSituacao] = useState("");
  const [aberta, definirAberta] = useState<number | null>(null);
  const [situacaoDeAbertura, definirSituacaoDeAbertura] = useState<string | undefined>(undefined);
  const [arrastando, definirArrastando] = useState<number | null>(null);
  const [colunaAlvo, definirColunaAlvo] = useState<string | null>(null);
  const [movendo, definirMovendo] = useState<number | null>(null);
  const [erroDeMovimento, definirErroDeMovimento] = useState<string | null>(null);
  const [criando, definirCriando] = useState(false);
  const { ordenacao, alternar: alternarOrdenacao } = usarOrdenacao();
  const { ordenacao: ordenacaoDoKanban, alternar: alternarOrdenacaoDoKanban } = usarOrdenacao();

  const kanban = usarDados<ColunaDoFunil[] | null>(
    () => (visao === "kanban" ? api.funil(paraConsulta(filtros)) : Promise.resolve(null)),
    [
      visao,
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
  const grade = usarDados<Pagina<OportunidadeResumo> | null>(
    () =>
      visao === "grade"
        ? api.oportunidades({ ...paraConsulta(filtros), situacao: situacao ? [situacao] : undefined })
        : Promise.resolve(null),
    [
      visao,
      situacao,
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

  const { dados, carregando, erro, recarregar } = visao === "kanban" ? kanban : grade;
  const questionarios = usarQuestionarios(recarregar);
  const total = visao === "kanban"
    ? (kanban.dados?.reduce((soma, coluna) => soma + coluna.quantas, 0) ?? 0)
    : (grade.dados?.total ?? 0);
  const filtrando = temFiltro(filtros) || (visao === "grade" && situacao !== "");

  function abrir(id: number, comSituacao?: string) {
    definirSituacaoDeAbertura(comSituacao);
    definirAberta(id);
  }

  function fechar() {
    definirAberta(null);
    definirSituacaoDeAbertura(undefined);
  }

  function limpar() {
    definirFiltros(FILTROS_VAZIOS);
    definirSituacao("");
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
      <div className="funil-analises">
        <Recolhivel titulo="Recortes do funil" resumo="por serviço, canal e captador">
          <Recortes filtros={filtros} />
        </Recolhivel>
        <Recolhivel titulo="Cenários de ticket" resumo="conservador, base e otimista">
          <CenariosDeTicket filtros={filtros} />
        </Recolhivel>
      </div>
      <Filtros
        filtros={filtros}
        aoMudar={definirFiltros}
        listas={listas}
        acao={
          <>
            {visao === "grade" && (
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
            )}
            {visao === "kanban" && (
              <button
                type="button"
                className={`kanban-ordenar-valor${ordenacaoDoKanban ? " th-ordenar-ativa" : ""}`}
                onClick={() => alternarOrdenacaoDoKanban("valor")}
                aria-pressed={!!ordenacaoDoKanban}
              >
                Ordenar por valor
                <span className="th-seta" aria-hidden="true">
                  {ordenacaoDoKanban ? (ordenacaoDoKanban.direcao === "asc" ? "▲" : "▼") : "⇅"}
                </span>
              </button>
            )}
            <div className="visao-toggle" role="group" aria-label="Visão do funil">
              <button
                type="button"
                aria-pressed={visao === "kanban"}
                className={visao === "kanban" ? "visao-botao visao-ativa" : "visao-botao"}
                onClick={() => definirVisao("kanban")}
              >
                ▦ Kanban
              </button>
              <button
                type="button"
                aria-pressed={visao === "grade"}
                className={visao === "grade" ? "visao-botao visao-ativa" : "visao-botao"}
                onClick={() => definirVisao("grade")}
              >
                ☰ Grade
              </button>
            </div>
            <BotaoBuscarQuestionarios estado={questionarios} />
            {visao === "grade" && (
              <a
                className="botao botao-secundario"
                href={api.enderecoDaExportacaoDoFunil({
                  ...paraConsulta(filtros),
                  situacao: situacao ? [situacao] : undefined,
                })}
                title="Baixa em Excel as oportunidades da Grade, com os filtros aplicados"
              >
                Exportar para Excel
              </a>
            )}
            <button type="button" className="botao botao-primario" onClick={() => definirCriando(true)}>
              Nova oportunidade
            </button>
          </>
        }
      />

      <QuestionariosDoSite estado={questionarios} aoAbrir={(id) => definirAberta(id)} />

      {visao === "kanban" && erroDeMovimento && (
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

      {carregando && (
        <Carregando rotulo={visao === "kanban" ? "Carregando o funil" : "Carregando as oportunidades"} />
      )}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}

      {!carregando && !erro && total === 0 && filtrando && (
        <VazioPorFiltro aoLimpar={limpar} />
      )}

      {!carregando && !erro && total === 0 && !filtrando && (
        <VazioSemDados
          titulo={visao === "kanban" ? "O funil está vazio" : "Nenhuma oportunidade"}
          explicacao="Nenhuma oportunidade foi carregada ainda. A carga da planilha de 2026 preenche esta tela."
        />
      )}

      {!carregando && !erro && total > 0 && visao === "kanban" && (
        <div className="kanban">
          {kanban.dados?.map((coluna) => (
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
                const origem = kanban.dados?.find((c) =>
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
                {ordenar(coluna.oportunidades, ordenacaoDoKanban, {
                  valor: (o) => (o.preco_mensal ? Number(o.preco_mensal) : o.preco_anual ? Number(o.preco_anual) : null),
                }).map((o) => (
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

      {!carregando && !erro && total > 0 && visao === "grade" && (
        <>
          <p style={{ color: "var(--texto-medio)", marginTop: 0 }}>
            {total} oportunidade{total === 1 ? "" : "s"}
          </p>
          <table className="tabela">
            <thead>
              <tr>
                <ThOrdenavel coluna="cliente" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Cliente</ThOrdenavel>
                <ThOrdenavel coluna="nome" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Oportunidade</ThOrdenavel>
                <ThOrdenavel coluna="situacao" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Situação</ThOrdenavel>
                <ThOrdenavel coluna="temperatura" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Temperatura</ThOrdenavel>
                <ThOrdenavel coluna="captador" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Captador</ThOrdenavel>
                <ThOrdenavel coluna="originacao" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Originação</ThOrdenavel>
                <ThOrdenavel coluna="mensal" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Mensal</ThOrdenavel>
                <ThOrdenavel coluna="anual" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Anual</ThOrdenavel>
              </tr>
            </thead>
            <tbody>
              {ordenar(grade.dados?.itens ?? [], ordenacao, {
                cliente: (o) => o.grupo_nome ?? o.nome,
                nome: (o) => o.nome,
                situacao: (o) => o.situacao,
                temperatura: (o) => o.temperatura,
                captador: (o) => o.captador,
                originacao: (o) => o.data_colocacao,
                mensal: (o) => (o.preco_mensal ? Number(o.preco_mensal) : null),
                anual: (o) => (o.preco_anual ? Number(o.preco_anual) : null),
              }).map((o) => (
                <tr
                  key={o.id}
                  className="tabela-clicavel"
                  onClick={() => abrir(o.id)}
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && abrir(o.id)}
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
