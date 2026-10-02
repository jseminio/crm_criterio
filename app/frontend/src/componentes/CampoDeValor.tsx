/** Campo de valor em reais no padrão brasileiro: aceita "3.287,38", "3287,38" ou "3287" e, ao sair
 * do campo, mostra "3.287,38". Por dentro o valor é o texto decimal que a API grava ("3287.38"),
 * como no `CampoDeData`. Valor que não dá para ler ("3,2,1", três casas) não é repassado: o campo
 * avisa "valor inválido" e o valor fica em branco (02/10/2026, a pedido de Eduardo). */

import { useState } from "react";
import { apiParaBr, brParaApi } from "../valorBr";

export function CampoDeValor({
  value,
  aoMudar,
  className = "entrada",
  ...resto
}: {
  value: string | null | undefined;
  aoMudar: (api: string | null) => void;
  className?: string;
  "aria-label"?: string;
}) {
  const [texto, definirTexto] = useState(apiParaBr(value));

  // O valor de fora mudou (rascunho descartado, outra matriz): o texto acompanha. Texto inválido
  // digitado aqui (valor em branco por fora) fica na tela, para a pessoa corrigir.
  const [valorVisto, definirValorVisto] = useState(value);
  if (value !== valorVisto) {
    definirValorVisto(value);
    const lido = brParaApi(texto);
    if (lido !== null && lido !== (value ?? "")) definirTexto(apiParaBr(value));
  }

  const digitar = (bruto: string) => {
    const t = bruto.replace(/[^\d.,]/g, "");
    definirTexto(t);
    // Inválido também zera o valor: gerar com o número anterior, que não está na tela, seria pior
    // do que o servidor pedir para preencher.
    const api = brParaApi(t);
    aoMudar(api ? api : null);
  };

  const invalido = brParaApi(texto) === null;
  return (
    <>
      <input
        {...resto}
        className={className}
        type="text"
        inputMode="decimal"
        placeholder="0,00"
        value={texto}
        aria-invalid={invalido || undefined}
        onChange={(e) => digitar(e.target.value)}
        onBlur={() => {
          const api = brParaApi(texto);
          if (api) definirTexto(apiParaBr(api));
        }}
      />
      {invalido && <p className="campo-ajuda campo-data-erro" role="alert">✗ Valor inválido: escreva como 3.287,38.</p>}
    </>
  );
}
