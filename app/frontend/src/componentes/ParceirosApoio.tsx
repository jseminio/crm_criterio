/** As peças da tela Parceiros (19/10/2026) fora do Kanban: a composição de cada indicador, a fila de fees que o sócio
 * da conta aprova e marca pago, e a conferência que liga os textos de canal antigos ao parceiro certo. */

import { useState } from "react";
import { api, ErroDaApi, type FiltrosDosParceiros } from "../api/cliente";
import type {
  FeeDeParceiro,
  IndicadorDosParceiros,
  ItemDaComposicaoDosParceiros,
  ParceiroResumo,
  TextoSemParceiro,
} from "../api/tipos";
import { CampoDeData } from "./CampoDeData";
import { Etiqueta } from "./Etiqueta";
import { TabelaDeComposicao, type ColunaDaComposicao } from "./TabelaDeComposicao";
import { Carregando, Erro } from "./estados";
import { usarAcesso } from "../entrada";
import { data, dinheiro, hojeIso, percentual } from "../formato";
import { usarDados } from "../usarDados";

export const ETAPAS = ["Mapeado", "Qualificado", "Formalizado", "Ativado", "Produtivo", "Estratégico", "Dormente"] as const;
export const ETAPAS_MANUAIS = ["Mapeado", "Qualificado", "Estratégico"];
export const NIVEIS = ["Indicador", "Estruturado", "Estratégico"];
export const ACORDOS = ["Contrato assinado", "Contrato em minuta", "Informal, com fee", "Sem acordo"];

// ------------------------------------------------------------------ composição

type Item = ItemDaComposicaoDosParceiros;

const DETALHE: Record<IndicadorDosParceiros, string> = {
  ativos: "Etapa", indicacoes: "Indicação", conversao: "Indicação", mrr: "Indicação", sem_contrato: "Acordo", fees: "Indicação",
};
const VALOR: Record<IndicadorDosParceiros, string> = {
  ativos: "Indicações", indicacoes: "Conta", conversao: "Fechada", mrr: "MRR (× 13 ÷ 12)", sem_contrato: "Indicações",
  fees: "Fee calculado",
};
const EM_DINHEIRO: IndicadorDosParceiros[] = ["mrr", "fees"];

export function ComposicaoDosParceiros({ indicador, filtros }: { indicador: IndicadorDosParceiros; filtros: FiltrosDosParceiros }) {
  const { dados, carregando, erro, recarregar } = usarDados<Item[]>(
    () => api.composicaoDosParceiros(indicador, filtros), [indicador, JSON.stringify(filtros)],
  );
  if (carregando) return <Carregando rotulo="Montando a composição" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  const itens = dados ?? [];
  if (itens.length === 0) return <p className="estado-texto">Nada compõe este número com os filtros da tela.</p>;
  const dinheiroNaColuna = EM_DINHEIRO.includes(indicador);
  const mostrarValor = (i: Item) => (dinheiroNaColuna ? dinheiro(i.valor) : indicador === "conversao"
    ? (Number(i.valor) ? "Sim" : "Não") : String(Number(i.valor)));
  const colunas: ColunaDaComposicao<Item>[] = [
    { titulo: "Parceiro", valor: (i) => i.parceiro },
    { titulo: DETALHE[indicador], valor: (i) => i.detalhe },
    ...(indicador === "ativos" || indicador === "sem_contrato" ? [] : [{
      titulo: "Situação", valor: (i: Item) => i.referencia, mostrar: (i: Item) => <Etiqueta texto={i.referencia} />,
    }]),
    { titulo: VALOR[indicador], numerico: true, valor: (i) => Number(i.valor), mostrar: mostrarValor },
  ];
  const soma = itens.reduce((s, i) => s + Number(i.valor), 0);
  const total = indicador === "conversao"
    ? percentual(((soma * 100) / itens.length).toFixed(1))
    : indicador === "ativos" || indicador === "sem_contrato" ? `${itens.length} parceiro${itens.length === 1 ? "" : "s"}`
      : dinheiroNaColuna ? dinheiro(soma) : String(soma);
  return (
    <TabelaDeComposicao colunas={colunas} linhas={itens} chave={(_, n) => n} rotulo="Composição"
      rodape={
        <tr className="linha-total">
          <td colSpan={colunas.length - 1}><strong>Total</strong></td>
          <td className="tabela-numero"><strong>{total}</strong></td>
        </tr>
      } />
  );
}

// ------------------------------------------------------------------ fees

export function FeesDosParceiros({ aoMudar }: { aoMudar: () => void }) {
  const { pode } = usarAcesso();
  const socio = pode("parceiros.aprovar_fee");
  const { dados, carregando, erro, recarregar } = usarDados<FeeDeParceiro[]>(
    () => api.feesDosParceiros(["A aprovar", "Aprovado, a pagar"]), [],
  );
  const [aviso, definirAviso] = useState<string | null>(null);
  const [calculando, definirCalculando] = useState(false);

  async function agir(acao: () => Promise<unknown>, depois?: string) {
    definirAviso(null);
    try {
      await acao();
      if (depois) definirAviso(depois);
    } catch (e) {
      definirAviso(e instanceof ErroDaApi ? e.message : "Não consegui salvar.");
    }
    recarregar();
    aoMudar();
  }

  async function calcular() {
    definirCalculando(true);
    await agir(async () => {
      const { novos } = await api.calcularFees();
      definirAviso(novos ? `${novos} fee${novos === 1 ? "" : "s"} novo${novos === 1 ? "" : "s"} para aprovar.` : "Nenhum fee novo: os recebidos já importados não geram fee pendente.");
    });
    definirCalculando(false);
  }

  return (
    <div>
      <p className="campo-ajuda">
        Recorrente: a 1ª parcela, o primeiro recebimento do grupo a partir do aceite, limitado à parcela mensal. Não
        recorrente: 10% de cada recebimento até o valor do contrato. O recebido vem do Omie, bruto e por grupo; o sócio
        confere o valor líquido de impostos antes de aprovar.
      </p>
      {(socio || pode("parceiros.editar")) && (
        <button type="button" className="botao botao-secundario" onClick={calcular} disabled={calculando}>
          {calculando ? "Calculando…" : "Calcular fees pelos recebidos"}
        </button>
      )}
      {aviso && <p className="campo-ajuda" role="status">{aviso}</p>}
      {carregando && <Carregando rotulo="Carregando os fees" />}
      {erro && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {dados && dados.length === 0 && <p className="estado-texto">Nenhum fee esperando aprovação ou pagamento.</p>}
      {dados && dados.length > 0 && (
        <table className="tabela">
          <thead>
            <tr>
              <th>Parceiro</th><th>Conta</th><th>Regra</th><th>Competência</th>
              <th className="tabela-numero">Recebido</th><th className="tabela-numero">Fee</th><th>Situação</th>{socio && <th>Ação</th>}
            </tr>
          </thead>
          <tbody>
            {dados.map((f) => <LinhaDoFee key={f.id} fee={f} socio={socio} agir={agir} />)}
          </tbody>
        </table>
      )}
    </div>
  );
}

function LinhaDoFee({ fee: f, socio, agir }: {
  fee: FeeDeParceiro;
  socio: boolean;
  agir: (acao: () => Promise<unknown>, depois?: string) => Promise<void>;
}) {
  const [valor, definirValor] = useState(f.calculado);
  const [motivo, definirMotivo] = useState("");
  const [pagoEm, definirPagoEm] = useState(hojeIso());
  return (
    <tr>
      <td>{f.parceiro}</td>
      <td>{f.grupo ?? f.oportunidade}<br /><span style={{ color: "var(--texto-fraco)", fontSize: 12 }}>{f.oportunidade}</span></td>
      <td>{f.regra}</td>
      <td>{data(f.competencia)}</td>
      <td className="tabela-numero">{dinheiro(f.base)}</td>
      <td className="tabela-numero">{dinheiro(f.valor_aprovado ?? f.calculado)}</td>
      <td><Etiqueta texto={f.situacao} />{f.decidido_por && <><br /><span style={{ fontSize: 12 }}>{f.decidido_por}</span></>}</td>
      {socio && (
        <td>
          {f.situacao === "A aprovar" && (
            <div className="formulario">
              <input className="entrada" type="number" step="0.01" min="0" aria-label={`Valor líquido do fee de ${f.parceiro}`}
                value={valor} onChange={(e) => definirValor(e.target.value)} />
              <button type="button" className="botao botao-secundario"
                onClick={() => agir(() => api.aprovarFee(f.id, valor || "0"), "Fee aprovado.")}>Aprovar</button>
              <input className="entrada" placeholder="Motivo da recusa" aria-label={`Motivo da recusa do fee de ${f.parceiro}`}
                value={motivo} onChange={(e) => definirMotivo(e.target.value)} />
              <button type="button" className="botao botao-secundario" disabled={motivo.trim().length < 3}
                onClick={() => agir(() => api.recusarFee(f.id, motivo.trim()), "Fee recusado.")}>Recusar</button>
            </div>
          )}
          {f.situacao === "Aprovado, a pagar" && (
            <div className="formulario">
              <CampoDeData value={pagoEm} aoMudar={definirPagoEm} aria-label={`Data do pagamento a ${f.parceiro}`} />
              <button type="button" className="botao botao-secundario" disabled={!pagoEm}
                onClick={() => agir(() => api.marcarFeePago(f.id, pagoEm), "Pagamento registrado.")}>Marcar pago</button>
            </div>
          )}
        </td>
      )}
    </tr>
  );
}

// ------------------------------------------------------------------ conferência

export function ConferenciaDosTextos({ aoLigar }: { aoLigar: () => void }) {
  const textos = usarDados<TextoSemParceiro[]>(() => api.conferenciaDosParceiros(), []);
  const parceiros = usarDados<ParceiroResumo[]>(() => api.parceiros(), []);
  const [aviso, definirAviso] = useState<string | null>(null);

  if (textos.carregando || parceiros.carregando) return <Carregando rotulo="Lendo os canais do funil" />;
  if (textos.erro) return <Erro mensagem={textos.erro} aoTentarDeNovo={textos.recarregar} />;
  if (parceiros.erro) return <Erro mensagem={parceiros.erro} aoTentarDeNovo={parceiros.recarregar} />;
  const lista = textos.dados ?? [];

  async function ligar(texto: string, parceiroId: number) {
    definirAviso(null);
    try {
      const p = await api.ligarTextoDoCanal(texto, parceiroId);
      definirAviso(`"${texto}" ligado a ${p.nome}.`);
    } catch (e) {
      definirAviso(e instanceof ErroDaApi ? e.message : "Não consegui ligar.");
    }
    textos.recarregar();
    aoLigar();
  }

  return (
    <div>
      <p className="campo-ajuda">
        Oportunidades do funil com tipo de canal Parceiros ou Advogados e sem parceiro ligado, agrupadas pelo texto do
        canal. Ligar leva todas as do texto ao parceiro, com a originação como data da indicação; a validação fica para o
        sócio confirmar.
      </p>
      {aviso && <p className="campo-ajuda" role="status">{aviso}</p>}
      {lista.length === 0 ? (
        <p className="estado-texto">Nenhuma indicação antiga sem parceiro.</p>
      ) : (
        <table className="tabela">
          <thead>
            <tr><th>Texto do canal</th><th>Tipo</th><th className="tabela-numero">Oportunidades</th><th>Parceiro</th></tr>
          </thead>
          <tbody>
            {lista.map((t) => (
              <LinhaDaConferencia key={`${t.tipo_canal}-${t.texto}`} texto={t} parceiros={parceiros.dados ?? []} aoLigar={ligar} />
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function LinhaDaConferencia({ texto: t, parceiros, aoLigar }: {
  texto: TextoSemParceiro;
  parceiros: ParceiroResumo[];
  aoLigar: (texto: string, parceiroId: number) => void;
}) {
  const [escolhido, definirEscolhido] = useState<string>(t.sugestao_id ? String(t.sugestao_id) : "");
  return (
    <tr>
      <td>{t.texto}</td>
      <td>{t.tipo_canal}</td>
      <td className="tabela-numero">{t.oportunidades}</td>
      <td>
        <select className="selecao" aria-label={`Parceiro para ${t.texto}`} value={escolhido}
          onChange={(e) => definirEscolhido(e.target.value)}>
          <option value="">Escolha o parceiro</option>
          {parceiros.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
        </select>{" "}
        <button type="button" className="botao botao-secundario" disabled={!escolhido}
          onClick={() => aoLigar(t.texto, Number(escolhido))}>Ligar</button>
        {parceiros.length === 0 && <span className="campo-ajuda"> Cadastre o parceiro antes.</span>}
      </td>
    </tr>
  );
}
