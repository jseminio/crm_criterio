/** Agenda › Aprovações (amostra aprovada por Eduardo em 02/10/2026): eventos de contrato acima da
 * alçada esperando quem aprova. Só aparece para quem tem "aprovar eventos acima da alçada" e só
 * quando há pedido. Aprovar aplica o evento com a data pedida; recusar pede o porquê. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { Aprovacao } from "../api/tipos";
import { data, dataHora, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { Erro } from "./estados";

function Mudanca({ a }: { a: Aprovacao }) {
  const partes: string[] = [];
  if (a.preco_mensal_novo !== null) partes.push(`mensal ${dinheiro(a.preco_mensal_anterior)} → ${dinheiro(a.preco_mensal_novo)}`);
  if (a.preco_anual_novo !== null) partes.push(`anual ${dinheiro(a.preco_anual_anterior)} → ${dinheiro(a.preco_anual_novo)}`);
  if (a.escopo_novo !== null) partes.push(`escopo “${a.escopo_anterior ?? "—"}” → “${a.escopo_novo}”`);
  return <>{partes.join(" · ") || "sem mudança de valores"}</>;
}

function Linha({ a, aoDecidir }: { a: Aprovacao; aoDecidir: (mensagem: string) => void }) {
  const [recusando, definirRecusando] = useState(false);
  const [motivo, definirMotivo] = useState("");
  const [ocupado, definirOcupado] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const decidir = async (acao: () => Promise<unknown>, mensagem: string) => {
    definirOcupado(true);
    definirErro(null);
    try {
      await acao();
      aoDecidir(mensagem);
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao decidir.");
    } finally {
      definirOcupado(false);
    }
  };
  return (
    <tr>
      <td>
        {a.tipo}
        <span className="celula-fonte">{a.grupo_nome} · evento em {data(a.data_do_evento)}</span>
      </td>
      <td>
        <Mudanca a={a} />
        <span className="celula-fonte">{a.motivo}{a.descricao ? ` · ${a.descricao}` : ""}</span>
      </td>
      <td>
        {a.pedido_por}
        <span className="celula-fonte">{dataHora(a.pedido_em)}</span>
      </td>
      <td>
        {recusando ? (
          <div className="aprovacao-recusa">
            <input className="entrada" value={motivo} maxLength={500} placeholder="Por que recusa?" aria-label={`Por que recusa ${a.tipo} de ${a.grupo_nome}`}
              onChange={(e) => definirMotivo(e.target.value)} />
            <button type="button" className="link-de-tabela" disabled={ocupado || motivo.trim().length < 3}
              onClick={() => void decidir(() => api.recusar(a.id, motivo.trim()), `Pedido de ${a.tipo.toLowerCase()} de ${a.grupo_nome} recusado: o contrato não mudou.`)}>
              Confirmar recusa
            </button>
            <button type="button" className="link-de-tabela" onClick={() => definirRecusando(false)}>Voltar</button>
          </div>
        ) : (
          <span className="aprovacao-acoes">
            <button type="button" className="link-de-tabela" disabled={ocupado}
              onClick={() => void decidir(() => api.aprovar(a.id), `Pedido de ${a.tipo.toLowerCase()} de ${a.grupo_nome} aprovado e aplicado ao contrato.`)}>
              Aprovar
            </button>
            {" · "}
            <button type="button" className="link-de-tabela" disabled={ocupado} onClick={() => definirRecusando(true)}>Recusar</button>
          </span>
        )}
        {erro && <span className="estado-texto estado-erro" role="alert">✗ {erro}</span>}
      </td>
    </tr>
  );
}

export function AprovacoesPendentes() {
  const { dados, erro, recarregar } = usarDados<Aprovacao[]>(() => api.aprovacoes(), []);
  const [feito, definirFeito] = useState<string | null>(null);
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados || (dados.length === 0 && !feito)) return null;
  return (
    <section className="aprovacoes" aria-labelledby="aprovacoes-titulo">
      <h3 className="numero-rotulo" id="aprovacoes-titulo">
        Aprovações · {dados.length} aguardando
      </h3>
      <p className="campo-ajuda">
        Eventos de contrato acima da alçada. Aprovar aplica o evento com a data pedida; recusar pede o porquê. Tudo fica no
        histórico, com quem pediu e quem decidiu.
      </p>
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {dados.length > 0 && (
        <div className="tabela-rolagem">
          <table className="tabela" aria-label="Aprovações pendentes">
            <thead>
              <tr><th scope="col">Pedido</th><th scope="col">Mudança</th><th scope="col">Quem pediu</th><th scope="col">Decisão</th></tr>
            </thead>
            <tbody>
              {dados.map((a) => (
                <Linha key={a.id} a={a} aoDecidir={(m) => { definirFeito(m); recarregar(); }} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
