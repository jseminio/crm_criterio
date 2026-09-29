/** "Janela de rentabilidade desejada" dentro de Parâmetros de cálculo: margem mínima e alvo do
 * período aberto (29/09/2026). O alvo define o honorário calculado; abaixo da mínima, o grupo entra
 * em "Revisão de honorários". */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { JanelaDeRentabilidade as Janela, PeriodoDeAvaliacao } from "../api/tipos";
import { fracaoEmPercentual } from "../formato";

const emPercentual = (fracao: string) => String(Math.round(Number(fracao) * 1000) / 10);

export function JanelaDeRentabilidade({
  periodo, janela, aoMudar,
}: {
  periodo: PeriodoDeAvaliacao | null;
  janela: Janela | null;
  aoMudar: () => void;
}) {
  const [minima, definirMinima] = useState(() => emPercentual(periodo?.margem_minima ?? janela?.margem_minima ?? "0.6"));
  const [alvo, definirAlvo] = useState(() => emPercentual(periodo?.margem_alvo ?? janela?.margem_alvo ?? "0.7"));
  const [autor, definirAutor] = useState("");
  const [erro, definirErro] = useState<string | null>(null);
  const [salvo, definirSalvo] = useState(false);

  const titulo = periodo ? `Janela de rentabilidade desejada · ${periodo.mes_de_referencia.slice(5, 7)}/${periodo.mes_de_referencia.slice(0, 4)}` : "Janela de rentabilidade desejada";

  if (!periodo) {
    return (
      <section className="parametros-grupo" aria-label="Janela de rentabilidade desejada">
        <h3>{titulo}</h3>
        <p className="campo-ajuda">
          Em uso agora: mínimo {fracaoEmPercentual(janela?.margem_minima, 0)} · alvo {fracaoEmPercentual(janela?.margem_alvo, 0)}
          {janela?.origem === "padrão" ? " (padrão)" : " (do último período)"}. Para mudar, abra um período de avaliação na Carteira.
        </p>
      </section>
    );
  }

  const salvar = async () => {
    definirErro(null);
    definirSalvo(false);
    try {
      await api.editarJanela({ autor: autor.trim(), margem_minima: Number(minima) / 100, margem_alvo: Number(alvo) / 100 });
      definirSalvo(true);
      aoMudar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar a janela.");
    }
  };

  return (
    <section className="parametros-grupo" aria-label="Janela de rentabilidade desejada">
      <h3>{titulo}</h3>
      <p className="campo-ajuda">
        O <strong>alvo</strong> define o honorário calculado. Abaixo da <strong>mínima</strong>, o grupo entra em
        "Revisão de honorários". Honorário calculado = custo ÷ (1 − imposto − alvo).
      </p>
      <div className="formulario-duplo">
        <label className="campo-bloco">
          <span className="campo-rotulo">Margem mínima (%)</span>
          <input className="entrada" type="number" min={1} max={99} step={0.5} value={minima} onChange={(e) => definirMinima(e.target.value)} />
        </label>
        <label className="campo-bloco">
          <span className="campo-rotulo">Margem alvo (%)</span>
          <input className="entrada" type="number" min={1} max={99} step={0.5} value={alvo} onChange={(e) => definirAlvo(e.target.value)} />
        </label>
        <label className="campo-bloco">
          <span className="campo-rotulo">Quem está alterando</span>
          <input className="entrada" value={autor} onChange={(e) => definirAutor(e.target.value)} />
        </label>
      </div>
      <button type="button" className="botao botao-secundario" disabled={autor.trim().length < 2} onClick={salvar}>
        Salvar janela
      </button>
      {salvo && <p className="campo-ajuda" role="status">Janela salva.</p>}
      {erro && <p className="periodo-erro" role="alert">{erro}</p>}
    </section>
  );
}
