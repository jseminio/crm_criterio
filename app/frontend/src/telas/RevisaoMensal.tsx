/** Revisão mensal do ISC (Etapa 3): congela o placar do mês e guarda a evolução.
 *
 * "Registrar revisão do mês" sempre registra o **mês civil atual** — sem escolher data, para reduzir
 * erro. Corrigir o rótulo de uma revisão passada (por exemplo, a de julho/2026) é uma ação à parte,
 * dentro do histórico: só muda a data, nunca os números congelados.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { RevisaoDaCarteira } from "../api/tipos";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { PainelLateral } from "../componentes/PainelLateral";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";

function chaveDoMes(iso: string): string {
  return iso.slice(0, 7);
}

function mesAno(chave: string): string {
  const d = new Date(`${chave}-01T00:00:00`);
  const s = d.toLocaleDateString("pt-BR", { month: "long", year: "numeric" });
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function mesCurto(chave: string): string {
  const d = new Date(`${chave}-01T00:00:00`);
  return d.toLocaleDateString("pt-BR", { month: "short", year: "2-digit" }).replace(".", "");
}

const um1 = (v: string) => Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

function GraficoDeEvolucao({ revisoes }: { revisoes: RevisaoDaCarteira[] }) {
  if (revisoes.length === 0) {
    return <p className="numero-nota">Nenhuma revisão registrada ainda — o gráfico aparece a partir da primeira.</p>;
  }
  const W = 640, H = 180, esq = 10, dir = 10, cima = 10, baixo = 26;
  const largura = W - esq - dir, altura = H - cima - baixo;
  const x = (i: number) => esq + (revisoes.length === 1 ? largura / 2 : (i / (revisoes.length - 1)) * largura);
  const y = (v: number) => cima + ((100 - v) / 100) * altura;
  const pontos = revisoes.map((r, i) => `${x(i)},${y(Number(r.isc_valor))}`).join(" ");

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="revisao-grafico" role="img"
      aria-label={`Evolução do ISC em ${revisoes.length} revisão${revisoes.length === 1 ? "" : "ões"}`}>
      <rect x={esq} y={cima} width={largura} height={altura * 0.35} className="revisao-faixa revisao-faixa-saudavel" />
      <rect x={esq} y={cima + altura * 0.35} width={largura} height={altura * 0.30} className="revisao-faixa revisao-faixa-atencao" />
      <rect x={esq} y={cima + altura * 0.65} width={largura} height={altura * 0.35} className="revisao-faixa revisao-faixa-critica" />
      <polyline points={pontos} className="revisao-linha" />
      {revisoes.map((r, i) => (
        <g key={r.id}>
          <circle cx={x(i)} cy={y(Number(r.isc_valor))} r={3.5} className="revisao-ponto" />
          <text x={x(i)} y={y(Number(r.isc_valor)) - 8} textAnchor="middle" className="revisao-rotulo-valor">{um1(r.isc_valor)}</text>
          <text x={x(i)} y={H - 8} textAnchor="middle" className="revisao-rotulo-eixo">{mesCurto(chaveDoMes(r.mes_de_referencia))}</text>
        </g>
      ))}
    </svg>
  );
}

function LinhaDaRevisao({ revisao, aoMudar }: { revisao: RevisaoDaCarteira; aoMudar: () => void }) {
  const [editando, definirEditando] = useState(false);
  const [mes, definirMes] = useState(chaveDoMes(revisao.mes_de_referencia));
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await api.editarMesDaRevisao(revisao.id, mes);
      definirEditando(false);
      aoMudar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao corrigir o mês.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <tr>
      <td>
        {editando ? (
          <span className="revisao-editar-mes">
            <input type="month" className="entrada" value={mes} onChange={(e) => definirMes(e.target.value)} aria-label={`Novo mês para a revisão de ${mesAno(chaveDoMes(revisao.mes_de_referencia))}`} />
            <button type="button" className="botao botao-secundario" disabled={salvando} onClick={salvar}>{salvando ? "Salvando…" : "Salvar"}</button>
            <button type="button" className="botao botao-secundario" disabled={salvando} onClick={() => definirEditando(false)}>Cancelar</button>
          </span>
        ) : (
          <>
            {mesAno(chaveDoMes(revisao.mes_de_referencia))}{" "}
            <button type="button" className="revisao-editar-link" onClick={() => definirEditando(true)}>Editar mês</button>
          </>
        )}
        {erro && <span role="alert" className="ia-analise-erro"> {erro}</span>}
      </td>
      <td className="tabela-numero">{um1(revisao.isc_valor)}</td>
      <td className="tabela-numero">{um1(revisao.componente_classe)}</td>
      <td className="tabela-numero">{um1(revisao.componente_semaforo)}</td>
      <td className="tabela-numero">{um1(revisao.componente_churn)}</td>
      <td className="tabela-numero">{revisao.grupos_travados}</td>
      <td>{revisao.registrada_por}</td>
    </tr>
  );
}

function HistoricoDeRevisoes({ revisoes, aoFechar, aoMudar }: { revisoes: RevisaoDaCarteira[]; aoFechar: () => void; aoMudar: () => void }) {
  const { ordenacao, alternar: alternarOrdenacao } = usarOrdenacao();
  const maisRecentePrimeiro = [...revisoes].reverse();
  const ordenadas = ordenar(maisRecentePrimeiro, ordenacao, {
    mes: (r) => r.mes_de_referencia,
    isc: (r) => Number(r.isc_valor),
    classe: (r) => Number(r.componente_classe),
    semaforo: (r) => Number(r.componente_semaforo),
    churn: (r) => Number(r.componente_churn),
    travados: (r) => r.grupos_travados,
    autor: (r) => r.registrada_por,
  });
  return (
    <PainelLateral titulo="Histórico de revisões" subtitulo="Evolução do ISC mês a mês, com a data de cada revisão corrigível." aoFechar={aoFechar}>
      <GraficoDeEvolucao revisoes={revisoes} />
      {revisoes.length === 0 ? (
        <p className="numero-nota">Registre a primeira revisão para começar o histórico.</p>
      ) : (
        <table className="tabela revisao-tabela" aria-label="Revisões registradas">
          <thead>
            <tr>
              <ThOrdenavel coluna="mes" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Mês</ThOrdenavel>
              <ThOrdenavel coluna="isc" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>ISC</ThOrdenavel>
              <ThOrdenavel coluna="classe" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Classe</ThOrdenavel>
              <ThOrdenavel coluna="semaforo" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Semáforo</ThOrdenavel>
              <ThOrdenavel coluna="churn" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Churn</ThOrdenavel>
              <ThOrdenavel coluna="travados" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Travados</ThOrdenavel>
              <ThOrdenavel coluna="autor" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Registrado por</ThOrdenavel>
            </tr>
          </thead>
          <tbody>
            {ordenadas.map((r) => <LinhaDaRevisao key={r.id} revisao={r} aoMudar={aoMudar} />)}
          </tbody>
        </table>
      )}
    </PainelLateral>
  );
}

export function RevisaoMensal() {
  const { dados, carregando, erro, recarregar } = usarDados<RevisaoDaCarteira[]>(() => api.revisoesDaCarteira(), []);
  const [autor, definirAutor] = useState("");
  const [registrando, definirRegistrando] = useState(false);
  const [erroDeRegistro, definirErroDeRegistro] = useState<string | null>(null);
  const [historico, definirHistorico] = useState(false);

  const mesAtual = new Date().toISOString().slice(0, 7);
  const revisaoDoMes = dados?.find((r) => chaveDoMes(r.mes_de_referencia) === mesAtual) ?? null;

  const registrar = async () => {
    definirRegistrando(true);
    definirErroDeRegistro(null);
    try {
      await api.registrarRevisaoDaCarteira(autor.trim());
      definirAutor("");
      recarregar();
    } catch (falha) {
      definirErroDeRegistro(falha instanceof ErroDaApi ? falha.message : "Falha ao registrar a revisão.");
    } finally {
      definirRegistrando(false);
    }
  };

  return (
    <div className="revisao-barra">
      <p className="revisao-status">
        {carregando && !dados
          ? "Carregando revisões…"
          : revisaoDoMes
            ? `Revisão de ${mesAno(mesAtual)} registrada por ${revisaoDoMes.registrada_por} em ${dataHora(revisaoDoMes.registrada_em)}.`
            : `Revisão de ${mesAno(mesAtual)} ainda não registrada.`}
        {erro && ` ${erro}`}
      </p>
      <div className="revisao-acoes">
        {!revisaoDoMes && (
          <>
            <input className="entrada revisao-autor" placeholder="Quem está revisando" value={autor}
              onChange={(e) => definirAutor(e.target.value)} aria-label="Quem está revisando" />
            <button type="button" className="botao botao-secundario" disabled={registrando || autor.trim().length < 2} onClick={registrar}>
              {registrando ? "Registrando…" : "Registrar revisão do mês"}
            </button>
          </>
        )}
        <button type="button" className="revisao-historico-link" onClick={() => definirHistorico(true)}>Ver histórico de revisões</button>
      </div>
      {erroDeRegistro && <p role="alert" className="ia-analise-erro">{erroDeRegistro}</p>}
      {historico && <HistoricoDeRevisoes revisoes={dados ?? []} aoFechar={() => definirHistorico(false)} aoMudar={recarregar} />}
    </div>
  );
}
