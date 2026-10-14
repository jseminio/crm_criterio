/** A lista de contratos — começo da Etapa 2 (23/09/2026).
 *
 * Nasce só da conversão de uma oportunidade aceita (ver `DetalheDaOportunidade`);
 * esta tela lê e edita, não cadastra do zero.
 */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ContratoDetalhe, ContratoResumo, Listas, Mrr, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro, VazioPorFiltro, VazioSemDados } from "../componentes/estados";
import { aliquota, data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { EventosDeContrato } from "./EventosDeContrato";
import { Receita } from "./Receita";
import { CampoDeData } from "../componentes/CampoDeData";
import { AlteracoesDoRegistro } from "../componentes/HistoricoDeAlteracoes";
import { ImportarRecebimentos } from "../componentes/ImportarRecebimentos";
import { usarAcesso } from "../entrada";
import { contratoCombina, Destaque } from "./pesquisaDeContratos";
import { GerarContrato } from "../componentes/GerarContrato";

const SITUACOES_DE_CONTRATO = ["Aguardando assinatura", "Ativo", "Suspenso", "Encerrado"];

/** O valor em bruto: líquido ÷ (1 − imposto), ao centavo, como o MRR soma (02/10/2026). */
export function brutoDoLiquido(liquido: string, imposto: string): number {
  return Math.round((Number(liquido) / (1 - Number(imposto))) * 100) / 100;
}

function BaseDoValor({ base }: { base: ContratoResumo["base_do_valor"] }) {
  if (base === "liquido") return <span className="celula-fonte">líquido</span>;
  if (base === "bruto") return <span className="celula-fonte">bruto</span>;
  return <span className="celula-fonte cartao-prazo-atrasado">⚠ bruto ou líquido?</span>;
}

function EdicaoDeContrato({
  contrato,
  motivos,
  iniciativas,
  aoFechar,
  aoSalvar,
}: {
  contrato: ContratoResumo;
  motivos: string[];
  iniciativas: string[];
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
    base_do_valor: contrato.base_do_valor ?? "",
    parcelas_no_ano: String(contrato.parcelas_no_ano ?? 13),
  });
  // A alíquota vem do MRR (Parâmetros de cálculo), para mostrar quanto o líquido vale em bruto.
  const { dados: mrr } = usarDados<Mrr>(() => api.mrr(), []);
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const [detalhe, definirDetalhe] = useState<ContratoDetalhe | null>(null);

  // O detalhe traz os eventos; a lista só traz o resumo.
  useEffect(() => {
    api.contrato(contrato.id).then(definirDetalhe).catch(() => definirDetalhe(null));
  }, [contrato.id]);

  const situacaoAtual = detalhe?.situacao ?? contrato.situacao;
  // Depois de assinado, preço e fim só mudam por evento — o que deixa o antes e o
  // depois registrados. O servidor recusa; aqui a tela nem deixa digitar.
  const assinado = situacaoAtual === "Ativo" || situacaoAtual === "Suspenso";
  const encerrado = situacaoAtual === "Encerrado";
  // O que está gravado, não o que veio da lista: uma Renovação muda o fim.
  const dataFimGravada = detalhe ? detalhe.data_fim : contrato.data_fim;
  // Encerrado não sai por edição; assinado só alterna entre Ativo e Suspenso; antes
  // da assinatura, tudo menos Encerrado (que só vem pelo evento de Encerramento).
  const situacoesPermitidas = encerrado
    ? ["Encerrado"]
    : assinado
      ? ["Ativo", "Suspenso"]
      : SITUACOES_DE_CONTRATO.filter((s) => s !== "Encerrado");
  // Contrato da carteira anterior ao CRM não tem a data e não precisa dela.
  const semAssinatura =
    rascunho.situacao === "Ativo" && !rascunho.data_inicio && !contrato.anterior_ao_crm;

  const mudar = (campo: string, valor: string) =>
    definirRascunho((atual) => ({ ...atual, [campo]: valor }));

  const aoRegistrarEvento = (atualizado: ContratoDetalhe) => {
    definirDetalhe(atualizado);
    definirRascunho((r) => ({
      ...r,
      escopo: atualizado.escopo ?? "",
      preco_mensal: atualizado.preco_mensal ?? "",
      preco_anual: atualizado.preco_anual ?? "",
      data_fim: atualizado.data_fim ?? "",
      situacao: atualizado.situacao,
    }));
    aoSalvar();
  };

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const mudancas: Record<string, unknown> = Object.fromEntries(
        Object.entries(rascunho).map(([k, v]) => [k, v === "" ? null : v]),
      );
      mudancas.parcelas_no_ano = Number(rascunho.parcelas_no_ano);
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
            disabled={salvando || semAssinatura || (encerrado && rascunho.base_do_valor === (contrato.base_do_valor ?? "") && rascunho.parcelas_no_ano === String(contrato.parcelas_no_ano ?? 13))}
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
            disabled={encerrado}
            onChange={(e) => mudar("situacao", e.target.value)}
          >
            {situacoesPermitidas.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          {semAssinatura && (
            <p className="campo-ajuda" role="alert">
              Para ativar, informe a data da assinatura: a vigência começa nela.
            </p>
          )}
        </div>

        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="c-escopo">
            Escopo
          </label>
          <input
            id="c-escopo"
            className="entrada"
            value={rascunho.escopo}
            disabled={encerrado}
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
              disabled={assinado || encerrado}
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
              disabled={assinado || encerrado}
              onChange={(e) => mudar("preco_anual", e.target.value)}
            />
          </div>
        </div>
        <fieldset className="campo-bloco base-do-valor">
          <legend className="campo-rotulo">O preço mensal é</legend>
          <div className="base-do-valor-opcoes">
            {(["liquido", "bruto"] as const).map((b) => (
              <label key={b}>
                <input type="radio" name="c-base" value={b} checked={rascunho.base_do_valor === b}
                  onChange={() => mudar("base_do_valor", b)} />
                {b === "liquido" ? "Líquido (sem o imposto)" : "Bruto (com o imposto)"}
              </label>
            ))}
          </div>
          <p className="campo-ajuda">
            {rascunho.base_do_valor === "liquido" && rascunho.preco_mensal && mrr
              ? `Entra no MRR como ${dinheiro(String(brutoDoLiquido(rascunho.preco_mensal, mrr.imposto)))} bruto, com o imposto de ${aliquota(mrr.imposto)}.`
              : rascunho.base_do_valor === "bruto"
                ? "Entra no MRR como está."
                : "⚠ Não informado: o MRR soma como está. Vale também para contrato assinado ou encerrado."}
          </p>
        </fieldset>
        <fieldset className="campo-bloco base-do-valor">
          <legend className="campo-rotulo">Parcelas no ano</legend>
          <div className="base-do-valor-opcoes">
            {(["13", "12"] as const).map((n) => (
              <label key={n}>
                <input type="radio" name="c-parcelas" value={n} checked={rascunho.parcelas_no_ano === n}
                  onChange={() => mudar("parcelas_no_ano", n)} />
                {n === "13" ? "13 (com a 13ª, padrão)" : "12 (formato antigo, sem a 13ª)"}
              </label>
            ))}
          </div>
          <p className="campo-ajuda">
            O MRR é a parcela × {rascunho.parcelas_no_ano} ÷ 12.{" "}
            {rascunho.parcelas_no_ano === "12" ? "Sem a 13ª: o MRR é a própria parcela, e dezembro não espera a 13ª no caixa." : "Em dezembro (ou na saída, proporcional) o caixa espera a 13ª."}
          </p>
        </fieldset>
        {encerrado && (
          <p className="campo-ajuda">Contrato encerrado: nada mais muda, nem por evento nem aqui (só o bruto ou líquido e as parcelas).</p>
        )}
        {assinado && (
          <p className="campo-ajuda">
            Contrato assinado: o preço e a data de fim só mudam por um evento (reajuste, expansão,
            contração ou renovação), que guarda o valor anterior.
          </p>
        )}

        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="c-inicio">
              Data da assinatura (início da vigência)
            </label>
            <CampoDeData
              id="c-inicio"
              value={rascunho.data_inicio}
              disabled={encerrado}
              aoMudar={(v) => mudar("data_inicio", v)}
            />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="c-fim">
              Fim da vigência
            </label>
            <CampoDeData
              id="c-fim"
              value={rascunho.data_fim}
              disabled={(assinado && !!dataFimGravada) || encerrado}
              aoMudar={(v) => mudar("data_fim", v)}
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
            disabled={encerrado}
            onChange={(e) => mudar("signatario", e.target.value)}
          />
        </div>
      </div>

      {contrato.recorrente !== false && contrato.situacao !== "Encerrado" && <GerarContrato contratoId={contrato.id} />}

      {detalhe && <EventosDeContrato contrato={detalhe} aoRegistrar={aoRegistrarEvento} motivos={motivos} iniciativas={iniciativas} />}

      <div className="recado">
        Sem assinatura eletrônica ainda (Clicksign fica para depois) e sem renovação automática:
        a vigência começa na data da assinatura que você informa aqui.
      </div>
      <AlteracoesDoRegistro tabela="contrato" id={contrato.id} />
    </PainelLateral>
  );
}

export function Contratos({ listas }: { listas: Listas | null }) {
  const [situacao, definirSituacao] = useState("");
  const [busca, definirBusca] = useState("");
  const [editando, definirEditando] = useState<ContratoResumo | null>(null);
  const [versaoDoMrr, definirVersaoDoMrr] = useState(0);
  const { ordenacao, alternar: alternarOrdenacao } = usarOrdenacao();
  const { eu } = usarAcesso();

  const { dados, carregando, erro, recarregar } = usarDados<Pagina<ContratoResumo>>(
    () => api.contratos(situacao ? { situacao: [situacao] } : {}),
    [situacao],
  );

  const achados = (dados?.itens ?? []).filter((c) => contratoCombina(c, busca));
  const somaDosAchados = achados.reduce((t, c) => t + (c.preco_mensal ? Number(c.preco_mensal) : 0), 0);
  const semDadosNenhuns = !carregando && !erro && dados?.total === 0 && situacao === "";
  const vazioPorFiltro = !carregando && !erro && !semDadosNenhuns && achados.length === 0;
  const limpar = () => {
    definirSituacao("");
    definirBusca("");
  };

  return (
    <>
      <Receita versao={versaoDoMrr} />
      {eu.administrador && (
        <div className="acoes-da-tela">
          <ImportarRecebimentos aoImportar={() => definirVersaoDoMrr((v) => v + 1)} />
        </div>
      )}

      <div className="filtros">
        <div className="campo" style={{ flex: 1, minWidth: 260 }}>
          <label className="campo-rotulo" htmlFor="ct-busca">
            Pesquisar
          </label>
          <input
            id="ct-busca"
            className="entrada entrada-busca"
            type="search"
            value={busca}
            onChange={(e) => definirBusca(e.target.value)}
            placeholder="Grupo, CNPJ, escopo, valor ou data"
            aria-describedby="ct-busca-ajuda"
          />
          <p className="campo-ajuda" id="ct-busca-ajuda" style={{ margin: 0 }}>
            Grupo, empresa ou CNPJ, escopo, situação, signatário, valor (6.538 ou 6538) ou data (05/2026).
          </p>
        </div>
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
      {vazioPorFiltro && <VazioPorFiltro aoLimpar={limpar} />}

      {!carregando && !erro && achados.length > 0 && (
        <p className="campo-ajuda" role="status" style={{ margin: "var(--e2) 0" }}>
          {busca.trim() ? `${achados.length} de ${dados!.itens.length}` : achados.length} contrato{achados.length === 1 ? "" : "s"}
          {" "}· soma do preço mensal: {dinheiro(somaDosAchados)}
        </p>
      )}
      {!carregando && !erro && achados.length > 0 && (
        <table className="tabela">
          <thead>
            <tr>
              <ThOrdenavel coluna="grupo" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Grupo</ThOrdenavel>
              <ThOrdenavel coluna="escopo" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Escopo</ThOrdenavel>
              <ThOrdenavel coluna="situacao" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Situação</ThOrdenavel>
              <ThOrdenavel coluna="preco" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Preço mensal</ThOrdenavel>
              <ThOrdenavel coluna="assinatura" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Assinatura</ThOrdenavel>
              <ThOrdenavel coluna="signatario" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Signatário</ThOrdenavel>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {ordenar(achados, ordenacao, {
              grupo: (c) => c.grupo_nome,
              escopo: (c) => c.escopo,
              situacao: (c) => c.situacao,
              preco: (c) => (c.preco_mensal ? Number(c.preco_mensal) : null),
              assinatura: (c) => c.data_inicio,
              signatario: (c) => c.signatario,
            }).map((contrato) => (
              <tr key={contrato.id}>
                <td>
                  <Destaque texto={contrato.grupo_nome} termo={busca} />
                  {busca.trim() && contrato.empresa_nome && (
                    <span className="campo-ajuda" style={{ display: "block", margin: 0 }}>
                      <Destaque texto={contrato.empresa_nome} termo={busca} />
                    </span>
                  )}
                </td>
                <td><Destaque texto={contrato.escopo} termo={busca} /></td>
                <td>
                  <Etiqueta texto={contrato.situacao} />
                  {contrato.situacao === "Ativo" && contrato.saida_em && (
                    <span className="etiqueta etiqueta-espera" style={{ marginLeft: "var(--e1)" }}>
                      Em aviso de saída · sai em {data(contrato.saida_em)}
                    </span>
                  )}
                </td>
                <td>
                  {dinheiro(contrato.preco_mensal)}
                  {contrato.preco_mensal && <BaseDoValor base={contrato.base_do_valor} />}
                </td>
                <td>
                  {contrato.data_inicio
                    ? data(contrato.data_inicio)
                    : contrato.anterior_ao_crm
                      ? <span className="numero-nota">anterior ao CRM</span>
                      : "—"}
                </td>
                <td><Destaque texto={contrato.signatario} termo={busca} /></td>
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
          motivos={listas?.motivos_de_encerramento ?? []}
          iniciativas={listas?.iniciativas_de_encerramento ?? []}
          aoFechar={() => definirEditando(null)}
          aoSalvar={() => {
            recarregar();
            definirVersaoDoMrr((v) => v + 1);
          }}
        />
      )}
    </>
  );
}
