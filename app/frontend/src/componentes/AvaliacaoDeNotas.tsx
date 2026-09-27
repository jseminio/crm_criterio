/** Avalia complexidade, risco técnico e disciplina de um grupo por checklist, não por nota "no olho".
 *
 * Régua em `escala-das-notas-humanas.md` (raiz do projeto). Cada seção conta quantos fatores
 * marcados "sim" e calcula a nota 1–5 sozinha — quem preenche marca fato observável, não escolhe
 * número. O motivo enviado ao servidor é montado a partir do que foi marcado: fica registrado sem
 * exigir texto livre de quem avalia.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
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

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await api.editarNotasDaCarteira(grupoId, {
        autor: autor.trim(), motivo: motivo(),
        complexidade: notaComplexidade, disciplina: notaDisciplina, risco: notaRisco,
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
      subtitulo="Avaliar complexidade, risco técnico e disciplina"
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
    </PainelLateral>
  );
}
