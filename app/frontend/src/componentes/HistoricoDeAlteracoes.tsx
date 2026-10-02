/** Histórico de alterações por usuário (E1, amostra aprovada por Eduardo em 02/10/2026): quem, quando,
 * o quê, o campo e o antes e depois. Não se edita nem se apaga. Em Configurações aparece tudo, com
 * filtro por pessoa, tela e período; no painel de um registro, só as alterações dele. Começa no dia em
 * que o login entrou no ar: o que veio antes não tem autor. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { Alteracao } from "../api/tipos";
import { dataHora } from "../formato";
import { CampoDeData } from "./CampoDeData";
import { Carregando, Erro } from "./estados";

const TABELAS: Record<string, string> = {
  oportunidade: "Oportunidade", lead: "Lead", proposta: "Proposta", pendencia_da_proposta: "O que falta",
  pessoa_contato: "Contato", empresa: "Empresa", vinculo_de_contato: "Vínculo de contato",
  grupo_economico: "Grupo", contrato: "Contrato", evento_de_contrato: "Evento de contrato",
  perfil: "Perfil", usuario: "Acesso", matriz_de_proposta: "Matriz de proposta", configuracao_de_proposta: "Configuração de proposta",
  abordagem: "Abordagem", classificacao_do_grupo: "Avaliação da carteira", conversa_do_sdr: "Conversa do SDR",
};
const ACAO: Record<Alteracao["acao"], string> = { criou: "criou", alterou: "alterou", excluiu: "excluiu" };

function Linhas({ itens, comQuem }: { itens: Alteracao[]; comQuem: boolean }) {
  if (itens.length === 0) return <p className="campo-ajuda">Nenhuma alteração registrada neste recorte.</p>;
  return (
    <div className="tabela-rolagem">
      <table className="tabela" aria-label="Alterações">
        <thead>
          <tr>
            <th scope="col">Quando</th>
            {comQuem && <th scope="col">Quem</th>}
            <th scope="col">O quê</th>
            <th scope="col">Campo</th>
            <th scope="col">Antes → depois</th>
          </tr>
        </thead>
        <tbody>
          {itens.map((a) => (
            <tr key={a.id}>
              <td className="celula-numero">{dataHora(a.quando)}</td>
              {comQuem && <td>{a.usuario_nome ?? a.usuario_email}</td>}
              <td>
                {TABELAS[a.tabela] ?? a.tabela}
                {a.descricao && <span className="celula-fonte">{a.descricao}</span>}
              </td>
              <td>{a.campo ?? ACAO[a.acao]}</td>
              <td className="historico-mudanca">
                {a.acao === "alterou" ? (
                  <>
                    <span className="historico-antes">{a.antes ?? "—"}</span> → <span className="historico-depois">{a.depois ?? "—"}</span>
                  </>
                ) : (
                  <span className="campo-ajuda">{a.acao === "criou" ? "registro criado" : "registro excluído"}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** O histórico de um registro, dentro do painel dele. */
export function HistoricoDoRegistro({ tabela, id }: { tabela: string; id: number }) {
  const [itens, definirItens] = useState<Alteracao[] | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const carregar = () => {
    definirErro(null);
    api
      .historico({ tabela, registro_id: id })
      .then(definirItens)
      .catch((f) => definirErro(f instanceof ErroDaApi ? f.message : "Falha ao abrir o histórico."));
  };
  useEffect(carregar, [tabela, id]);
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={carregar} />;
  if (!itens) return <Carregando rotulo="Abrindo o histórico" />;
  return (
    <section aria-label="Histórico de alterações">
      <p className="campo-ajuda">Quem mudou o quê neste registro, desde que o login entrou no ar.</p>
      <Linhas itens={itens} comQuem />
    </section>
  );
}

/** O histórico de um registro recolhido no fim do painel: só busca quando alguém abre. */
export function AlteracoesDoRegistro({ tabela, id }: { tabela: string; id: number }) {
  const [aberto, definirAberto] = useState(false);
  return (
    <details className="historico-do-registro" onToggle={(e) => definirAberto((e.target as HTMLDetailsElement).open)}>
      <summary>Histórico de alterações</summary>
      {aberto && <HistoricoDoRegistro tabela={tabela} id={id} />}
    </details>
  );
}

/** Configurações › Histórico de alterações. */
export function HistoricoDeAlteracoes() {
  const [pessoa, definirPessoa] = useState("");
  const [tabela, definirTabela] = useState("");
  const [de, definirDe] = useState("");
  const [ate, definirAte] = useState("");
  const [itens, definirItens] = useState<Alteracao[] | null>(null);
  const [pessoas, definirPessoas] = useState<{ email: string; nome: string | null }[]>([]);
  const [erro, definirErro] = useState<string | null>(null);

  useEffect(() => {
    api.usuarios().then((u) => definirPessoas(u.map((x) => ({ email: x.email, nome: x.nome })))).catch(() => definirPessoas([]));
  }, []);
  useEffect(() => {
    definirErro(null);
    api
      .historico({ usuario: pessoa || undefined, tabela: tabela || undefined, de: de || undefined, ate: ate || undefined, limite: 500 })
      .then(definirItens)
      .catch((f) => definirErro(f instanceof ErroDaApi ? f.message : "Falha ao abrir o histórico."));
  }, [pessoa, tabela, de, ate]);

  return (
    <section className="numero" aria-labelledby="historico-titulo">
      <h3 className="numero-rotulo" id="historico-titulo">Histórico de alterações</h3>
      <p className="campo-ajuda">Não se edita nem se apaga. Começa no dia em que o login entrou no ar: o que veio antes não tem autor.</p>
      <div className="historico-filtros">
        <select className="selecao" value={pessoa} aria-label="Pessoa" onChange={(e) => definirPessoa(e.target.value)}>
          <option value="">Todas as pessoas</option>
          {pessoas.map((p) => <option key={p.email} value={p.email}>{p.nome ?? p.email}</option>)}
        </select>
        <select className="selecao" value={tabela} aria-label="O quê" onChange={(e) => definirTabela(e.target.value)}>
          <option value="">Tudo</option>
          {Object.entries(TABELAS).map(([chave, rotulo]) => <option key={chave} value={chave}>{rotulo}</option>)}
        </select>
        <span className="historico-periodo">
          de <CampoDeData aria-label="De" value={de} aoMudar={definirDe} /> a <CampoDeData aria-label="Até" value={ate} aoMudar={definirAte} />
        </span>
      </div>
      {erro && <p className="estado estado-erro estado-texto" role="alert">✗ {erro}</p>}
      {!itens && !erro ? <Carregando rotulo="Abrindo o histórico" /> : itens && <Linhas itens={itens} comQuem />}
      {itens && itens.length === 500 && <p className="campo-ajuda">Mostrando as 500 mais recentes: use os filtros para ver o resto.</p>}
    </section>
  );
}
