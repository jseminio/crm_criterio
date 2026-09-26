/** Classificação da carteira (Etapa 3): classe, Score, alerta e eixo de ação por grupo, e o ISC.
 *
 * Somente leitura. Os números vêm do snapshot mais recente carregado da planilha de saúde da
 * carteira e são recalculados no CRM. Estado nunca só por cor: classe, alerta e cobrança têm texto.
 */

import { Fragment, useState } from "react";
import { api } from "../api/cliente";
import type { ClassificacaoDaCarteira } from "../api/tipos";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { cnpj, data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";

const decimais = (v: string, n: number) =>
  Number(v).toLocaleString("pt-BR", { minimumFractionDigits: n, maximumFractionDigits: n });
const um = (v: string) => decimais(v, 2);
const um1 = (v: string) => decimais(v, 1);
const ALERTA: Record<string, string> = { "⚠": "⚠ Risco de churn", "⚑": "⚑ Saída a organizar" };
const PRIORIDADE = ["Cobrança", "Reter já", "Reter / vigiar", "Saída organizada", "Sem urgência"];

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

export function Carteira() {
  const { dados, carregando, erro, recarregar } = usarDados<ClassificacaoDaCarteira>(() => api.classificacaoDaCarteira(), []);
  const [eixo, definirEixo] = useState("");
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
  const itens = dados.itens
    .filter((i) => !eixo || i.eixo_de_acao === eixo)
    .sort((a, b) => rank(a.eixo_de_acao) - rank(b.eixo_de_acao) || Number(b.receita_mensal) - Number(a.receita_mensal));
  const { isc } = dados;

  return (
    <section className="carteira" aria-label="Classificação da carteira">
      <div className="isc-chips">
        <div className="isc-chip"><b>{dados.itens.length}</b><small>grupos</small></div>
        <div className="isc-chip"><b>{dinheiro(dados.itens.reduce((t, i) => t + Number(i.receita_mensal), 0))}</b><small>receita/mês</small></div>
      </div>

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

      <details className="carteira-legenda-eixos" open>
        <summary>Legenda do eixo de ação</summary>
        <p className="numero-nota">Ordem de precedência: vale o primeiro eixo que se aplica ao grupo.</p>
        <ol>
          {LEGENDA_DOS_EIXOS.map((e) => (
            <li key={e.nome}>
              <strong>{e.nome}</strong>
              <span>{e.quando}</span>
              <span>{e.significa}</span>
            </li>
          ))}
        </ol>
      </details>

      {itens.length === 0 ? (
        <VazioPorFiltro aoLimpar={() => definirEixo("")} />
      ) : (
        <table className="tabela" aria-label="Grupos classificados">
          <thead>
            <tr>
              <th>Grupo</th>
              <th className="tabela-numero">Receita/mês</th>
              <th className="tabela-numero">Score</th>
              <th>Classe</th>
              <th>Alerta</th>
              <th className="tabela-numero">Churn</th>
              <th>Eixo de ação</th>
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
