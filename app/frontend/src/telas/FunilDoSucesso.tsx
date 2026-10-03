/** Funil do Sucesso do Cliente (aprovado por Eduardo em 02 e 03/10/2026). O caminho do fluxograma
 * "Macroprocesso — Comercial & Sucesso do Cliente": Contrato → Handover → Kickoff (implantação) e a
 * reunião de resultado de cada classe (em curso): A mensal, B trimestral, C semestral.
 *
 * - Escolhe-se a visão: Consolidado (todas as classes, com o quadro que as compara e a bimestral
 *   interna da carteira), Classe A, B ou C (com a intenção da classe) ou Sem classe.
 * - Kanban ou Grade, como o Funil comercial. O que se faz em cada etapa aparece no ⓘ do cabeçalho
 *   (passar o mouse, focar ou clicar), em vez de ocupar a coluna.
 * - Estado nunca só por cor: vencida leva ⚠ e texto. O clique abre o painel com uma ação principal. */

import { useState, type ReactNode } from "react";
import { api } from "../api/cliente";
import type { FunilDoSucesso as Funil, GrupoNoFunilDoSucesso as Grupo, ReuniaoDevida } from "../api/tipos";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { usarAcesso } from "../entrada";
import { data, dinheiro, dinheiroCurto } from "../formato";
import { usarDados } from "../usarDados";
import { PainelDaCarteira } from "./PainelDaCarteira";
import { PainelDoGrupo } from "./PainelDoGrupo";

const MEMORIA_DA_VISAO = "crm.sucesso.visao";
const MEMORIA_DA_CLASSE = "crm.sucesso.classe";
const CLASSES = ["A", "B", "C"] as const;

type Recorte = "todas" | "A" | "B" | "C" | "sem";
type Visao = "kanban" | "grade";

type Coluna = {
  chave: string;
  fase: string;
  nome: string;
  quem: string | null;
  itens: string[];
  quantas: number;
  vencidas: number;
  /** Soma do MRR bruto dos clientes da coluna, como o "ao ano" do Funil comercial. */
  mrr: number;
  cartoes: ReactNode[];
};

export const nomeDoTipo = (f: Funil, chave: string) =>
  f.tipos.find((t) => t.chave === chave)?.nome ?? f.tipos_antigos?.[chave] ?? chave;

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

const piorReuniao = (g: Grupo): ReuniaoDevida | null => [...g.reunioes].sort(ordemDaReuniao)[0] ?? null;

const plural = (n: number, um: string, varios: string) => `${n} ${n === 1 ? um : varios}`;

/** Mensal e projeto nunca se somam: um é receita por mês, o outro entra uma vez. */
export function textoDasVendas(n: number, porMes: number, emProjeto: number): string {
  if (n === 0) return "0";
  const valores = [porMes > 0 && `${dinheiro(porMes)}/mês`, emProjeto > 0 && `${dinheiro(emProjeto)} em projeto`].filter(Boolean);
  return `${n}${valores.length ? ` · ${valores.join(" + ")}` : ""}`;
}

function Ajustes({ g }: { g: Grupo }) {
  if (g.ajustes_pendentes === 0) return null;
  return (
    <span className={`cartao-prazo ${g.ajustes_atrasados ? "cartao-prazo-atrasado" : ""}`}>
      {plural(g.ajustes_pendentes, "ajuste pendente", "ajustes pendentes")}
      {g.ajustes_atrasados > 0 && ` · ⚠ ${g.ajustes_atrasados} atrasado${g.ajustes_atrasados === 1 ? "" : "s"}`}
    </span>
  );
}

function Vendas({ g }: { g: Grupo }) {
  if (g.vendas_abertas === 0) return null;
  return <span className="cartao-prazo">{plural(g.vendas_abertas, "venda aberta", "vendas abertas")}</span>;
}

/** O valor do cartão, como no Funil comercial: o MRR bruto do cliente, por mês. */
function MrrDoCartao({ g }: { g: Grupo }) {
  const mrr = Number(g.mrr_bruto);
  return mrr > 0 ? <span className="cartao-valor">{dinheiroCurto(mrr)}/mês</span> : null;
}

function CartaoDaImplantacao({ f, g, aoAbrir }: { f: Funil; g: Grupo; aoAbrir: () => void }) {
  const itens = f.checklist[g.etapa] ?? [];
  const feitos = itens.filter((i) => g.itens_feitos.includes(i.chave)).length;
  return (
    <button type="button" className="cartao cartao-clicavel" onClick={aoAbrir}>
      <span className="cartao-grupo">{g.nome}</span>
      <MrrDoCartao g={g} />
      {g.classe && <span className="cartao-linha"><span className="etiqueta etiqueta-neutra">Classe {g.classe}</span></span>}
      <span className="cartao-prazo">{feitos} de {plural(itens.length, "item feito", "itens feitos")}</span>
    </button>
  );
}

function CartaoDaReuniao({ g, r, aoAbrir }: { g: Grupo; r: ReuniaoDevida | null; aoAbrir: () => void }) {
  return (
    <button type="button" className="cartao cartao-clicavel" onClick={aoAbrir}>
      <span className="cartao-grupo">{g.nome}</span>
      <MrrDoCartao g={g} />
      <span className="cartao-linha">
        {g.classe ? <span className="etiqueta etiqueta-neutra">Classe {g.classe}</span>
          : <span className="etiqueta etiqueta-perda">⚠ sem classe</span>}
      </span>
      {r && <span className={`cartao-prazo ${r.atrasada ? "cartao-prazo-atrasado" : ""}`}>{textoDaReuniao(r)}</span>}
      <Ajustes g={g} />
      <Vendas g={g} />
    </button>
  );
}

function lembrar<T extends string>(chave: string, validos: readonly T[], padrao: T): T {
  try {
    const v = localStorage.getItem(chave);
    return validos.includes(v as T) ? (v as T) : padrao;
  } catch {
    return padrao;
  }
}

function guardar(chave: string, valor: string) {
  try {
    localStorage.setItem(chave, valor);
  } catch {
    /* sem armazenamento: vale só nesta visita */
  }
}

/** A explicação da coluna: abre no mouse, no foco e no clique (no celular não há mouse). Fica fora
 * do kanban, em posição fixa, para a rolagem do kanban não cortar. */
type Dica = { chave: string; titulo: string; itens: string[]; topo: number; esquerda: number; fixa: boolean };

function CabecalhoDaColuna({ c, dica, aoMostrar, aoEsconder }: {
  c: Coluna; dica: Dica | null; aoMostrar: (d: Dica) => void; aoEsconder: (forcar?: boolean) => void;
}) {
  const aberta = dica?.chave === c.chave;
  const mostrar = (alvo: HTMLElement, fixa: boolean) => {
    const caixa = alvo.getBoundingClientRect();
    const esquerda = Math.max(8, Math.min(caixa.right - 300, window.innerWidth - 308));
    aoMostrar({ chave: c.chave, titulo: `${c.nome}${c.quem ? ` · ${c.quem}` : ""}`, itens: c.itens, topo: caixa.bottom + 6, esquerda, fixa });
  };
  return (
    <header className="coluna-topo">
      <h2 className="coluna-nome">
        <span>{c.nome}</span>
        <span className="sucesso-coluna-direita">
          <span className="coluna-quantas">{c.quantas}</span>
          {c.itens.length > 0 && (
            <button
              type="button" className="sucesso-info" aria-label={`O que se faz em ${c.nome}`} aria-expanded={aberta}
              aria-describedby={aberta ? "sucesso-dica" : undefined}
              onMouseEnter={(e) => mostrar(e.currentTarget, false)} onMouseLeave={() => aoEsconder()}
              onFocus={(e) => mostrar(e.currentTarget, false)} onBlur={() => aoEsconder(true)}
              onClick={(e) => (aberta && dica?.fixa ? aoEsconder(true) : mostrar(e.currentTarget, true))}
            >
              i
            </button>
          )}
        </span>
      </h2>
      <p className="coluna-valor">{c.fase} · {dinheiroCurto(c.mrr)}/mês</p>
      {c.vencidas > 0 && <p className="coluna-valor cartao-prazo-atrasado">⚠ {c.vencidas} vencida{c.vencidas === 1 ? "" : "s"}</p>}
    </header>
  );
}

function Kanban({ fases, dica, definirDica }: {
  fases: [string, Coluna[]][]; dica: Dica | null; definirDica: (d: Dica | null) => void;
}) {
  const esconder = (forcar = false) => {
    if (forcar || !dica?.fixa) definirDica(null);
  };
  // As mesmas colunas e cartões do Funil comercial (Eduardo, 03/10/2026): uma fileira só, rolando
  // na horizontal; a fase e quem participa ficam na linha de baixo e no ⓘ.
  return (
    <div className="kanban">
      {fases.flatMap(([, cols]) => cols).map((c) => (
        <section className="coluna" key={c.chave} aria-label={c.nome}>
          <CabecalhoDaColuna c={c} dica={dica} aoMostrar={definirDica} aoEsconder={esconder} />
          <div className="coluna-cartoes">
            {c.cartoes}
            {c.quantas === 0 && <p className="coluna-vazia">Nenhum grupo nesta etapa.</p>}
          </div>
        </section>
      ))}
    </div>
  );
}

type Linha = { g: Grupo; r: ReuniaoDevida | null; etapa: string; reuniao: string; ordem: number };

function Grade({ f, linhas, aoAbrir }: { f: Funil; linhas: Linha[]; aoAbrir: (g: Grupo, tipo: string | null) => void }) {
  const { ordenacao, alternar } = usarOrdenacao();
  const ordenadas = ordenar(linhas, ordenacao, {
    grupo: (l) => l.g.nome,
    classe: (l) => l.g.classe,
    etapa: (l) => l.etapa,
    reuniao: (l) => l.reuniao,
    ultima: (l) => l.r?.ultima,
    proxima: (l) => l.r?.proxima,
    ajustes: (l) => l.g.ajustes_pendentes,
    vendas: (l) => l.g.vendas_abertas,
  });
  const th = (coluna: string, rotulo: string, numerico = false) => (
    <ThOrdenavel coluna={coluna} ordenacao={ordenacao} aoAlternar={alternar} numerico={numerico}>{rotulo}</ThOrdenavel>
  );
  return (
    <div className="tabela-rolagem">
      <table className="tabela sucesso-grade">
        <thead>
          <tr>
            {th("grupo", "Grupo")}{th("classe", "Classe")}{th("etapa", "Etapa")}{th("reuniao", "Reunião da classe")}
            {th("ultima", "Última")}{th("proxima", "Próxima")}{th("ajustes", "Ajustes da área técnica")}{th("vendas", "Vendas abertas")}
          </tr>
        </thead>
        <tbody>
          {ordenadas.map(({ g, r, etapa, reuniao }) => {
            const itens = f.checklist[g.etapa] ?? [];
            const feitos = itens.filter((i) => g.itens_feitos.includes(i.chave)).length;
            return (
              <tr key={g.grupo_id} className="linha-clicavel" onClick={() => aoAbrir(g, r?.tipo ?? null)}>
                <td>
                  <button type="button" className="link-de-tabela" onClick={(e) => { e.stopPropagation(); aoAbrir(g, r?.tipo ?? null); }}>
                    {g.nome}
                  </button>
                </td>
                <td>
                  {g.classe ? <span className="etiqueta etiqueta-neutra">{g.classe}</span>
                    : g.situacao === "sem_classe" ? <span className="etiqueta etiqueta-perda">⚠ sem classe</span> : "—"}
                </td>
                <td>{etapa}</td>
                {g.etapa !== "em_curso" ? (
                  <td colSpan={3}>{feitos} de {plural(itens.length, "item do checklist feito", "itens do checklist feitos")}</td>
                ) : g.situacao === "sem_classe" ? (
                  <td colSpan={3}>Sem classe: avalie o Score na Saúde da carteira</td>
                ) : (
                  <>
                    <td>{reuniao}</td>
                    <td>{r?.ultima ? data(r.ultima) : <span className="campo-ajuda">nenhuma</span>}</td>
                    <td className={r?.atrasada ? "cartao-prazo-atrasado" : undefined}>{r ? textoDaReuniao(r) : "—"}</td>
                  </>
                )}
                <td>
                  {g.ajustes_pendentes === 0 ? "—" : (
                    <>
                      {plural(g.ajustes_pendentes, "pendente", "pendentes")}
                      {g.ajustes_atrasados > 0 && <span className="cartao-prazo-atrasado"> · ⚠ {g.ajustes_atrasados} atrasado{g.ajustes_atrasados === 1 ? "" : "s"}</span>}
                    </>
                  )}
                </td>
                <td>{g.vendas_abertas === 0 ? "—" : textoDasVendas(g.vendas_abertas, Number(g.vendas_por_mes), Number(g.vendas_em_projeto))}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

type Numeros = {
  clientes: number; mrr: number; emCurso: number; emDia: number; vencidas: number;
  ajustes: number; ajustesAtrasados: number; vendas: number; porMes: number; emProjeto: number;
};

function numerosDe(grupos: Grupo[]): Numeros {
  const emCurso = grupos.filter((g) => g.etapa === "em_curso" && g.situacao !== "sem_classe");
  return {
    clientes: grupos.length,
    mrr: grupos.reduce((s, g) => s + Number(g.mrr_bruto), 0),
    emCurso: emCurso.length,
    emDia: emCurso.filter((g) => g.situacao === "em_dia").length,
    vencidas: emCurso.filter((g) => g.situacao === "atrasada").length,
    ajustes: grupos.reduce((s, g) => s + g.ajustes_pendentes, 0),
    ajustesAtrasados: grupos.reduce((s, g) => s + g.ajustes_atrasados, 0),
    vendas: grupos.reduce((s, g) => s + g.vendas_abertas, 0),
    porMes: grupos.reduce((s, g) => s + Number(g.vendas_por_mes), 0),
    emProjeto: grupos.reduce((s, g) => s + Number(g.vendas_em_projeto), 0),
  };
}

const emDia = (n: Numeros) => (n.emCurso ? `${Math.round((n.emDia / n.emCurso) * 100)}%` : "—");
const textoDosAjustes = (n: Numeros) =>
  `${n.ajustes}${n.ajustesAtrasados ? ` · ⚠ ${n.ajustesAtrasados} atrasado${n.ajustesAtrasados === 1 ? "" : "s"}` : ""}`;

function QuadroDasClasses({ f, aoEscolher }: { f: Funil; aoEscolher: (c: Recorte) => void }) {
  return (
    <section className="numero sucesso-quadro" aria-label="Comparativo das classes">
      <div className="tabela-rolagem">
        <table className="quadro">
          <thead>
            <tr>
              <th scope="col">Classe</th><th scope="col">Clientes</th><th scope="col">MRR bruto</th><th scope="col">Reuniões em dia</th>
              <th scope="col">Vencidas</th><th scope="col">Ajustes pendentes</th><th scope="col">Vendas abertas</th>
            </tr>
          </thead>
          <tbody>
            {CLASSES.map((c) => {
              const n = numerosDe(f.grupos.filter((g) => g.classe === c));
              const reuniao = (f.cadencia[c] ?? []).map((t) => nomeDoTipo(f, t).toLowerCase()).join(", ");
              return (
                <tr key={c}>
                  <td>
                    <button type="button" className="link-de-tabela" onClick={() => aoEscolher(c)}>
                      <strong>{c}</strong> · {reuniao}
                    </button>
                  </td>
                  <td>{n.clientes}</td>
                  <td>{dinheiro(n.mrr)}</td>
                  <td>{emDia(n)}</td>
                  <td className={n.vencidas ? "cartao-prazo-atrasado" : undefined}>{n.vencidas ? `⚠ ${n.vencidas}` : "0"}</td>
                  <td className={n.ajustesAtrasados ? "cartao-prazo-atrasado" : undefined}>{textoDosAjustes(n)}</td>
                  <td className="quadro-vendas">
                    {n.vendas}
                    {n.porMes > 0 && <span>{dinheiro(n.porMes)}/mês</span>}
                    {n.emProjeto > 0 && <span>{n.porMes > 0 ? "+ " : ""}{dinheiro(n.emProjeto)} em projeto</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="campo-ajuda" style={{ margin: 0 }}>
        MRR em bruto, dos contratos ativos. Vendas abertas: oportunidades que as reuniões abriram no Funil comercial e ainda
        não foram decididas; o valor por mês e o de projeto ficam separados.
      </p>
    </section>
  );
}

function CartaoDaCarteira({ f, aoAbrir }: { f: Funil; aoAbrir: () => void }) {
  const c = f.carteira;
  return (
    <section className="numero sucesso-carteira" aria-label="Reunião bimestral da carteira">
      <p className="numero-rotulo" style={{ margin: 0 }}>Reunião bimestral da carteira · interna</p>
      <p style={{ margin: 0 }}>{c.participantes}: overview da carteira e correção de rotas de análise.</p>
      <p style={{ margin: 0 }}>
        {c.ultima ? `Última ${data(c.ultima)}` : "Nenhuma registrada"} ·{" "}
        {c.atrasada
          ? <strong className="cartao-prazo-atrasado">⚠ venceu em {data(c.proxima)} ({c.dias_de_atraso} d)</strong>
          : <strong>próxima até {data(c.proxima)}</strong>}
      </p>
      <div><button type="button" className="botao botao-secundario" onClick={aoAbrir}>Registrar a bimestral</button></div>
    </section>
  );
}

function Intencao({ f, classe, grupos }: { f: Funil; classe: string; grupos: Grupo[] }) {
  const { pode } = usarAcesso();
  const n = numerosDe(grupos);
  const reuniao = (f.cadencia[classe] ?? []).map((t) => nomeDoTipo(f, t).toLowerCase()).join(", ");
  return (
    <section className="sucesso-intencao" aria-label={`Intenção da classe ${classe}`}>
      <p className="numero-rotulo" style={{ margin: 0 }}>Classe {classe} · reunião {reuniao} · intenção</p>
      <p style={{ margin: 0 }}>
        {f.intencao[classe]}
        {pode("configuracoes.metas") && <span className="campo-ajuda"> · muda em Configurações › Metas</span>}
      </p>
      <p className="campo-ajuda" style={{ margin: 0 }}>
        {plural(n.clientes, "cliente", "clientes")} · {dinheiro(n.mrr)} bruto · {emDia(n)} das reuniões em dia
        {n.vencidas > 0 && <span className="cartao-prazo-atrasado"> · ⚠ {plural(n.vencidas, "vencida", "vencidas")}</span>}
        {" · "}{plural(n.ajustes, "ajuste pendente", "ajustes pendentes")}
        {n.ajustesAtrasados > 0 && ` (⚠ ${n.ajustesAtrasados} atrasado${n.ajustesAtrasados === 1 ? "" : "s"})`}
        {" · "}vendas abertas: {textoDasVendas(n.vendas, n.porMes, n.emProjeto)}
      </p>
    </section>
  );
}

export function FunilDoSucesso() {
  const { dados, carregando, erro, recarregar } = usarDados<Funil>(() => api.funilDoSucesso(), []);
  const [busca, definirBusca] = useState("");
  const [recorte, definirRecorte] = useState<Recorte>(() => lembrar(MEMORIA_DA_CLASSE, ["todas", "A", "B", "C", "sem"] as const, "todas"));
  const [visao, definirVisao] = useState<Visao>(() => lembrar(MEMORIA_DA_VISAO, ["kanban", "grade"] as const, "kanban"));
  const [aberto, definirAberto] = useState<{ grupo: number; tipo: string | null } | null>(null);
  const [carteiraAberta, definirCarteiraAberta] = useState(false);
  const [dica, definirDica] = useState<Dica | null>(null);

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
  const escolher = (r: Recorte) => {
    definirRecorte(r);
    definirDica(null);
    guardar(MEMORIA_DA_CLASSE, r);
  };
  const mudarVisao = (v: Visao) => {
    definirVisao(v);
    definirDica(null);
    guardar(MEMORIA_DA_VISAO, v);
  };
  const semClasse = (g: Grupo) => g.situacao === "sem_classe";
  const doRecorte = (r: Recorte) => dados.grupos.filter((g) =>
    r === "todas" ? true : r === "sem" ? semClasse(g) : g.classe === r);
  const doRecorteAtual = doRecorte(recorte);
  const termo = busca.trim().toLocaleLowerCase("pt-BR");
  const filtrados = termo ? doRecorteAtual.filter((g) => g.nome.toLocaleLowerCase("pt-BR").includes(termo)) : doRecorteAtual;
  const abrir = (g: Grupo, tipo: string | null = null) => definirAberto({ grupo: g.grupo_id, tipo });

  // Colunas: a implantação sempre; em curso, as reuniões da classe (todas, no consolidado).
  const implantacao: Coluna[] = recorte === "sem" ? [] : dados.etapas.filter((e) => e.chave !== "em_curso").map((e) => {
    const grupos = filtrados.filter((g) => g.etapa === e.chave);
    return {
      chave: e.chave, fase: "Implantação", nome: e.nome, quem: e.participantes,
      itens: (dados.checklist[e.chave] ?? []).map((i) => i.rotulo),
      quantas: grupos.length, vencidas: 0, mrr: grupos.reduce((t, g) => t + Number(g.mrr_bruto), 0),
      cartoes: grupos.map((g) => <CartaoDaImplantacao key={g.grupo_id} f={dados} g={g} aoAbrir={() => abrir(g)} />),
    };
  });
  const tiposDoRecorte = recorte === "todas" || recorte === "sem"
    ? dados.tipos : dados.tipos.filter((t) => (dados.cadencia[recorte] ?? []).includes(t.chave));
  const emCurso: Coluna[] = recorte === "sem"
    ? [{
      chave: "sem_classe", fase: "Em curso", nome: "Sem classe", quem: null,
      mrr: filtrados.reduce((t, g) => t + Number(g.mrr_bruto), 0),
      itens: ["Sem a leitura do Score, não há reunião cobrada.", "Avalie o grupo na aba Saúde da carteira: a classe diz qual reunião ele recebe."],
      quantas: filtrados.length, vencidas: 0,
      cartoes: filtrados.map((g) => <CartaoDaReuniao key={g.grupo_id} g={g} r={null} aoAbrir={() => abrir(g)} />),
    }]
    : tiposDoRecorte.map((t) => {
      const pares = filtrados.flatMap((g) => g.reunioes.filter((r) => r.tipo === t.chave).map((r) => ({ g, r })))
        .sort((a, b) => ordemDaReuniao(a.r, b.r) || a.g.nome.localeCompare(b.g.nome, "pt-BR"));
      return {
        chave: t.chave, fase: "Em curso", nome: t.nome, quem: t.participantes, itens: t.pauta,
        quantas: pares.length, vencidas: pares.filter((p) => p.r.atrasada).length,
        mrr: pares.reduce((total, p) => total + Number(p.g.mrr_bruto), 0),
        cartoes: pares.map(({ g, r }) => <CartaoDaReuniao key={g.grupo_id} g={g} r={r} aoAbrir={() => abrir(g, t.chave)} />),
      };
    });
  const fases: [string, Coluna[]][] = [["Implantação", implantacao], ["Em curso", emCurso]];

  // Grade: as mais atrasadas primeiro; depois em dia, pela próxima; depois implantação e sem classe.
  const linhas: Linha[] = filtrados.map((g) => {
    const r = piorReuniao(g);
    const etapa = g.etapa === "em_curso" ? "Em curso" : `Implantação · ${dados.etapas.find((e) => e.chave === g.etapa)?.nome ?? g.etapa}`;
    const ordem = g.etapa !== "em_curso" ? 3 : semClasse(g) ? 4 : r?.atrasada ? 1 : 2;
    return { g, r, etapa, reuniao: r ? nomeDoTipo(dados, r.tipo) : "", ordem };
  }).sort((a, b) => a.ordem - b.ordem
    || (a.r && b.r ? ordemDaReuniao(a.r, b.r) : 0)
    || a.g.nome.localeCompare(b.g.nome, "pt-BR"));

  const semClasseNoRecorte = recorte === "todas" ? filtrados.filter(semClasse) : [];
  const grupo = aberto ? dados.grupos.find((g) => g.grupo_id === aberto.grupo) ?? null : null;
  const botoes: [Recorte, string][] = [["todas", "Consolidado"], ["A", "Classe A"], ["B", "Classe B"], ["C", "Classe C"], ["sem", "Sem classe"]];

  return (
    <div className="sucesso">
      <div className="sucesso-barra">
        <div className="sucesso-classes" role="group" aria-label="Classe">
          {botoes.map(([r, rotulo]) => (
            <button key={r} type="button" className="sucesso-classe" aria-pressed={recorte === r} onClick={() => escolher(r)}>
              {rotulo}<span className="sucesso-classe-quantas">{doRecorte(r).length}</span>
            </button>
          ))}
        </div>
        <div className="sucesso-barra-direita">
          <input
            className="entrada entrada-busca" type="search" placeholder="Buscar grupo" aria-label="Buscar grupo"
            value={busca} onChange={(e) => definirBusca(e.target.value)}
          />
          <div className="visao-toggle" role="group" aria-label="Visão">
            <button type="button" className={`visao-botao ${visao === "kanban" ? "visao-ativa" : ""}`} aria-pressed={visao === "kanban"}
              onClick={() => mudarVisao("kanban")}>▦ Kanban</button>
            <button type="button" className={`visao-botao ${visao === "grade" ? "visao-ativa" : ""}`} aria-pressed={visao === "grade"}
              onClick={() => mudarVisao("grade")}>☰ Grade</button>
          </div>
        </div>
      </div>

      {recorte === "todas" && (
        <div className="sucesso-resumo">
          <QuadroDasClasses f={dados} aoEscolher={escolher} />
          <CartaoDaCarteira f={dados} aoAbrir={() => definirCarteiraAberta(true)} />
        </div>
      )}
      {(recorte === "A" || recorte === "B" || recorte === "C") && <Intencao f={dados} classe={recorte} grupos={doRecorteAtual} />}
      {semClasseNoRecorte.length > 0 && (
        <p className="recado sucesso-sem-classe">
          ⚠ Sem classe, sem reunião cobrada: avalie o Score na Saúde da carteira.{" "}
          {semClasseNoRecorte.map((g, i) => (
            <span key={g.grupo_id}>
              {i > 0 && ", "}
              <button type="button" className="link-de-tabela" onClick={() => abrir(g)}>{g.nome}</button>
            </span>
          ))}
        </p>
      )}

      {doRecorteAtual.length === 0 ? (
        <p className="coluna-vazia">
          {recorte === "sem" ? "Todo cliente em curso tem classe." : `Nenhum cliente da classe ${recorte} no funil.`}
        </p>
      ) : filtrados.length === 0 ? (
        <VazioPorFiltro aoLimpar={() => definirBusca("")} />
      ) : visao === "kanban" ? (
        <Kanban fases={fases} dica={dica} definirDica={definirDica} />
      ) : (
        <>
          <p className="campo-ajuda" style={{ margin: 0 }}>
            {plural(filtrados.length, "cliente", "clientes")} · as mais atrasadas primeiro. Clique numa linha para abrir o cliente.
          </p>
          <Grade f={dados} linhas={linhas} aoAbrir={abrir} />
        </>
      )}

      {dica && (
        <div className="sucesso-dica" id="sucesso-dica" role="tooltip" style={{ top: dica.topo, left: dica.esquerda }}>
          <strong>{dica.titulo}</strong>
          O que se faz nesta etapa:
          <ul>{dica.itens.map((i) => <li key={i}>{i}</li>)}</ul>
        </div>
      )}
      {grupo && (
        <PainelDoGrupo
          key={`${grupo.grupo_id}-${aberto?.tipo ?? ""}`} f={dados} g={grupo} tipo={aberto?.tipo ?? null}
          aoFechar={() => definirAberto(null)} aoMudar={recarregar}
        />
      )}
      {carteiraAberta && <PainelDaCarteira aoFechar={() => definirCarteiraAberta(false)} aoMudar={recarregar} />}
    </div>
  );
}
