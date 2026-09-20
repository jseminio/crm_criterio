/** A barra de filtros, compartilhada pelo kanban e pela lista.
 *
 * Os valores vêm de `/api/listas`: o servidor é a única fonte das listas
 * controladas.
 */

import type { Listas } from "../api/tipos";

export interface EstadoDosFiltros {
  busca: string;
  captador: string;
  tipo_canal: string;
  temperatura: string;
}

export const FILTROS_VAZIOS: EstadoDosFiltros = {
  busca: "",
  captador: "",
  tipo_canal: "",
  temperatura: "",
};

export function temFiltro(filtros: EstadoDosFiltros): boolean {
  return Object.values(filtros).some((v) => v !== "");
}

/** Converte para o formato que a API espera: ausente em vez de vazio. */
export function paraConsulta(filtros: EstadoDosFiltros) {
  return {
    busca: filtros.busca || undefined,
    captador: filtros.captador ? [filtros.captador] : undefined,
    tipo_canal: filtros.tipo_canal ? [filtros.tipo_canal] : undefined,
    temperatura: filtros.temperatura ? [filtros.temperatura] : undefined,
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
