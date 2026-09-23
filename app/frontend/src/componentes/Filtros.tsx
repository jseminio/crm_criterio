/** A barra de filtros, compartilhada pelo kanban e pela lista.
 *
 * Os valores vêm de `/api/listas`: o servidor é a única fonte das listas
 * controladas.
 */

import type { Listas } from "../api/tipos";
import { PRESETS, resolverPeriodo, type Preset } from "../periodo";

export interface EstadoDosFiltros {
  busca: string;
  captador: string;
  tipo_canal: string;
  temperatura: string;
  servico: string;
  dataTipo: "colocacao" | "aceite";
  periodo: Preset | "";
  dataDe: string;
  dataAte: string;
}

export const FILTROS_VAZIOS: EstadoDosFiltros = {
  busca: "",
  captador: "",
  tipo_canal: "",
  temperatura: "",
  servico: "",
  dataTipo: "colocacao",
  periodo: "",
  dataDe: "",
  dataAte: "",
};

/** `dataTipo` sozinho não conta: é o acompanhante do período, não um filtro
 * em si — só passa a valer quando um período é escolhido. */
export function temFiltro(filtros: EstadoDosFiltros): boolean {
  return (
    filtros.busca !== "" ||
    filtros.captador !== "" ||
    filtros.tipo_canal !== "" ||
    filtros.temperatura !== "" ||
    filtros.servico !== "" ||
    filtros.periodo !== ""
  );
}

/** Converte para o formato que a API espera: ausente em vez de vazio.
 *
 * Um atalho ("Este trimestre") vira datas concretas aqui, no navegador — a
 * API só entende De/Até, nunca o nome do atalho.
 */
export function paraConsulta(filtros: EstadoDosFiltros) {
  const intervalo =
    filtros.periodo === "personalizado"
      ? { de: filtros.dataDe || undefined, ate: filtros.dataAte || undefined }
      : filtros.periodo
        ? resolverPeriodo(filtros.periodo)
        : null;

  return {
    busca: filtros.busca || undefined,
    captador: filtros.captador ? [filtros.captador] : undefined,
    tipo_canal: filtros.tipo_canal ? [filtros.tipo_canal] : undefined,
    temperatura: filtros.temperatura ? [filtros.temperatura] : undefined,
    servico: filtros.servico ? [filtros.servico] : undefined,
    data_tipo: intervalo ? filtros.dataTipo : undefined,
    data_de: intervalo?.de,
    data_ate: intervalo?.ate,
  };
}

export function Filtros({
  filtros,
  aoMudar,
  listas,
  acao,
}: {
  filtros: EstadoDosFiltros;
  aoMudar: (novos: EstadoDosFiltros) => void;
  listas: Listas | null;
  acao?: React.ReactNode;
}) {
  const mudar = (campo: keyof EstadoDosFiltros) => (evento: { target: { value: string } }) =>
    aoMudar({ ...filtros, [campo]: evento.target.value });

  return (
    <div className="filtros">
      <div className="campo">
        <label className="campo-rotulo" htmlFor="filtro-busca">
          Buscar
        </label>
        <input
          id="filtro-busca"
          className="entrada entrada-busca"
          placeholder="Cliente ou nome da oportunidade"
          value={filtros.busca}
          onChange={mudar("busca")}
        />
      </div>

      <div className="campo">
        <label className="campo-rotulo" htmlFor="filtro-captador">
          Captador
        </label>
        <select
          id="filtro-captador"
          className="selecao"
          value={filtros.captador}
          onChange={mudar("captador")}
        >
          <option value="">Todos</option>
          {listas?.captadores.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div className="campo">
        <label className="campo-rotulo" htmlFor="filtro-canal">
          Tipo de canal
        </label>
        <select
          id="filtro-canal"
          className="selecao"
          value={filtros.tipo_canal}
          onChange={mudar("tipo_canal")}
        >
          <option value="">Todos</option>
          {listas?.tipos_de_canal.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>

      <div className="campo">
        <label className="campo-rotulo" htmlFor="filtro-servico">
          Serviço
        </label>
        <select
          id="filtro-servico"
          className="selecao"
          value={filtros.servico}
          onChange={mudar("servico")}
        >
          <option value="">Todos</option>
          {listas?.servicos.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div className="campo">
        <label className="campo-rotulo" htmlFor="filtro-temperatura">
          Temperatura
        </label>
        <select
          id="filtro-temperatura"
          className="selecao"
          value={filtros.temperatura}
          onChange={mudar("temperatura")}
        >
          <option value="">Todas</option>
          {listas?.temperaturas.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      <div className="campo">
        <label className="campo-rotulo" htmlFor="filtro-periodo">
          Período
        </label>
        <select
          id="filtro-periodo"
          className="selecao"
          value={filtros.periodo}
          onChange={mudar("periodo")}
        >
          <option value="">Todo o período</option>
          {PRESETS.map((p) => (
            <option key={p.valor} value={p.valor}>
              {p.rotulo}
            </option>
          ))}
        </select>
      </div>

      {filtros.periodo !== "" && (
        <div className="campo">
          <label className="campo-rotulo" htmlFor="filtro-data-tipo">
            Data de
          </label>
          <select
            id="filtro-data-tipo"
            className="selecao"
            value={filtros.dataTipo}
            onChange={mudar("dataTipo")}
          >
            <option value="colocacao">Originação</option>
            <option value="aceite">Aceite</option>
          </select>
        </div>
      )}

      {filtros.periodo === "personalizado" && (
        <>
          <div className="campo">
            <label className="campo-rotulo" htmlFor="filtro-data-de">
              De
            </label>
            <input
              id="filtro-data-de"
              type="date"
              className="entrada"
              value={filtros.dataDe}
              onChange={mudar("dataDe")}
            />
          </div>
          <div className="campo">
            <label className="campo-rotulo" htmlFor="filtro-data-ate">
              Até
            </label>
            <input
              id="filtro-data-ate"
              type="date"
              className="entrada"
              value={filtros.dataAte}
              onChange={mudar("dataAte")}
            />
          </div>
        </>
      )}

      {temFiltro(filtros) && (
        <button
          type="button"
          className="botao botao-secundario"
          onClick={() => aoMudar(FILTROS_VAZIOS)}
        >
          Limpar filtros
        </button>
      )}

      {acao && <div style={{ marginLeft: "auto" }}>{acao}</div>}
    </div>
  );
}
