/** Classificação da carteira (Etapa 3): classe, Score, alerta e eixo de ação por grupo, e o ISC.
 *
 * Somente leitura. Os números vêm do snapshot mais recente carregado da planilha de saúde da
 * carteira e são recalculados no CRM. Estado nunca só por cor: classe, alerta e cobrança têm texto.
 */

import { Fragment, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { AnaliseDaCarteira, ClassificacaoDaCarteira } from "../api/tipos";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { cnpj, data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { RevisaoMensal } from "./RevisaoMensal";

const decimais = (v: string, n: number) =>
  Number(v).toLocaleString("pt-BR", { minimumFractionDigits: n, maximumFractionDigits: n });
const um = (v: string) => decimais(v, 2);
const um1 = (v: string) => decimais(v, 1);
const ALERTA: Record<string, string> = { "⚠": "⚠ Risco de churn", "⚑": "⚑ Saída a organizar" };
const PRIORIDADE = ["Cobrança", "Reter já", "Reter / vigiar", "Saída organizada", "Sem urgência"];
const EIXO_COBRANCA = "Cobrança — sem tratamento preferencial";
const SEMAFORO_ROTULO: Record<number, string> = { 1: "Controlada", 2: "Atenção", 3: "Crítico" };

const LEGENDA_DOS_EIXOS: { nome: string; quando: string; significa: string }[] = [
  {
    nome: "Cobrança — sem tratamento preferencial",
    quando: "Adimplência ≤ 2 ($$$). Vence qualquer outro eixo.",
    significa: "Conversa de cobrança (renegociação, corte). Enquanto não pagar, o cliente não recebe tratamento preferencial, mesmo sendo A ou B.",
  },
  {
    nome: "Reter já (crítico)",
    quando: "Classe A com alerta de churn ⚠ (churn ≥ 4).",
    significa: "Há muito a salvar: conversa de retenção imediata (sponsor, diagnóstico, plano).",
  },
  {
    nome: "Reter / vigiar",
    quando: "Classe B com alerta de churn ⚠ (churn ≥ 4).",
    significa: "Risco de saída em cliente que vale segurar: acompanhar de perto e conduzir a retenção.",
  },
  {
    nome: "Saída organizada",
    quando: "Classe C com alerta ⚑ (churn ≥ 4).",
    significa: "Churn alto aqui não é emergência: preparar uma saída ordenada, sem gastar esforço de retenção.",
  },
  {
    nome: "Sem urgência de churn",
    quando: "Nenhum dos casos acima.",
    significa: "Nenhuma ação extra agora; segue a rotina e a revisão mensal do ISC.",
  },
];

const rank = (eixo: string) => {
  const i = PRIORIDADE.findIndex((p) => eixo.startsWith(p));
  return i === -1 ? PRIORIDADE.length : i;
};

const CX = 200, CY = 195, R = 170;
const ponto = (valor: number) => {
  const a = ((180 - valor * 1.8) * Math.PI) / 180;
  return `${(CX + R * Math.cos(a)).toFixed(1)} ${(CY - R * Math.sin(a)).toFixed(1)}`;
};
const arco = (de: number, ate: number) => `M ${ponto(de)} A ${R} ${R} 0 0 1 ${ponto(ate)}`;

function Medidor({ valor, zona }: { valor: string; zona: string }) {
  const v = Math.max(0, Math.min(100, Number(valor)));
  return (
    <div className="isc-medidor">
      <svg viewBox="0 0 400 215" role="img" aria-label={`ISC ${um1(valor)} de 100, zona ${zona}`}>
        <path d={arco(0, 35)} className="isc-arco isc-arco-critica" />
        <path d={arco(35, 65)} className="isc-arco isc-arco-atencao" />
        <path d={arco(65, 100)} className="isc-arco isc-arco-saudavel" />
        <g transform={`rotate(${(v * 1.8 - 90).toFixed(1)} ${CX} ${CY})`} className="isc-ponteiro">
          <polygon points="193,8 207,8 200,36" />
          <rect x="198" y="36" width="4" height="46" />
        </g>
      </svg>
      <div className="isc-centro">
        <b>{um1(valor)}</b>
        <small>de 100</small>
        <span className="isc-zona">ZONA DE {zona.toUpperCase()}</span>
      </div>
      <div className="isc-faixas">
        <span>CRÍTICO 0–35</span><span>ATENÇÃO 35–65</span><span>SAUDÁVEL 65–100</span>
      </div>
    </div>
  );
}

function Componente({ nome, valor, legenda, cor }: { nome: string; valor: string; legenda: string; cor: string }) {
  return (
    <div className="isc-componente">
      <h4>{nome}</h4>
      <div className="isc-numero">{um1(valor)} <small>/100</small></div>
      <div className="isc-trilho" aria-hidden="true"><div style={{ width: `${Math.min(100, Number(valor))}%`, background: cor }} /></div>
      <p>{legenda}</p>
    </div>
  );
}

function AnaliseDaIA() {
  const { dados, carregando, erro, recarregar } = usarDados<AnaliseDaCarteira | null>(
    () => api.analiseDaCarteira(), [],
  );
  const [autor, definirAutor] = useState("");
  const [gerando, definirGerando] = useState(false);
  const [erroDeGeracao, definirErroDeGeracao] = useState<string | null>(null);

  const gerar = async () => {
    definirGerando(true);
    definirErroDeGeracao(null);
    try {
      await api.gerarAnaliseDaCarteira(autor.trim());
      recarregar();
    } catch (falha) {
      definirErroDeGeracao(falha instanceof ErroDaApi ? falha.message : "Falha ao gerar a análise.");
    } finally {
      definirGerando(false);
    }
  };

  return (
    <section className="ia-analise" aria-label="Análise da IA sobre a carteira">
      <div className="ia-analise-cab">
        <span className="ia-analise-titulo">Análise da IA · situação de hoje</span>
        <span className="ia-analise-acao">
          <label className="campo-rotulo" htmlFor="ia-autor">Quem está gerando</label>
          <input id="ia-autor" className="entrada ia-analise-autor" value={autor}
            onChange={(e) => definirAutor(e.target.value)} placeholder="Eduardo Luiz" />
          <button type="button" className="ia-analise-botao" disabled={gerando || autor.trim().length < 2} onClick={gerar}>
            {gerando ? "Gerando…" : dados ? "Gerar de novo" : "Gerar análise"}
          </button>
        </span>
      </div>
      {carregando && !dados && <p className="numero-nota">Carregando…</p>}
      {erro && <p className="numero-nota">{erro}</p>}
      {erroDeGeracao && <p role="alert" className="ia-analise-erro">{erroDeGeracao}</p>}
      {dados ? (
        <>
          <p>{dados.texto}</p>
          <p className="ia-analise-meta">
            Gerada em {new Date(dados.gerada_em).toLocaleString("pt-BR")} por {dados.gerada_por}
          </p>
        </>
      ) : (
        !carregando && <p className="numero-nota">Nenhuma análise gerada ainda. Informe seu nome e clique em &quot;Gerar análise&quot;.</p>
      )}
    </section>
  );
}

export function Carteira() {
  const { dados, carregando, erro, recarregar } = usarDados<ClassificacaoDaCarteira>(() => api.classificacaoDaCarteira(), []);
  const [eixo, definirEixo] = useState("");
  const [semaforoFiltro, definirSemaforoFiltro] = useState<number | null>(null);
  const { ordenacao, alternar: alternarOrdenacao } = usarOrdenacao();
  const [abertos, definirAbertos] = useState<Set<number>>(new Set());
  const alternar = (id: number) =>
    definirAbertos((antes) => {
      const novo = new Set(antes);
      if (!novo.delete(id)) novo.add(id);
      return novo;
    });

  if (carregando && !dados) return <Carregando rotulo="Carregando a classificação" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  if (dados.itens.length === 0)
    return (
      <VazioSemDados
        titulo="Nenhuma classificação carregada"
        explicacao="Carregue a planilha de saúde da carteira com scripts/importar_classificacao.py; o ensaio mostra o que será gravado."
      />
    );

  const eixos = Array.from(new Set(dados.itens.map((i) => i.eixo_de_acao))).sort((a, b) => rank(a) - rank(b));
  const itensDoEixo = dados.itens
    .filter((i) => (!eixo || i.eixo_de_acao === eixo) && (semaforoFiltro === null || i.semaforo === semaforoFiltro))
    .sort((a, b) => rank(a.eixo_de_acao) - rank(b.eixo_de_acao) || Number(b.receita_mensal) - Number(a.receita_mensal));
  const porSemaforo = { 1: 0, 2: 0, 3: 0 } as Record<number, number>;
  for (const i of dados.itens) porSemaforo[i.semaforo] = (porSemaforo[i.semaforo] ?? 0) + 1;
  const alternarSemaforo = (s: number) => definirSemaforoFiltro((atual) => (atual === s ? null : s));
  const itens = ordenar(itensDoEixo, ordenacao, {
    grupo: (i) => i.grupo_nome,
    receita: (i) => Number(i.receita_mensal),
    score: (i) => Number(i.score),
    classe: (i) => i.classe_efetiva,
    alerta: (i) => i.alerta_de_churn,
    churn: (i) => i.churn,
    eixo: (i) => i.eixo_de_acao,
  });
  const { isc } = dados;

  return (
    <section className="carteira" aria-label="Classificação da carteira">
      {dados.retrato && (
        <div className="retrato-faixa">
          <div className="retrato-chip"><b>{dados.retrato.unidades}</b><small>unidades (grupos + individuais)</small></div>
          <div className="retrato-chip"><b>{dinheiro(dados.retrato.receita_total)}</b><small>receita mensal recorrente</small></div>
          <button
            type="button"
            className="retrato-chip retrato-chip-trav"
            onClick={() => definirEixo(EIXO_COBRANCA)}
            aria-label={`${dados.retrato.grupos_travados} grupos travados, ${um1(dados.retrato.percentual_travado)}% da receita travada por inadimplência — clique para filtrar`}
          >
            <b>{dados.retrato.grupos_travados}</b>
            <small>
              grupos travados (clique para filtrar)
              <br />
              {um1(dados.retrato.percentual_travado)}% da receita travada por inadimplência
            </small>
          </button>
          <div className="retrato-chip retrato-semaforo">
            <small className="retrato-semaforo-rotulo">Semáforo (clique para filtrar)</small>
            <div className="retrato-semaforo-itens">
              {([1, 2, 3] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={semaforoFiltro === s}
                  aria-label={`Semáforo ${s} — ${SEMAFORO_ROTULO[s]}: ${porSemaforo[s]} grupo${porSemaforo[s] === 1 ? "" : "s"}`}
                  className={`retrato-semaforo-item retrato-semaforo-${s}${semaforoFiltro === s ? " retrato-semaforo-ativo" : ""}`}
                  onClick={() => alternarSemaforo(s)}
                >
                  <b>{s}</b>
                  <small>{porSemaforo[s]}</small>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      <AnaliseDaIA />
      <RevisaoMensal />

      {isc && (
        <>
          <section className="isc-hero" aria-label="Índice de saúde da carteira">
            <div>
              <div className="isc-rotulo">ÍNDICE DE SAÚDE DA CARTEIRA</div>
              <div className="isc-titulo">ISC</div>
              <p>Indicador único 0–100 · revisão mensal</p>
              <p>Base: classe + semáforo + churn, ponderados por receita</p>
              <p className="isc-ref">Referência {data(dados.referencia)} · parâmetros {dados.versao_dos_parametros}</p>
            </div>
            <Medidor valor={isc.valor} zona={isc.zona} />
          </section>

          <div className="isc-componentes">
            <Componente nome="Classe" valor={isc.componente_classe} cor="#2e5496"
              legenda={`${Object.entries(dados.por_classe).map(([c, n]) => `${c} ${n}`).join(" · ")}, ponderado por receita`} />
            <Componente nome="Semáforo" valor={isc.componente_semaforo} cor="#b8860b" legenda="Saúde operacional (pior = 3, melhor = 1)" />
            <Componente nome="Churn" valor={isc.componente_churn} cor="#2e7d5b" legenda="Risco de saída ponderado por receita" />
          </div>
        </>
      )}

      <div className="carteira-filtro">
        <label className="campo">
          <span className="campo-rotulo">Eixo de ação</span>
          <select className="selecao" value={eixo} onChange={(e) => definirEixo(e.target.value)}>
            <option value="">Todos</option>
            {eixos.map((e) => <option key={e} value={e}>{e}</option>)}
          </select>
        </label>
      </div>


      {itens.length === 0 ? (
        <VazioPorFiltro aoLimpar={() => { definirEixo(""); definirSemaforoFiltro(null); }} />
      ) : (
        <table className="tabela" aria-label="Grupos classificados">
          <thead>
            <tr>
              <ThOrdenavel coluna="grupo" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Grupo</ThOrdenavel>
              <ThOrdenavel coluna="receita" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Receita/mês</ThOrdenavel>
              <ThOrdenavel coluna="score" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Score</ThOrdenavel>
              <ThOrdenavel coluna="classe" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Classe</ThOrdenavel>
              <ThOrdenavel coluna="alerta" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Alerta</ThOrdenavel>
              <ThOrdenavel coluna="churn" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Churn</ThOrdenavel>
              <ThOrdenavel coluna="eixo" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>
                Eixo de ação <span className="carteira-remissao">Legenda do Eixo de Ação no rodapé</span>
              </ThOrdenavel>
            </tr>
          </thead>
          <tbody>
            {itens.map((i) => {
              const aberto = abertos.has(i.grupo_id);
              return (
                <Fragment key={i.grupo_id}>
                  <tr>
                    <td className="carteira-grupo">
                      {i.empresas.length > 0 ? (
                        <button
                          type="button"
                          className="carteira-mais"
                          aria-expanded={aberto}
                          aria-label={`${aberto ? "Ocultar" : "Mostrar"} as empresas de ${i.grupo_nome}`}
                          onClick={() => alternar(i.grupo_id)}
                        >
                          {aberto ? "−" : "+"}
                        </button>
                      ) : (
                        <span className="carteira-mais-vazio" aria-hidden="true" />
                      )}
                      ▸ {i.grupo_nome}
                      {i.sem_contrato_ativo && <span className="numero-nota"> · sem contrato ativo hoje</span>}
                    </td>
                    <td className="tabela-numero">{dinheiro(i.receita_mensal)}</td>
                    <td className="tabela-numero">{um(i.score)}</td>
                    <td className="carteira-classe">{i.classe_efetiva}{i.em_cobranca ? " · $$$ cobrança" : ""}</td>
                    <td>{i.alerta_de_churn ? ALERTA[i.alerta_de_churn] ?? i.alerta_de_churn : "—"}</td>
                    <td className="tabela-numero">{i.churn ?? "—"}</td>
                    <td>{i.eixo_de_acao}</td>
                  </tr>
                  {aberto &&
                    i.empresas.map((e) => (
                      <tr key={`e${e.id}`} className="carteira-empresa">
                        <td>• {e.razao_social}{e.cnpj ? <span className="numero-nota"> · {cnpj(e.cnpj)}</span> : null}</td>
                        <td className="tabela-numero">{e.mensalidade !== null ? dinheiro(e.mensalidade) : "—"}</td>
                        <td colSpan={5} />
                      </tr>
                    ))}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      )}
          <p className="carteira-legenda">
        ▸ grupo (consolidado) · + mostra as empresas do grupo · • empresa (CNPJ) · classe efetiva = letra + semáforo · ⚠ risco de churn em A/B · ⚑ saída a organizar em C ·
        $$$ adimplência ≤ 2 trava a classe, sem rebaixar
      </p>
      <details className="carteira-legenda-eixos" open>
        <summary>Legenda do eixo de ação (vale o primeiro que se aplica)</summary>
        <ol>
          {LEGENDA_DOS_EIXOS.map((e) => (
            <li key={e.nome}>
              <strong>{e.nome}:</strong> {e.quando} {e.significa}
            </li>
          ))}
        </ol>
      </details>
      <ul className="carteira-notas" aria-label="Observações sobre estes números">
        {dados.avisos.map((a) => <li key={a}>{a}</li>)}
      </ul>
      <details className="isc-como">
        <summary>Como é calculado</summary>
        <p>
          ISC = Classe × 33% + Semáforo × 33% + Churn × 34%, cada componente ponderado pela receita do grupo.
          Classe: A = 100, B = 60, C = 20. Semáforo: 1 = 100, 2 = 50, 3 = 0. Churn: 1 = 100, 2 = 80, 3 = 60, 4 = 20, 5 = 0.
          Zonas: crítica abaixo de 35, atenção de 35 a 65, saudável a partir de 65.
          Revisão mensal nos primeiros 6 a 12 meses; depois, trimestral.
        </p>
      </details>
    </section>
  );
}
