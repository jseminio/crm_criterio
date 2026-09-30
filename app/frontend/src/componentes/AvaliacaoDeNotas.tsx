/** Avalia os sete componentes do Score de um grupo, um por aba, mais o Porte.
 *
 * Receita e Rentabilidade são calculadas (percentil da carteira e margem/atrito); as outras cinco —
 * Complexidade, Risco técnico, Disciplina, Cross-sell e Inadimplência — são checklist: quem preenche
 * marca fato observável, não escolhe número "no olho". Réguas em `escala-das-notas-humanas.md`
 * (Complexidade, Risco, Disciplina) e a proposta de Cross-sell/Inadimplência aprovada por Eduardo em
 * 27/09/2026 (hipótese, mesma cautela). O motivo enviado ao servidor é montado a partir do que foi
 * marcado, sem exigir texto livre.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type {
  AbaDaAvaliacao, AvaliacaoGravada, NotasDoGrupo, PeriodoDeAvaliacao, PorteDoGrupo, RascunhoDaAvaliacao,
  RespostasDoRascunho, SimulacaoDoCliente, SugestaoDePorte, VolumetriaEntrada,
} from "../api/tipos";
import { dataHora, defasagem, dinheiro, fracaoEmPercentual } from "../formato";
import { DIRECIONADORES_DE_PORTE } from "./direcionadoresDePorte";
import { PainelLateral } from "./PainelLateral";

const FATORES_COMPLEXIDADE = [
  { id: "holding", rotulo: "Holding com consolidação de mais de uma empresa", curto: "holding" },
  { id: "centros_de_custo", rotulo: "Mais de um centro de custo ou rateio entre unidades", curto: "centros de custo/rateio" },
  { id: "plano_de_contas", rotulo: "Plano de contas fora do padrão (customizado)", curto: "plano de contas customizado" },
  { id: "auditoria", rotulo: "Auditoria externa (obrigatória ou contratada)", curto: "auditoria externa" },
  { id: "regimes", rotulo: "Mais de um regime tributário no grupo", curto: "múltiplos regimes" },
  { id: "parcelamento_complexidade", rotulo: "Parcelamento tributário ativo", curto: "parcelamento ativo" },
] as const;

const FATORES_RISCO = [
  { id: "auto_de_infracao", rotulo: "Auto de infração ou processo fiscal em andamento", curto: "auto de infração" },
  { id: "parcelamento_atraso", rotulo: "Parcelamento tributário em atraso, ou já quebrado antes", curto: "parcelamento em atraso" },
  { id: "obrigacao_atrasada", rotulo: "Obrigação acessória entregue com atraso nos últimos 3 meses", curto: "obrigação atrasada" },
  { id: "certificado_vencendo", rotulo: "Certificado digital vencendo em 60 dias, sem renovação agendada", curto: "certificado vencendo" },
  { id: "passivo_sem_provisao", rotulo: "Passivo tributário sem provisionamento", curto: "passivo sem provisão" },
] as const;

const FATORES_CROSS_SELL = [
  { id: "mais_de_uma_linha", rotulo: "Contratou mais de uma linha de serviço do catálogo (ex.: BPO Contábil + BPO Financeiro)", curto: "mais de uma linha contratada" },
  { id: "empresa_do_grupo_fora", rotulo: "Há outra empresa do mesmo grupo econômico ainda não atendida pela Critério", curto: "empresa do grupo fora" },
  { id: "interesse_formal", rotulo: "Já demonstrou interesse formal em outro serviço (proposta enviada, mesmo sem fechar)", curto: "interesse formal em outro serviço" },
  { id: "porte_comporta", rotulo: "Porte comporta upsell (Médio ou maior, pela régua de porte)", curto: "porte comporta upsell" },
  { id: "gancho_societario", rotulo: "Tem processo societário, M&A ou reestruturação em andamento (gancho para Advisory)", curto: "gancho societário/M&A" },
] as const;

function notaDeComplexidade(sims: number): number {
  if (sims === 0) return 1;
  if (sims === 1) return 2;
  if (sims <= 3) return 3;
  if (sims === 4) return 4;
  return 5;
}

/** Mais fator de risco = nota mais alta, como na Complexidade: o Score inverte (6 − nota) e o atrito
 * cresce com a nota. Até 29/09/2026 a contagem saía invertida (0 fatores = 5) e a inversão do Score
 * vinha por cima — cliente sem risco nenhum era tratado como risco máximo. */
function notaDeRisco(sims: number): number {
  return Math.min(5, 1 + sims);
}

function notaDeCrossSell(sims: number): number {
  if (sims === 0) return 1;
  if (sims === 1) return 2;
  if (sims === 2) return 3;
  if (sims === 3) return 4;
  return 5;
}

function notaDeDisciplina(mesesNoPrazo: number, cobrancaDobrada: boolean, atrasoRecorrente: boolean): number {
  const furos = (3 - mesesNoPrazo) + (cobrancaDobrada ? 1 : 0) + (atrasoRecorrente ? 1 : 0);
  return Math.max(1, 5 - furos);
}

/** Mesma lógica da Disciplina interina — furo por furo, piso em 1 — aplicada ao pagamento em vez do
 * prazo de entrega. Proposta de 27/09/2026: o CRM ainda não registra atraso de pagamento, então fica
 * interina até existir esse dado (a mesma cautela do plano de Disciplina). */
function notaDeInadimplencia(mesesEmDia: number, emNegociacao: boolean, jaSuspenso: boolean): number {
  const furos = (3 - mesesEmDia) + (emNegociacao ? 1 : 0) + (jaSuspenso ? 1 : 0);
  return Math.max(1, 5 - furos);
}

function Checklist({
  titulo, ajuda, fatores, marcados, aoAlternar, nota,
}: {
  titulo: string;
  ajuda?: string;
  fatores: readonly { id: string; rotulo: string }[];
  marcados: Set<string>;
  aoAlternar: (id: string) => void;
  nota: number;
}) {
  return (
    <section className="avaliacao-secao">
      <h3>{titulo}</h3>
      {ajuda && <p className="campo-ajuda" style={{ marginTop: 0 }}>{ajuda}</p>}
      <div className="campo-bloco">
        {fatores.map((f) => (
          <label key={f.id} className="avaliacao-item">
            <input type="checkbox" checked={marcados.has(f.id)} onChange={() => aoAlternar(f.id)} />
            {f.rotulo}
          </label>
        ))}
      </div>
      <p className="recado">
        Nota calculada: <strong>{nota}</strong> ({marcados.size} de {fatores.length} marcados)
      </p>
    </section>
  );
}

function NotaCalculada({ valor }: { valor: string }) {
  return <p className="numero-valor" style={{ fontSize: 28, margin: "var(--e2) 0" }}>{Number(valor).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>;
}

const ABAS = [
  { chave: "receita", rotulo: "Receita" },
  { chave: "rentabilidade", rotulo: "Rentabilidade" },
  { chave: "complexidade", rotulo: "Complexidade" },
  { chave: "risco", rotulo: "Risco técnico" },
  { chave: "disciplina", rotulo: "Disciplina" },
  { chave: "cross_sell", rotulo: "Cross-sell" },
  { chave: "inadimplencia", rotulo: "Adimplência" },
  { chave: "porte", rotulo: "Porte" },
] as const;
type Aba = (typeof ABAS)[number]["chave"];
const DE_PREENCHER: readonly AbaDaAvaliacao[] = ["complexidade", "risco", "disciplina", "cross_sell", "inadimplencia", "porte"];
const preenchivel = (a: Aba): a is AbaDaAvaliacao => (DE_PREENCHER as readonly string[]).includes(a);
const MES = (iso: string) => `${iso.slice(5, 7)}/${iso.slice(0, 4)}`;

function ResultadoDoCliente({ r }: { r: SimulacaoDoCliente }) {
  const rent = r.rentabilidade;
  const rotulos: Record<string, string> = { disciplina: "Disciplina", cross_sell: "Cross-sell", inadimplencia: "Adimplência", porte: "Porte", complexidade: "Complexidade", risco: "Risco técnico" };
  return (
    <section className="resultado-do-cliente" aria-label="Resultado deste cliente">
      <strong>Resultado só deste grupo{r.pendentes.length ? `, com ${r.pendentes.length} aba${r.pendentes.length > 1 ? "s" : ""} pendente${r.pendentes.length > 1 ? "s" : ""}` : ""}</strong>
      <p className="campo-ajuda">
        {r.pendentes.length > 0 && <>Pendentes ({r.pendentes.map((a) => rotulos[a]).join(", ")}): usada a nota atual da carteira. </>}
        <strong>A carteira não muda</strong>; ela só é atualizada no "Calcular carteira".
      </p>
      <table>
        <tbody>
          <tr><td>Score</td><td>{Number(r.score_antes).toFixed(2).replace(".", ",")} → {Number(r.score_depois).toFixed(2).replace(".", ",")}</td></tr>
          <tr><td>Classe</td><td>{r.classe_antes} → {r.classe_depois}</td></tr>
          {r.notas_antes.rentabilidade !== undefined && r.notas_depois.rentabilidade !== undefined && (
            <tr>
              <td>Nota de rentabilidade (pela margem do CRM)</td>
              <td>{Number(r.notas_antes.rentabilidade).toLocaleString("pt-BR")} → {Number(r.notas_depois.rentabilidade).toLocaleString("pt-BR")}</td>
            </tr>
          )}
          {rent ? (
            <>
              <tr><td>Horas/mês ({rent.porte})</td><td>{Number(rent.horas).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} h</td></tr>
              <tr><td>Margem com o honorário praticado</td><td className={rent.revisao_de_honorarios ? "texto-revisao" : undefined}>{fracaoEmPercentual(rent.margem)}</td></tr>
              <tr><td>Honorário calculado (alvo)</td><td>{dinheiro(rent.honorario_calculado)}</td></tr>
              <tr><td>Honorário praticado</td><td>{dinheiro(rent.honorario_praticado)}</td></tr>
              <tr><td>Defasagem</td><td>{defasagem(rent.defasagem)}</td></tr>
              <tr><td>Revisão de honorários?</td><td className={rent.revisao_de_honorarios ? "texto-revisao" : undefined}>{rent.revisao_de_honorarios ? "Sim, abaixo da mínima" : "Não"}</td></tr>
            </>
          ) : (
            <tr><td colSpan={2}>Sem porte confirmado: não dá para calcular a margem nem o honorário.</td></tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

export function AvaliacaoDeNotas({
  grupoId, grupoNome, notasAtuais, porteAtual, avaliacaoGravada = null, rascunho = null, periodo = null,
  portes, aoFechar, aoMudar,
}: {
  grupoId: number;
  grupoNome: string;
  notasAtuais: NotasDoGrupo;
  porteAtual: PorteDoGrupo;
  avaliacaoGravada?: AvaliacaoGravada | null;
  rascunho?: RascunhoDaAvaliacao | null;
  periodo?: PeriodoDeAvaliacao | null;
  portes: string[];
  aoFechar: () => void;
  /** Depois de salvar: recarrega a lista (status do botão Avaliar) sem fechar o painel. */
  aoMudar: () => void;
}) {
  const [aba, definirAba] = useState<Aba>("complexidade");
  // Abre com o rascunho do período; na falta dele, com a última avaliação gravada (para só revisar).
  const r = rascunho?.respostas;
  const g = avaliacaoGravada?.respostas;
  const porteInicial = r?.porte;
  const [complexidadeMarcada, definirComplexidadeMarcada] = useState<Set<string>>(() => new Set(r?.complexidade ?? g?.complexidade));
  const [riscoMarcado, definirRiscoMarcado] = useState<Set<string>>(() => new Set(r?.risco ?? g?.risco));
  const [crossSellMarcado, definirCrossSellMarcado] = useState<Set<string>>(() => new Set(r?.cross_sell ?? g?.cross_sell));
  const disc = r?.disciplina ?? g?.disciplina;
  const adim = r?.inadimplencia ?? g?.inadimplencia;
  const [mesesNoPrazo, definirMesesNoPrazo] = useState(disc?.meses_no_prazo ?? 3);
  const [cobrancaDobrada, definirCobrancaDobrada] = useState(disc?.cobranca_dobrada ?? false);
  const [atrasoRecorrente, definirAtrasoRecorrente] = useState(disc?.atraso_recorrente ?? false);
  const [mesesEmDia, definirMesesEmDia] = useState(adim?.meses_em_dia ?? 3);
  const [emNegociacao, definirEmNegociacao] = useState(adim?.em_negociacao ?? false);
  const [jaSuspenso, definirJaSuspenso] = useState(adim?.ja_suspenso ?? false);
  const origemDoPorte: Partial<PorteDoGrupo> = porteInicial ?? porteAtual;
  const [volumetria, definirVolumetria] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      DIRECIONADORES_DE_PORTE.map((d) => {
        const valor = origemDoPorte[d.id as keyof PorteDoGrupo];
        return [d.id, valor === null || valor === undefined ? "" : String(valor)];
      }),
    ),
  );
  const [servicosAlem, definirServicosAlem] = useState(origemDoPorte.servicos_contratados_alem_do_primeiro ?? 0);
  const [consolidacaoDeGrupo, definirConsolidacaoDeGrupo] = useState(origemDoPorte.tem_consolidacao_de_grupo ?? false);
  const [auditada, definirAuditada] = useState(origemDoPorte.e_auditada ?? false);
  const [porteConfirmado, definirPorteConfirmado] = useState(porteInicial?.porte ?? porteAtual.porte ?? "");
  const [justificativa, definirJustificativa] = useState(porteInicial?.justificativa ?? porteAtual.porte_justificativa ?? "");
  const [sugestao, definirSugestao] = useState<SugestaoDePorte | null>(null);
  const [buscandoSugestao, definirBuscandoSugestao] = useState(false);
  const [autor, definirAutor] = useState("");
  const [trabalhando, definirTrabalhando] = useState<"salvando" | "calculando" | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [salvoEm, definirSalvoEm] = useState<string | null>(null);
  const [salvas, definirSalvas] = useState<Set<AbaDaAvaliacao>>(() => new Set(rascunho?.preenchidas ?? []));
  const [tocadas, definirTocadas] = useState<Set<AbaDaAvaliacao>>(new Set());
  const [resultado, definirResultado] = useState<SimulacaoDoCliente | null>(null);

  // Uma aba vista (saiu dela, mexeu nela ou está aberta ao salvar) conta como revisada, mesmo sem
  // nada marcado: "nada se aplica" também é resposta.
  const tocar = (a: Aba) => {
    if (preenchivel(a)) definirTocadas((antes) => (antes.has(a) ? antes : new Set(antes).add(a)));
  };
  const irPara = (nova: Aba) => {
    tocar(aba);
    definirAba(nova);
  };

  const alternar = (grupo: "complexidade" | "risco" | "cross_sell") => (id: string) => {
    tocar(grupo);
    const definir = grupo === "complexidade" ? definirComplexidadeMarcada : grupo === "risco" ? definirRiscoMarcado : definirCrossSellMarcado;
    definir((antes) => {
      const novo = new Set(antes);
      if (!novo.delete(id)) novo.add(id);
      return novo;
    });
  };

  const notaComplexidade = notaDeComplexidade(complexidadeMarcada.size);
  const notaRisco = notaDeRisco(riscoMarcado.size);
  const notaDisciplina = notaDeDisciplina(mesesNoPrazo, cobrancaDobrada, atrasoRecorrente);
  const notaCrossSell = notaDeCrossSell(crossSellMarcado.size);
  const notaAdimplencia = notaDeInadimplencia(mesesEmDia, emNegociacao, jaSuspenso);

  const numeroOuVazio = (v: string): number | undefined => (v.trim() === "" ? undefined : Number(v));

  const volumetriaEntrada = (): VolumetriaEntrada => ({
    ...(Object.fromEntries(
      DIRECIONADORES_DE_PORTE.map((d) => [d.id, numeroOuVazio(volumetria[d.id] ?? "")]),
    ) as VolumetriaEntrada),
    servicos_contratados_alem_do_primeiro: servicosAlem,
    tem_consolidacao_de_grupo: consolidacaoDeGrupo,
    e_auditada: auditada,
  });

  const buscarSugestao = async () => {
    definirBuscandoSugestao(true);
    definirErro(null);
    try {
      definirSugestao(await api.sugestaoDePorte(volumetriaEntrada()));
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao calcular a sugestão de porte.");
    } finally {
      definirBuscandoSugestao(false);
    }
  };

  const abasParaSalvar = (): Set<AbaDaAvaliacao> => {
    const todas = new Set(tocadas);
    if (preenchivel(aba)) todas.add(aba);
    return todas;
  };

  const montarRascunho = (abas: Set<AbaDaAvaliacao>): RespostasDoRascunho => ({
    ...(abas.has("complexidade") && { complexidade: [...complexidadeMarcada] }),
    ...(abas.has("risco") && { risco: [...riscoMarcado] }),
    ...(abas.has("cross_sell") && { cross_sell: [...crossSellMarcado] }),
    ...(abas.has("disciplina") && {
      disciplina: { meses_no_prazo: mesesNoPrazo, cobranca_dobrada: cobrancaDobrada, atraso_recorrente: atrasoRecorrente },
    }),
    ...(abas.has("inadimplencia") && {
      inadimplencia: { meses_em_dia: mesesEmDia, em_negociacao: emNegociacao, ja_suspenso: jaSuspenso },
    }),
    ...(abas.has("porte") && {
      porte: { ...volumetriaEntrada(), porte: porteConfirmado, justificativa: justificativa.trim() || null },
    }),
  });

  /** Grava o que foi revisto; devolve false se não deu. */
  const gravar = async (): Promise<boolean> => {
    const abas = abasParaSalvar();
    if (abas.has("porte") && !porteConfirmado) {
      definirErro("Escolha o porte confirmado antes de salvar a aba Porte.");
      return false;
    }
    const salvo = await api.salvarRascunho(grupoId, { autor: autor.trim(), ...montarRascunho(abas) });
    definirSalvas(new Set(salvo.preenchidas));
    definirTocadas(new Set());
    definirSalvoEm(salvo.atualizado_em);
    aoMudar();
    return true;
  };

  const salvarRascunho = async () => {
    definirTrabalhando("salvando");
    definirErro(null);
    try {
      await gravar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar o rascunho.");
    } finally {
      definirTrabalhando(null);
    }
  };

  const calcularCliente = async () => {
    definirTrabalhando("calculando");
    definirErro(null);
    try {
      // O cálculo usa o rascunho gravado: o que está na tela e ainda não foi salvo vai junto.
      if (!(await gravar())) return;
      definirResultado(await api.simularCliente(grupoId));
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao calcular este cliente.");
    } finally {
      definirTrabalhando(null);
    }
  };

  const status = (a: AbaDaAvaliacao) =>
    salvas.has(a) && !tocadas.has(a)
      ? <span className="aba-status aba-status-ok">✓ preenchida</span>
      : tocadas.has(a)
        ? <span className="aba-status aba-status-pendente">✎ não salva</span>
        : <span className="aba-status aba-status-pendente">· pendente</span>;

  const semPeriodo = periodo === null;
  const podeGravar = !semPeriodo && trabalhando === null && autor.trim().length >= 2;

  return (
    <PainelLateral
      titulo={grupoNome}
      subtitulo={
        periodo
          ? `${MES(periodo.mes_de_referencia)} · ${salvas.size} de ${DE_PREENCHER.length} abas preenchidas`
          : "Avalie os sete componentes do Score, um de cada vez, e o porte"
      }
      aoFechar={aoFechar}
      rodape={
        <>
          <label className="campo-bloco" style={{ flex: 1 }}>
            <span className="campo-rotulo">Quem está avaliando</span>
            <input
              className="entrada"
              value={autor}
              onChange={(e) => definirAutor(e.target.value)}
              placeholder="Nome de quem preencheu"
            />
          </label>
          <button type="button" className="botao botao-secundario" onClick={salvarRascunho} disabled={!podeGravar}>
            {trabalhando === "salvando" ? "Salvando…" : "Salvar rascunho"}
          </button>
          <button type="button" className="botao botao-primario" onClick={calcularCliente} disabled={!podeGravar}>
            {trabalhando === "calculando" ? "Calculando…" : "Calcular este cliente"}
          </button>
        </>
      }
    >
      {erro && (
        <div className="estado estado-erro" role="alert">
          <p className="estado-texto">{erro}</p>
        </div>
      )}

      {semPeriodo ? (
        <p className="recado">
          Nenhum período de avaliação aberto. Abra um na Carteira para salvar o rascunho e calcular.
        </p>
      ) : salvoEm || rascunho ? (
        <p className="campo-ajuda">
          Rascunho salvo em {dataHora(salvoEm ?? rascunho!.atualizado_em)}
          {!salvoEm && rascunho ? ` por ${rascunho.atualizado_por}` : ""}. Nada aqui muda a carteira até o "Calcular carteira".
        </p>
      ) : avaliacaoGravada ? (
        <p className="campo-ajuda">
          Os itens já marcados vêm da última avaliação ({dataHora(avaliacaoGravada.registrado_em)}
          {avaliacaoGravada.atribuido_por ? `, por ${avaliacaoGravada.atribuido_por}` : ""}). Revise cada aba e salve.
        </p>
      ) : (
        <p className="recado">
          Este grupo ainda não tem respostas gravadas. Revise e marque cada aba; salve o rascunho quantas vezes precisar.
        </p>
      )}

      <div className="abas abas-avaliacao" role="tablist" aria-label="Componentes do Score e porte">
        {ABAS.map((a) => (
          <button
            key={a.chave}
            type="button"
            role="tab"
            className="aba"
            aria-selected={aba === a.chave}
            onClick={() => irPara(a.chave)}
          >
            {a.rotulo}
            {preenchivel(a.chave) ? status(a.chave) : <span className="aba-status">calculada</span>}
          </button>
        ))}
      </div>

      {aba === "receita" && (
        <section className="avaliacao-secao">
          <h3>Receita (20% do Score)</h3>
          <p className="campo-ajuda" style={{ marginTop: 0 }}>
            Calculada, não avaliada: o Porte do grupo mapeia direto para a nota — Micro=1, Pequeno=2,
            Médio=3, Grande=4, Extra Grande=5 (decisão de 27/09/2026, substitui o corte por percentil
            sobre o honorário praticado). Nada aqui é editável.
          </p>
          <NotaCalculada valor={notasAtuais.receita} />
        </section>
      )}

      {aba === "rentabilidade" && (
        <section className="avaliacao-secao">
          <h3>Rentabilidade (25% do Score)</h3>
          <p className="campo-ajuda" style={{ marginTop: 0 }}>
            Calculada a partir da margem (honorário menos imposto e custo de servir, pelo porte do grupo e pelo
            atrito de complexidade/disciplina/risco). Até o próximo "Calcular carteira" vale a nota abaixo
            {notasAtuais.rentabilidade_da_planilha ? ", que veio da planilha de saúde da carteira" : ""}; a partir
            dele, a nota sai da margem calculada pelo CRM, pela régua de margem dos Parâmetros.
          </p>
          <NotaCalculada valor={notasAtuais.rentabilidade} />
        </section>
      )}

      {aba === "complexidade" && (
        <Checklist
          titulo="Complexidade (12% do Score, entra invertida)"
          fatores={FATORES_COMPLEXIDADE} marcados={complexidadeMarcada}
          aoAlternar={alternar("complexidade")} nota={notaComplexidade}
        />
      )}

      {aba === "risco" && (
        <Checklist
          titulo="Risco técnico (7% do Score, entra invertida)"
          fatores={FATORES_RISCO} marcados={riscoMarcado}
          aoAlternar={alternar("risco")} nota={notaRisco}
        />
      )}

      {aba === "disciplina" && (
        <section className="avaliacao-secao">
          <h3>Disciplina (9% do Score, entra direta)</h3>
          <p className="campo-ajuda" style={{ marginTop: 0 }}>
            Interina, até existir o registro de prazo × entrega por documento.
          </p>
          <label className="campo-bloco">
            <span className="campo-rotulo">
              Nos últimos 3 meses, quantos o cliente entregou tudo no prazo combinado?
            </span>
            <select className="selecao" value={mesesNoPrazo} onChange={(e) => { tocar("disciplina"); definirMesesNoPrazo(Number(e.target.value)); }}>
              <option value={3}>3 — todos no prazo</option>
              <option value={2}>2</option>
              <option value={1}>1</option>
              <option value={0}>0 — nenhum no prazo</option>
            </select>
          </label>
          <label className="avaliacao-item">
            <input type="checkbox" checked={cobrancaDobrada} onChange={(e) => { tocar("disciplina"); definirCobrancaDobrada(e.target.checked); }} />
            Algum documento precisou de mais de uma cobrança para chegar
          </label>
          <label className="avaliacao-item">
            <input type="checkbox" checked={atrasoRecorrente} onChange={(e) => { tocar("disciplina"); definirAtrasoRecorrente(e.target.checked); }} />
            O mesmo documento atrasou mais de uma vez
          </label>
          <p className="recado">
            Nota calculada: <strong>{notaDisciplina}</strong>
          </p>
        </section>
      )}

      {aba === "cross_sell" && (
        <Checklist
          titulo="Cross-sell (12% do Score)"
          ajuda="Proposta de 27/09/2026, aprovada por Eduardo: fato estrutural, sim/não — revisita só quando algo muda (novo contrato, nova empresa do grupo, nova proposta)."
          fatores={FATORES_CROSS_SELL} marcados={crossSellMarcado}
          aoAlternar={alternar("cross_sell")} nota={notaCrossSell}
        />
      )}

      {aba === "inadimplencia" && (
        <section className="avaliacao-secao">
          <h3>Adimplência (15% do Score, trava a classe se ≤ 2)</h3>
          <p className="campo-ajuda" style={{ marginTop: 0 }}>
            Nota alta = paga em dia. Interina (proposta de 27/09/2026): o CRM ainda não registra atraso de
            pagamento, então mede por três perguntas, mesma lógica da Disciplina — até existir o registro automático.
          </p>
          <label className="campo-bloco">
            <span className="campo-rotulo">
              Dos últimos 3 meses, quantos o cliente pagou em dia?
            </span>
            <select className="selecao" value={mesesEmDia} onChange={(e) => { tocar("inadimplencia"); definirMesesEmDia(Number(e.target.value)); }}>
              <option value={3}>3 — todos em dia</option>
              <option value={2}>2</option>
              <option value={1}>1</option>
              <option value={0}>0 — nenhum em dia</option>
            </select>
          </label>
          <label className="avaliacao-item">
            <input type="checkbox" checked={emNegociacao} onChange={(e) => { tocar("inadimplencia"); definirEmNegociacao(e.target.checked); }} />
            Está em negociação ou cobrança agora
          </label>
          <label className="avaliacao-item">
            <input type="checkbox" checked={jaSuspenso} onChange={(e) => { tocar("inadimplencia"); definirJaSuspenso(e.target.checked); }} />
            Já teve contrato suspenso por inadimplência alguma vez
          </label>
          <p className="recado">
            Nota calculada: <strong>{notaAdimplencia}</strong>
            {notaAdimplencia <= 2 && " — trava a classe e marca $$$ (cobrança)"}
          </p>
        </section>
      )}

      {aba === "porte" && (
        <section className="avaliacao-secao">
          <h3>Porte</h3>
          <p className="campo-ajuda" style={{ marginTop: 0 }}>
            Os nove direcionadores do questionário de porte. Em branco, o campo não entra na média — não é
            "zero". A régua sugere; o porte confirmado abaixo é o que vale, e diferente da sugestão pede justificativa.
          </p>
          <div className="formulario-duplo">
            {DIRECIONADORES_DE_PORTE.map((d) => (
              <label key={d.id} className="campo-bloco">
                <span className="campo-rotulo">{d.rotulo}</span>
                <input
                  className="entrada"
                  type="number"
                  min={0}
                  placeholder={d.placeholder}
                  value={volumetria[d.id] ?? ""}
                  onChange={(e) => { tocar("porte"); definirVolumetria((antes) => ({ ...antes, [d.id]: e.target.value })); }}
                />
              </label>
            ))}
          </div>

          <div className="formulario-duplo">
            <label className="campo-bloco">
              <span className="campo-rotulo">Serviços contratados além do primeiro</span>
              <input
                className="entrada" type="number" min={0} value={servicosAlem}
                onChange={(e) => { tocar("porte"); definirServicosAlem(Number(e.target.value)); }}
              />
            </label>
            <div className="campo-bloco">
              <span className="campo-rotulo">Ajustes</span>
              <label className="avaliacao-item">
                <input type="checkbox" checked={consolidacaoDeGrupo} onChange={(e) => { tocar("porte"); definirConsolidacaoDeGrupo(e.target.checked); }} />
                Há consolidação de grupo
              </label>
              <label className="avaliacao-item">
                <input type="checkbox" checked={auditada} onChange={(e) => { tocar("porte"); definirAuditada(e.target.checked); }} />
                Empresa auditada
              </label>
            </div>
          </div>

          <button type="button" className="botao botao-secundario" onClick={buscarSugestao} disabled={buscandoSugestao}>
            {buscandoSugestao ? "Calculando…" : "Ver sugestão"}
          </button>

          {sugestao && (
            <p className="recado">
              {sugestao.calculavel ? (
                <>
                  Sugestão pelo questionário de porte: <strong>{sugestao.porte}</strong> — pontuação{" "}
                  {sugestao.pontuacao?.replace(".", ",")}, {sugestao.horas_base}h base/mês,{" "}
                  {sugestao.direcionadores_aplicados} de 9 direcionadores preenchidos.
                </>
              ) : (
                "Sugestão da régua: não calculável — nenhum direcionador preenchido ainda."
              )}
            </p>
          )}

          <label className="campo-bloco">
            <span className="campo-rotulo">Porte confirmado</span>
            <select className="selecao" value={porteConfirmado} onChange={(e) => { tocar("porte"); definirPorteConfirmado(e.target.value); }}>
              <option value="">— não confirmado —</option>
              {portes.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          {sugestao?.calculavel && porteConfirmado !== sugestao.porte && (
            <button
              type="button" className="botao botao-secundario"
              onClick={() => { tocar("porte"); definirPorteConfirmado(sugestao.porte ?? ""); }}
            >
              Usar sugestão ({sugestao.porte})
            </button>
          )}
          <label className="campo-bloco">
            <span className="campo-rotulo">Justificativa (obrigatória se o porte for diferente da sugestão do questionário)</span>
            <textarea
              className="entrada"
              rows={3}
              maxLength={500}
              value={justificativa}
              onChange={(e) => { tocar("porte"); definirJustificativa(e.target.value); }}
            />
          </label>
        </section>
      )}

      {resultado && <ResultadoDoCliente r={resultado} />}
    </PainelLateral>
  );
}
