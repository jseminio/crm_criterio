/** Funil do Sucesso do Cliente (aprovado por Eduardo em 02/10/2026), a terceira aba do Sucesso do
 * Cliente. Cada grupo com contrato valendo aparece numa coluna: Contrato → Handover → Kickoff
 * (a implantação, com o checklist do fluxograma) e, em curso, Em dia ou Atrasada pelas reuniões de
 * resultado que a classe do Score pede. O clique abre o painel com uma só ação principal: concluir a
 * etapa ou registrar a reunião. Atraso aparece com ⚠ e texto, nunca só pela cor. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { FunilDoSucesso as Funil, GrupoNoFunilDoSucesso as Grupo, ReuniaoDeResultado, ReuniaoDevida, TipoDeReuniao } from "../api/tipos";
import { CampoDeData } from "../componentes/CampoDeData";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { PainelLateral } from "../componentes/PainelLateral";
import { usarAcesso } from "../entrada";
import { data, dataHora } from "../formato";
import { usarDados } from "../usarDados";

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
    ? <EmCurso f={f} g={g} titulo={g.nome} subtitulo={subtitulo} aoFechar={aoFechar} aoMudar={aoMudar} />
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

const pautaDe = (t: TipoDeReuniao | undefined) => (t ? t.pauta.map((p) => `• ${p}`).join("\n") : "");

function EmCurso({ f, g, titulo, subtitulo, aoFechar, aoMudar }: PropsDoPainel) {
  const { pode } = usarAcesso();
  const edita = pode("sucesso.editar");
  const historico = usarDados<ReuniaoDeResultado[]>(() => api.reunioesDoGrupo(g.grupo_id), [g.grupo_id]);
  const sugerido = g.reunioes.find((r) => r.atrasada)?.tipo ?? g.reunioes[0]?.tipo ?? f.tipos[0].chave;
  const tipoInicial = f.tipos.find((t) => t.chave === sugerido);
  const hoje = new Date().toLocaleDateString("sv");
  const [campos, definirCampos] = useState({
    tipo: sugerido, data: hoje, participantes: tipoInicial?.participantes ?? "", pauta: pautaDe(tipoInicial),
    dashboard: "", decisoes: "", proximos_passos: "",
  });
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);
  const mudar = (campo: keyof typeof campos, valor: string) => {
    definirFeito(null);
    definirCampos((c) => ({ ...c, [campo]: valor }));
  };
  const mudarTipo = (chave: string) => {
    const t = f.tipos.find((x) => x.chave === chave);
    definirFeito(null);
    definirCampos((c) => ({ ...c, tipo: chave, participantes: t?.participantes ?? "", pauta: pautaDe(t) }));
  };

  const registrar = async () => {
    definirOcupado(true);
    definirFalha(null);
    try {
      await api.registrarReuniao(g.grupo_id, campos);
      definirFeito(`Reunião ${nomeDoTipo(f, campos.tipo).toLowerCase()} de ${data(campos.data)} registrada.`);
      definirCampos((c) => ({ ...c, dashboard: "", decisoes: "", proximos_passos: "" }));
      historico.recarregar();
      aoMudar();
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui registrar. Tente de novo.");
    } finally {
      definirOcupado(false);
    }
  };

  return (
    <PainelLateral
      titulo={titulo} subtitulo={subtitulo} aoFechar={aoFechar}
      rodape={edita ? (
        <button type="button" className="botao botao-primario" disabled={ocupado || !campos.data} onClick={() => void registrar()}>
          {ocupado ? "Registrando…" : "Registrar reunião"}
        </button>
      ) : undefined}
    >
      {g.situacao === "sem_classe" ? (
        <p className="recado">⚠ Este grupo ainda não tem classe. Avalie o Score na aba Saúde da carteira: é a classe que diz quais reuniões ele recebe.</p>
      ) : (
        <table className="tabela">
          <caption className="campo-rotulo" style={{ textAlign: "left", paddingBottom: "var(--e2)" }}>Reuniões da classe {g.classe}</caption>
          <thead>
            <tr><th>Reunião</th><th>Com quem</th><th>Última</th><th>Próxima</th></tr>
          </thead>
          <tbody>
            {g.reunioes.map((r) => (
              <tr key={r.tipo}>
                <td>{nomeDoTipo(f, r.tipo)}</td>
                <td>{f.tipos.find((t) => t.chave === r.tipo)?.participantes}</td>
                <td>{r.ultima ? data(r.ultima) : "nenhuma"}</td>
                <td className={r.atrasada ? "cartao-prazo-atrasado" : undefined}>
                  {!r.proxima ? "⚠ registre a primeira" : r.atrasada ? `⚠ venceu em ${data(r.proxima)} (${r.dias_de_atraso} d)` : `até ${data(r.proxima)}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {edita && (
        <fieldset className="formulario" disabled={ocupado}>
          <legend className="campo-rotulo">Registrar reunião feita</legend>
          <div className="formulario-duplo">
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="re-tipo">Tipo</label>
              <select id="re-tipo" className="selecao" value={campos.tipo} onChange={(e) => mudarTipo(e.target.value)}>
                {f.tipos.map((t) => <option key={t.chave} value={t.chave}>{t.nome}</option>)}
              </select>
            </div>
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="re-data">Data</label>
              <CampoDeData id="re-data" value={campos.data} aoMudar={(v) => mudar("data", v)} />
            </div>
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-participantes">Participantes</label>
            <input id="re-participantes" className="entrada" maxLength={300} value={campos.participantes} onChange={(e) => mudar("participantes", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-pauta">Pauta</label>
            <textarea id="re-pauta" className="entrada" rows={4} value={campos.pauta} onChange={(e) => mudar("pauta", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-dashboard">Dashboard apresentado (opcional)</label>
            <input id="re-dashboard" className="entrada" maxLength={400} placeholder="Link ou caminho no SharePoint"
              value={campos.dashboard} onChange={(e) => mudar("dashboard", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-decisoes">Decisões do cliente</label>
            <textarea id="re-decisoes" className="entrada" rows={3} placeholder="O que o cliente decidiu a partir dos números"
              value={campos.decisoes} onChange={(e) => mudar("decisoes", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-passos">Próximos passos da Critério</label>
            <textarea id="re-passos" className="entrada" rows={3} placeholder="O quê, quem e até quando"
              value={campos.proximos_passos} onChange={(e) => mudar("proximos_passos", e.target.value)} />
          </div>
          {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
          {feito && <p className="recado" role="status">✓ {feito}</p>}
        </fieldset>
      )}

      <section aria-labelledby="re-historico">
        <h3 className="campo-rotulo" id="re-historico">Reuniões registradas</h3>
        {historico.carregando && !historico.dados ? (
          <Carregando rotulo="Abrindo as reuniões" />
        ) : historico.erro ? (
          <Erro mensagem={historico.erro} aoTentarDeNovo={historico.recarregar} />
        ) : !historico.dados?.length ? (
          <p className="campo-ajuda">Nenhuma reunião registrada ainda.</p>
        ) : (
          <ol className="sucesso-historico">
            {historico.dados.map((r) => (
              <li key={r.id}>
                <strong>{nomeDoTipo(f, r.tipo)} · {data(r.data)}</strong>
                {r.participantes && <span className="campo-ajuda">{r.participantes}</span>}
                {r.decisoes && <p><b>Decisões:</b> {r.decisoes}</p>}
                {r.proximos_passos && <p><b>Próximos passos:</b> {r.proximos_passos}</p>}
                {r.dashboard && <p><b>Dashboard:</b> {r.dashboard}</p>}
                <span className="campo-ajuda">Registrada {r.registrada_por ? `por ${r.registrada_por} ` : ""}em {dataHora(r.criado_em)}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </PainelLateral>
  );
}
