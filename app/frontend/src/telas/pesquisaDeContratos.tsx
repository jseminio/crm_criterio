/** Pesquisa da Gestão de contratos (amostra aprovada por Eduardo em 13/10/2026): um campo só, que procura por
 * grupo, empresa ou CNPJ, escopo, situação, signatário, valor ("6.538" ou "6538") e data ("05/2026"). Várias
 * palavras: o contrato precisa ter todas. Sem acento e sem diferença de maiúscula. */

import type { ReactNode } from "react";
import type { ContratoResumo } from "../api/tipos";
import { data, dinheiro } from "../formato";

/** Minúscula e sem acento, letra a letra: o texto mantém o tamanho, para marcar o trecho achado no original. */
export function normalizar(texto: string): string {
  return Array.from(texto, (c) => c.normalize("NFD")[0].toLowerCase()).join("");
}

function textosDoContrato(c: ContratoResumo): string[] {
  const textos = [c.grupo_nome, c.escopo, c.situacao, c.signatario, c.empresa_nome, c.empresa_cnpj];
  if (c.preco_mensal) {
    textos.push(c.preco_mensal, c.preco_mensal.replace(".", ","), dinheiro(c.preco_mensal));
  }
  for (const d of [c.data_inicio, c.saida_em]) {
    if (d) textos.push(data(d), `${d.slice(5, 7)}/${d.slice(0, 4)}`);
  }
  if (c.saida_em) textos.push("em aviso de saída");
  return textos.filter((t): t is string => !!t).map(normalizar);
}

export function contratoCombina(c: ContratoResumo, termo: string): boolean {
  const palavras = normalizar(termo).split(/\s+/).filter(Boolean);
  if (palavras.length === 0) return true;
  const textos = textosDoContrato(c);
  const digitosDoCnpj = (c.empresa_cnpj ?? "").replace(/\D/g, "");
  return palavras.every((p) => {
    if (textos.some((t) => t.includes(p))) return true;
    const digitos = p.replace(/\D/g, "");
    return digitos.length >= 4 && /^[\d./-]+$/.test(p) && digitosDoCnpj.includes(digitos);
  });
}

/** Marca no texto o trecho que a pesquisa achou. */
export function Destaque({ texto, termo }: { texto: string | null | undefined; termo: string }): ReactNode {
  if (!texto) return "—";
  const palavras = normalizar(termo).split(/\s+/).filter(Boolean);
  const base = normalizar(texto);
  const achado = palavras.map((p) => ({ i: base.indexOf(p), n: p.length })).find((x) => x.i >= 0);
  if (!achado) return texto;
  return (
    <>
      {texto.slice(0, achado.i)}
      <mark className="busca-achado">{texto.slice(achado.i, achado.i + achado.n)}</mark>
      {texto.slice(achado.i + achado.n)}
    </>
  );
}
