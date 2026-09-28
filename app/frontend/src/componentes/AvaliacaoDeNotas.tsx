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
import type { NotasDoGrupo, PorteDoGrupo, SugestaoDePorte, VolumetriaEntrada } from "../api/tipos";
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

function notaDeRisco(sims: number): number {
  if (sims === 0) return 5;
  if (sims === 1) return 4;
  if (sims === 2) return 3;
  if (sims === 3) return 2;
  return 1;
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
  { chave: "inadimplencia", rotulo: "Inadimplência" },
  { chave: "porte", rotulo: "Porte" },
] as const;
type Aba = (typeof ABAS)[number]["chave"];

export function AvaliacaoDeNotas({
  grupoId, grupoNome, notasAtuais, porteAtual, portes, aoFechar, aoSalvar,
}: {
  grupoId: number;
  grupoNome: string;
  notasAtuais: NotasDoGrupo;
  porteAtual: PorteDoGrupo;
  portes: string[];
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const [aba, definirAba] = useState<Aba>("complexidade");
  const [complexidadeMarcada, definirComplexidadeMarcada] = useState<Set<string>>(new Set());
  const [riscoMarcado, definirRiscoMarcado] = useState<Set<string>>(new Set());
  const [crossSellMarcado, definirCrossSellMarcado] = useState<Set<string>>(new Set());
  const [mesesNoPrazo, definirMesesNoPrazo] = useState(3);
  const [cobrancaDobrada, definirCobrancaDobrada] = useState(false);
  const [atrasoRecorrente, definirAtrasoRecorrente] = useState(false);
  const [mesesEmDia, definirMesesEmDia] = useState(3);
  const [emNegociacao, definirEmNegociacao] = useState(false);
  const [jaSuspenso, definirJaSuspenso] = useState(false);
  const [volumetria, definirVolumetria] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      DIRECIONADORES_DE_PORTE.map((d) => {
        const valor = porteAtual[d.id as keyof PorteDoGrupo];
        return [d.id, valor === null || valor === undefined ? "" : String(valor)];
      }),
    ),
  );
  const [servicosAlem, definirServicosAlem] = useState(porteAtual.servicos_contratados_alem_do_primeiro ?? 0);
  const [consolidacaoDeGrupo, definirConsolidacaoDeGrupo] = useState(porteAtual.tem_consolidacao_de_grupo ?? false);
  const [auditada, definirAuditada] = useState(porteAtual.e_auditada ?? false);
  const [porteConfirmado, definirPorteConfirmado] = useState(porteAtual.porte ?? "");
  const [sugestao, definirSugestao] = useState<SugestaoDePorte | null>(null);
  const [buscandoSugestao, definirBuscandoSugestao] = useState(false);
  const [autor, definirAutor] = useState("");
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  const alternar = (grupo: "complexidade" | "risco" | "cross_sell") => (id: string) => {
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
  const notaInadimplencia = notaDeInadimplencia(mesesEmDia, emNegociacao, jaSuspenso);

  const motivo = () => {
    const partes = [
      `Complexidade ${notaComplexidade} (${complexidadeMarcada.size}/${FATORES_COMPLEXIDADE.length}` +
        (complexidadeMarcada.size ? ": " + FATORES_COMPLEXIDADE.filter((f) => complexidadeMarcada.has(f.id)).map((f) => f.curto).join("; ") : "") + ")",
      `Risco técnico ${notaRisco} (${riscoMarcado.size}/${FATORES_RISCO.length}` +
        (riscoMarcado.size ? ": " + FATORES_RISCO.filter((f) => riscoMarcado.has(f.id)).map((f) => f.curto).join("; ") : "") + ")",
      `Disciplina ${notaDisciplina} (${mesesNoPrazo}/3 meses no prazo` +
        (cobrancaDobrada ? ", com cobrança dobrada" : "") + (atrasoRecorrente ? ", com atraso recorrente" : "") + ")",
      `Cross-sell ${notaCrossSell} (${crossSellMarcado.size}/${FATORES_CROSS_SELL.length}` +
        (crossSellMarcado.size ? ": " + FATORES_CROSS_SELL.filter((f) => crossSellMarcado.has(f.id)).map((f) => f.curto).join("; ") : "") + ")",
      `Inadimplência ${notaInadimplencia} (${mesesEmDia}/3 meses em dia` +
        (emNegociacao ? ", em negociação/cobrança" : "") + (jaSuspenso ? ", já teve contrato suspenso" : "") + ")",
    ];
    return partes.join(". ").slice(0, 500);
  };

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

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await api.editarNotasDaCarteira(grupoId, {
        autor: autor.trim(), motivo: motivo(),
        complexidade: notaComplexidade, disciplina: notaDisciplina, risco: notaRisco,
        cross_sell: notaCrossSell, adimplencia: notaInadimplencia,
      });
      await api.editarPorte(grupoId, {
        autor: autor.trim(), ...volumetriaEntrada(),
        porte: porteConfirmado || undefined,
      });
      aoSalvar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar a avaliação.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <PainelLateral
      titulo={grupoNome}
      subtitulo="Avalie os sete componentes do Score, um de cada vez, e o porte"
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
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>
            Cancelar
          </button>
          <button
            type="button"
            className="botao botao-primario"
            onClick={salvar}
            disabled={salvando || autor.trim().length < 2}
          >
            {salvando ? "Salvando…" : "Salvar avaliação"}
          </button>
        </>
      }
    >
      {erro && (
        <div className="estado estado-erro" role="alert">
          <p className="estado-texto">{erro}</p>
        </div>
      )}

      <div className="abas abas-avaliacao" role="tablist" aria-label="Componentes do Score e porte">
        {ABAS.map((a) => (
          <button
            key={a.chave}
            type="button"
            role="tab"
            className="aba"
            aria-selected={aba === a.chave}
            onClick={() => definirAba(a.chave)}
          >
            {a.rotulo}
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
            Calculada a partir da margem (honorário menos custo de servir, pelo porte e pelo atrito de
            complexidade/disciplina/risco). {notasAtuais.rentabilidade_da_planilha
              ? "Esta unidade ainda usa a nota da planilha de saúde da carteira (os honorários por empresa não fecham com a receita oficial)."
              : "Recalculada pelo CRM, com a disciplina invertida (correção do defeito 7.2)."}
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
            <select className="selecao" value={mesesNoPrazo} onChange={(e) => definirMesesNoPrazo(Number(e.target.value))}>
              <option value={3}>3 — todos no prazo</option>
              <option value={2}>2</option>
              <option value={1}>1</option>
              <option value={0}>0 — nenhum no prazo</option>
            </select>
          </label>
          <label className="avaliacao-item">
            <input type="checkbox" checked={cobrancaDobrada} onChange={(e) => definirCobrancaDobrada(e.target.checked)} />
            Algum documento precisou de mais de uma cobrança para chegar
          </label>
          <label className="avaliacao-item">
            <input type="checkbox" checked={atrasoRecorrente} onChange={(e) => definirAtrasoRecorrente(e.target.checked)} />
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
          <h3>Inadimplência (15% do Score, trava a classe se ≤ 2)</h3>
          <p className="campo-ajuda" style={{ marginTop: 0 }}>
            Interina (proposta de 27/09/2026): o CRM ainda não registra atraso de pagamento, então mede
            por três perguntas, mesma lógica da Disciplina — até existir o registro automático.
          </p>
          <label className="campo-bloco">
            <span className="campo-rotulo">
              Dos últimos 3 meses, quantos o cliente pagou em dia?
            </span>
            <select className="selecao" value={mesesEmDia} onChange={(e) => definirMesesEmDia(Number(e.target.value))}>
              <option value={3}>3 — todos em dia</option>
              <option value={2}>2</option>
              <option value={1}>1</option>
              <option value={0}>0 — nenhum em dia</option>
            </select>
          </label>
          <label className="avaliacao-item">
            <input type="checkbox" checked={emNegociacao} onChange={(e) => definirEmNegociacao(e.target.checked)} />
            Está em negociação ou cobrança agora
          </label>
          <label className="avaliacao-item">
            <input type="checkbox" checked={jaSuspenso} onChange={(e) => definirJaSuspenso(e.target.checked)} />
            Já teve contrato suspenso por inadimplência alguma vez
          </label>
          <p className="recado">
            Nota calculada: <strong>{notaInadimplencia}</strong>
            {notaInadimplencia <= 2 && " — trava a classe e marca $$$ (cobrança)"}
          </p>
        </section>
      )}

      {aba === "porte" && (
        <section className="avaliacao-secao">
          <h3>Porte</h3>
          <p className="campo-ajuda" style={{ marginTop: 0 }}>
            Os nove direcionadores da régua de volume. Em branco, o campo não entra na média — não é
            "zero". A régua sugere; o porte confirmado abaixo é o que vale.
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
                  onChange={(e) => definirVolumetria((antes) => ({ ...antes, [d.id]: e.target.value }))}
                />
              </label>
            ))}
          </div>

          <div className="formulario-duplo">
            <label className="campo-bloco">
              <span className="campo-rotulo">Serviços contratados além do primeiro</span>
              <input
                className="entrada" type="number" min={0} value={servicosAlem}
                onChange={(e) => definirServicosAlem(Number(e.target.value))}
              />
            </label>
            <div className="campo-bloco">
              <span className="campo-rotulo">Ajustes</span>
              <label className="avaliacao-item">
                <input type="checkbox" checked={consolidacaoDeGrupo} onChange={(e) => definirConsolidacaoDeGrupo(e.target.checked)} />
                Há consolidação de grupo
              </label>
              <label className="avaliacao-item">
                <input type="checkbox" checked={auditada} onChange={(e) => definirAuditada(e.target.checked)} />
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
                  Sugestão da régua: <strong>{sugestao.porte}</strong> — pontuação{" "}
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
            <select className="selecao" value={porteConfirmado} onChange={(e) => definirPorteConfirmado(e.target.value)}>
              <option value="">— não confirmado —</option>
              {portes.map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </label>
          {sugestao?.calculavel && porteConfirmado !== sugestao.porte && (
            <button
              type="button" className="botao botao-secundario"
              onClick={() => definirPorteConfirmado(sugestao.porte ?? "")}
            >
              Usar sugestão ({sugestao.porte})
            </button>
          )}
        </section>
      )}
    </PainelLateral>
  );
}
