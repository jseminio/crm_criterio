/** O painel de detalhe, onde a oportunidade se move pelo funil. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { Listas, OportunidadeDetalhe } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro } from "../componentes/estados";
import { data, dinheiro } from "../formato";

function Par({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="par">
      <span className="par-rotulo">{rotulo}</span>
      <span className="par-valor">{children}</span>
    </div>
  );
}

export function DetalheDaOportunidade({
  id,
  listas,
  aoFechar,
  aoSalvar,
}: {
  id: number;
  listas: Listas | null;
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const [detalhe, definirDetalhe] = useState<OportunidadeDetalhe | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const [rascunho, definirRascunho] = useState<Record<string, string>>({});

  const carregar = () => {
    definirErro(null);
    api
      .oportunidade(id)
      .then((d) => {
        definirDetalhe(d);
        definirRascunho({
          situacao: d.situacao,
          temperatura: d.temperatura ?? "",
          motivo_recusa: d.motivo_recusa ?? "",
          data_aceite: d.data_aceite ?? "",
          proxima_acao: d.proxima_acao ?? "",
          proxima_acao_em: d.proxima_acao_em ?? "",
          observacao: d.observacao ?? "",
        });
      })
      .catch((f) => definirErro(f instanceof ErroDaApi ? f.message : "Falha inesperada."));
  };

  useEffect(carregar, [id]);

  const mudar = (campo: string, valor: string) =>
    definirRascunho((atual) => ({ ...atual, [campo]: valor }));

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      // Campo vazio vira null, não string vazia: no banco a ausência é null.
      const mudancas = Object.fromEntries(
        Object.entries(rascunho).map(([k, v]) => [k, v === "" ? null : v]),
      );
      await api.editarOportunidade(id, mudancas);
      aoSalvar();
      aoFechar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  const exigeDataDeAceite = rascunho.situacao === "Aceita" && !rascunho.data_aceite;

  return (
    <PainelLateral
      titulo={detalhe?.grupo_nome ?? "Oportunidade"}
      // A carga formou o grupo pelo nome da oportunidade, então os dois
      // coincidem em quase toda linha de 2026. Repetir a mesma frase duas
      // vezes não informa nada e rouba a atenção do que mudou.
      subtitulo={detalhe && detalhe.nome !== detalhe.grupo_nome ? detalhe.nome : undefined}
      aoFechar={aoFechar}
      rodape={
        detalhe && (
          <>
            <button type="button" className="botao botao-secundario" onClick={aoFechar}>
              Cancelar
            </button>
            {/* Uma ação primária por painel — regra 2 do PAD-002. */}
            <button
              type="button"
              className="botao botao-primario"
              onClick={salvar}
              disabled={salvando || exigeDataDeAceite}
            >
              {salvando ? "Salvando…" : "Salvar alterações"}
            </button>
          </>
        )
      }
    >
      {erro && !detalhe && <Erro mensagem={erro} aoTentarDeNovo={carregar} />}
      {!detalhe && !erro && <Carregando rotulo="Abrindo a oportunidade" />}

      {detalhe && (
        <>
          {erro && (
            <div className="estado estado-erro" role="alert">
              <p className="estado-texto">{erro}</p>
            </div>
          )}

          <div className="formulario">
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="d-situacao">
                Situação
              </label>
              <select
                id="d-situacao"
                className="selecao"
                value={rascunho.situacao}
                onChange={(e) => mudar("situacao", e.target.value)}
              >
                {listas?.situacoes.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div className="formulario-duplo">
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="d-temperatura">
                  Temperatura
                </label>
                <select
                  id="d-temperatura"
                  className="selecao"
                  value={rascunho.temperatura}
                  onChange={(e) => mudar("temperatura", e.target.value)}
                >
                  <option value="">Não informada</option>
                  {listas?.temperaturas.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="d-aceite">
                  Data do aceite
                </label>
                <input
                  id="d-aceite"
                  type="date"
                  className="entrada"
                  value={rascunho.data_aceite}
                  onChange={(e) => mudar("data_aceite", e.target.value)}
                  aria-describedby={exigeDataDeAceite ? "d-aceite-aviso" : undefined}
                />
                {exigeDataDeAceite && (
                  <span id="d-aceite-aviso" style={{ fontSize: 12, color: "var(--perda)" }}>
                    Para marcar como aceita, informe a data.
                  </span>
                )}
              </div>
            </div>

            {(rascunho.situacao === "Recusada" || rascunho.situacao === "Perdido") && (
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="d-motivo">
                  Motivo
                </label>
                <select
                  id="d-motivo"
                  className="selecao"
                  value={rascunho.motivo_recusa}
                  onChange={(e) => mudar("motivo_recusa", e.target.value)}
                >
                  <option value="">Não informado</option>
                  {listas?.motivos_de_recusa.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                {detalhe.motivo_recusa_original && (
                  <span style={{ fontSize: 12, color: "var(--texto-medio)" }}>
                    Texto original da planilha: “{detalhe.motivo_recusa_original}”
                  </span>
                )}
              </div>
            )}

            <div className="formulario-duplo">
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="d-acao">
                  Próxima ação
                </label>
                <input
                  id="d-acao"
                  className="entrada"
                  value={rascunho.proxima_acao}
                  onChange={(e) => mudar("proxima_acao", e.target.value)}
                  placeholder="Ligar para o decisor"
                />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="d-acao-em">
                  Quando
                </label>
                <input
                  id="d-acao-em"
                  type="date"
                  className="entrada"
                  value={rascunho.proxima_acao_em}
                  onChange={(e) => mudar("proxima_acao_em", e.target.value)}
                />
              </div>
            </div>

            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="d-obs">
                Observação
              </label>
              <textarea
                id="d-obs"
                className="entrada"
                rows={3}
                value={rascunho.observacao}
                onChange={(e) => mudar("observacao", e.target.value)}
              />
            </div>
          </div>

          <div>
            <h3 style={{ fontSize: 14, marginBottom: "var(--e2)" }}>Vem da planilha</h3>
            <div className="recado">
              Enquanto a planilha roda em paralelo, <strong>ela é a fonte destes campos</strong>.
              Editá-los nos dois lugares criaria divergência. Eles passam a ser editáveis aqui
              quando a proposta nascer no CRM.
            </div>
            <Par rotulo="Serviço">{detalhe.servico ?? "—"}</Par>
            <Par rotulo="Tipo de serviço">{detalhe.tipo_servico ?? "—"}</Par>
            <Par rotulo="Preço mensal">{dinheiro(detalhe.preco_mensal)}</Par>
            <Par rotulo="Preço anual">{dinheiro(detalhe.preco_anual)}</Par>
            <Par rotulo="Data da colocação">{data(detalhe.data_colocacao)}</Par>
            <Par rotulo="Captador">{detalhe.captador ?? "—"}</Par>
            <Par rotulo="Origem">
              <Etiqueta texto={detalhe.tipo_canal} tipo="neutra" />{" "}
              {detalhe.canal && <span>{detalhe.canal}</span>}
            </Par>
            {detalhe.linha_planilha && (
              <Par rotulo="Linha na planilha">{detalhe.linha_planilha}</Par>
            )}
          </div>
        </>
      )}
    </PainelLateral>
  );
}
