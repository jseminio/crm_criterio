/** O relatório de conferência da carga.
 *
 * Existe para responder, sem ler a saída de um script, à pergunta de quem vai
 * decidir se confia na base — e portanto se larga a planilha: o que entrou, o
 * que ficou pendente e o que foi ajustado sozinho.
 */

import { useState } from "react";
import { api } from "../api/cliente";
import type { Execucao, ExecucaoDetalhe, Ocorrencia, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { dataHora } from "../formato";
import { usarDados } from "../usarDados";

const TIPOS = [
  {
    valor: "Precisa de você",
    titulo: "Precisa de você",
    explicacao:
      "O que só uma pessoa resolve: linhas que ficaram de fora, duplicatas e propostas aceitas sem a data do aceite.",
  },
  {
    valor: "Ajustado sozinho",
    titulo: "Ajustado sozinho",
    explicacao:
      "O que a carga corrigiu ou anotou sem perguntar — grafias unificadas, valores arredondados, campos vazios de propósito. Confira por amostragem.",
  },
  {
    valor: "Mudou na recarga",
    titulo: "Mudou na recarga",
    explicacao:
      "O que a planilha alterou desde a rodada anterior e foi aplicado no CRM, com o antes e o depois.",
  },
] as const;

function Numero({
  rotulo,
  valor,
  nota,
}: {
  rotulo: string;
  valor: string | number;
  nota?: string;
}) {
  return (
    <section className="numero">
      <h3 className="numero-rotulo">{rotulo}</h3>
      <p className="numero-valor">{valor}</p>
      {nota && <div className="numero-detalhe">{nota}</div>}
    </section>
  );
}

function Detalhe({ execucao }: { execucao: ExecucaoDetalhe }) {
  const [tipo, definirTipo] = useState<string>(
    execucao.pendencias > 0 ? "Precisa de você" : "Ajustado sozinho",
  );
  const [campo, definirCampo] = useState<string>("");

  const ocorrencias = usarDados<Pagina<Ocorrencia>>(
    () => api.ocorrencias(execucao.id, { tipo, campo: campo || undefined }),
    [execucao.id, tipo, campo],
  );

  const contagem: Record<string, number> = {
    "Precisa de você": execucao.pendencias,
    "Ajustado sozinho": execucao.ajustes,
    "Mudou na recarga": execucao.mudancas,
  };
  const camposDoTipo = execucao.por_campo.filter((c) => c.tipo === tipo);
  const atual = TIPOS.find((t) => t.valor === tipo)!;

  // A conta fecha? Toda linha de 2026 lida ou virou oportunidade, ou ficou de
  // fora com motivo. Se não fechar, há linha sumindo — e isso precisa gritar.
  const fora = execucao.ignoradas_incompletas + execucao.ignoradas_duplicatas;
  const fecha = execucao.gravadas + fora === execucao.importadas;

  return (
    <>
      <div className="numeros">
        <Numero
          rotulo="Lidas na planilha"
          valor={execucao.lidas}
          nota={`${execucao.de_outro_ano} são de outro ano e não entram — só 2026.`}
        />
        <Numero
          rotulo="De 2026"
          valor={execucao.importadas}
          nota="Linhas que a carga tentou gravar."
        />
        <Numero
          rotulo="Gravadas no CRM"
          valor={execucao.gravadas}
          nota={`${execucao.criadas} novas · ${execucao.atualizadas} alteradas · ${execucao.inalteradas} sem mudança`}
        />
        <Numero
          rotulo="Ficaram de fora"
          valor={fora}
          nota={`${execucao.ignoradas_incompletas} incompletas · ${execucao.ignoradas_duplicatas} duplicata(s)`}
        />
      </div>

      <p className={fecha ? "conta-fecha" : "conta-nao-fecha"} role={fecha ? undefined : "alert"}>
        {fecha
          ? `A conta fecha: ${execucao.gravadas} gravadas + ${fora} de fora = ${execucao.importadas} de 2026.`
          : `A conta NÃO fecha: ${execucao.gravadas} gravadas + ${fora} de fora ≠ ${execucao.importadas} de 2026. Há linha sumindo.`}
      </p>

      <div className="abas" role="tablist" aria-label="Tipo de ocorrência">
        {TIPOS.map((t) => (
          <button
            key={t.valor}
            type="button"
            role="tab"
            aria-selected={tipo === t.valor}
            className="aba"
            onClick={() => {
              definirTipo(t.valor);
              definirCampo("");
            }}
          >
            {t.titulo} <span className="aba-contagem">{contagem[t.valor]}</span>
          </button>
        ))}
      </div>

      <p className="campo-ajuda" style={{ margin: "var(--e2) 0 var(--e3)" }}>
        {atual.explicacao}
      </p>

      {camposDoTipo.length > 1 && (
        <div className="filtros" role="group" aria-label="Filtrar por campo">
          <button
            type="button"
            className="botao botao-secundario"
            aria-pressed={campo === ""}
            onClick={() => definirCampo("")}
          >
            Todos ({contagem[tipo]})
          </button>
          {camposDoTipo.map((c) => (
            <button
              key={c.campo ?? "—"}
              type="button"
              className="botao botao-secundario"
              aria-pressed={campo === c.campo}
              onClick={() => definirCampo(c.campo ?? "")}
            >
              {c.campo ?? "—"} ({c.quantas})
            </button>
          ))}
        </div>
      )}

      {ocorrencias.carregando && <Carregando rotulo="Carregando as ocorrências" />}
      {ocorrencias.erro && (
        <Erro mensagem={ocorrencias.erro} aoTentarDeNovo={ocorrencias.recarregar} />
      )}

      {!ocorrencias.carregando && !ocorrencias.erro && ocorrencias.dados?.total === 0 && (
        <VazioSemDados
          titulo="Nada aqui"
          explicacao={
            tipo === "Mudou na recarga"
              ? "Nenhuma recarga alterou dados ainda. Na primeira rodada tudo é novo, e nas seguintes só o que a planilha mudou aparece aqui."
              : "Nenhuma ocorrência deste tipo nesta rodada."
          }
        />
      )}

      {!ocorrencias.carregando && (ocorrencias.dados?.total ?? 0) > 0 && (
        <>
          <p style={{ color: "var(--texto-medio)", margin: "0 0 var(--e2)" }}>
            {ocorrencias.dados!.itens.length < ocorrencias.dados!.total
              ? `Mostrando as primeiras ${ocorrencias.dados!.itens.length} de ${ocorrencias.dados!.total}, na ordem da planilha. Filtre por campo para ver o resto.`
              : `${ocorrencias.dados!.total} ocorrência${ocorrencias.dados!.total === 1 ? "" : "s"}, na ordem da planilha.`}
          </p>
          <table className="tabela">
            <thead>
              <tr>
                <th scope="col" className="tabela-numero">
                  Linha
                </th>
                <th scope="col">Campo</th>
                <th scope="col">O que aconteceu</th>
              </tr>
            </thead>
            <tbody>
              {ocorrencias.dados!.itens.map((o) => (
                <tr key={o.id}>
                  <td className="tabela-numero">{o.linha ?? "—"}</td>
                  <td>{o.campo ?? "—"}</td>
                  <td>{o.texto}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

export function Conferencia() {
  const [escolhida, definirEscolhida] = useState<number | null>(null);

  const cargas = usarDados<Execucao[]>(() => api.cargas(), []);
  const id = escolhida ?? cargas.dados?.[0]?.id ?? null;

  const detalhe = usarDados<ExecucaoDetalhe | null>(
    () => (id === null ? Promise.resolve(null) : api.carga(id)),
    [id],
  );

  if (cargas.carregando) return <Carregando rotulo="Carregando as cargas" />;
  if (cargas.erro) return <Erro mensagem={cargas.erro} aoTentarDeNovo={cargas.recarregar} />;

  if (!cargas.dados || cargas.dados.length === 0) {
    return (
      <VazioSemDados
        titulo="Nenhuma carga registrada"
        explicacao="O relatório de conferência nasce da carga da planilha. Ao gravar a planilha de 2026 com o script de importação, cada rodada passa a aparecer aqui."
      />
    );
  }

  const atual = cargas.dados.find((c) => c.id === id) ?? cargas.dados[0];

  return (
    <>
      <div className="filtros">
        <div className="campo">
          <label className="campo-rotulo" htmlFor="carga-escolhida">
            Rodada da carga
          </label>
          <select
            id="carga-escolhida"
            className="selecao"
            value={atual.id}
            onChange={(e) => definirEscolhida(Number(e.target.value))}
          >
            {cargas.dados.map((c) => (
              <option key={c.id} value={c.id}>
                Nº {c.id} · {dataHora(c.executada_em)}
              </option>
            ))}
          </select>
        </div>
        <p className="campo-ajuda" style={{ alignSelf: "flex-end", margin: 0 }}>
          Planilha: {atual.arquivo}
          {atual.mudancas === 0 && atual.criadas === 0 && cargas.dados.length > 0 && (
            <> · <Etiqueta texto="Sem mudança" tipo="neutra" /></>
          )}
        </p>
      </div>

      {detalhe.carregando && <Carregando rotulo="Abrindo o relatório" />}
      {detalhe.erro && <Erro mensagem={detalhe.erro} aoTentarDeNovo={detalhe.recarregar} />}
      {detalhe.dados && <Detalhe key={detalhe.dados.id} execucao={detalhe.dados} />}
    </>
  );
}
