/** Agenda › Ajustes da área técnica (aprovado por Eduardo em 02/10/2026): o que as reuniões de
 * resultado identificaram e a área técnica faz. Quem tem o perfil Área técnica vê os seus; quem gere
 * vê os de todos. Prazo vencido aparece com ⚠ e texto. "Marcar feito" aceita uma observação. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { AjusteTecnico } from "../api/tipos";
import { usarAcesso } from "../entrada";
import { data, dataHora, prazo as quandoVence } from "../formato";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";

const NOME_DA_REUNIAO: Record<string, string> = { mensal: "mensal", bimestral: "bimestral", trimestral: "trimestral", anual: "anual" };

function Ajuste({ a, aoMudar }: { a: AjusteTecnico; aoMudar: (recado: string) => void }) {
  const { pode } = usarAcesso();
  const conclui = pode("ajustes.concluir");
  const [marcando, definirMarcando] = useState(false);
  const [observacao, definirObservacao] = useState("");
  const [ocupado, definirOcupado] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const vence = a.feito_em ? null : quandoVence(a.prazo);

  const fazer = async (acao: () => Promise<unknown>, recado: string) => {
    definirOcupado(true);
    definirErro(null);
    try {
      await acao();
      aoMudar(recado);
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Não consegui gravar. Tente de novo.");
    } finally {
      definirOcupado(false);
    }
  };

  return (
    <li className="ajuste">
      <div className="ajuste-texto">
        <strong>{a.descricao}</strong>
        <span className="celula-fonte">
          {a.grupo_nome} · reunião {NOME_DA_REUNIAO[a.reuniao_tipo] ?? a.reuniao_tipo} de {data(a.reuniao_data)} ·{" "}
          {a.responsavel_nome ?? a.responsavel_email}
        </span>
        {a.feito_em ? (
          <span className="celula-fonte">
            ✓ Feito por {a.feito_por ?? "—"} em {dataHora(a.feito_em)}{a.observacao ? ` · ${a.observacao}` : ""}
          </span>
        ) : (
          <span className={`cartao-prazo ${vence?.atrasado ? "cartao-prazo-atrasado" : ""}`}>
            {a.prazo ? `${vence?.atrasado ? "⚠ " : ""}Prazo ${data(a.prazo)} (${vence?.texto})` : "Sem prazo"}
          </span>
        )}
        {erro && <span className="estado-texto estado-erro" role="alert">✗ {erro}</span>}
      </div>
      {conclui && (
        <div className="ajuste-acoes">
          {a.feito_em ? (
            <button type="button" className="link-de-tabela" disabled={ocupado}
              onClick={() => void fazer(() => api.reabrirAjuste(a.id), "Ajuste reaberto: voltou para os pendentes.")}>
              Reabrir
            </button>
          ) : marcando ? (
            <>
              <input className="entrada" maxLength={500} placeholder="Observação (opcional)" value={observacao}
                aria-label={`Observação sobre: ${a.descricao}`} onChange={(e) => definirObservacao(e.target.value)} />
              <button type="button" className="botao botao-secundario" disabled={ocupado}
                onClick={() => void fazer(() => api.marcarAjusteFeito(a.id, observacao), "Ajuste marcado como feito.")}>
                Confirmar
              </button>
              <button type="button" className="link-de-tabela" onClick={() => definirMarcando(false)}>Voltar</button>
            </>
          ) : (
            <button type="button" className="botao botao-secundario" onClick={() => definirMarcando(true)}>Marcar feito</button>
          )}
        </div>
      )}
    </li>
  );
}

export function AjustesDaAreaTecnica() {
  const { pode } = usarAcesso();
  const [situacao, definirSituacao] = useState<"pendentes" | "feitos">("pendentes");
  const { dados, carregando, erro, recarregar } = usarDados<AjusteTecnico[]>(() => api.ajustes(situacao), [situacao]);
  const [recado, definirRecado] = useState<string | null>(null);
  const todos = pode("ajustes.ver", "sucesso.ver");
  const atrasados = situacao === "pendentes" ? (dados ?? []).filter((a) => quandoVence(a.prazo)?.atrasado).length : 0;

  return (
    <section className="numero ajustes" aria-labelledby="ajustes-titulo">
      <div className="ajustes-topo">
        <h3 className="numero-rotulo" id="ajustes-titulo">
          {todos ? "Ajustes da área técnica" : "Meus ajustes"}
          {dados && situacao === "pendentes" && ` · ${dados.length} pendente${dados.length === 1 ? "" : "s"}`}
          {atrasados > 0 && ` · ⚠ ${atrasados} atrasado${atrasados === 1 ? "" : "s"}`}
        </h3>
        <div className="abas" role="tablist" aria-label="Situação dos ajustes">
          {(["pendentes", "feitos"] as const).map((s) => (
            <button key={s} type="button" role="tab" className="aba" aria-selected={situacao === s}
              onClick={() => { definirRecado(null); definirSituacao(s); }}>
              {s === "pendentes" ? "Pendentes" : "Feitos"}
            </button>
          ))}
        </div>
      </div>
      {recado && <p className="recado" role="status">✓ {recado}</p>}
      {carregando && !dados ? (
        <Carregando rotulo="Abrindo os ajustes" />
      ) : erro ? (
        <Erro mensagem={erro} aoTentarDeNovo={recarregar} />
      ) : !dados?.length ? (
        <p className="campo-ajuda">
          {situacao === "pendentes"
            ? "Nenhum ajuste pendente. Eles nascem da ata de cada reunião de resultado, no Funil do Sucesso do Cliente."
            : "Nenhum ajuste feito ainda."}
        </p>
      ) : (
        <ul className="ajustes-lista">
          {dados.map((a) => <Ajuste key={a.id} a={a} aoMudar={(r) => { definirRecado(r); recarregar(); }} />)}
        </ul>
      )}
    </section>
  );
}
