/** Aba "Proposta" da oportunidade (01/10/2026): o preço sugerido com a conta aberta, os valores que
 * vão na proposta, a carta, o perfil do cliente e as propostas já geradas.
 *
 * A proposta sai em PowerPoint: Eduardo ou Karine revisam, ajustam à mão se preciso, salvam como PDF
 * e enviam. "Marcar como enviada" registra quem enviou e quando. Amostra aprovada em 01/10/2026.
 *
 * Desde 03/10/2026 (Eduardo, amostra aprovada): Contábil/Fiscal vem do apurado pelo questionário e DP
 * de R$ 50 por colaborador, os dois editáveis; as horas de consulta são calculadas e não se digitam.
 */

import { useEffect, useState } from "react";
import { api, baixarArquivo, entradaLigada, ErroDaApi } from "../api/cliente";
import type { AbaDaProposta, EntradaDaProposta, PropostaResumo, TipoDeMatriz } from "../api/tipos";
import { data, dataHora, dinheiro, fracaoEmPercentual } from "../formato";
import { brutoPrevio, horasDeConsulta } from "../proposta";
import { CampoDeValor } from "./CampoDeValor";
import { Etiqueta } from "./Etiqueta";
import { Carregando, Erro } from "./estados";
import { LinkDeArquivo } from "./LinkDeArquivo";
import { SEM_PERMISSAO, usarAcesso } from "../entrada";

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

function baixar(proposta: PropostaResumo, aoFalhar: (mensagem: string) => void) {
  // Com login, o download leva o token (um link comum não leva).
  if (entradaLigada()) {
    baixarArquivo(`/api/propostas/${proposta.id}/pptx`, proposta.arquivo).catch((f) =>
      aoFalhar(`A proposta foi gerada, mas o download falhou (${f instanceof ErroDaApi ? f.message : "sem resposta"}). Use "Baixar de novo", logo abaixo.`),
    );
    return;
  }
  // O nome do arquivo vem do cabeçalho da API; o link só sai da página depois que o navegador o usou.
  const a = document.createElement("a");
  a.href = `/api/propostas/${proposta.id}/pptx`;
  a.download = proposta.arquivo;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => a.remove(), 1000);
}

/** O que foi digitado e ainda não virou PowerPoint fica guardado neste navegador, por oportunidade:
 * trocar de aba, salvar a oportunidade (que fecha o painel) ou recarregar a página não perde nada.
 * Some ao gerar. Navegador sem armazenamento (janela anônima) só não guarda: a tela funciona igual. */
type Guardado = { entrada: EntradaDaProposta; salvo_em: string };
const chaveDoRascunho = (id: number) => `crm.proposta.rascunho.${id}`;

function lerRascunho(id: number): Guardado | null {
  try {
    const bruto = localStorage.getItem(chaveDoRascunho(id));
    return bruto ? (JSON.parse(bruto) as Guardado) : null;
  } catch {
    return null;
  }
}

function guardarRascunho(id: number, entrada: EntradaDaProposta) {
  try {
    localStorage.setItem(chaveDoRascunho(id), JSON.stringify({ entrada, salvo_em: new Date().toISOString() }));
  } catch {
    /* sem armazenamento: segue sem guardar */
  }
}

function apagarRascunho(id: number) {
  try {
    localStorage.removeItem(chaveDoRascunho(id));
  } catch {
    /* idem */
  }
}

export function PropostaDaOportunidade({
  oportunidadeId,
  aoEnviar,
  aoGerar,
}: {
  oportunidadeId: number;
  aoEnviar: () => void;
  /** Gerar fecha o item "Proposta ainda não gerada" do que falta (E4). */
  aoGerar?: () => void;
}) {
  const { pode } = usarAcesso();
  const [aba, definirAba] = useState<AbaDaProposta | null>(null);
  const [entrada, definirEntrada] = useState<EntradaDaProposta | null>(null);
  const [erroAoAbrir, definirErroAoAbrir] = useState<string | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [aviso, definirAviso] = useState<string | null>(null);
  const [gerando, definirGerando] = useState(false);
  const [enviando, definirEnviando] = useState<{ id: number; por: string; em: string } | null>(null);
  const [editado, definirEditado] = useState(false);
  const [restaurado, definirRestaurado] = useState<string | null>(null);

  const carregar = () => {
    definirErroAoAbrir(null);
    api
      .abaDaProposta(oportunidadeId)
      .then((a) => {
        definirAba(a);
        const guardado = lerRascunho(oportunidadeId);
        definirEntrada(guardado ? { ...a.rascunho, ...guardado.entrada } : a.rascunho);
        definirRestaurado(guardado ? guardado.salvo_em : null);
      })
      .catch((f) => definirErroAoAbrir(f instanceof ErroDaApi ? f.message : "Falha ao abrir a proposta."));
  };
  useEffect(carregar, [oportunidadeId]);
  useEffect(() => {
    if (editado && entrada) guardarRascunho(oportunidadeId, entrada);
  }, [editado, entrada, oportunidadeId]);

  if (erroAoAbrir) return <Erro mensagem={erroAoAbrir} aoTentarDeNovo={carregar} />;
  if (!aba || !entrada) return <Carregando rotulo="Montando a proposta" />;

  const mudar = <K extends keyof EntradaDaProposta>(campo: K, valor: EntradaDaProposta[K]) => {
    definirEditado(true);
    definirEntrada((atual) => (atual ? { ...atual, [campo]: valor } : atual));
  };
  const descartarRascunho = () => {
    apagarRascunho(oportunidadeId);
    definirEditado(false);
    definirRestaurado(null);
    definirEntrada(aba.rascunho);
  };
  const semMatriz = !aba.matrizes[entrada.matriz]
    ? `Falta a matriz ${entrada.matriz}: suba o PowerPoint com os marcadores em Configurações › Propostas.`
    : !aba.matrizes[entrada.matriz]!.utilizavel
      ? `A matriz ${entrada.matriz} em uso tem marcador faltando ou errado: corrija em Configurações › Propostas.`
      : null;

  const matriz = entrada.matriz;
  const outra: TipoDeMatriz = matriz === "Contábil" ? "Financeiro" : "Contábil";
  const emUso = aba.matrizes[matriz];
  const s = aba.sugestao;
  const imposto = Number(aba.imposto);
  const liquido = (numero(entrada.valor_contabil) ?? 0) + (numero(entrada.valor_dp) ?? 0);
  const horas = horasDeConsulta(numero(entrada.valor_contabil) ?? 0, numero(entrada.valor_dp) ?? 0, Number(aba.valor_da_hora_de_consulta));
  const col = aba.colaboradores;
  const apurado = numero(aba.contabil_apurado);
  const aberta = aba.propostas.find((p) => p.enviada_em === null);

  const gerar = async () => {
    definirGerando(true);
    definirErro(null);
    definirAviso(null);
    try {
      // O servidor refaz as horas; mandar as calculadas só deixa o rascunho guardado coerente.
      const p = await api.gerarProposta(oportunidadeId, { ...entrada, horas_contabil: horas.contabil, horas_dp: horas.dp });
      apagarRascunho(oportunidadeId);
      definirEditado(false);
      definirRestaurado(null);
      baixar(p, definirErro);
      definirAviso(
        `✓ Proposta ${p.numero} gerada. O arquivo ${p.arquivo} foi para a pasta Downloads do navegador. ` +
          `Se não apareceu, use "Baixar de novo", logo abaixo. Revise, salve como PDF e envie.`,
      );
      carregar();
      aoGerar?.();
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
      definirAviso(`✓ Proposta ${p.numero} marcada como enviada por ${p.enviada_por} em ${data(p.enviada_em)}.`);
      carregar();
      aoEnviar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao marcar como enviada.");
    }
  };

  return (
    <section className="proposta-da-oportunidade" aria-label="Proposta">
      {restaurado && (
        <p className="recado">
          Rascunho ainda não gerado, guardado em {dataHora(restaurado)}.{" "}
          <button type="button" className="link-de-tabela" onClick={descartarRascunho}>descartar e voltar ao sugerido</button>
        </p>
      )}

      <p className="recado">
        Matriz: <strong>{matriz}</strong>{" "}
        {emUso ? (
          <span className="campo-ajuda">(enviada por {emUso.enviada_por} em {data(emUso.enviada_em)})</span>
        ) : (
          <span>· ainda não há matriz {matriz}: suba o PowerPoint em Configurações › Propostas.</span>
        )}
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
            <div className="campo">
              <label className="campo">
                <span className="campo-rotulo">Contábil / Fiscal (R$/mês)</span>
                <CampoDeValor value={entrada.valor_contabil} aoMudar={(v) => mudar("valor_contabil", v)} />
              </label>
              <span className="campo-ajuda">
                {apurado === null ? (
                  "Sem valor apurado: o questionário ainda não deu porte."
                ) : (
                  <>
                    apurado pelo questionário: {dinheiro(aba.contabil_apurado)}
                    {numero(entrada.valor_contabil) !== apurado && (
                      <>
                        {" · "}
                        <button type="button" className="link-de-tabela" onClick={() => mudar("valor_contabil", aba.contabil_apurado)}>
                          voltar ao apurado
                        </button>
                      </>
                    )}
                  </>
                )}
              </span>
            </div>
            <div className="campo">
              <label className="campo">
                <span className="campo-rotulo">Departamento Pessoal (R$/mês)</span>
                <CampoDeValor value={entrada.valor_dp} aoMudar={(v) => mudar("valor_dp", v)} />
              </label>
              <span className="campo-ajuda">
                {col ? (
                  <>
                    {col.total} colaboradores × {dinheiro(col.valor_por_colaborador)} ({col.clt ?? 0} CLT + {col.pjs_estagiarios ?? 0} PJs/estagiários)
                    {numero(entrada.valor_dp) !== Number(col.valor_dp) && (
                      <>
                        {" · "}
                        <button type="button" className="link-de-tabela" onClick={() => mudar("valor_dp", col.valor_dp)}>
                          voltar ao calculado
                        </button>
                      </>
                    )}
                  </>
                ) : aba.tem_dp ? (
                  "Sem colaboradores informados: R$ 50 por colaborador, preencha à mão."
                ) : null}
              </span>
            </div>
            <div className="proposta-caixa">
              Horas de consulta/ano: Contábil{horas.dp !== null ? " · 70%" : ""}
              <strong className="proposta-valor">{horas.contabil} h</strong>
            </div>
            <div className="proposta-caixa">
              Horas de consulta/ano: DP · 30%
              <strong className="proposta-valor">{horas.dp !== null ? `${horas.dp} h` : "—"}</strong>
            </div>
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
          <p className="campo-ajuda">
            Horas de consulta (calculadas, não se digitam): 50% do 13º honorário ({dinheiro(liquido)}) = {dinheiro(horas.base)} ÷{" "}
            {dinheiro(aba.valor_da_hora_de_consulta)}/h = {virgula((horas.base / Number(aba.valor_da_hora_de_consulta)).toFixed(1))} h →{" "}
            {horas.total} h{horas.dp === null ? ", todas de Contábil (sem DP)" : ""}.{aba.tem_dp && " O questionário ainda não separa jovem aprendiz: some à mão no DP."}
          </p>
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
                  <CampoDeValor value={entrada[campo]} aoMudar={(v) => mudar(campo, v)} />
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
        <button type="button" className="botao botao-primario" onClick={gerar} disabled={gerando || !!semMatriz || !pode("funil.proposta")}>
          {gerando ? "Gerando…" : "Gerar PowerPoint"}
        </button>
        {!pode("funil.proposta") ? (
          <span className="proposta-bloqueio" role="note">⚠ {SEM_PERMISSAO}</span>
        ) : semMatriz ? (
          <span className="proposta-bloqueio" role="note">⚠ {semMatriz}</span>
        ) : (
          <span className="campo-ajuda">
            {aberta
              ? `Baixa o .pptx. A ${aberta.numero} ainda não foi enviada: gerar de novo regrava ela, com o mesmo número.`
              : "Baixa o .pptx. Revise, salve como PDF no PowerPoint e envie."}
          </span>
        )}
      </div>
      {erro && <p className="estado estado-erro estado-texto proposta-resultado" role="alert">✗ {erro}</p>}
      {aviso && <p className="recado proposta-resultado" role="status">{aviso}</p>}
      <p className="campo-ajuda">
        O que você digita aqui fica guardado neste navegador até gerar o PowerPoint, mesmo trocando de aba.
        "Salvar alterações", no rodapé, grava só os dados da oportunidade.
      </p>

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
                  <LinkDeArquivo className="link-de-tabela" href={`/api/propostas/${p.id}/pptx`} nome={p.arquivo}>
                    Baixar de novo
                  </LinkDeArquivo>
                  {!p.enviada_em && pode("funil.enviar_proposta") && (
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
