/** O período de avaliação na Carteira: abrir, acompanhar quem falta e calcular a carteira inteira
 * (29/09/2026). O "Calcular carteira" só libera com todos os grupos completos. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { JanelaDeRentabilidade, PeriodoDeAvaliacao } from "../api/tipos";
import { fracaoEmPercentual } from "../formato";

const MES = (iso: string) => `${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
const mesAtual = () => new Date().toISOString().slice(0, 7);

export function FaixaDoPeriodo({
  periodo, janela, aoMudar,
}: {
  periodo: PeriodoDeAvaliacao | null;
  janela: JanelaDeRentabilidade | null;
  aoMudar: () => void;
}) {
  const [autor, definirAutor] = useState("");
  const [mes, definirMes] = useState(mesAtual);
  const [confirmando, definirConfirmando] = useState(false);
  const [trabalhando, definirTrabalhando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  const executar = async (acao: () => Promise<string>) => {
    definirTrabalhando(true);
    definirErro(null);
    try {
      definirFeito(await acao());
      aoMudar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao falar com o servidor.");
    } finally {
      definirTrabalhando(false);
      definirConfirmando(false);
    }
  };

  const autorOk = autor.trim().length >= 2;
  const campoAutor = (
    <label className="campo">
      <span className="campo-rotulo">Quem está fazendo</span>
      <input className="entrada" value={autor} onChange={(e) => definirAutor(e.target.value)} placeholder="Seu nome" />
    </label>
  );

  if (periodo === null) {
    return (
      <section className="periodo-faixa" aria-label="Período de avaliação">
        <div>
          <span className="campo-rotulo">Período de avaliação</span>
          <p className="periodo-titulo">Nenhum período aberto</p>
          {janela && (
            <p className="campo-ajuda">
              Janela de rentabilidade {janela.origem === "padrão" ? "inicial" : "do último período"}: mínimo{" "}
              {fracaoEmPercentual(janela.margem_minima, 0)} · alvo {fracaoEmPercentual(janela.margem_alvo, 0)} (ajustável depois de abrir).
            </p>
          )}
          {feito && <p className="campo-ajuda" role="status">{feito}</p>}
        </div>
        <div className="periodo-acoes">
          <label className="campo">
            <span className="campo-rotulo">Mês</span>
            <input className="entrada" type="month" value={mes} onChange={(e) => definirMes(e.target.value)} />
          </label>
          {campoAutor}
          <button
            type="button" className="botao botao-secundario" disabled={!autorOk || !mes || trabalhando}
            onClick={() => executar(async () => {
              const p = await api.abrirPeriodo({ autor: autor.trim(), mes });
              return `Período ${MES(p.mes_de_referencia)} aberto.`;
            })}
          >
            Abrir período
          </button>
        </div>
        {erro && <p className="periodo-erro" role="alert">{erro}</p>}
      </section>
    );
  }

  const faltam = periodo.grupos - periodo.completos;
  const nomes = periodo.pendentes.slice(0, 6).map((p) =>
    `${p.grupo_nome}${p.novo ? ", novo" : ""} (${p.preenchidas === 0 ? "vazio" : `${p.preenchidas} de ${p.abas ?? periodo.abas}`})`,
  );
  const resto = periodo.pendentes.length - nomes.length;

  return (
    <section className="periodo-faixa" aria-label="Período de avaliação">
      <div>
        <span className="campo-rotulo">Período de avaliação</span>
        <p className="periodo-titulo">{MES(periodo.mes_de_referencia)} · aberto</p>
        <p className="campo-ajuda">
          Janela de rentabilidade: <strong>mínimo {fracaoEmPercentual(periodo.margem_minima, 0)}</strong> ·{" "}
          <strong>alvo {fracaoEmPercentual(periodo.margem_alvo, 0)}</strong>
        </p>
      </div>
      <div className="periodo-acoes">
        {faltam > 0 ? (
          <p className="periodo-faltam">
            Faltam {faltam} de {periodo.grupos} grupos: {nomes.join(", ")}
            {resto > 0 ? ` e mais ${resto}` : ""}
          </p>
        ) : (
          <p className="periodo-completo">✓ Todos os {periodo.grupos} grupos completos</p>
        )}
        {campoAutor}
        {confirmando ? (
          <button
            type="button" className="botao botao-primario" disabled={trabalhando}
            onClick={() => executar(async () => {
              const r = await api.calcularCarteira(autor.trim());
              return `Carteira calculada: ${r.grupos_calculados} grupos, período ${MES(r.periodo.mes_de_referencia)} fechado.`;
            })}
          >
            {trabalhando ? "Calculando…" : `Confirmar: recalcular os ${periodo.grupos} grupos`}
          </button>
        ) : (
          <button
            type="button" className="botao botao-primario" disabled={faltam > 0 || !autorOk}
            title={faltam > 0 ? "Só libera com todos os grupos completos" : undefined}
            onClick={() => definirConfirmando(true)}
          >
            Calcular carteira
          </button>
        )}
      </div>
      {erro && <p className="periodo-erro" role="alert">{erro}</p>}
    </section>
  );
}
