/** Aba "Proposta" da oportunidade (01/10/2026): o preço sugerido com a conta aberta, os valores que
 * vão na proposta, a carta, o perfil do cliente e as propostas já geradas.
 *
 * A proposta sai em PowerPoint: Eduardo ou Karine revisam, ajustam à mão se preciso, salvam como PDF
 * e enviam. "Marcar como enviada" registra quem enviou e quando. Amostra aprovada em 01/10/2026.
 */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { AbaDaProposta, EntradaDaProposta, PropostaResumo, TipoDeMatriz } from "../api/tipos";
import { data, dataHora, dinheiro, fracaoEmPercentual } from "../formato";
import { brutoPrevio } from "../proposta";
import { Etiqueta } from "./Etiqueta";
import { Carregando, Erro } from "./estados";

const virgula = (v: string | number) => String(v).replace(".", ",");
const numero = (v: string | null | undefined) => (v === null || v === undefined || v === "" ? null : Number(v));

const PERFIL: Record<TipoDeMatriz, [string, string, string?][]> = {
  Contábil: [
    ["movimentacao", "Movimentação", "lançamentos/mês"], ["faturamento", "Faturamento", "por ano"],
    ["instituicoes", "Instituições", "contas bancárias"], ["funcionarios", "Funcionários", "CLT + PJs"],
    ["regime", "Regime"], ["sistema", "Sistema"], ["empresas", "Empresas"], ["localidade", "Localidade"],
  ],
  Financeiro: [
    ["volume_documentos", "Volume de documentos", "por mês"], ["faturamento", "Faturamento", "por ano"],
    ["instituicoes", "Instituições", "contas bancárias"], ["meios_de_pagamento", "Meios de pagamento"],
    ["regime", "Regime"], ["sistema", "Sistema"], ["segmento", "Segmento"], ["localidade", "Localidade"],
  ],
};

function hoje(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function baixar(proposta: PropostaResumo) {
  // O nome do arquivo vem do cabeçalho da API; o link só sai da página depois que o navegador o usou.
  const a = document.createElement("a");
  a.href = `/api/propostas/${proposta.id}/pptx`;
  a.download = proposta.arquivo;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => a.remove(), 1000);
}

export function PropostaDaOportunidade({ oportunidadeId, aoEnviar }: { oportunidadeId: number; aoEnviar: () => void }) {
  const [aba, definirAba] = useState<AbaDaProposta | null>(null);
  const [entrada, definirEntrada] = useState<EntradaDaProposta | null>(null);
  const [erroAoAbrir, definirErroAoAbrir] = useState<string | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [aviso, definirAviso] = useState<string | null>(null);
  const [gerando, definirGerando] = useState(false);
  const [enviando, definirEnviando] = useState<{ id: number; por: string; em: string } | null>(null);

  const carregar = () => {
    definirErroAoAbrir(null);
    api
      .abaDaProposta(oportunidadeId)
      .then((a) => {
        definirAba(a);
        definirEntrada(a.rascunho);
      })
      .catch((f) => definirErroAoAbrir(f instanceof ErroDaApi ? f.message : "Falha ao abrir a proposta."));
  };
  useEffect(carregar, [oportunidadeId]);

  if (erroAoAbrir) return <Erro mensagem={erroAoAbrir} aoTentarDeNovo={carregar} />;
  if (!aba || !entrada) return <Carregando rotulo="Montando a proposta" />;

  const mudar = <K extends keyof EntradaDaProposta>(campo: K, valor: EntradaDaProposta[K]) =>
    definirEntrada((atual) => (atual ? { ...atual, [campo]: valor } : atual));
  const texto = (campo: keyof EntradaDaProposta) => (e: { target: { value: string } }) =>
    mudar(campo, (e.target.value === "" ? null : e.target.value) as never);
  const inteiro = (campo: "horas_contabil" | "horas_dp") => (e: { target: { value: string } }) =>
    mudar(campo, e.target.value === "" ? null : Number(e.target.value));

  const matriz = entrada.matriz;
  const outra: TipoDeMatriz = matriz === "Contábil" ? "Financeiro" : "Contábil";
  const emUso = aba.matrizes[matriz];
  const s = aba.sugestao;
  const imposto = Number(aba.imposto);
  const liquido = (numero(entrada.valor_contabil) ?? 0) + (numero(entrada.valor_dp) ?? 0);
  const aberta = aba.propostas.find((p) => p.enviada_em === null);

  const gerar = async () => {
    definirGerando(true);
    definirErro(null);
    definirAviso(null);
    try {
      const p = await api.gerarProposta(oportunidadeId, entrada);
      baixar(p);
      definirAviso(`Proposta ${p.numero} gerada: o PowerPoint está sendo baixado. Revise, salve como PDF e envie.`);
      carregar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao gerar a proposta.");
    } finally {
      definirGerando(false);
    }
  };

  const confirmarEnvio = async () => {
    if (!enviando) return;
    definirErro(null);
    try {
      const p = await api.marcarPropostaEnviada(enviando.id, enviando.por, enviando.em);
      definirEnviando(null);
      definirAviso(`Proposta ${p.numero} marcada como enviada por ${p.enviada_por} em ${data(p.enviada_em)}.`);
      carregar();
      aoEnviar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao marcar como enviada.");
    }
  };

  return (
    <section className="proposta-da-oportunidade" aria-label="Proposta">
      {erro && <p className="estado estado-erro estado-texto" role="alert">{erro}</p>}
      {aviso && <p className="recado" role="status">{aviso}</p>}

      <p className="recado">
        Matriz: <strong>{matriz}</strong>{" "}
        {emUso ? (
          <span className="campo-ajuda">(enviada por {emUso.enviada_por} em {data(emUso.enviada_em)})</span>
        ) : (
          <span>· ainda não há matriz {matriz}: suba o PowerPoint em Configurações › Propostas.</span>
        )}
        {emUso && !emUso.utilizavel && <span> · ⚠ a matriz em uso tem marcador faltando; corrija em Configurações › Propostas.</span>}
        {" · "}
        <button type="button" className="link-de-tabela" onClick={() => mudar("matriz", outra)}>
          usar a {outra}
        </button>
      </p>

      {matriz === "Contábil" ? (
        <>
          <h3 className="proposta-titulo">Preço sugerido</h3>
          {s ? (
            <div className="proposta-conta">
              <p>
                Porte <strong>{s.porte}</strong>{s.porte_confirmado ? "" : " (sugerido pela régua)"} → {virgula(Number(s.horas_base))} h/mês ·
                atrito +{fracaoEmPercentual(s.atrito, 0)} (complexidade {s.complexidade}
                {s.complexidade_informada ? "" : " neutra, sem nota"}, disciplina {s.disciplina} neutra, risco {s.risco}
                {s.risco_informado ? "" : " neutro, sem nota"}) → <strong>{virgula(Number(s.horas))} h</strong>
              </p>
              <p>Custo de servir: {virgula(Number(s.horas))} h × {dinheiro(s.custo_hora)} = <strong>{dinheiro(s.custo)}</strong></p>
              <p>
                Bruto = custo ÷ (1 − {fracaoEmPercentual(s.imposto, 0)} imposto − {fracaoEmPercentual(s.margem_alvo, 0)} margem alvo) ={" "}
                <strong>{dinheiro(s.bruto)}</strong>
              </p>
              <p>Líquido sugerido = bruto × {virgula((1 - Number(s.imposto)).toFixed(2))} = <strong>{dinheiro(s.liquido)} por mês</strong></p>
              <p className="campo-ajuda">
                Mesma conta do honorário calculado da Carteira (margem alvo do {s.origem_da_margem}). Disciplina 3 porque cliente novo ainda não tem nota.
              </p>
            </div>
          ) : (
            <p className="campo-ajuda">{aba.sem_sugestao}</p>
          )}

          <h3 className="proposta-titulo">Honorários que vão na proposta (líquidos, como no contrato)</h3>
          <div className="proposta-grade proposta-grade-fixa">
            <label className="campo">
              <span className="campo-rotulo">Contábil / Fiscal (R$/mês)</span>
              <input className="entrada" type="number" min="0" step="0.01" value={entrada.valor_contabil ?? ""} onChange={texto("valor_contabil")} />
            </label>
            <label className="campo">
              <span className="campo-rotulo">Departamento Pessoal (R$/mês)</span>
              <input className="entrada" type="number" min="0" step="0.01" value={entrada.valor_dp ?? ""} onChange={texto("valor_dp")} />
            </label>
            <label className="campo">
              <span className="campo-rotulo">Horas de consulta/ano: Contábil</span>
              <input className="entrada" type="number" min="0" step="1" value={entrada.horas_contabil ?? ""} onChange={inteiro("horas_contabil")} />
            </label>
            <label className="campo">
              <span className="campo-rotulo">Horas de consulta/ano: DP</span>
              <input className="entrada" type="number" min="0" step="1" value={entrada.horas_dp ?? ""} onChange={inteiro("horas_dp")} />
            </label>
            <div className="proposta-caixa">
              Total líquido
              <strong className="proposta-valor">{dinheiro(liquido)}</strong>
              {s && liquido > 0 && (
                <span className="campo-ajuda">
                  sugerido {dinheiro(s.liquido)} · diferença{" "}
                  {`${liquido >= Number(s.liquido) ? "+" : "−"}${virgula(Math.abs((liquido / Number(s.liquido) - 1) * 100).toFixed(1))}%`}
                </span>
              )}
            </div>
            <div className="proposta-caixa">
              Valor bruto (alíquota estimada {fracaoEmPercentual(aba.imposto, 0)})
              <strong className="proposta-valor">{liquido > 0 ? dinheiro(brutoPrevio(liquido, imposto)) : "—"}</strong>
              <span className="campo-ajuda">= líquido ÷ {virgula((1 - imposto).toFixed(2))}, ao múltiplo de R$ 50 mais próximo</span>
            </div>
          </div>
          {!aba.tem_dp && <p className="campo-ajuda">O questionário não pediu DP: sem valor de DP, a proposta sai com "—" nessa caixa.</p>}
        </>
      ) : (
        <>
          <h3 className="proposta-titulo">Planos (R$/mês)</h3>
          <div className="proposta-grade">
            {([["plano_bpo", "1 · BPO Financeiro"], ["plano_plus", "2 · BPO Financeiro PLUS"], ["plano_cfo", "3 · CFO as a Service"]] as const).map(
              ([campo, rotulo]) => (
                <label className="campo" key={campo}>
                  <span className="campo-rotulo">{rotulo}</span>
                  <input className="entrada" type="number" min="0" step="0.01" value={entrada[campo] ?? ""} onChange={texto(campo)} />
                </label>
              ),
            )}
          </div>
          <p className="campo-ajuda">Preço de tabela de Configurações › Propostas. Mudar aqui vale só para esta proposta.</p>
        </>
      )}

      <h3 className="proposta-titulo">Carta e contexto</h3>
      <div className="proposta-grade proposta-grade-2">
        <label className="campo">
          <span className="campo-rotulo">Nome do cliente na proposta</span>
          <input className="entrada" value={entrada.cliente} onChange={(e) => mudar("cliente", e.target.value)} />
        </label>
        <label className="campo">
          <span className="campo-rotulo">Número</span>
          <input className="entrada" value={`PROP CCE RJ ${aba.proximo_numero}`} readOnly aria-readonly="true" />
          <span className="campo-ajuda">{aberta ? "a mesma da proposta ainda não enviada" : "reservado ao gerar; não se repete"}</span>
        </label>
      </div>
      <label className="campo">
        <span className="campo-rotulo">Tratamento</span>
        <input className="entrada" value={entrada.tratamento} onChange={(e) => mudar("tratamento", e.target.value)} />
      </label>
      <label className="campo">
        <span className="campo-rotulo">Contextualização (rascunho a partir do questionário; ajuste aqui ou no PowerPoint)</span>
        <textarea className="entrada" rows={5} value={entrada.contextualizacao} onChange={(e) => mudar("contextualizacao", e.target.value)} />
      </label>

      <h3 className="proposta-titulo">Perfil do cliente</h3>
      <p className="campo-ajuda">Do questionário e da oportunidade; o que não veio sai como "N/D". Ajuste no PowerPoint, se preciso.</p>
      <dl className="proposta-perfil">
        {PERFIL[matriz].map(([chave, rotulo, unidade]) => (
          <div key={chave}>
            <dt>{rotulo}</dt>
            <dd>
              {aba.perfil[chave]}
              {chave === "regime" && <span className="celula-fonte">CNPJ {aba.perfil.cnpj}</span>}
              {unidade && aba.perfil[chave] !== "N/D" && <span className="celula-fonte">{unidade}</span>}
            </dd>
          </div>
        ))}
      </dl>

      <div className="proposta-acoes">
        <button type="button" className="botao botao-primario" onClick={gerar} disabled={gerando || !emUso?.utilizavel}>
          {gerando ? "Gerando…" : "Gerar PowerPoint"}
        </button>
        <span className="campo-ajuda">
          {aberta
            ? `Baixa o .pptx. A ${aberta.numero} ainda não foi enviada: gerar de novo regrava ela, com o mesmo número.`
            : "Baixa o .pptx. Revise, salve como PDF no PowerPoint e envie."}
        </span>
      </div>

      <h3 className="proposta-titulo">Propostas desta oportunidade</h3>
      {aba.propostas.length === 0 ? (
        <p className="campo-ajuda">Nenhuma proposta gerada ainda.</p>
      ) : (
        <table className="tabela" aria-label="Propostas geradas">
          <thead>
            <tr>
              <th scope="col">Proposta</th>
              <th scope="col">Situação</th>
              <th scope="col" aria-label="Ações" />
            </tr>
          </thead>
          <tbody>
            {aba.propostas.map((p) => (
              <tr key={p.id}>
                <td>
                  {p.numero}
                  <span className="celula-fonte">
                    {p.matriz} · {p.valor_liquido ? `${dinheiro(p.valor_liquido)} líquido` : "três planos"}
                  </span>
                  <span className="celula-fonte">gerada em {dataHora(p.gerada_em)}</span>
                </td>
                <td>
                  <Etiqueta texto={p.enviada_em ? "enviada" : "gerada, não enviada"} />
                  {p.enviada_em && <span className="celula-fonte">por {p.enviada_por} em {data(p.enviada_em)}</span>}
                </td>
                <td>
                  <div className="proposta-acoes-da-linha">
                  <a className="link-de-tabela" href={`/api/propostas/${p.id}/pptx`} download={p.arquivo}>
                    Baixar de novo
                  </a>
                  {!p.enviada_em && (
                    <>
                      <button type="button" className="link-de-tabela" onClick={() => definirEnviando({ id: p.id, por: aba.revisores[0] ?? "", em: hoje() })}>
                        Marcar como enviada
                      </button>
                    </>
                  )}
                  {enviando?.id === p.id && (
                    <div className="proposta-envio" role="group" aria-label={`Envio da proposta ${p.numero}`}>
                      <label className="campo">
                        <span className="campo-rotulo">Quem enviou</span>
                        <select className="entrada" value={enviando.por} onChange={(e) => definirEnviando({ ...enviando, por: e.target.value })}>
                          {aba.revisores.map((r) => <option key={r} value={r}>{r}</option>)}
                        </select>
                      </label>
                      <label className="campo">
                        <span className="campo-rotulo">Quando</span>
                        <input className="entrada" type="date" max={hoje()} value={enviando.em} onChange={(e) => definirEnviando({ ...enviando, em: e.target.value })} />
                      </label>
                      <button type="button" className="botao botao-secundario" onClick={confirmarEnvio}>Confirmar envio</button>
                      <button type="button" className="link-de-tabela" onClick={() => definirEnviando(null)}>cancelar</button>
                    </div>
                  )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="campo-ajuda">
        "Marcar como enviada" registra quem enviou e quando; a oportunidade em "Enviar proposta" passa a "Em avaliação pela empresa"
        e, na matriz Contábil, o total líquido vira o preço mensal (com histórico). Mudou um detalhe à mão e reenviou? Continua o mesmo número.
      </p>
    </section>
  );
}
