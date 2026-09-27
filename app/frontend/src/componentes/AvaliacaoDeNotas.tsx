/** Avalia complexidade, risco técnico e disciplina de um grupo por checklist, não por nota "no olho".
 *
 * Régua em `escala-das-notas-humanas.md` (raiz do projeto). Cada seção conta quantos fatores
 * marcados "sim" e calcula a nota 1–5 sozinha — quem preenche marca fato observável, não escolhe
 * número. O motivo enviado ao servidor é montado a partir do que foi marcado: fica registrado sem
 * exigir texto livre de quem avalia.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { SugestaoDePorte, VolumetriaEntrada } from "../api/tipos";
import { DIRECIONADORES_DE_PORTE, PORTES } from "./direcionadoresDePorte";
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

function notaDeDisciplina(mesesNoPrazo: number, cobrancaDobrada: boolean, atrasoRecorrente: boolean): number {
  const furos = (3 - mesesNoPrazo) + (cobrancaDobrada ? 1 : 0) + (atrasoRecorrente ? 1 : 0);
  return Math.max(1, 5 - furos);
}

function Checklist({
  titulo, fatores, marcados, aoAlternar, nota,
}: {
  titulo: string;
  fatores: readonly { id: string; rotulo: string }[];
  marcados: Set<string>;
  aoAlternar: (id: string) => void;
  nota: number;
}) {
  return (
    <section className="avaliacao-secao">
      <h3>{titulo}</h3>
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

export function AvaliacaoDeNotas({
  grupoId, grupoNome, aoFechar, aoSalvar,
}: {
  grupoId: number;
  grupoNome: string;
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const [complexidadeMarcada, definirComplexidadeMarcada] = useState<Set<string>>(new Set());
  const [riscoMarcado, definirRiscoMarcado] = useState<Set<string>>(new Set());
  const [mesesNoPrazo, definirMesesNoPrazo] = useState(3);
  const [cobrancaDobrada, definirCobrancaDobrada] = useState(false);
  const [atrasoRecorrente, definirAtrasoRecorrente] = useState(false);
  const [volumetria, definirVolumetria] = useState<Record<string, string>>({});
  const [servicosAlem, definirServicosAlem] = useState(0);
  const [consolidacaoDeGrupo, definirConsolidacaoDeGrupo] = useState(false);
  const [auditada, definirAuditada] = useState(false);
  const [porteConfirmado, definirPorteConfirmado] = useState("");
  const [sugestao, definirSugestao] = useState<SugestaoDePorte | null>(null);
  const [buscandoSugestao, definirBuscandoSugestao] = useState(false);
  const [autor, definirAutor] = useState("");
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  const alternar = (grupo: "complexidade" | "risco") => (id: string) => {
    const definir = grupo === "complexidade" ? definirComplexidadeMarcada : definirRiscoMarcado;
    definir((antes) => {
      const novo = new Set(antes);
      if (!novo.delete(id)) novo.add(id);
      return novo;
    });
  };

  const notaComplexidade = notaDeComplexidade(complexidadeMarcada.size);
  const notaRisco = notaDeRisco(riscoMarcado.size);
  const notaDisciplina = notaDeDisciplina(mesesNoPrazo, cobrancaDobrada, atrasoRecorrente);

  const motivo = () => {
    const partes = [
      `Complexidade ${notaComplexidade} (${complexidadeMarcada.size}/${FATORES_COMPLEXIDADE.length}` +
        (complexidadeMarcada.size ? ": " + FATORES_COMPLEXIDADE.filter((f) => complexidadeMarcada.has(f.id)).map((f) => f.curto).join("; ") : "") + ")",
      `Risco técnico ${notaRisco} (${riscoMarcado.size}/${FATORES_RISCO.length}` +
        (riscoMarcado.size ? ": " + FATORES_RISCO.filter((f) => riscoMarcado.has(f.id)).map((f) => f.curto).join("; ") : "") + ")",
      `Disciplina ${notaDisciplina} (${mesesNoPrazo}/3 meses no prazo` +
        (cobrancaDobrada ? ", com cobrança dobrada" : "") + (atrasoRecorrente ? ", com atraso recorrente" : "") + ")",
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
      subtitulo="Avaliar complexidade, risco técnico, disciplina e porte"
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

      <Checklist
        titulo="Complexidade" fatores={FATORES_COMPLEXIDADE} marcados={complexidadeMarcada}
        aoAlternar={alternar("complexidade")} nota={notaComplexidade}
      />
      <Checklist
        titulo="Risco técnico" fatores={FATORES_RISCO} marcados={riscoMarcado}
        aoAlternar={alternar("risco")} nota={notaRisco}
      />

      <section className="avaliacao-secao">
        <h3>Disciplina (interina, até existir o registro de prazo × entrega)</h3>
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
            {PORTES.map((p) => <option key={p} value={p}>{p}</option>)}
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
    </PainelLateral>
  );
}
