/** Gerar contrato (amostra aprovada por Eduardo em 14/10/2026): o contrato recorrente em Word, pela matriz com
 * marcadores. Cada campo mostra o valor sugerido e de onde veio; a pessoa confere, ajusta e gera. O número CONT CCE RJ1
 * fica reservado; gerar de novo antes da assinatura regrava o mesmo documento. As marcas INCLUÍDO / N/A dos anexos
 * continuam sendo ajustadas no Word (primeira versão). */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { DocumentoDoContrato } from "../api/tipos";
import { usarAcesso } from "../entrada";
import { dataHora } from "../formato";

const TOM_DA_ORIGEM: Record<string, string> = {
  empresa: "ganho", proposta: "ganho", contrato: "ganho", "parâmetros": "ganho", gerado: "andamento",
  "configurações": "andamento", "sequência": "andamento", hoje: "andamento", digitar: "espera",
};

export function GerarContrato({ contratoId }: { contratoId: number }) {
  const { eu, pode } = usarAcesso();
  const podeGerar = pode("contratos.editar");
  const [aba, definirAba] = useState<DocumentoDoContrato | null>(null);
  const [valores, definirValores] = useState<Record<string, string>>({});
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  const aplicar = (nova: DocumentoDoContrato) => {
    definirAba(nova);
    definirValores(Object.fromEntries(nova.campos.map((c) => [c.nome, c.valor])));
  };

  useEffect(() => {
    api.documentoDoContrato(contratoId).then(aplicar)
      .catch((f) => definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao abrir o contrato em Word."));
  }, [contratoId]);

  if (!aba) return falha ? <p className="estado-texto estado-erro" role="alert">✗ {falha}</p> : null;

  const gerar = async () => {
    const vazios = aba.campos.filter((c) => c.nome !== "numero" && !(valores[c.nome] ?? "").trim());
    if (vazios.length) {
      definirFalha(`Preencha: ${vazios.map((c) => c.descricao).join("; ")}.`);
      return;
    }
    definirOcupado(true);
    definirFalha(null);
    definirFeito(null);
    try {
      const nova = await api.gerarDocumentoDoContrato(contratoId, valores, eu.modo === "local" ? eu.nome ?? "" : undefined);
      aplicar(nova);
      if (nova.gerado) await api.baixarDocumentoDoContrato(nova.gerado.id);
      definirFeito(`${nova.gerado?.numero} gerado. O Word está na pasta Downloads: ajuste os anexos e envie para assinatura.`);
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao gerar o contrato.");
    } finally {
      definirOcupado(false);
    }
  };

  return (
    <section className="gerar-contrato" aria-labelledby="gerar-contrato-titulo">
      <div className="reajuste-cabecalho">
        <div>
          <h3 className="reajuste-titulo" id="gerar-contrato-titulo">Gerar contrato · CONT CCE RJ1 {aba.numero}</h3>
          <p className="campo-ajuda" style={{ margin: 0 }}>
            Modelo: {aba.modelo}
            {aba.gerado && ` · gerado por ${aba.gerado.gerado_por} em ${dataHora(aba.gerado.gerado_em)}`}
          </p>
        </div>
        <div className="reajuste-acoes">
          {aba.gerado && (
            <button type="button" className="botao botao-secundario" onClick={() => void api.baixarDocumentoDoContrato(aba.gerado!.id)}>
              Baixar de novo
            </button>
          )}
          {podeGerar && !aba.problema && (
            <button type="button" className="botao botao-secundario" disabled={ocupado} onClick={() => void gerar()}>
              {ocupado ? "Gerando…" : "Gerar Word"}
            </button>
          )}
        </div>
      </div>
      {aba.problema && <p className="recado recado-alcada" role="status">{aba.problema}</p>}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {falha && <p className="estado-texto estado-erro" role="alert">✗ {falha}</p>}

      {!aba.problema && (
        <div className="tabela-rolagem">
          <table className="tabela" aria-label="Campos do contrato">
            <thead>
              <tr><th scope="col">Campo</th><th scope="col">Valor</th><th scope="col">Origem</th></tr>
            </thead>
            <tbody>
              {aba.campos.map((c) => (
                <tr key={c.nome}>
                  <td>
                    {c.descricao}
                    <span className="celula-fonte">{`{{${c.nome}}}`}</span>
                  </td>
                  <td>
                    {c.nome === "numero" || !podeGerar ? (
                      valores[c.nome] || "—"
                    ) : (
                      <input className="entrada" value={valores[c.nome] ?? ""} aria-label={c.descricao} maxLength={400}
                        onChange={(e) => definirValores((v) => ({ ...v, [c.nome]: e.target.value }))} />
                    )}
                  </td>
                  <td>
                    <span className={`etiqueta etiqueta-${TOM_DA_ORIGEM[c.origem] ?? "neutra"}`}>{c.origem}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="campo-ajuda" style={{ marginTop: "var(--e2)" }}>
        As marcas INCLUÍDO / N/A dos anexos ainda se ajustam no Word. Depois de assinado, o documento não muda: baixe o gerado.
      </p>
    </section>
  );
}
