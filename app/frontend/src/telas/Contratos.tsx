/** A lista de contratos — começo da Etapa 2 (23/09/2026).
 *
 * Nasce só da conversão de uma oportunidade aceita (ver `DetalheDaOportunidade`);
 * esta tela lê e edita, não cadastra do zero.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ContratoResumo, Listas, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";

const SITUACOES_DE_CONTRATO = ["Aguardando assinatura", "Ativo", "Suspenso", "Encerrado"];

function EdicaoDeContrato({
  contrato,
  aoFechar,
  aoSalvar,
}: {
  contrato: ContratoResumo;
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const [rascunho, definirRascunho] = useState({
    escopo: contrato.escopo ?? "",
    preco_mensal: contrato.preco_mensal ?? "",
    preco_anual: contrato.preco_anual ?? "",
    data_inicio: contrato.data_inicio ?? "",
    data_fim: contrato.data_fim ?? "",
    situacao: contrato.situacao,
    signatario: contrato.signatario ?? "",
  });
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);

  const mudar = (campo: string, valor: string) =>
    definirRascunho((atual) => ({ ...atual, [campo]: valor }));

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const mudancas: Record<string, unknown> = Object.fromEntries(
        Object.entries(rascunho).map(([k, v]) => [k, v === "" ? null : v]),
      );
      await api.editarContrato(contrato.id, mudancas);
      aoSalvar();
      aoFechar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <PainelLateral
      titulo={contrato.grupo_nome ?? "Contrato"}
      subtitulo={contrato.escopo ?? undefined}
      aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>
            Cancelar
          </button>
          <button
            type="button"
            className="botao botao-primario"
            onClick={salvar}
            disabled={salvando}
          >
            {salvando ? "Salvando…" : "Salvar alterações"}
          </button>
        </>
      }
    >
      {erro && (
        <div className="estado estado-erro" role="alert">
          <p className="estado-texto">{erro}</p>
        </div>
      )}

      <div className="formulario">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="c-situacao">
            Situação
          </label>
          <select
            id="c-situacao"
            className="selecao"
            value={rascunho.situacao}
            onChange={(e) => mudar("situacao", e.target.value)}
          >
            {SITUACOES_DE_CONTRATO.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="c-escopo">
            Escopo
          </label>
          <input
            id="c-escopo"
            className="entrada"
            value={rascunho.escopo}
            onChange={(e) => mudar("escopo", e.target.value)}
          />
        </div>

        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="c-mensal">
              Preço mensal
            </label>
            <input
              id="c-mensal"
              className="entrada"
              type="number"
              step="0.01"
              value={rascunho.preco_mensal}
              onChange={(e) => mudar("preco_mensal", e.target.value)}
            />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="c-anual">
              Preço anual
            </label>
            <input
              id="c-anual"
              className="entrada"
              type="number"
              step="0.01"
              value={rascunho.preco_anual}
              onChange={(e) => mudar("preco_anual", e.target.value)}
            />
          </div>
        </div>

        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="c-inicio">
              Início da vigência
            </label>
            <input
              id="c-inicio"
              type="date"
              className="entrada"
              value={rascunho.data_inicio}
              onChange={(e) => mudar("data_inicio", e.target.value)}
            />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="c-fim">
              Fim da vigência
            </label>
            <input
              id="c-fim"
              type="date"
              className="entrada"
              value={rascunho.data_fim}
              onChange={(e) => mudar("data_fim", e.target.value)}
            />
          </div>
        </div>

        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="c-signatario">
            Signatário
          </label>
          <input
            id="c-signatario"
            className="entrada"
            value={rascunho.signatario}
            onChange={(e) => mudar("signatario", e.target.value)}
          />
        </div>
      </div>

      <div className="recado">
        Só o registro, ainda: sem assinatura eletrônica (Clicksign fica para depois) e sem
        renovação automática.
      </div>
    </PainelLateral>
  );
}

export function Contratos({ listas: _listas }: { listas: Listas | null }) {
  const [situacao, definirSituacao] = useState("");
  const [editando, definirEditando] = useState<ContratoResumo | null>(null);

  const { dados, carregando, erro, recarregar } = usarDados<Pagina<ContratoResumo>>(
    () => api.contratos(situacao ? { situacao: [situacao] } : {}),
    [situacao],
  );

  const semDadosNenhuns = !carregando && !erro && dados?.total === 0 && situacao === "";
  const vazioPorFiltro = !carregando && !erro && dados?.total === 0 && situacao !== "";

  return (
    <>
      <div className="filtros">
        <div className="campo">
          <label className="campo-rotulo" htmlFor="ct-situacao">
            Situação
          </label>
          <select
            id="ct-situacao"
            className="selecao"
            value={situacao}
            onChange={(e) => definirSituacao(e.target.value)}
          >
            <option value="">Todas</option>
            {SITUACOES_DE_CONTRATO.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {carregando && <Carregando rotulo="Carregando os contratos" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}

      {semDadosNenhuns && (
        <VazioSemDados
          titulo="Nenhum contrato ainda"
          explicacao="O contrato nasce da conversão de uma oportunidade aceita — abra a oportunidade e converta."
        />
      )}
      {vazioPorFiltro && <VazioPorFiltro aoLimpar={() => definirSituacao("")} />}

      {!carregando && !erro && (dados?.total ?? 0) > 0 && (
        <table className="tabela">
          <thead>
            <tr>
              <th scope="col">Grupo</th>
              <th scope="col">Escopo</th>
              <th scope="col">Situação</th>
              <th scope="col">Preço mensal</th>
              <th scope="col">Início</th>
              <th scope="col">Signatário</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {dados!.itens.map((contrato) => (
              <tr key={contrato.id}>
                <td>{contrato.grupo_nome ?? "—"}</td>
                <td>{contrato.escopo ?? "—"}</td>
                <td>
                  <Etiqueta texto={contrato.situacao} />
                </td>
                <td>{dinheiro(contrato.preco_mensal)}</td>
                <td>{data(contrato.data_inicio)}</td>
                <td>{contrato.signatario ?? "—"}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button
                    type="button"
                    className="botao botao-secundario"
                    onClick={() => definirEditando(contrato)}
                  >
                    Abrir
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editando && (
        <EdicaoDeContrato
          contrato={editando}
          aoFechar={() => definirEditando(null)}
          aoSalvar={recarregar}
        />
      )}
    </>
  );
}
