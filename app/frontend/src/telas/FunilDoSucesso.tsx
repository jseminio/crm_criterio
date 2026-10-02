/** Funil do Sucesso do Cliente no formato do fluxograma "Macroprocesso — Comercial & Sucesso do
 * Cliente" (aprovado por Eduardo em 02/10/2026): uma coluna por etapa, Contrato → Handover → Kickoff
 * (implantação) e Mensal → Bimestral → Trimestral → Anual (em curso). Cada cabeçalho é a seta do
 * fluxograma, com quem participa e o que se faz ali. Na implantação, o grupo fica numa etapa só; em
 * curso, aparece em todas as reuniões que a classe dele pede, ordenado pelo vencimento (vencidas no
 * topo, com ⚠ e texto). O clique abre o painel com uma só ação principal. */

import { useState, type ReactNode } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { FunilDoSucesso as Funil, GrupoNoFunilDoSucesso as Grupo, ReuniaoDevida } from "../api/tipos";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { PainelLateral } from "../componentes/PainelLateral";
import { usarAcesso } from "../entrada";
import { data } from "../formato";
import { usarDados } from "../usarDados";
import { PainelEmCurso } from "./PainelEmCurso";

const MEMORIA_DO_FLUXOGRAMA = "crm.sucesso.fluxograma";

type Coluna = {
  chave: string;
  nome: string;
  quem: string | null;
  itens: string[];
  quantas: number;
  vencidas: number;
  cartoes: ReactNode[];
};

const nomeDoTipo = (f: Funil, chave: string) => f.tipos.find((t) => t.chave === chave)?.nome ?? chave;

function textoDaReuniao(r: ReuniaoDevida): string {
  if (!r.proxima) return "⚠ nenhuma registrada ainda";
  if (r.atrasada) return `⚠ venceu em ${data(r.proxima)} (${r.dias_de_atraso} d)`;
  return `até ${data(r.proxima)}`;
}

/** Vencidas primeiro (mais dias de atraso antes; a nunca registrada depois delas), depois pela data. */
function ordemDaReuniao(a: ReuniaoDevida, b: ReuniaoDevida): number {
  if (a.atrasada !== b.atrasada) return a.atrasada ? -1 : 1;
  if (a.atrasada) return (b.dias_de_atraso ?? -1) - (a.dias_de_atraso ?? -1);
  return (a.proxima ?? "").localeCompare(b.proxima ?? "");
}

function Ajustes({ g }: { g: Grupo }) {
  if (g.ajustes_pendentes === 0) return null;
  return (
    <span className={`cartao-prazo ${g.ajustes_atrasados ? "cartao-prazo-atrasado" : ""}`}>
      {g.ajustes_pendentes} {g.ajustes_pendentes === 1 ? "ajuste pendente" : "ajustes pendentes"}
      {g.ajustes_atrasados > 0 && ` · ⚠ ${g.ajustes_atrasados} atrasado${g.ajustes_atrasados === 1 ? "" : "s"}`}
    </span>
  );
}

function CartaoDaImplantacao({ f, g, aoAbrir }: { f: Funil; g: Grupo; aoAbrir: () => void }) {
  const itens = f.checklist[g.etapa] ?? [];
  const feitos = itens.filter((i) => g.itens_feitos.includes(i.chave)).length;
  return (
    <button type="button" className="cartao cartao-clicavel" onClick={aoAbrir}>
      <span className="cartao-grupo">{g.nome}</span>
      <span className="cartao-linha">
        {g.classe && <span className="etiqueta etiqueta-neutra">Classe {g.classe}</span>}
        <span className="cartao-prazo">{feitos} de {itens.length} itens feitos</span>
      </span>
    </button>
  );
}

function CartaoDaReuniao({ g, r, aoAbrir }: { g: Grupo; r: ReuniaoDevida; aoAbrir: () => void }) {
  return (
    <button type="button" className="cartao cartao-clicavel" onClick={aoAbrir}>
      <span className="cartao-grupo">{g.nome}</span>
      <span className="cartao-linha">
        <span className="etiqueta etiqueta-neutra">Classe {g.classe}</span>
        <span className={`cartao-prazo ${r.atrasada ? "cartao-prazo-atrasado" : ""}`}>{textoDaReuniao(r)}</span>
      </span>
      <Ajustes g={g} />
    </button>
  );
}

function lembrado(): boolean {
  try {
    return localStorage.getItem(MEMORIA_DO_FLUXOGRAMA) !== "recolhido";
  } catch {
    return true;
  }
}

export function FunilDoSucesso() {
  const { dados, carregando, erro, recarregar } = usarDados<Funil>(() => api.funilDoSucesso(), []);
  const [busca, definirBusca] = useState("");
  const [aberto, definirAberto] = useState<{ grupo: number; tipo: string | null } | null>(null);
  const [verItens, definirVerItens] = useState(lembrado);

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
  const abrir = (g: Grupo, tipo: string | null = null) => definirAberto({ grupo: g.grupo_id, tipo });

  const implantacao: Coluna[] = dados.etapas.filter((e) => e.chave !== "em_curso").map((e) => {
    const grupos = filtrados.filter((g) => g.etapa === e.chave);
    return {
      chave: e.chave, nome: e.nome, quem: e.participantes, itens: (dados.checklist[e.chave] ?? []).map((i) => i.rotulo),
      quantas: grupos.length, vencidas: 0,
      cartoes: grupos.map((g) => <CartaoDaImplantacao key={g.grupo_id} f={dados} g={g} aoAbrir={() => abrir(g)} />),
    };
  });
  const emCurso: Coluna[] = dados.tipos.map((t) => {
    const pares = filtrados.flatMap((g) => g.reunioes.filter((r) => r.tipo === t.chave).map((r) => ({ g, r })))
      .sort((a, b) => ordemDaReuniao(a.r, b.r) || a.g.nome.localeCompare(b.g.nome, "pt-BR"));
    return {
      chave: t.chave, nome: t.nome, quem: t.participantes, itens: t.pauta,
      quantas: pares.length, vencidas: pares.filter((p) => p.r.atrasada).length,
      cartoes: pares.map(({ g, r }) => <CartaoDaReuniao key={g.grupo_id} g={g} r={r} aoAbrir={() => abrir(g, t.chave)} />),
    };
  });
  const semClasse = filtrados.filter((g) => g.situacao === "sem_classe");
  const fases: [string, Coluna[]][] = [["Implantação", implantacao], ["Em curso", emCurso]];
  const grupo = aberto ? dados.grupos.find((g) => g.grupo_id === aberto.grupo) ?? null : null;
  const cadencia = Object.entries(dados.cadencia)
    .map(([classe, tipos]) => `${classe}: ${tipos.map((t) => nomeDoTipo(dados, t)).join(", ")}`).join(" · ");
  const alternarItens = () => {
    const novo = !verItens;
    definirVerItens(novo);
    try {
      localStorage.setItem(MEMORIA_DO_FLUXOGRAMA, novo ? "aberto" : "recolhido");
    } catch {
      /* sem armazenamento: vale só nesta visita */
    }
  };

  return (
    <div className="sucesso">
      <div className="sucesso-topo">
        <input
          className="entrada entrada-busca" type="search" placeholder="Buscar grupo" aria-label="Buscar grupo"
          value={busca} onChange={(e) => definirBusca(e.target.value)}
        />
        <button type="button" className="botao botao-secundario" aria-expanded={verItens} onClick={alternarItens}>
          {verItens ? "Recolher o que se faz em cada etapa" : "Mostrar o que se faz em cada etapa"}
        </button>
        <p className="campo-ajuda" style={{ margin: 0 }}>
          Reuniões por classe ({cadencia}). Muda em Configurações › Metas.
        </p>
      </div>
      {semClasse.length > 0 && (
        <p className="recado sucesso-sem-classe">
          ⚠ Sem classe, sem reunião cobrada: avalie o Score na Saúde da carteira.{" "}
          {semClasse.map((g, i) => (
            <span key={g.grupo_id}>
              {i > 0 && ", "}
              <button type="button" className="link-de-tabela" onClick={() => abrir(g)}>{g.nome}</button>
            </span>
          ))}
        </p>
      )}
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
                    <header className="sucesso-seta">
                      <h2 className="sucesso-seta-nome">{c.nome}</h2>
                      {c.quem && <p className="sucesso-seta-quem">{c.quem}</p>}
                    </header>
                    {verItens && (
                      <ul className="sucesso-itens">
                        {c.itens.map((i) => <li key={i}>{i}</li>)}
                      </ul>
                    )}
                    <p className="sucesso-contagem">
                      {c.quantas} {c.quantas === 1 ? "grupo" : "grupos"}
                      {c.vencidas > 0 && <span className="cartao-prazo-atrasado"> · ⚠ {c.vencidas} vencida{c.vencidas === 1 ? "" : "s"}</span>}
                    </p>
                    <div className="coluna-cartoes">
                      {c.cartoes}
                      {c.quantas === 0 && <p className="coluna-vazia">Nenhum grupo nesta etapa.</p>}
                    </div>
                  </section>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {grupo && (
        <PainelDoGrupo
          key={`${grupo.grupo_id}-${aberto?.tipo ?? ""}`} f={dados} g={grupo} tipo={aberto?.tipo ?? null}
          aoFechar={() => definirAberto(null)} aoMudar={recarregar}
        />
      )}
    </div>
  );
}

function PainelDoGrupo({ f, g, tipo, aoFechar, aoMudar }: {
  f: Funil; g: Grupo; tipo: string | null; aoFechar: () => void; aoMudar: () => void;
}) {
  const etapa = f.etapas.find((e) => e.chave === g.etapa);
  const subtitulo = g.etapa === "em_curso"
    ? `Em curso${g.classe ? ` · classe ${g.classe}` : ""}${g.em_curso_desde ? ` · desde ${data(g.em_curso_desde)}` : ""}`
    : `Implantação · ${etapa?.nome}${etapa?.participantes ? ` (${etapa.participantes})` : ""}`;
  return g.etapa === "em_curso"
    ? <PainelEmCurso f={f} g={g} tipoPedido={tipo} titulo={g.nome} subtitulo={subtitulo} aoFechar={aoFechar} aoMudar={aoMudar} />
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
