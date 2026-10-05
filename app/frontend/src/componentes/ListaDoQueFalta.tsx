/** "O que falta para a proposta", no alto da aba Proposta (E4, amostra aprovada por Eduardo em
 * 02/10/2026). Os itens automáticos o CRM confere sozinho e fecha quando o dado chega; os manuais são
 * de quem cadastrou. Todos podem ter responsável e prazo, e os que têm prazo entram na Agenda.
 * A lista avisa e não bloqueia: "Gerar PowerPoint" continua liberado. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { MudancaDePendencia, PendenciaDaProposta, PendenciasDaProposta } from "../api/tipos";
import { data } from "../formato";
import { usarQuemPreenche } from "../quemPreenche";
import { CampoDeData } from "./CampoDeData";
import { usarAcesso } from "../entrada";

function Estado({ item }: { item: PendenciaDaProposta }) {
  if (!item.aberta)
    return (
      <span className="etiqueta etiqueta-ganho">
        {item.automatica ? "✓ resolvido" : `✓ feito em ${data(item.feita_em)}${item.feita_por ? ` · ${item.feita_por}` : ""}`}
      </span>
    );
  if (item.dias_de_atraso > 0)
    return (
      <span className="etiqueta etiqueta-perda">
        ✗ atrasado {item.dias_de_atraso} dia{item.dias_de_atraso === 1 ? "" : "s"}
      </span>
    );
  return <span className="etiqueta etiqueta-espera">em aberto</span>;
}

export function ListaDoQueFalta({
  oportunidadeId,
  dados,
  aoMudar,
}: {
  oportunidadeId: number;
  dados: PendenciasDaProposta;
  aoMudar: (novos: PendenciasDaProposta) => void;
}) {
  const [quem, definirQuem] = usarQuemPreenche(dados.revisores);
  const comLogin = usarAcesso().eu.modo !== "local"; // com login (senha ou Microsoft), o nome vem de quem entrou
  const [nova, definirNova] = useState("");
  const [erro, definirErro] = useState<string | null>(null);
  const [mostrarFeitas, definirMostrarFeitas] = useState(false);

  const tentar = async (acao: () => Promise<PendenciasDaProposta>) => {
    definirErro(null);
    try {
      aoMudar(await acao());
      return true;
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
      return false;
    }
  };
  const mudar = (chave: string, mudanca: Omit<MudancaDePendencia, "por">) =>
    tentar(() => api.mudarPendencia(oportunidadeId, chave, { ...mudanca, por: quem }));
  const adicionar = async () => {
    const descricao = nova.trim();
    if (!descricao) return;
    if (await tentar(() => api.novaPendencia(oportunidadeId, { descricao, por: quem }))) definirNova("");
  };

  const abertas = dados.itens.filter((i) => i.aberta).sort((a, b) => b.dias_de_atraso - a.dias_de_atraso);
  const feitas = dados.itens.filter((i) => !i.aberta);

  const linha = (i: PendenciaDaProposta) => (
    <li key={i.chave} className={`falta-item${i.aberta ? "" : " falta-item-feito"}`}>
      {i.automatica ? (
        <span className="falta-marca falta-marca-auto" aria-hidden="true">{i.aberta ? "" : "✓"}</span>
      ) : (
        <input
          type="checkbox"
          className="falta-marca"
          checked={!i.aberta}
          aria-label={`${i.descricao}: feito`}
          onChange={(e) => void mudar(i.chave, { feita: e.target.checked })}
        />
      )}
      <span className="falta-titulo">
        {i.descricao}
        {i.automatica && <span className="campo-ajuda"> · automático</span>}
      </span>
      <span className="falta-meta">
        {i.aberta && (
          <>
            <label>
              Responsável{" "}
              <select
                className="selecao"
                value={i.responsavel ?? ""}
                onChange={(e) => void mudar(i.chave, { responsavel: e.target.value || null })}
              >
                <option value="">—</option>
                {dados.revisores.map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>
            </label>
            <span className="falta-prazo">
              Prazo
              <CampoDeData
                aria-label={`Prazo de ${i.descricao}`}
                value={i.prazo ?? ""}
                aoMudar={(iso) => void mudar(i.chave, { prazo: iso || null })}
              />
            </span>
          </>
        )}
        <Estado item={i} />
      </span>
    </li>
  );

  return (
    <section className="falta" aria-label="O que falta para a proposta">
      <h3 className="proposta-titulo">O que falta para a proposta</h3>
      <div className="recado falta-resumo">
        <span>
          <strong>{dados.abertas} pendente{dados.abertas === 1 ? "" : "s"}</strong>
          {dados.atrasadas > 0 && ` · ${dados.atrasadas} atrasada${dados.atrasadas === 1 ? "" : "s"}`} · {dados.feitas} feita
          {dados.feitas === 1 ? "" : "s"}
        </span>
        {!comLogin && (
          <label>
            Quem está mexendo{" "}
            <select className="selecao" value={quem} onChange={(e) => definirQuem(e.target.value)} aria-label="Quem está mexendo">
              {dados.revisores.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </label>
        )}
      </div>
      <p className="campo-ajuda">
        Os itens com caixa pontilhada o CRM confere sozinho e fecha quando o dado chega. Os que têm prazo entram na Agenda.
        A lista avisa, não bloqueia: dá para gerar o PowerPoint mesmo com pendências.
      </p>
      {erro && <p className="estado estado-erro estado-texto" role="alert">✗ {erro}</p>}

      {abertas.length === 0 ? (
        <p className="campo-ajuda">✓ Nada pendente para esta proposta.</p>
      ) : (
        <ul className="falta-lista">{abertas.map(linha)}</ul>
      )}
      {feitas.length > 0 && (
        <button type="button" className="link-de-tabela" onClick={() => definirMostrarFeitas((v) => !v)} aria-expanded={mostrarFeitas}>
          {mostrarFeitas ? "Esconder" : "Mostrar"} as {feitas.length} feitas
        </button>
      )}
      {mostrarFeitas && <ul className="falta-lista">{feitas.map(linha)}</ul>}

      <div className="falta-nova">
        <input
          className="entrada"
          value={nova}
          maxLength={300}
          placeholder="O que falta (ex.: pedir o contrato atual)"
          aria-label="Novo item do que falta"
          onChange={(e) => definirNova(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void adicionar();
          }}
        />
        <button type="button" className="botao botao-secundario" onClick={() => void adicionar()} disabled={!nova.trim()}>
          Adicionar
        </button>
      </div>
    </section>
  );
}
