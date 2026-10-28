/** Datas e pagamento (amostra aprovada por Eduardo em 28/10/2026), no card da oportunidade e no painel do contrato.
 *
 * - **Data de competência**: quando a Critério assume os serviços; a 13ª conta os avos a partir dela.
 * - **Início do pagamento**: o vencimento da 1ª parcela; o MRR conta a partir dele.
 * - **Parcelas** (só no não recorrente): número, vencimento e valor de cada uma, que podem ser diferentes. A 1ª vence
 *   no início do pagamento e as seguintes mês a mês; qualquer vencimento pode ser mudado. A soma tem de bater com o
 *   valor total, ou nada é salvo (o servidor confere de novo).
 */

import type { ReactNode } from "react";
import type { ParcelaDoServico } from "../api/tipos";
import { dinheiro } from "../formato";
import { CampoDeData } from "./CampoDeData";
import { CampoDeValor } from "./CampoDeValor";

const MAXIMO = 60;

/** Soma ao centavo, sem o erro de ponto flutuante. */
function centavos(valor: string | null | undefined): number {
  const n = Number(valor);
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
}

/** Mesmo dia, `meses` depois; dia que não existe no mês cai no último dia dele (31/01 + 1 = 28/02). */
export function somarMeses(iso: string, meses: number): string {
  const [a, m, d] = iso.split("-").map(Number);
  const alvo = new Date(Date.UTC(a, m - 1 + meses, 1));
  const ultimo = new Date(Date.UTC(alvo.getUTCFullYear(), alvo.getUTCMonth() + 1, 0)).getUTCDate();
  alvo.setUTCDate(Math.min(d, ultimo));
  return alvo.toISOString().slice(0, 10);
}

/** Divide o total em `n` partes iguais ao centavo; a última leva a sobra. */
export function partesIguais(total: string, n: number, primeiroVencimento: string): ParcelaDoServico[] {
  const t = centavos(total);
  const base = Math.floor(t / n);
  return Array.from({ length: n }, (_, i) => ({
    vencimento: primeiroVencimento ? somarMeses(primeiroVencimento, i) : "",
    valor: ((i === n - 1 ? t - base * (n - 1) : base) / 100).toFixed(2),
  }));
}

/** A frase de por que as parcelas não podem ser salvas; `null` se podem (a mesma regra do servidor). */
export function problemaNasParcelas(parcelas: ParcelaDoServico[], total: string | null | undefined): string | null {
  if (parcelas.length === 0) return null;
  if (parcelas.some((p) => !p.vencimento)) return "Informe o vencimento de cada parcela.";
  if (parcelas.some((p) => centavos(p.valor) <= 0)) return "Toda parcela precisa de valor maior que zero.";
  if (!total) return "Informe o valor total antes de dividir em parcelas.";
  const diferenca = centavos(total) - parcelas.reduce((s, p) => s + centavos(p.valor), 0);
  if (diferenca === 0) return null;
  return `Soma ${dinheiro((centavos(total) - diferenca) / 100)}: ${diferenca > 0 ? "faltam" : "sobram"} ${dinheiro(Math.abs(diferenca) / 100)}. Não salva até conferir.`;
}

interface Marcas {
  classe: (chave: string) => string;
  id: (chave: string) => string;
  aviso: (chave: string) => ReactNode;
}

export function DatasEPagamento({
  prefixo,
  competencia,
  inicioPagamento,
  naoRecorrente,
  total,
  parcelas,
  aoMudarData,
  aoMudarParcelas,
  desabilitado = false,
  marcas,
}: {
  /** Prefixo dos ids, para dois cards abertos não terem o mesmo id. */
  prefixo: string;
  competencia: string;
  inicioPagamento: string;
  naoRecorrente: boolean;
  /** O valor total do serviço (preço anual; sem ele, o mensal), em texto decimal da API. */
  total: string | null | undefined;
  parcelas: ParcelaDoServico[];
  aoMudarData: (campo: "data_competencia" | "data_inicio_pagamento", valor: string) => void;
  aoMudarParcelas: (parcelas: ParcelaDoServico[]) => void;
  desabilitado?: boolean;
  marcas?: Marcas;
}) {
  const classe = (c: string) => (marcas ? marcas.classe(c) : "");
  const id = (c: string) => (marcas ? marcas.id(c) : undefined);

  const mudarQuantidade = (texto: string) => {
    const n = Math.max(0, Math.min(MAXIMO, Math.round(Number(texto) || 0)));
    const lista = parcelas.slice(0, n);
    while (lista.length < n) {
      const anterior = lista[lista.length - 1]?.vencimento || "";
      const vencimento = anterior ? somarMeses(anterior, 1) : inicioPagamento;
      lista.push({ vencimento, valor: "" });
    }
    aoMudarParcelas(lista);
  };

  const mudarParcela = (i: number, campo: keyof ParcelaDoServico, valor: string) =>
    aoMudarParcelas(parcelas.map((p, j) => (j === i ? { ...p, [campo]: valor } : p)));

  const problema = problemaNasParcelas(parcelas, total);
  const soma = parcelas.reduce((s, p) => s + centavos(p.valor), 0);

  return (
    <fieldset className="campo-bloco datas-e-pagamento">
      <legend className="campo-rotulo">Datas e pagamento</legend>
      <div className="formulario-duplo">
        <div className={`campo-bloco ${classe("data_competencia")}`} id={id("data_competencia")}>
          <label className="campo-rotulo" htmlFor={`${prefixo}-competencia`}>Data de competência</label>
          <CampoDeData id={`${prefixo}-competencia`} value={competencia} disabled={desabilitado}
            aoMudar={(v) => aoMudarData("data_competencia", v)} />
          <p className="campo-ajuda">Quando assumimos os serviços. A 13ª conta a partir dela.</p>
          {marcas?.aviso("data_competencia")}
        </div>
        <div className={`campo-bloco ${classe("data_inicio_pagamento")}`} id={id("data_inicio_pagamento")}>
          <label className="campo-rotulo" htmlFor={`${prefixo}-pagamento`}>Início do pagamento</label>
          <CampoDeData id={`${prefixo}-pagamento`} value={inicioPagamento} disabled={desabilitado}
            aoMudar={(v) => aoMudarData("data_inicio_pagamento", v)} />
          <p className="campo-ajuda">Vencimento da 1ª parcela. O MRR conta a partir dele.</p>
          {marcas?.aviso("data_inicio_pagamento")}
        </div>
      </div>

      {naoRecorrente && (
        <div className={`parcelas-do-servico ${classe("parcelas")}`} id={id("parcelas")}>
          <div className="parcelas-topo">
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor={`${prefixo}-n-parcelas`}>Número de parcelas</label>
              <input id={`${prefixo}-n-parcelas`} className="entrada" type="number" min={0} max={MAXIMO} step={1}
                value={parcelas.length || ""} disabled={desabilitado} onChange={(e) => mudarQuantidade(e.target.value)} />
            </div>
            <button type="button" className="botao botao-secundario" disabled={desabilitado || !total || parcelas.length === 0}
              onClick={() => aoMudarParcelas(partesIguais(total ?? "0", parcelas.length, parcelas[0]?.vencimento || inicioPagamento))}>
              Dividir em partes iguais
            </button>
          </div>
          <p className="campo-ajuda">
            Valor total {dinheiro(total)}. As parcelas podem ter valores diferentes; a soma tem de bater com o total.
          </p>
          {parcelas.length > 0 && (
            <table className="tabela tabela-parcelas">
              <thead>
                <tr><th scope="col">Nº</th><th scope="col">Vencimento</th><th scope="col" className="numero">Valor</th></tr>
              </thead>
              <tbody>
                {parcelas.map((p, i) => (
                  <tr key={i}>
                    <td>{i + 1}ª</td>
                    <td>
                      <CampoDeData id={`${prefixo}-venc-${i}`} value={p.vencimento} disabled={desabilitado}
                        aoMudar={(v) => mudarParcela(i, "vencimento", v)} />
                    </td>
                    <td className="numero">
                      {desabilitado ? dinheiro(p.valor) : (
                        <CampoDeValor value={p.valor} aria-label={`Valor da ${i + 1}ª parcela`}
                          aoMudar={(v) => mudarParcela(i, "valor", v ?? "")} />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {parcelas.length > 0 && (problema ? (
            <p className="campo-ajuda parcelas-erro" role="alert">⚠ {problema}</p>
          ) : (
            <p className="campo-ajuda parcelas-ok">✓ Soma das parcelas {dinheiro(soma / 100)}: confere com o valor total.</p>
          ))}
          {marcas?.aviso("parcelas")}
        </div>
      )}
    </fieldset>
  );
}
