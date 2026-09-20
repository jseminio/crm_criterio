/** Os quatro estados que o PAD-002 exige de toda lista.
 *
 * "Toda lista tem quatro estados: carregando, vazio sem dados, vazio por
 * filtro, erro com tentar de novo." Separar vazio-sem-dados de vazio-por-filtro
 * não é preciosismo: são problemas diferentes. O primeiro se resolve
 * cadastrando, o segundo limpando filtro — e dizer "nada encontrado" nos dois
 * casos manda a pessoa para o lado errado.
 */

import type { ReactNode } from "react";

export function Carregando({ rotulo = "Carregando" }: { rotulo?: string }) {
  return (
    <div className="estado" role="status" aria-live="polite">
      <div className="esqueleto-linhas" aria-hidden="true">
        <span /> <span /> <span />
      </div>
      <p className="estado-texto">{rotulo}…</p>
    </div>
  );
}

export function VazioSemDados({
  titulo,
  explicacao,
  acao,
}: {
  titulo: string;
  explicacao: string;
  acao?: ReactNode;
}) {
  return (
    <div className="estado">
      <h3 className="estado-titulo">{titulo}</h3>
      <p className="estado-texto">{explicacao}</p>
      {acao}
    </div>
  );
}

export function VazioPorFiltro({ aoLimpar }: { aoLimpar: () => void }) {
  return (
    <div className="estado">
      <h3 className="estado-titulo">Nenhum resultado para esses filtros</h3>
      <p className="estado-texto">
        Existem registros na base — eles só não passam pelos filtros de agora.
      </p>
      <button type="button" className="botao botao-secundario" onClick={aoLimpar}>
        Limpar filtros
      </button>
    </div>
  );
}

export function Erro({ mensagem, aoTentarDeNovo }: { mensagem: string; aoTentarDeNovo: () => void }) {
  return (
    <div className="estado estado-erro" role="alert">
      <h3 className="estado-titulo">Não consegui carregar</h3>
      <p className="estado-texto">{mensagem}</p>
      <button type="button" className="botao botao-secundario" onClick={aoTentarDeNovo}>
        Tentar de novo
      </button>
    </div>
  );
}
