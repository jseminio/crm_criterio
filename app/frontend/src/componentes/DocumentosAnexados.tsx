/** PDF assinado no CRM (amostra aprovada por Eduardo em 18/10/2026): o contrato assinado no painel do contrato e a
 * proposta aceita na oportunidade. A IA lê o PDF e sugere os campos; a conferência mostra lado a lado o que está no
 * CRM e o que foi lido, com a página e o trecho, e só grava o que a pessoa marcar. Diferente nunca vem marcado. */

import { useCallback, useEffect, useRef, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { DocumentoAnexado, DocumentoComConferencia, LinhaDaConferencia, TipoDeDocumento } from "../api/tipos";
import { usarAcesso } from "../entrada";
import { cnpj, data, dataHora, dinheiro } from "../formato";

const SITUACAO: Record<LinhaDaConferencia["situacao"], [string, string]> = {
  igual: ["Igual", "ganho"],
  diferente: ["Diferente", "espera"],
  novo: ["Novo", "andamento"],
  nao_achou: ["Não achou", "neutra"],
  informativo: ["Só no documento", "neutra"],
};

const LEITURA: Record<DocumentoAnexado["leitura_situacao"], [string, string]> = {
  pendente: ["Lendo…", "andamento"],
  lendo: ["Lendo…", "andamento"],
  lida: ["Conferir", "espera"],
  falhou: ["Leitura falhou", "perda"],
  conferida: ["Gravado", "ganho"],
  parada: ["Leitura parada", "perda"],
};

/** O texto da etiqueta da leitura ("Conferir", "Gravado"…): a pesquisa e a ordenação da lista usam o mesmo. */
export function rotuloDaLeitura(situacao: DocumentoAnexado["leitura_situacao"]): string {
  return LEITURA[situacao][0];
}

export function EtiquetaDaLeitura({ situacao }: { situacao: DocumentoAnexado["leitura_situacao"] }) {
  const [texto, tom] = LEITURA[situacao];
  return <span className={`etiqueta etiqueta-${tom}`}>{texto}</span>;
}

export function lendo(d: Pick<DocumentoAnexado, "leitura_situacao"> | null | undefined): boolean {
  return d?.leitura_situacao === "pendente" || d?.leitura_situacao === "lendo";
}

function mostrar(l: Pick<LinhaDaConferencia, "campo" | "tipo_do_valor">, valor: string): string {
  if (!valor) return "—";
  if (l.tipo_do_valor === "data") return data(valor);
  if (l.tipo_do_valor === "dinheiro") return dinheiro(valor);
  if (l.campo === "cnpj") return cnpj(valor);
  if (l.campo === "base_do_valor") return valor === "liquido" ? "Líquido" : "Bruto";
  return valor;
}

function tamanho(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function resumoDoArquivo(d: DocumentoAnexado): string {
  return `${tamanho(d.tamanho)} · anexado por ${d.enviado_por} em ${dataHora(d.enviado_em)}`;
}

/** Acompanha a leitura: enquanto a IA lê, pergunta de novo a cada 3 segundos. */
export function usarDocumento(id: number | null) {
  const [doc, definirDoc] = useState<DocumentoComConferencia | null>(null);
  const [falha, definirFalha] = useState<string | null>(null);
  const relogio = useRef<ReturnType<typeof setTimeout> | null>(null);

  const buscar = useCallback(async (alvo: number) => {
    try {
      const novo = await api.documento(alvo);
      definirDoc(novo);
      definirFalha(null);
      if (lendo(novo)) relogio.current = setTimeout(() => void buscar(alvo), 3000);
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao abrir o documento.");
    }
  }, []);

  useEffect(() => {
    definirDoc(null);
    if (id !== null) void buscar(id);
    return () => {
      if (relogio.current) clearTimeout(relogio.current);
    };
  }, [id, buscar]);

  const trocar = (novo: DocumentoComConferencia) => {
    if (relogio.current) clearTimeout(relogio.current);
    definirDoc(novo);
    if (lendo(novo)) relogio.current = setTimeout(() => void buscar(novo.id), 3000);
  };
  return { doc, falha, trocar };
}

export function ConferenciaDoDocumento({
  documento,
  aoMudar,
}: {
  documento: DocumentoComConferencia;
  aoMudar: (d: DocumentoComConferencia) => void;
}) {
  const { eu, pode } = usarAcesso();
  const podeEditar = pode("contratos.documentos");
  const sugeridos = () => new Set(documento.conferencia.filter((l) => l.marcar).map((l) => l.campo));
  const [marcados, definirMarcados] = useState<Set<string>>(sugeridos);
  const [valores, definirValores] = useState<Record<string, string>>({});
  const [chave, definirChave] = useState(`${documento.id}:${documento.leitura_situacao}`);
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  // Outro documento ou nova leitura: a marcação volta à sugestão (ajuste de estado durante o render, sem efeito).
  const chaveAtual = `${documento.id}:${documento.leitura_situacao}`;
  if (chave !== chaveAtual) {
    definirChave(chaveAtual);
    definirMarcados(sugeridos());
    definirValores({});
  }

  const vinculado = documento.contrato_id !== null || documento.oportunidade_id !== null;
  // Sem valor lido, a pessoa pode digitar o valor e gravar; o servidor confere o formato.
  const digitavel = (l: LinhaDaConferencia) => podeEditar && vinculado && l.destino !== "nenhum" && !l.motivo;
  const podeMarcar = (l: LinhaDaConferencia) =>
    digitavel(l) && l.situacao !== "igual" && (l.gravavel || !!(valores[l.campo] ?? "").trim());

  const alternar = (campo: string) =>
    definirMarcados((m) => {
      const novo = new Set(m);
      if (novo.has(campo)) novo.delete(campo);
      else novo.add(campo);
      return novo;
    });

  const gravar = async () => {
    definirOcupado(true);
    definirFalha(null);
    definirFeito(null);
    try {
      const campos = documento.conferencia.filter((l) => marcados.has(l.campo) && podeMarcar(l)).map((l) => l.campo);
      const corrigidos = Object.fromEntries(Object.entries(valores).filter(([c, v]) => campos.includes(c) && v.trim()));
      const novo = await api.conferirDocumento(documento.id, campos, corrigidos, eu.modo === "local" ? eu.nome ?? "" : undefined);
      aoMudar(novo);
      definirFeito(campos.length ? `${campos.length} ${campos.length === 1 ? "campo gravado" : "campos gravados"}.` : "Conferência registrada.");
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao gravar a conferência.");
    } finally {
      definirOcupado(false);
    }
  };

  const lerDeNovo = async () => {
    definirFalha(null);
    try {
      aoMudar(await api.lerDocumentoDeNovo(documento.id));
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao pedir a leitura.");
    }
  };

  const quantos = documento.conferencia.filter((l) => marcados.has(l.campo) && podeMarcar(l)).length;
  const parou = documento.leitura_situacao === "falhou" || documento.leitura_situacao === "parada";

  return (
    <div className="conferencia-do-documento">
      <p className="campo-ajuda" style={{ margin: 0 }}>
        <span className="etiqueta etiqueta-andamento">IA sugere · você confirma</span>{" "}
        {documento.conferido_em
          ? `Conferido por ${documento.conferido_por} em ${dataHora(documento.conferido_em)}.`
          : "Marque o que gravar. Campo diferente nunca vem marcado."}
      </p>
      {documento.aviso && <p className={`recado ${parou ? "recado-alcada" : ""}`} role="status">{documento.aviso}</p>}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {falha && <p className="estado-texto estado-erro" role="alert">✗ {falha}</p>}

      {documento.conferencia.length > 0 && (
        <div className="tabela-rolagem">
          <table className="tabela" aria-label="Conferência do documento">
            <thead>
              <tr>
                <th scope="col">Campo</th>
                <th scope="col">No CRM</th>
                <th scope="col">Lido no PDF</th>
                <th scope="col">Situação</th>
                <th scope="col">Usar</th>
              </tr>
            </thead>
            <tbody>
              {documento.conferencia.map((l) => {
                const [rotulo, tom] = SITUACAO[l.situacao];
                return (
                  <tr key={l.campo}>
                    <td>{l.rotulo}</td>
                    <td>{l.destino === "nenhum" ? <span className="celula-fonte">não vai para o CRM</span> : mostrar(l, l.no_crm)}</td>
                    <td>
                      {digitavel(l) && l.situacao !== "igual" ? (
                        <input className="entrada" aria-label={`${l.rotulo} lido`} maxLength={200}
                          placeholder={l.lido ? undefined : l.tipo_do_valor === "data" ? "AAAA-MM-DD" : "digite, se souber"}
                          value={valores[l.campo] ?? l.lido}
                          onChange={(e) => definirValores((v) => ({ ...v, [l.campo]: e.target.value }))} />
                      ) : (
                        mostrar(l, l.lido)
                      )}
                      {l.pagina > 0 && (
                        <span className="celula-fonte">p. {l.pagina}{l.trecho ? `, “${l.trecho}”` : ""}</span>
                      )}
                      {l.motivo && <span className="celula-fonte">{l.motivo}</span>}
                    </td>
                    <td><span className={`etiqueta etiqueta-${tom}`}>{rotulo}</span></td>
                    <td>
                      {podeMarcar(l) ? (
                        <input type="checkbox" aria-label={`Usar ${l.rotulo}`} checked={marcados.has(l.campo)}
                          onChange={() => alternar(l.campo)} />
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {podeEditar && !lendo(documento) && (
        <div className="reajuste-acoes" style={{ justifyContent: "flex-end", marginTop: "var(--e2)" }}>
          <button type="button" className="botao botao-secundario" onClick={() => void lerDeNovo()}>
            Ler o PDF de novo
          </button>
          {vinculado && (
            <button type="button" className="botao botao-secundario" disabled={ocupado || quantos === 0} onClick={() => void gravar()}>
              {ocupado ? "Gravando…" : `Gravar ${quantos} ${quantos === 1 ? "campo marcado" : "campos marcados"}`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/** Seção do painel: o PDF principal (contrato assinado ou proposta aceita), a conferência dele e os outros
 * documentos ligados (aditivos, proposta antiga do contrato). */
export function DocumentosAnexados({
  contratoId,
  oportunidadeId,
  tipo,
  titulo,
  aoGravar,
}: {
  contratoId?: number;
  oportunidadeId?: number;
  tipo: Extract<TipoDeDocumento, "contrato" | "proposta">;
  titulo: string;
  aoGravar?: () => void;
}) {
  const { pode } = usarAcesso();
  const podeAnexar = pode("contratos.documentos");
  const podeBaixar = pode("contratos.baixar");
  const [lista, definirLista] = useState<DocumentoAnexado[] | null>(null);
  const [aberto, definirAberto] = useState<number | null>(null);
  const [enviando, definirEnviando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const entrada = useRef<HTMLInputElement>(null);
  const { doc, falha: falhaDoDoc, trocar } = usarDocumento(aberto);

  const carregar = useCallback(async () => {
    try {
      const filtro = contratoId !== undefined ? { contrato_id: contratoId } : { oportunidade_id: oportunidadeId };
      const docs = await api.documentos(filtro);
      definirLista(docs);
      definirAberto((atual) => atual ?? docs.find((d) => d.tipo === tipo)?.id ?? null);
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao carregar os documentos.");
    }
  }, [contratoId, oportunidadeId, tipo]);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  const anexar = async (arquivo: File | undefined) => {
    if (!arquivo) return;
    definirEnviando(true);
    definirFalha(null);
    try {
      const novo = await api.anexarDocumento(arquivo, { tipo, contrato_id: contratoId, oportunidade_id: oportunidadeId });
      definirAberto(novo.id);
      trocar(novo);
      await carregar();
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao anexar o PDF.");
    } finally {
      definirEnviando(false);
      if (entrada.current) entrada.current.value = "";
    }
  };

  const principal = lista?.find((d) => d.tipo === tipo) ?? null;
  const outros = (lista ?? []).filter((d) => d.id !== principal?.id);

  return (
    <section className="gerar-contrato" aria-labelledby={`docs-${tipo}-titulo`}>
      <div className="reajuste-cabecalho">
        <h3 className="reajuste-titulo" id={`docs-${tipo}-titulo`}>{titulo}</h3>
        {podeAnexar && (
          <div className="reajuste-acoes">
            <input ref={entrada} type="file" accept="application/pdf,.pdf" hidden aria-label="Escolher o PDF"
              onChange={(e) => void anexar(e.target.files?.[0])} />
            <button type="button" className="botao botao-secundario" disabled={enviando} onClick={() => entrada.current?.click()}>
              {enviando ? "Enviando…" : principal ? "Substituir" : "Anexar PDF"}
            </button>
          </div>
        )}
      </div>
      {falha && <p className="estado-texto estado-erro" role="alert">✗ {falha}</p>}
      {lista === null && !falha && <p className="campo-ajuda">Carregando os documentos…</p>}
      {lista !== null && !principal && (
        <p className="campo-ajuda">
          {tipo === "contrato" ? "Nenhum PDF assinado anexado." : "Nenhuma proposta aceita anexada."} Só PDF, até 20 MB.
          {podeAnexar ? " Substituir guarda a versão anterior no histórico." : ""}
        </p>
      )}

      {[principal, ...outros].filter((d): d is DocumentoAnexado => d !== null).map((d) => (
        <div key={d.id} className="documento-anexado">
          <div className="documento-linha">
            <div style={{ minWidth: 0, flex: 1 }}>
              <strong>{d.nome_arquivo}</strong>
              <span className="celula-fonte">
                {d.tipo !== tipo && `${d.tipo === "aditivo" ? "Aditivo" : d.tipo === "proposta" ? "Proposta" : "Contrato"} · `}
                {resumoDoArquivo(d)}
              </span>
            </div>
            <EtiquetaDaLeitura situacao={d.leitura_situacao} />
            {podeBaixar && (
              <button type="button" className="botao botao-secundario" onClick={() => void api.baixarDocumentoAnexado(d.id, d.nome_arquivo)}>
                Baixar
              </button>
            )}
            {aberto !== d.id && (
              <button type="button" className="botao botao-secundario" onClick={() => definirAberto(d.id)}>Conferir</button>
            )}
          </div>
          {aberto === d.id && falhaDoDoc && <p className="estado-texto estado-erro" role="alert">✗ {falhaDoDoc}</p>}
          {aberto === d.id && doc?.id === d.id && (
            <ConferenciaDoDocumento documento={doc} aoMudar={(novo) => {
              trocar(novo);
              void carregar();
              if (novo.leitura_situacao === "conferida") aoGravar?.();
            }} />
          )}
        </div>
      ))}
    </section>
  );
}
