/** Agenda › Questionários que precisam de você (aprovado por Eduardo em 02/10/2026). A busca
 * automática não duplica oportunidade: se o grupo já tem uma em aberto, o questionário espera alguém
 * escolher "Mesclar com existente" ou "Criar nova" (mescla desde 15/10/2026). Só aparece quando há algum, e só para quem resolve. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { QuestionarioResumo } from "../api/tipos";
import { cnpj, dataHora } from "../formato";
import { usarDados } from "../usarDados";
import { BotaoMesclar } from "./MesclarQuestionario";

const PRECISA = "Precisa de você";

export function QuestionariosQuePrecisam() {
  const { dados, recarregar } = usarDados<QuestionarioResumo[]>(() => api.questionarios(), []);
  const [erro, definirErro] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);
  const pendentes = (dados ?? []).filter((q) => q.situacao === PRECISA);
  if (pendentes.length === 0 && !feito) return null;

  const resolver = async (q: QuestionarioResumo, acao: "criar") => {
    definirErro(null);
    try {
      await api.resolverQuestionario(q.id, acao);
      definirFeito(`Questionário de ${q.razao_social} virou uma oportunidade nova.`);
      recarregar();
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao resolver o questionário.");
    }
  };

  return (
    <section className="numero ajustes" aria-labelledby="qp-titulo">
      <h3 className="numero-rotulo" id="qp-titulo">
        ! Questionários que precisam de você{pendentes.length > 0 && ` · ${pendentes.length}`}
      </h3>
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {erro && <p className="estado-texto estado-erro" role="alert">✗ {erro}</p>}
      {pendentes.length > 0 && (
        <ul className="ajustes-lista">
          {pendentes.map((q) => (
            <li key={q.id} className="ajuste">
              <div className="ajuste-texto">
                <strong>{q.nome_fantasia || q.razao_social}</strong>
                <span className="celula-fonte">
                  CNPJ {cnpj(q.cnpj)} · {q.contato_nome} · recebido em {dataHora(q.recebido_em)}
                </span>
                <span className="celula-fonte">{q.o_que_fez}</span>
              </div>
              <div className="ajuste-acoes">
                <BotaoMesclar q={q} classe="botao botao-secundario"
                  aoMesclar={(texto) => { definirFeito(texto); recarregar(); }} />
                <button type="button" className="botao botao-secundario" onClick={() => void resolver(q, "criar")}>Criar nova</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
