/** A tela Parceiros (19/10/2026, amostra aprovada por Eduardo): menu próprio, no padrão do Funil comercial.
 *
 * - Indicadores com a explicação ao passar o mouse e o "Ver composição" de cada número, da mesma conta e com os
 *   mesmos filtros.
 * - Filtros com período (os atalhos do funil, "Data de" indicação ou fechamento, e o intervalo personalizado).
 * - Kanban (uma coluna por etapa da relação) ou Grade, com ordenação crescente, decrescente e de volta à original.
 * - O arrasto só vale entre as etapas marcadas à mão (Mapeado, Qualificado, Estratégico); as outras saem dos dados.
 * - Fees a aprovar (o sócio da conta aprova e marca pago) e a conferência dos textos de canal antigos, recolhidos.
 */

import { useState } from "react";
import { api, ErroDaApi, type FiltrosDosParceiros } from "../api/cliente";
import type { IndicadorDosParceiros, IndicadoresDosParceiros, ParceiroResumo } from "../api/tipos";
import { CampoDeData } from "../componentes/CampoDeData";
import { Etiqueta } from "../componentes/Etiqueta";
import { FolhaMoverPara } from "../componentes/FolhaMoverPara";
import { Indicador, type Composicao } from "../componentes/Indicador";
import { LinkDeArquivo } from "../componentes/LinkDeArquivo";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { Recolhivel } from "../componentes/Recolhivel";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import {
  ACORDOS, ComposicaoDosParceiros, ConferenciaDosTextos, ETAPAS, ETAPAS_MANUAIS, FeesDosParceiros, NIVEIS,
  SeloDoFollowUp,
} from "../componentes/ParceirosApoio";
import { DetalheDoParceiro } from "./DetalheDoParceiro";
import { usarAcesso } from "../entrada";
import { abrirParaImprimir, mesPadrao } from "../relatorioDoParceiro";
import { data, dinheiro, dinheiroCurto, hojeIso, percentual } from "../formato";
import { PRESETS, resolverPeriodo, type Preset } from "../periodo";
import { usarDados } from "../usarDados";
import { usarTelaEstreita, usarToque } from "../usarTelaEstreita";


type Visao = "kanban" | "grade";

interface EstadoDosFiltros {
  busca: string;
  nivel: string;
  acordo: string;
  periodo: Preset | "";
  dataTipo: "indicacao" | "fechamento";
  dataDe: string;
  dataAte: string;
}

const VAZIOS: EstadoDosFiltros = { busca: "", nivel: "", acordo: "", periodo: "", dataTipo: "indicacao", dataDe: "", dataAte: "" };

export function paraConsulta(f: EstadoDosFiltros): FiltrosDosParceiros {
  const intervalo = f.periodo === "personalizado"
    ? { de: f.dataDe || undefined, ate: f.dataAte || undefined }
    : f.periodo ? resolverPeriodo(f.periodo) : null;
  return {
    busca: f.busca.trim() || undefined,
    nivel: f.nivel ? [f.nivel] : undefined,
    acordo: f.acordo ? [f.acordo] : undefined,
    data_tipo: intervalo ? f.dataTipo : undefined,
    data_de: intervalo?.de ?? undefined,
    data_ate: intervalo?.ate ?? undefined,
  };
}

const temFiltro = (f: EstadoDosFiltros) => f.busca !== "" || f.nivel !== "" || f.acordo !== "" || f.periodo !== "";

export function Parceiros() {
  const { pode } = usarAcesso();
  const [filtros, definirFiltros] = useState<EstadoDosFiltros>(VAZIOS);
  const [visao, definirVisao] = useState<Visao>("kanban");
  const [aberto, definirAberto] = useState<number | "novo" | null>(null);
  const [arrastando, definirArrastando] = useState<number | null>(null);
  const [colunaAlvo, definirColunaAlvo] = useState<string | null>(null);
  const [aviso, definirAviso] = useState<string | null>(null);
  const [movendoPelaFolha, definirMovendoPelaFolha] = useState<ParceiroResumo | null>(null);
  const [etapaVisivel, definirEtapaVisivel] = useState<string>("Produtivo");
  const [mesDoRelatorio, definirMesDoRelatorio] = useState(mesPadrao());
  const estreita = usarTelaEstreita();
  const toque = usarToque();
  const semArrasto = estreita || toque;
  const { ordenacao, alternar } = usarOrdenacao();
  const { ordenacao: ordenacaoDoKanban, alternar: alternarDoKanban } = usarOrdenacao();

  const consulta = paraConsulta(filtros);
  const chave = JSON.stringify(consulta);
  const lista = usarDados<ParceiroResumo[]>(() => api.parceiros(consulta), [chave]);
  const numeros = usarDados<IndicadoresDosParceiros>(() => api.indicadoresDosParceiros(consulta), [chave]);
  const recarregar = () => {
    lista.recarregar();
    numeros.recarregar();
  };

  const mudar = (campo: keyof EstadoDosFiltros) => (evento: { target: { value: string } }) =>
    definirFiltros({ ...filtros, [campo]: evento.target.value });

  async function mover(p: ParceiroResumo, etapa: string) {
    if (p.etapa === etapa) return;
    if (!ETAPAS_MANUAIS.includes(etapa)) {
      definirAviso(`${etapa} muda sozinha pelos dados: contrato assinado, indicação validada, proposta enviada ou seis meses sem indicação.`);
      return;
    }
    try {
      await api.moverParceiro(p.id, etapa);
      definirAviso(null);
    } catch (falha) {
      definirAviso(falha instanceof ErroDaApi ? falha.message : "Não consegui mover o parceiro.");
    }
    recarregar();
  }

  async function relatoriosDoMes() {
    try {
      const relatorios = await api.relatoriosDosParceiros(mesDoRelatorio);
      if (relatorios.length === 0) definirAviso("Nenhum parceiro tem indicação até o fim desse mês.");
      else if (!abrirParaImprimir(relatorios)) definirAviso("Não consegui preparar a impressão do relatório.");
    } catch (falha) {
      definirAviso(falha instanceof ErroDaApi ? falha.message : "Não consegui montar os relatórios.");
    }
  }

  const itens = lista.dados ?? [];
  const filtrando = temFiltro(filtros);
  const colunas = ETAPAS.map((etapa) => {
    const deles = itens.filter((p) => p.etapa === etapa);
    return {
      etapa,
      parceiros: ordenar(deles, ordenacaoDoKanban, { mrr: (p) => Number(p.mrr) }),
      mrr: deles.reduce((s, p) => s + Number(p.mrr), 0),
      pontual: deles.reduce((s, p) => s + Number(p.pontual), 0),
    };
  });
  const etapaAVista = colunas.some((c) => c.etapa === etapaVisivel) ? etapaVisivel : "Produtivo";

  return (
    <>
      <NumerosDosParceiros estado={numeros} consulta={consulta} />

      {(pode("parceiros.aprovar_fee", "parceiros.editar") || pode("parceiros.ver")) && (
        <div className="funil-analises">
          <Recolhivel titulo="Fees a aprovar e a pagar" resumo="o sócio da conta aprova, com o valor líquido de impostos">
            <FeesDosParceiros aoMudar={recarregar} />
          </Recolhivel>
          {pode("parceiros.editar") && (
            <Recolhivel titulo="Conferência das indicações antigas" resumo="liga o texto do canal ao parceiro certo">
              <ConferenciaDosTextos aoLigar={recarregar} />
            </Recolhivel>
          )}
        </div>
      )}

      <div className="filtros">
        <div className="campo">
          <label className="campo-rotulo" htmlFor="parceiros-busca">Buscar</label>
          <input id="parceiros-busca" className="entrada entrada-busca" placeholder="Nome do parceiro"
            value={filtros.busca} onChange={mudar("busca")} />
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="parceiros-nivel">Nível</label>
          <select id="parceiros-nivel" className="selecao" value={filtros.nivel} onChange={mudar("nivel")}>
            <option value="">Todos</option>
            {NIVEIS.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="parceiros-acordo">Acordo</label>
          <select id="parceiros-acordo" className="selecao" value={filtros.acordo} onChange={mudar("acordo")}>
            <option value="">Todos</option>
            {ACORDOS.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="parceiros-periodo">Período</label>
          <select id="parceiros-periodo" className="selecao" value={filtros.periodo} onChange={mudar("periodo")}>
            <option value="">Todo o período</option>
            {PRESETS.map((p) => <option key={p.valor} value={p.valor}>{p.rotulo}</option>)}
          </select>
        </div>
        {filtros.periodo !== "" && (
          <div className="campo">
            <label className="campo-rotulo" htmlFor="parceiros-data-tipo">Data de</label>
            <select id="parceiros-data-tipo" className="selecao" value={filtros.dataTipo} onChange={mudar("dataTipo")}>
              <option value="indicacao">Indicação</option>
              <option value="fechamento">Fechamento</option>
            </select>
          </div>
        )}
        {filtros.periodo === "personalizado" && (
          <>
            <div className="campo">
              <label className="campo-rotulo" htmlFor="parceiros-de">De</label>
              <CampoDeData id="parceiros-de" value={filtros.dataDe} aoMudar={(v) => definirFiltros({ ...filtros, dataDe: v })} />
            </div>
            <div className="campo">
              <label className="campo-rotulo" htmlFor="parceiros-ate">Até</label>
              <CampoDeData id="parceiros-ate" value={filtros.dataAte} aoMudar={(v) => definirFiltros({ ...filtros, dataAte: v })} />
            </div>
          </>
        )}
        {filtrando && (
          <button type="button" className="botao botao-secundario" onClick={() => definirFiltros(VAZIOS)}>Limpar filtros</button>
        )}
        <div style={{ marginLeft: "auto" }}>
          {visao === "kanban" && (
            <button type="button" className={`kanban-ordenar-valor${ordenacaoDoKanban ? " th-ordenar-ativa" : ""}`}
              onClick={() => alternarDoKanban("mrr")} aria-pressed={!!ordenacaoDoKanban}>
              Ordenar por MRR
              <span className="th-seta" aria-hidden="true">
                {ordenacaoDoKanban ? (ordenacaoDoKanban.direcao === "asc" ? "▲" : "▼") : "⇅"}
              </span>
            </button>
          )}
          <div className="visao-toggle" role="group" aria-label="Visão dos parceiros">
            <button type="button" aria-pressed={visao === "kanban"}
              className={visao === "kanban" ? "visao-botao visao-ativa" : "visao-botao"} onClick={() => definirVisao("kanban")}>
              ▦ Kanban
            </button>
            <button type="button" aria-pressed={visao === "grade"}
              className={visao === "grade" ? "visao-botao visao-ativa" : "visao-botao"} onClick={() => definirVisao("grade")}>
              ☰ Grade
            </button>
          </div>
          {visao === "grade" && pode("parceiros.exportar") && (
            <LinkDeArquivo className="botao botao-secundario" href={api.enderecoDaExportacaoDosParceiros(consulta)}
              title="Baixa em Excel os parceiros da Grade, com os filtros aplicados">
              Exportar para Excel
            </LinkDeArquivo>
          )}
          <input className="entrada" type="month" aria-label="Mês dos relatórios" value={mesDoRelatorio}
            style={{ width: "auto" }} onChange={(e) => definirMesDoRelatorio(e.target.value)} />
          <button type="button" className="botao botao-secundario" onClick={relatoriosDoMes} disabled={!mesDoRelatorio}
            title="Um relatório por parceiro com indicação, pronto para salvar em PDF">
            Relatórios do mês
          </button>
          {pode("parceiros.editar") && (
            <button type="button" className="botao botao-primario" onClick={() => definirAberto("novo")}>Novo parceiro</button>
          )}
        </div>
      </div>

      {aviso && (
        <div className="aviso-de-movimento" role="alert">
          <span>{aviso}</span>
          <button type="button" className="botao-icone" onClick={() => definirAviso(null)} aria-label="Dispensar aviso">✕</button>
        </div>
      )}

      {lista.carregando && <Carregando rotulo="Carregando os parceiros" />}
      {lista.erro && !lista.carregando && <Erro mensagem={lista.erro} aoTentarDeNovo={lista.recarregar} />}
      {!lista.carregando && !lista.erro && itens.length === 0 && filtrando && <VazioPorFiltro aoLimpar={() => definirFiltros(VAZIOS)} />}
      {!lista.carregando && !lista.erro && itens.length === 0 && !filtrando && (
        <VazioSemDados titulo="Nenhum parceiro cadastrado"
          explicacao="Cadastre quem indica clientes à Critério em Novo parceiro. A conferência liga as indicações antigas do funil." />
      )}

      {!lista.carregando && !lista.erro && itens.length > 0 && visao === "kanban" && estreita && (
        <div className="etapas-do-kanban" role="tablist" aria-label="Etapas da relação">
          {colunas.map((c) => (
            <button key={c.etapa} type="button" role="tab" className="etapa-do-kanban" aria-selected={c.etapa === etapaAVista}
              onClick={() => definirEtapaVisivel(c.etapa)}>
              {c.etapa}
              <span className="etapa-do-kanban-quantas">{c.parceiros.length}</span>
            </button>
          ))}
        </div>
      )}

      {!lista.carregando && !lista.erro && itens.length > 0 && visao === "kanban" && (
        <div className={`kanban ${estreita ? "kanban-uma-etapa" : ""}`}>
          {colunas.filter((c) => !estreita || c.etapa === etapaAVista).map((c) => (
            <section key={c.etapa} className={`coluna ${colunaAlvo === c.etapa ? "coluna-alvo" : ""}`}
              aria-label={c.etapa}
              onDragOver={(evento) => {
                if (arrastando === null) return;
                evento.preventDefault();
                evento.dataTransfer.dropEffect = "move";
                if (colunaAlvo !== c.etapa) definirColunaAlvo(c.etapa);
              }}
              onDragLeave={() => definirColunaAlvo((atual) => (atual === c.etapa ? null : atual))}
              onDrop={(evento) => {
                evento.preventDefault();
                definirColunaAlvo(null);
                const p = itens.find((x) => x.id === arrastando);
                definirArrastando(null);
                if (p) mover(p, c.etapa);
              }}>
              <header className="coluna-topo">
                <h2 className="coluna-nome">
                  <span>{c.etapa}</span>
                  <span className="coluna-quantas">{c.parceiros.length}</span>
                </h2>
                <p className="coluna-valor">{dinheiroCurto(c.mrr)}/mês originado</p>
                {c.pontual > 0 && <p className="coluna-mensal">+ {dinheiroCurto(c.pontual)} pontual</p>}
                {!ETAPAS_MANUAIS.includes(c.etapa) && <p className="coluna-mensal">muda pelos dados</p>}
              </header>
              <div className="coluna-cartoes">
                {c.parceiros.map((p) => (
                  <CartaoDoParceiro key={p.id} parceiro={p} aoAbrir={() => definirAberto(p.id)}
                    arrastavel={!semArrasto && pode("parceiros.editar")}
                    aoComecarArrasto={() => definirArrastando(p.id)}
                    aoTerminarArrasto={() => {
                      definirArrastando(null);
                      definirColunaAlvo(null);
                    }}
                    aoMover={semArrasto && pode("parceiros.editar") ? () => definirMovendoPelaFolha(p) : undefined} />
                ))}
                {c.parceiros.length === 0 && <p className="coluna-vazia">Nenhum parceiro nesta etapa.</p>}
              </div>
            </section>
          ))}
        </div>
      )}

      {!lista.carregando && !lista.erro && itens.length > 0 && visao === "grade" && (
        <>
          <p style={{ color: "var(--texto-medio)", marginTop: 0 }}>{itens.length} parceiro{itens.length === 1 ? "" : "s"}</p>
          <table className="tabela">
            <thead>
              <tr>
                <ThOrdenavel coluna="nome" ordenacao={ordenacao} aoAlternar={alternar}>Parceiro</ThOrdenavel>
                <ThOrdenavel coluna="nivel" ordenacao={ordenacao} aoAlternar={alternar}>Nível</ThOrdenavel>
                <ThOrdenavel coluna="acordo" ordenacao={ordenacao} aoAlternar={alternar}>Acordo</ThOrdenavel>
                <ThOrdenavel coluna="etapa" ordenacao={ordenacao} aoAlternar={alternar}>Etapa</ThOrdenavel>
                <ThOrdenavel coluna="socio" ordenacao={ordenacao} aoAlternar={alternar}>Sócio</ThOrdenavel>
                <ThOrdenavel coluna="indicacoes" numerico ordenacao={ordenacao} aoAlternar={alternar}>Indicações</ThOrdenavel>
                <ThOrdenavel coluna="abertas" numerico ordenacao={ordenacao} aoAlternar={alternar}>Abertas</ThOrdenavel>
                <ThOrdenavel coluna="fechadas" numerico ordenacao={ordenacao} aoAlternar={alternar}>Fechadas</ThOrdenavel>
                <ThOrdenavel coluna="mrr" numerico ordenacao={ordenacao} aoAlternar={alternar}>MRR originado</ThOrdenavel>
                <ThOrdenavel coluna="follow_up" ordenacao={ordenacao} aoAlternar={alternar}>Próximo follow-up</ThOrdenavel>
              </tr>
            </thead>
            <tbody>
              {ordenar(itens, ordenacao, {
                nome: (p) => p.nome, nivel: (p) => p.nivel, acordo: (p) => p.acordo, etapa: (p) => ETAPAS.indexOf(p.etapa),
                socio: (p) => p.socio_responsavel, indicacoes: (p) => p.indicacoes, abertas: (p) => p.abertas,
                fechadas: (p) => p.fechadas, mrr: (p) => Number(p.mrr), follow_up: (p) => p.proximo_follow_up_em,
              }).map((p) => (
                <tr key={p.id} className="tabela-clicavel" tabIndex={0} onClick={() => definirAberto(p.id)}
                  onKeyDown={(e) => e.key === "Enter" && definirAberto(p.id)}>
                  <td>{p.nome} <span style={{ color: "var(--texto-fraco)" }}>{p.tipo_pessoa}</span></td>
                  <td>{p.nivel}</td>
                  <td><Etiqueta texto={p.acordo} /></td>
                  <td><Etiqueta texto={p.etapa} /></td>
                  <td>{p.socio_responsavel ?? "—"}</td>
                  <td className="tabela-numero">{p.indicacoes}</td>
                  <td className="tabela-numero">{p.abertas}</td>
                  <td className="tabela-numero">{p.fechadas}</td>
                  <td className="tabela-numero">{Number(p.mrr) ? dinheiro(p.mrr) : "—"}</td>
                  <td>
                    {p.proximo_follow_up && <span>{p.proximo_follow_up}<br /></span>}
                    {p.proximo_follow_up_em && p.proximo_follow_up_em >= hojeIso()
                      ? <span>{data(p.proximo_follow_up_em)}</span>
                      : <SeloDoFollowUp iso={p.proximo_follow_up_em} hoje={hojeIso()} />}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {movendoPelaFolha && (
        <FolhaMoverPara nome={movendoPelaFolha.nome} etapaAtual={movendoPelaFolha.etapa} etapas={ETAPAS_MANUAIS}
          aoFechar={() => definirMovendoPelaFolha(null)}
          aoEscolher={(etapa) => {
            const p = movendoPelaFolha;
            definirMovendoPelaFolha(null);
            mover(p, etapa);
          }} />
      )}

      {aberto !== null && (
        <DetalheDoParceiro id={aberto === "novo" ? null : aberto} aoFechar={() => definirAberto(null)}
          aoSalvar={(id) => {
            recarregar();
            if (aberto === "novo" && id) definirAberto(id);
          }} />
      )}
    </>
  );
}

function CartaoDoParceiro({ parceiro: p, aoAbrir, arrastavel, aoComecarArrasto, aoTerminarArrasto, aoMover }: {
  parceiro: ParceiroResumo;
  aoAbrir: () => void;
  arrastavel: boolean;
  aoComecarArrasto: () => void;
  aoTerminarArrasto: () => void;
  aoMover?: () => void;
}) {
  const cartao = (
    <button type="button" className="cartao" onClick={aoAbrir} draggable={arrastavel}
      onDragStart={(evento) => {
        evento.dataTransfer.effectAllowed = "move";
        evento.dataTransfer.setData("text/plain", String(p.id));
        aoComecarArrasto();
      }}
      onDragEnd={aoTerminarArrasto}>
      <span className="cartao-grupo">{p.nome}</span>
      <span className="cartao-nome">{p.tipo_pessoa} · {p.nivel}{p.socio_responsavel ? ` · ${p.socio_responsavel}` : ""}</span>
      <span className="cartao-valor">{Number(p.mrr) ? `${dinheiroCurto(p.mrr)}/mês` : "sem MRR no período"}</span>
      <span className="cartao-linha"><Etiqueta texto={p.acordo} /></span>
      <span className="cartao-linha"><SeloDoFollowUp iso={p.proximo_follow_up_em} hoje={hojeIso()} /></span>
      <span className="cartao-nome">
        {p.indicacoes} indicaç{p.indicacoes === 1 ? "ão" : "ões"} · {p.abertas} aberta{p.abertas === 1 ? "" : "s"}
      </span>
    </button>
  );
  if (!aoMover) return cartao;
  return (
    <div className="cartao-com-mover">
      {cartao}
      <button type="button" className="cartao-mover" onClick={aoMover} aria-label={`Mover ${p.nome}`}>Mover ▸</button>
    </div>
  );
}

const TITULOS: Record<IndicadorDosParceiros, string> = {
  ativos: "Parceiros ativos",
  indicacoes: "Indicações",
  conversao: "Conversão das indicações",
  mrr: "MRR originado",
  sem_contrato: "Sem contrato assinado",
  fees: "Fees a aprovar",
  sem_follow_up: "Sem follow-up marcado",
};

function NumerosDosParceiros({ estado, consulta }: {
  estado: ReturnType<typeof usarDados<IndicadoresDosParceiros>>;
  consulta: FiltrosDosParceiros;
}) {
  const { dados, carregando, erro, recarregar } = estado;
  if (carregando && !dados) return <Carregando rotulo="Calculando os números" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const composicao = (indicador: IndicadorDosParceiros, quantos?: number): Composicao => ({
    titulo: TITULOS[indicador], subtitulo: "O que compõe o número, com os filtros da tela", quantos,
    conteudo: () => <ComposicaoDosParceiros indicador={indicador} filtros={consulta} />,
  });
  const cards: { chave: IndicadorDosParceiros; destaque: string; tom: "azul" | "verde" | "ambar" | "marinho" | "violeta" | "rosa";
    quantos?: number; apoio?: string }[] = [
    { chave: "ativos", destaque: String(dados.ativos), tom: "marinho", quantos: dados.ativos },
    { chave: "indicacoes", destaque: String(dados.indicacoes), tom: "azul", quantos: dados.indicacoes },
    { chave: "conversao", destaque: dados.conversao === null ? "" : percentual(dados.conversao), tom: "verde" },
    { chave: "mrr", destaque: dinheiro(dados.mrr), tom: "violeta" },
    { chave: "sem_contrato", destaque: String(dados.sem_contrato), tom: "ambar", quantos: dados.sem_contrato },
    { chave: "fees", destaque: dinheiro(dados.fees), tom: "rosa", quantos: dados.fees_quantos },
    { chave: "sem_follow_up", destaque: String(dados.sem_follow_up), tom: "ambar",
      quantos: dados.sem_follow_up + dados.follow_up_atrasado,
      apoio: dados.follow_up_atrasado ? `+ ${dados.follow_up_atrasado} atrasado${dados.follow_up_atrasado === 1 ? "" : "s"}` : undefined },
  ];
  return (
    <div className="numeros" aria-label="Números dos parceiros">
      {cards.map((c) => (
        <Indicador key={c.chave} rotulo={TITULOS[c.chave]} destaque={c.destaque || undefined} tom={c.tom} apoio={c.apoio}
          composicao={composicao(c.chave, c.quantos)}>
          {dados.explicacoes[c.chave]}
        </Indicador>
      ))}
    </div>
  );
}
