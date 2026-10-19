/** Os PDFs de um cliente num lugar só, no card do grupo (amostra aprovada por Eduardo em 19/10/2026): contratos
 * assinados, propostas aceitas e aditivos, inclusive os antigos. Clicar no nome abre o contrato ou a oportunidade;
 * a conferência continua lá. Baixar pede a permissão contratos.baixar. */

import { api } from "../api/cliente";
import type { ContratoResumo, DocumentoAnexado, OportunidadeResumo, TipoDeDocumento } from "../api/tipos";
import { EtiquetaDaLeitura } from "../componentes/DocumentosAnexados";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { usarAcesso } from "../entrada";
import { data } from "../formato";
import { usarDados } from "../usarDados";

const TIPO: Record<TipoDeDocumento, string> = { contrato: "Contrato", proposta: "Proposta", aditivo: "Aditivo" };

type Dono = { tipo: "contrato" | "oportunidade"; id: number; rotulo: string; nota: string } | null;

/** A proposta é da oportunidade; o contrato e o aditivo, do contrato. Sem o preferido, vale o que houver. */
function dono(d: DocumentoAnexado, contratos: ContratoResumo[] | null, propostas: OportunidadeResumo[]): Dono {
  const doContrato = (id: number): Dono => {
    const c = contratos?.find((x) => x.id === id);
    const nota = c ? [c.situacao, c.anterior_ao_crm ? "anterior ao CRM" : null, c.empresa_nome].filter(Boolean).join(" · ") : "";
    return { tipo: "contrato", id, rotulo: `Contrato · ${c?.escopo || "sem escopo"}`, nota };
  };
  const daOportunidade = (id: number): Dono => {
    const o = propostas.find((x) => x.id === id);
    return { tipo: "oportunidade", id, rotulo: `Oportunidade · ${o?.nome ?? `nº ${id}`}`, nota: o?.situacao ?? "" };
  };
  if (d.tipo === "proposta" && d.oportunidade_id !== null) return daOportunidade(d.oportunidade_id);
  if (d.contrato_id !== null) return doContrato(d.contrato_id);
  if (d.oportunidade_id !== null) return daOportunidade(d.oportunidade_id);
  return null;
}

/** O mais recente pela data do documento; sem data lida, no fim, pela data do envio. */
function ordem(a: DocumentoAnexado, b: DocumentoAnexado): number {
  if (a.data_do_documento && b.data_do_documento) return b.data_do_documento.localeCompare(a.data_do_documento);
  if (a.data_do_documento || b.data_do_documento) return a.data_do_documento ? -1 : 1;
  return b.enviado_em.localeCompare(a.enviado_em);
}

export function DocumentosDoGrupo({
  grupoId,
  propostas,
  aoAbrirContrato,
  aoAbrirOportunidade,
}: {
  grupoId: number;
  /** As oportunidades do grupo, já carregadas pelo card: dão o nome da oportunidade dona do PDF. */
  propostas: OportunidadeResumo[];
  aoAbrirContrato: (id: number) => void;
  aoAbrirOportunidade: (id: number) => void;
}) {
  const { pode } = usarAcesso();
  const podeBaixar = pode("contratos.baixar");
  const busca = usarDados(async () => {
    const [documentos, contratos] = await Promise.all([
      api.documentos({ grupo_id: grupoId }),
      // Sem ver contratos, o perfil ainda vê os PDFs; o contrato aparece sem o escopo.
      api.contratos({ grupo_id: grupoId }).then((p) => p.itens).catch(() => null),
    ]);
    return { documentos: [...documentos].sort(ordem), contratos };
  }, [grupoId]);

  return (
    <div className="secao-do-painel">
      <h3>Documentos</h3>
      {busca.carregando && <Carregando rotulo="Carregando os documentos" />}
      {busca.erro && <Erro mensagem={busca.erro} aoTentarDeNovo={busca.recarregar} />}
      {!busca.carregando && !busca.erro && busca.dados?.documentos.length === 0 && (
        <VazioSemDados
          titulo="Nenhum PDF neste grupo"
          explicacao="O contrato assinado entra pelo painel do contrato; os antigos, por Sucesso do Cliente › Documentos antigos."
        />
      )}
      {!busca.carregando && !busca.erro && (busca.dados?.documentos.length ?? 0) > 0 && (
        <>
          <p className="campo-ajuda" style={{ margin: "0 0 var(--e2)" }}>
            Contratos assinados, propostas aceitas e aditivos, inclusive os antigos. Clique no nome para abrir o contrato
            ou a oportunidade.
          </p>
          <table className="mini-tabela" aria-label="Documentos do grupo">
            <thead>
              <tr>
                <th scope="col">Tipo</th>
                <th scope="col">Documento</th>
                <th scope="col">Pertence a</th>
                <th scope="col">Conferência</th>
                {podeBaixar && <th scope="col"><span className="visualmente-oculto">Baixar</span></th>}
              </tr>
            </thead>
            <tbody>
              {busca.dados!.documentos.map((d) => {
                const de = dono(d, busca.dados!.contratos, propostas);
                const abrir = de ? () => (de.tipo === "contrato" ? aoAbrirContrato(de.id) : aoAbrirOportunidade(de.id)) : null;
                return (
                  <tr key={d.id}>
                    <td><span className="etiqueta etiqueta-neutra">{TIPO[d.tipo]}</span></td>
                    <td style={{ wordBreak: "break-word" }}>
                      {abrir ? (
                        <button type="button" className="link-de-tabela" onClick={abrir}>{d.nome_arquivo}</button>
                      ) : (
                        <span>{d.nome_arquivo}</span>
                      )}
                      <span className="celula-fonte">
                        {d.numero_no_documento ? `nº ${d.numero_no_documento}` : "número não lido"}
                        {" · "}
                        {d.data_do_documento ? `de ${data(d.data_do_documento)}` : "data não lida"}
                      </span>
                    </td>
                    <td>
                      {de ? de.rotulo : "Sem contrato nem oportunidade"}
                      <span className="celula-fonte">
                        {de ? de.nota : "vincule em Sucesso do Cliente › Documentos antigos"}
                      </span>
                    </td>
                    <td><EtiquetaDaLeitura situacao={d.leitura_situacao} /></td>
                    {podeBaixar && (
                      <td>
                        <button type="button" className="botao botao-secundario" aria-label={`Baixar ${d.nome_arquivo}`}
                          onClick={() => void api.baixarDocumentoAnexado(d.id, d.nome_arquivo)}>
                          Baixar
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!podeBaixar && (
            <p className="campo-ajuda">Baixar o PDF pede a permissão "Gestão de contratos: baixar PDF assinado".</p>
          )}
        </>
      )}
    </div>
  );
}
