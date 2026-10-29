/** Incluir documentos antigos (amostra aprovada por Eduardo em 18/10/2026): contratos, propostas e aditivos feitos fora
 * do CRM, vários PDFs de uma vez. A IA lê cada um, diz o tipo e acha o cliente pelo número do CRM ou pelo CNPJ; a
 * pessoa confirma o vínculo e confere os campos linha a linha. A IA nunca cria cliente nem contrato sozinha. */

import { useEffect, useMemo, useRef, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ContratoResumo, DocumentoAnexado, DocumentoComConferencia, TipoDeDocumento } from "../api/tipos";
import { ConferenciaDoDocumento, EtiquetaDaLeitura, lendo, resumoDoArquivo, rotuloDaLeitura, usarDocumento } from "../componentes/DocumentosAnexados";
import { ThOrdenavel, ordenar, usarOrdenacao, type Acessor } from "../componentes/Ordenacao";
import { Modal } from "../componentes/Modal";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { usarAcesso } from "../entrada";
import { cnpj, data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { normalizar } from "./pesquisaDeContratos";

const TIPOS: Record<TipoDeDocumento, string> = { contrato: "Contrato", proposta: "Proposta aceita", aditivo: "Aditivo" };

// ── Pesquisa e ordenação da lista (amostra aprovada por Eduardo em 29/10/2026) ────────────────────────

function tipoNaLista(d: DocumentoAnexado): string {
  return lendo(d) ? "" : TIPOS[d.tipo];
}

function clienteNaLista(d: DocumentoAnexado): string {
  return d.grupo_nome ?? d.sugestao?.grupo_nome ?? "";
}

function vinculoNaLista(d: DocumentoAnexado): string {
  return d.contrato_id !== null ? "Contrato vinculado" : d.sugestao?.contrato_id ? "Contrato sugerido" : "Sem vínculo";
}

/** Um campo só: arquivo, cliente, razão social lida, CNPJ (com ou sem pontos), número, tipo, vínculo e situação.
 * Várias palavras: o documento precisa ter todas. Sem acento e sem diferença de maiúscula. */
export function documentoCombina(d: DocumentoAnexado, termo: string): boolean {
  const palavras = normalizar(termo).split(/\s+/).filter(Boolean);
  if (palavras.length === 0) return true;
  const textos = [d.nome_arquivo, clienteNaLista(d), d.razao_social_lida, d.numero_no_documento, tipoNaLista(d),
    vinculoNaLista(d), rotuloDaLeitura(d.leitura_situacao), ...d.cnpjs_lidos.map(cnpj)]
    .filter((t): t is string => !!t).map(normalizar);
  const digitosDosCnpjs = d.cnpjs_lidos.map((c) => c.replace(/\D/g, ""));
  return palavras.every((p) => {
    if (textos.some((t) => t.includes(p))) return true;
    const digitos = p.replace(/\D/g, "");
    return digitos.length >= 4 && /^[\d./-]+$/.test(p) && digitosDosCnpjs.some((c) => c.includes(digitos));
  });
}

const ACESSORES: Record<string, Acessor<DocumentoAnexado>> = {
  arquivo: (d) => d.nome_arquivo,
  tipo: (d) => tipoNaLista(d),
  cliente: (d) => clienteNaLista(d),
  vinculo: (d) => vinculoNaLista(d),
  situacao: (d) => rotuloDaLeitura(d.leitura_situacao),
};

function rotuloDoContrato(c: ContratoResumo): string {
  const valor = c.preco_mensal ? ` · ${dinheiro(c.preco_mensal)}` : "";
  return `${c.escopo || "Contrato"} · ${c.situacao}${valor}${c.data_inicio ? ` · desde ${data(c.data_inicio)}` : ""}`;
}

function DetalheDoDocumento({ id, aoFechar, aoMudar }: { id: number; aoFechar: () => void; aoMudar: () => void }) {
  const { pode } = usarAcesso();
  const podeEditar = pode("contratos.documentos");
  const { doc, falha, trocar } = usarDocumento(id);
  const grupos = usarDados(() => api.grupos({ limite: 500 }), []);
  const [grupoId, definirGrupoId] = useState<number | null>(null);
  const [contratos, definirContratos] = useState<ContratoResumo[] | null>(null);
  const [erro, definirErro] = useState<string | null>(null);

  useEffect(() => {
    if (doc && grupoId === null) definirGrupoId(doc.grupo_id ?? doc.sugestao?.grupo_id ?? null);
  }, [doc, grupoId]);

  useEffect(() => {
    definirContratos(null);
    if (grupoId !== null) void api.contratos({ grupo_id: grupoId }).then((p) => definirContratos(p.itens)).catch(() => definirContratos([]));
  }, [grupoId]);

  const mudar = (novo: DocumentoComConferencia) => {
    trocar(novo);
    aoMudar();
  };

  const vincular = async (acao: Parameters<typeof api.vincularDocumento>[1]) => {
    definirErro(null);
    try {
      mudar(await api.vincularDocumento(id, acao));
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao vincular o documento.");
    }
  };

  if (!doc) {
    return (
      <Modal titulo="Documento" aoFechar={aoFechar}>
        {falha ? <p className="estado-texto estado-erro" role="alert">✗ {falha}</p> : <Carregando rotulo="Abrindo o documento" />}
      </Modal>
    );
  }

  const conferido = doc.conferido_em !== null;
  const sugerido = doc.sugestao?.contrato_id ?? null;

  return (
    <Modal titulo={doc.nome_arquivo} subtitulo={resumoDoArquivo(doc)} aoFechar={aoFechar}
      rodape={<button type="button" className="botao botao-secundario" onClick={aoFechar}>Fechar</button>}>
      <div className="formulario">
        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="doc-tipo">Tipo</label>
            <select id="doc-tipo" className="selecao" value={doc.tipo} disabled={!podeEditar}
              onChange={(e) => void vincular({ tipo: e.target.value as TipoDeDocumento })}>
              {(Object.keys(TIPOS) as TipoDeDocumento[]).map((t) => <option key={t} value={t}>{TIPOS[t]}</option>)}
            </select>
            {doc.tipo_lido && doc.tipo_lido !== doc.tipo && <p className="campo-ajuda">A IA leu como {doc.tipo_lido}.</p>}
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="doc-grupo">Cliente (grupo)</label>
            <select id="doc-grupo" className="selecao" value={grupoId ?? ""} disabled={!podeEditar || conferido || doc.contrato_id !== null}
              onChange={(e) => definirGrupoId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Escolher grupo…</option>
              {(grupos.dados?.itens ?? []).map((g) => <option key={g.id} value={g.id}>{g.nome}</option>)}
            </select>
            <p className="campo-ajuda">
              {doc.razao_social_lida && `${doc.razao_social_lida} · `}
              {doc.cnpjs_lidos.map(cnpj).join(", ") || "sem CNPJ lido"}
              {doc.sugestao?.motivo && ` · ${doc.sugestao.motivo === "pelo CNPJ" || doc.sugestao.motivo === "pelo número" ? `achado ${doc.sugestao.motivo}` : doc.sugestao.motivo}`}
            </p>
          </div>
        </div>

        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="doc-contrato">Vincular ao contrato</label>
          {doc.contrato_id !== null ? (
            <p className="campo-ajuda" style={{ margin: 0 }}>
              Vinculado ao contrato {contratos?.find((c) => c.id === doc.contrato_id) ? rotuloDoContrato(contratos.find((c) => c.id === doc.contrato_id)!) : `nº ${doc.contrato_id}`}.
              {podeEditar && !conferido && (
                <> <button type="button" className="botao-link" onClick={() => void vincular({ desvincular: true })}>Desfazer</button></>
              )}
            </p>
          ) : (
            <div className="reajuste-acoes">
              <select id="doc-contrato" className="selecao" disabled={!podeEditar || grupoId === null} defaultValue=""
                onChange={(e) => {
                  const valor = e.target.value;
                  if (valor === "novo") void vincular({ criar_contrato: true, grupo_id: grupoId ?? undefined });
                  else if (valor) void vincular({ contrato_id: Number(valor) });
                }}>
                <option value="">{grupoId === null ? "Escolha o grupo primeiro" : "Escolher contrato…"}</option>
                {(contratos ?? []).map((c) => (
                  <option key={c.id} value={c.id}>{rotuloDoContrato(c)}{c.id === sugerido ? " (sugerido)" : ""}</option>
                ))}
                {doc.tipo === "contrato" && grupoId !== null && <option value="novo">Criar contrato anterior ao CRM</option>}
              </select>
            </div>
          )}
          {erro && <p className="estado-texto estado-erro" role="alert">✗ {erro}</p>}
        </div>
      </div>

      <ConferenciaDoDocumento documento={doc} aoMudar={mudar} />
    </Modal>
  );
}

export function DocumentosAntigos() {
  const { pode } = usarAcesso();
  const podeAnexar = pode("contratos.documentos");
  const lista = usarDados(() => api.documentos({ origem: "lote" }), []);
  const [aberto, definirAberto] = useState<number | null>(null);
  const [enviando, definirEnviando] = useState<string | null>(null);
  const [falhas, definirFalhas] = useState<string[]>([]);
  const entrada = useRef<HTMLInputElement>(null);
  const { recarregar } = lista;

  // Enquanto algum PDF está sendo lido, a lista se atualiza sozinha.
  const algumLendo = (lista.dados ?? []).some((d) => lendo(d));
  useEffect(() => {
    if (!algumLendo) return;
    const relogio = setTimeout(recarregar, 4000);
    return () => clearTimeout(relogio);
  }, [algumLendo, lista.dados, recarregar]);

  const enviar = async (arquivos: FileList | null) => {
    if (!arquivos?.length) return;
    const recusas: string[] = [];
    const todos = Array.from(arquivos);
    for (const [i, arquivo] of todos.entries()) {
      definirEnviando(`Enviando ${i + 1} de ${todos.length}…`);
      try {
        await api.anexarDocumento(arquivo, {});
      } catch (f) {
        recusas.push(`${arquivo.name}: ${f instanceof ErroDaApi ? f.message : "falha ao enviar"}`);
      }
    }
    definirEnviando(null);
    definirFalhas(recusas);
    if (entrada.current) entrada.current.value = "";
    recarregar();
  };

  const docs: DocumentoAnexado[] = lista.dados ?? [];
  const conferidos = docs.filter((d) => d.conferido_em !== null).length;
  const [busca, definirBusca] = useState("");
  const { ordenacao, alternar } = usarOrdenacao();
  const visiveis = useMemo(
    () => ordenar(docs.filter((d) => documentoCombina(d, busca)), ordenacao, ACESSORES),
    [docs, busca, ordenacao],
  );

  return (
    <div className="documentos-antigos">
      <div className="reajuste-cabecalho">
        <div>
          <h2 className="reajuste-titulo">Incluir documentos antigos</h2>
          <p className="campo-ajuda" style={{ margin: 0 }}>Contratos, propostas e aditivos feitos fora do CRM.</p>
        </div>
        {docs.length > 0 && <span className="etiqueta etiqueta-neutra">{docs.length} enviados · {conferidos} conferidos</span>}
      </div>

      {podeAnexar && (
        <div className="area-de-envio">
          <input ref={entrada} type="file" accept="application/pdf,.pdf" multiple hidden aria-label="Escolher os PDFs"
            onChange={(e) => void enviar(e.target.files)} />
          <p style={{ margin: 0 }}>Envie vários PDFs de uma vez.</p>
          <p className="campo-ajuda" style={{ margin: 0 }}>Só PDF, até 20 MB cada. A leitura roda em fila: pode fechar a tela.</p>
          <button type="button" className="botao botao-primario" disabled={enviando !== null} onClick={() => entrada.current?.click()}>
            {enviando ?? "Escolher os arquivos"}
          </button>
        </div>
      )}
      {falhas.length > 0 && (
        <div className="estado estado-erro" role="alert">
          {falhas.map((f) => <p key={f} className="estado-texto">✗ {f}</p>)}
        </div>
      )}

      {lista.carregando && !lista.dados && <Carregando rotulo="Carregando os documentos" />}
      {lista.erro && <Erro mensagem={lista.erro} aoTentarDeNovo={recarregar} />}
      {lista.dados && docs.length === 0 && (
        <VazioSemDados titulo="Nenhum documento antigo incluído" explicacao="Os PDFs enviados aqui aparecem nesta lista, com o que a IA leu." />
      )}
      {docs.length > 0 && (
        <div className="campo">
          <label className="campo-rotulo" htmlFor="da-busca">Pesquisar</label>
          <input id="da-busca" className="entrada entrada-busca" type="search" value={busca}
            onChange={(e) => definirBusca(e.target.value)} placeholder="Arquivo, cliente, CNPJ, número ou tipo"
            aria-describedby="da-busca-ajuda" />
          <p className="campo-ajuda" id="da-busca-ajuda" style={{ margin: 0 }}>
            Arquivo, cliente, CNPJ (com ou sem pontos), número do documento, tipo, vínculo ou situação.
            {busca.trim() && ` Mostrando ${visiveis.length} de ${docs.length}.`}
          </p>
        </div>
      )}
      {docs.length > 0 && visiveis.length === 0 && <VazioPorFiltro aoLimpar={() => definirBusca("")} />}
      {visiveis.length > 0 && (
        <div className="tabela-rolagem">
          <table className="tabela" aria-label="Documentos antigos">
            <thead>
              <tr>
                <ThOrdenavel coluna="arquivo" ordenacao={ordenacao} aoAlternar={alternar}>Arquivo</ThOrdenavel>
                <ThOrdenavel coluna="tipo" ordenacao={ordenacao} aoAlternar={alternar}>Tipo lido</ThOrdenavel>
                <ThOrdenavel coluna="cliente" ordenacao={ordenacao} aoAlternar={alternar}>Cliente</ThOrdenavel>
                <ThOrdenavel coluna="vinculo" ordenacao={ordenacao} aoAlternar={alternar}>Vínculo</ThOrdenavel>
                <ThOrdenavel coluna="situacao" ordenacao={ordenacao} aoAlternar={alternar}>Situação</ThOrdenavel>
              </tr>
            </thead>
            <tbody>
              {visiveis.map((d) => (
                <tr key={d.id} className="linha-clicavel" onClick={() => definirAberto(d.id)}>
                  <td>
                    <button type="button" className="botao-link" onClick={(e) => { e.stopPropagation(); definirAberto(d.id); }}>
                      {d.nome_arquivo}
                    </button>
                    <span className="celula-fonte">
                      {d.numero_no_documento ?? ""}{d.data_do_documento ? ` · ${data(d.data_do_documento)}` : ""}
                    </span>
                  </td>
                  <td>{tipoNaLista(d) || "—"}</td>
                  <td>
                    {d.grupo_nome ?? d.sugestao?.grupo_nome ?? <span className="celula-fonte">{d.sugestao?.motivo ?? "—"}</span>}
                    {d.cnpjs_lidos[0] && <span className="celula-fonte">{cnpj(d.cnpjs_lidos[0])}</span>}
                  </td>
                  <td>{vinculoNaLista(d)}</td>
                  <td><EtiquetaDaLeitura situacao={d.leitura_situacao} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {aberto !== null && <DetalheDoDocumento id={aberto} aoFechar={() => definirAberto(null)} aoMudar={recarregar} />}
    </div>
  );
}
