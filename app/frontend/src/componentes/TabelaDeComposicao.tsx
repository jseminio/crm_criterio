/** A tabela de toda composição ("Ver composição"), com ordenação pelo título da coluna (aprovado por Eduardo em
 * 15/10/2026, caminho A): crescente, decrescente e volta à ordem original, como nas grades (`Ordenacao`). Cada coluna
 * diz o valor que compara — número para dinheiro, % e contagens; data ISO; texto — e o vazio fica sempre por último.
 * A linha de total (`rodape`) fica no fim, fora da ordenação. Composição com seções usa uma tabela por seção. */

import { Fragment, type ReactNode } from "react";
import { ThOrdenavel, ordenar, usarOrdenacao, type Acessor } from "./Ordenacao";

export interface ColunaDaComposicao<T> {
  titulo: string;
  /** O que compara ao ordenar (e o que aparece, se não houver `mostrar`). */
  valor: Acessor<T>;
  mostrar?: (linha: T) => ReactNode;
  numerico?: boolean;
  /** Coluna só para ler, sem ordenação (ações, ícones). */
  semOrdem?: boolean;
}

export function TabelaDeComposicao<T>({
  colunas, linhas, chave, rotulo, rodape, classeDaLinha, linha: renderizar,
}: {
  colunas: ColunaDaComposicao<T>[];
  linhas: T[];
  chave: (linha: T, posicao: number) => string | number;
  rotulo?: string;
  /** Linhas fixas no fim (o total), fora da ordenação. */
  rodape?: ReactNode;
  classeDaLinha?: (linha: T) => string | undefined;
  /** Linha própria (ex.: cliente que abre os contratos embaixo): no lugar do <tr> padrão, já na ordem escolhida. */
  linha?: (linha: T) => ReactNode;
}) {
  const { ordenacao, alternar } = usarOrdenacao();
  const acessores = Object.fromEntries(colunas.map((c, n) => [String(n), c.valor]));
  const ordenadas = ordenar(linhas, ordenacao, acessores);
  return (
    <table className="tabela" aria-label={rotulo}>
      <thead>
        <tr>
          {colunas.map((c, n) => c.semOrdem ? (
            <th key={n} scope="col" className={c.numerico ? "tabela-numero" : undefined}>{c.titulo}</th>
          ) : (
            <ThOrdenavel key={n} coluna={String(n)} ordenacao={ordenacao} aoAlternar={alternar} numerico={c.numerico}>
              {c.titulo}
            </ThOrdenavel>
          ))}
        </tr>
      </thead>
      <tbody>
        {ordenadas.map((linha, n) => renderizar ? <Fragment key={chave(linha, n)}>{renderizar(linha)}</Fragment> : (
          <tr key={chave(linha, n)} className={classeDaLinha?.(linha)}>
            {colunas.map((c, m) => {
              const v = c.valor(linha);
              return (
                <td key={m} className={c.numerico ? "tabela-numero" : undefined}>
                  {c.mostrar ? c.mostrar(linha) : v === null || v === undefined || v === "" ? "—" : v}
                </td>
              );
            })}
          </tr>
        ))}
        {rodape}
      </tbody>
    </table>
  );
}
