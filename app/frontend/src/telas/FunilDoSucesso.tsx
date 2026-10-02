/** Funil do Sucesso do Cliente (aprovado por Eduardo em 02/10/2026), a terceira aba do Sucesso do
 * Cliente. Cada grupo com contrato valendo aparece numa coluna: Contrato → Handover → Kickoff
 * (a implantação, com o checklist do fluxograma) e, em curso, Em dia ou Atrasada pelas reuniões de
 * resultado que a classe do Score pede. O clique abre o painel com uma só ação principal: concluir a
 * etapa ou registrar a reunião. Atraso aparece com ⚠ e texto, nunca só pela cor. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { FunilDoSucesso as Funil, GrupoNoFunilDoSucesso as Grupo, ReuniaoDevida } from "../api/tipos";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { PainelLateral } from "../componentes/PainelLateral";
import { usarAcesso } from "../entrada";
import { data } from "../formato";
import { usarDados } from "../usarDados";
import { PainelEmCurso } from "./PainelEmCurso";

type Coluna = { chave: string; nome: string; quem: string | null; grupos: Grupo[] };

const nomeDoTipo = (f: Funil, chave: string) => f.tipos.find((t) => t.chave === chave)?.nome ?? chave;

/** A reunião que mais pesa no cartão: a mais atrasada (a que tem data de vencimento vem antes da
 * nunca registrada, que não diz há quanto tempo); em dia, a próxima a vencer. */
function principal(g: Grupo): ReuniaoDevida | null {
  const atrasadas = g.reunioes.filter((r) => r.atrasada);
  if (atrasadas.length) return [...atrasadas].sort((a, b) => (b.dias_de_atraso ?? -1) - (a.dias_de_atraso ?? -1))[0];
  return [...g.reunioes].sort((a, b) => (a.proxima ?? "").localeCompare(b.proxima ?? ""))[0] ?? null;
}

function textoDaReuniao(f: Funil, r: ReuniaoDevida): string {
  const nome = nomeDoTipo(f, r.tipo);
  if (!r.proxima) return `⚠ ${nome}: nenhuma registrada ainda`;
  if (r.atrasada) return `⚠ ${nome} venceu em ${data(r.proxima)} (${r.dias_de_atraso} d)`;
  return `Próxima: ${nome} até ${data(r.proxima)}`;
}

function colunas(f: Funil, grupos: Grupo[]): Coluna[] {
  const implantacao = f.etapas.filter((e) => e.chave !== "em_curso").map((e) => ({
    chave: e.chave, nome: e.nome, quem: e.participantes, grupos: grupos.filter((g) => g.etapa === e.chave),
  }));
  // Mais dias de atraso primeiro; depois as nunca registradas; por último, sem classe.
  const peso = (g: Grupo) => (g.situacao === "sem_classe" ? -2 : principal(g)?.dias_de_atraso ?? -1);
  const emDia = grupos.filter((g) => g.situacao === "em_dia")
    .sort((a, b) => (principal(a)?.proxima ?? "").localeCompare(principal(b)?.proxima ?? ""));
  const atrasadas = grupos.filter((g) => g.situacao === "atrasada" || g.situacao === "sem_classe")
    .sort((a, b) => peso(b) - peso(a));
  return [
    ...implantacao,
    { chave: "em_dia", nome: "Em dia", quem: null, grupos: emDia },
    { chave: "atrasada", nome: "Atrasada", quem: null, grupos: atrasadas },
  ];
}

function Cartao({ f, g, aoAbrir }: { f: Funil; g: Grupo; aoAbrir: () => void }) {
  const itens = f.checklist[g.etapa] ?? [];
  const feitos = itens.filter((i) => g.itens_feitos.includes(i.chave)).length;
  const r = principal(g);
  const outras = r?.atrasada ? g.reunioes.filter((x) => x.atrasada).length - 1 : 0;
  return (
    <button type="button" className="cartao cartao-clicavel" onClick={aoAbrir}>
      <span className="cartao-grupo">{g.nome}</span>
      <span className="cartao-linha">
        {g.classe ? <span className="etiqueta etiqueta-neutra">Classe {g.classe}</span> : null}
        {g.etapa !== "em_curso" && <span className="cartao-prazo">{feitos} de {itens.length} itens feitos</span>}
      </span>
      {g.situacao === "sem_classe" && (
        <span className="cartao-prazo cartao-prazo-atrasado">⚠ Sem classe: avalie o Score na Saúde da carteira</span>
      )}
      {r && <span className={`cartao-prazo ${r.atrasada ? "cartao-prazo-atrasado" : ""}`}>{textoDaReuniao(f, r)}</span>}
      {outras > 0 && <span className="cartao-prazo">e mais {outras} {outras === 1 ? "reunião atrasada" : "reuniões atrasadas"}</span>}
      {g.ajustes_pendentes > 0 && (
        <span className={`cartao-prazo ${g.ajustes_atrasados ? "cartao-prazo-atrasado" : ""}`}>
          {g.ajustes_pendentes} {g.ajustes_pendentes === 1 ? "ajuste pendente" : "ajustes pendentes"}
          {g.ajustes_atrasados > 0 && ` · ⚠ ${g.ajustes_atrasados} atrasado${g.ajustes_atrasados === 1 ? "" : "s"}`}
        </span>
      )}
    </button>
  );
}

export function FunilDoSucesso() {
  const { dados, carregando, erro, recarregar } = usarDados<Funil>(() => api.funilDoSucesso(), []);
  const [busca, definirBusca] = useState("");
  const [aberto, definirAberto] = useState<number | null>(null);

  if (carregando && !dados) return <Carregando rotulo="Abrindo o funil do sucesso do cliente" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  if (dados.grupos.length === 0) {
    return (
      <VazioSemDados
        titulo="Nenhum cliente com contrato valendo"
        explicacao="O grupo entra no funil quando tem contrato ativo, suspenso ou aguardando assinatura em Gestão de contratos."
      />
    );
  }
  const termo = busca.trim().toLocaleLowerCase("pt-BR");
  const filtrados = termo ? dados.grupos.filter((g) => g.nome.toLocaleLowerCase("pt-BR").includes(termo)) : dados.grupos;
  const lista = colunas(dados, filtrados);
  const fases: [string, Coluna[]][] = [["Implantação", lista.slice(0, -2)], ["Em curso", lista.slice(-2)]];
  const grupo = dados.grupos.find((g) => g.grupo_id === aberto) ?? null;
  const cadencia = Object.entries(dados.cadencia)
    .map(([classe, tipos]) => `${classe}: ${tipos.map((t) => nomeDoTipo(dados, t)).join(", ")}`).join(" · ");

  return (
    <div className="sucesso">
      <div className="sucesso-topo">
        <input
          className="entrada entrada-busca" type="search" placeholder="Buscar grupo" aria-label="Buscar grupo"
          value={busca} onChange={(e) => definirBusca(e.target.value)}
        />
        <p className="campo-ajuda" style={{ margin: 0 }}>
          Reuniões por classe ({cadencia}). Muda em Configurações › Metas.
        </p>
      </div>
      {filtrados.length === 0 ? (
        <VazioPorFiltro aoLimpar={() => definirBusca("")} />
      ) : (
        <div className="kanban sucesso-kanban">
          {fases.map(([fase, cols]) => (
            <div className="sucesso-fase" key={fase}>
              <p className="sucesso-fase-nome">{fase}</p>
              <div className="sucesso-fase-colunas">
                {cols.map((c) => (
                  <section className="coluna" key={c.chave} aria-label={c.nome}>
                    <header className="coluna-topo">
                      <h2 className="coluna-nome">
                        <span>{c.nome}</span>
                        <span className="coluna-quantas">{c.grupos.length}</span>
                      </h2>
                      {c.quem && <p className="coluna-valor">{c.quem}</p>}
                    </header>
                    <div className="coluna-cartoes">
                      {c.grupos.map((g) => <Cartao key={g.grupo_id} f={dados} g={g} aoAbrir={() => definirAberto(g.grupo_id)} />)}
                      {c.grupos.length === 0 && <p className="coluna-vazia">Nenhum grupo nesta etapa.</p>}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {grupo && (
        <PainelDoGrupo key={grupo.grupo_id} f={dados} g={grupo} aoFechar={() => definirAberto(null)} aoMudar={recarregar} />
      )}
    </div>
  );
}

function PainelDoGrupo({ f, g, aoFechar, aoMudar }: { f: Funil; g: Grupo; aoFechar: () => void; aoMudar: () => void }) {
  const etapa = f.etapas.find((e) => e.chave === g.etapa);
  const subtitulo = g.etapa === "em_curso"
    ? `Em curso${g.classe ? ` · classe ${g.classe}` : ""}${g.em_curso_desde ? ` · desde ${data(g.em_curso_desde)}` : ""}`
    : `Implantação · ${etapa?.nome}${etapa?.participantes ? ` (${etapa.participantes})` : ""}`;
  return g.etapa === "em_curso"
    ? <PainelEmCurso f={f} g={g} titulo={g.nome} subtitulo={subtitulo} aoFechar={aoFechar} aoMudar={aoMudar} />
    : <Implantacao f={f} g={g} titulo={g.nome} subtitulo={subtitulo} aoFechar={aoFechar} aoMudar={aoMudar} />;
}

type PropsDoPainel = { f: Funil; g: Grupo; titulo: string; subtitulo: string; aoFechar: () => void; aoMudar: () => void };

function Implantacao({ f, g, titulo, subtitulo, aoFechar, aoMudar }: PropsDoPainel) {
  const { pode } = usarAcesso();
  const edita = pode("sucesso.editar");
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const itens = f.checklist[g.etapa] ?? [];
  const faltam = itens.filter((i) => !g.itens_feitos.includes(i.chave)).length;
  const seguinte = f.etapas[f.etapas.findIndex((e) => e.chave === g.etapa) + 1];

  const fazer = async (acao: () => Promise<unknown>) => {
    definirOcupado(true);
    definirFalha(null);
    try {
      await acao();
      aoMudar();
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui gravar. Tente de novo.");
    } finally {
      definirOcupado(false);
    }
  };

  return (
    <PainelLateral
      titulo={titulo} subtitulo={subtitulo} aoFechar={aoFechar}
      rodape={edita ? (
        <>
          <button type="button" className="botao botao-primario" disabled={faltam > 0 || ocupado}
            onClick={() => void fazer(() => api.concluirEtapaDoSucesso(g.grupo_id))}>
            Concluir etapa e passar para {seguinte?.nome}
          </button>
          {faltam > 0 && <span className="campo-ajuda">· faltam {faltam} {faltam === 1 ? "item" : "itens"}</span>}
        </>
      ) : undefined}
    >
      <fieldset className="sucesso-checklist" disabled={!edita || ocupado}>
        <legend className="campo-rotulo">Checklist da etapa</legend>
        {itens.map((i) => (
          <label key={i.chave}>
            <input type="checkbox" checked={g.itens_feitos.includes(i.chave)}
              onChange={(e) => void fazer(() => api.marcarItemDoSucesso(g.grupo_id, i.chave, e.target.checked))} />
            {i.rotulo}
          </label>
        ))}
      </fieldset>
      {g.etapa === "kickoff" && (
        <p className="campo-ajuda">Ao concluir o kickoff, o grupo entra em curso e as reuniões de resultado passam a contar a partir de hoje.</p>
      )}
      {!edita && <p className="campo-ajuda">O seu perfil só vê: marcar itens pede "Funil do Sucesso do Cliente: marcar etapas e registrar reuniões".</p>}
      {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
    </PainelLateral>
  );
}
