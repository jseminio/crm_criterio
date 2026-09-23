/** O painel de detalhe, onde a oportunidade se move pelo funil. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { Listas, OportunidadeDetalhe } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro } from "../componentes/estados";
import { dataHora } from "../formato";

function Par({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="par">
      <span className="par-rotulo">{rotulo}</span>
      <span className="par-valor">{children}</span>
    </div>
  );
}

/** Os nove direcionadores da régua de porte, na ordem de
 * `regua-de-porte-e-plano-de-teste.md`, seção 2. Em branco = "não se aplica
 * ao escopo contratado" — fica fora da média, nunca vira zero. */
const DIRECIONADORES: { id: string; rotulo: string; placeholder: string }[] = [
  { id: "documentos_fiscais_mes", rotulo: "Documentos fiscais/mês", placeholder: "emitidas + recebidas" },
  { id: "lancamentos_contabeis_mes", rotulo: "Lançamentos contábeis/mês", placeholder: "" },
  { id: "pagamentos_mes", rotulo: "Pagamentos/mês", placeholder: "" },
  { id: "contas_bancarias", rotulo: "Contas bancárias", placeholder: "" },
  { id: "conciliacoes_cartao_mes", rotulo: "Conciliações de cartão/mês", placeholder: "0 = nenhuma" },
  { id: "empregados_clt", rotulo: "Empregados CLT", placeholder: "" },
  { id: "admissoes_desligamentos_mes", rotulo: "Admissões + desligamentos/mês", placeholder: "" },
  { id: "cnpjs_no_escopo", rotulo: "CNPJs no escopo", placeholder: "" },
  { id: "tomadores_de_servico", rotulo: "Tomadores de serviço", placeholder: "" },
];

function paresDe<T>(itens: T[]): T[][] {
  const pares: T[][] = [];
  for (let i = 0; i < itens.length; i += 2) pares.push(itens.slice(i, i + 2));
  return pares;
}

function VolumetriaEPorte({
  detalhe,
  rascunho,
  mudar,
  alternar,
  listas,
}: {
  detalhe: OportunidadeDetalhe;
  rascunho: Record<string, string>;
  mudar: (campo: string, valor: string) => void;
  alternar: (campo: string) => (evento: { target: { checked: boolean } }) => void;
  listas: Listas | null;
}) {
  const sugestao = detalhe.sugestao_de_porte;

  const numero = (id: string, rotulo: string, placeholder?: string) => (
    <div className="campo-bloco" key={id}>
      <label className="campo-rotulo" htmlFor={`d-${id}`}>
        {rotulo}
      </label>
      <input
        id={`d-${id}`}
        type="number"
        min="0"
        step="1"
        className="entrada"
        value={rascunho[id] ?? ""}
        onChange={(e) => mudar(id, e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );

  const nota1a5 = (id: string, rotulo: string) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`d-${id}`}>
        {rotulo}
      </label>
      <select
        id={`d-${id}`}
        className="selecao"
        value={rascunho[id] ?? ""}
        onChange={(e) => mudar(id, e.target.value)}
      >
        <option value="">Não avaliada</option>
        {[1, 2, 3, 4, 5].map((n) => (
          <option key={n} value={n}>
            {n}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <div className="formulario">
      <h3 style={{ fontSize: 14, marginBottom: "var(--e2)" }}>Volumetria e porte</h3>
      <p className="campo-ajuda" style={{ marginTop: 0 }}>
        A régua sugere o porte a partir do volume — <strong>nunca decide sozinha</strong>.
        Preencha só o que já for conhecido; direcionador em branco não entra na média.
      </p>

      <div className="formulario-duplo">
        {nota1a5("complexidade", "Complexidade")}
        {nota1a5("risco_tecnico", "Risco técnico")}
      </div>

      {paresDe(DIRECIONADORES).map((par, i) => (
        <div className="formulario-duplo" key={i}>
          {par.map((d) => numero(d.id, d.rotulo, d.placeholder))}
        </div>
      ))}

      <div className="formulario-duplo">
        {numero(
          "servicos_contratados_alem_do_primeiro",
          "Serviços contratados além do primeiro",
          "0",
        )}
        <div className="campo-bloco">
          <label className="campo-rotulo">Ajustes</label>
          <label style={{ display: "flex", alignItems: "center", gap: "var(--e1)", fontSize: 14 }}>
            <input
              type="checkbox"
              checked={rascunho.tem_consolidacao_de_grupo === "sim"}
              onChange={alternar("tem_consolidacao_de_grupo")}
            />
            Há consolidação de grupo
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: "var(--e1)", fontSize: 14 }}>
            <input
              type="checkbox"
              checked={rascunho.e_auditada === "sim"}
              onChange={alternar("e_auditada")}
            />
            Empresa auditada
          </label>
        </div>
      </div>

      <div className="recado">
        {sugestao?.calculavel ? (
          <>
            Sugestão da régua: <strong>{sugestao.porte}</strong> — pontuação{" "}
            {sugestao.pontuacao?.replace(".", ",")}, {sugestao.horas_base}h base/mês,{" "}
            {sugestao.direcionadores_aplicados} de 9 direcionadores preenchidos.
          </>
        ) : (
          "Sugestão da régua: não calculável — nenhum direcionador preenchido ainda."
        )}
        <br />
        <span style={{ fontSize: 12 }}>
          Reflete o que está salvo; salve as mudanças acima para atualizar.
        </span>
      </div>

      <div className="formulario-duplo">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="d-porte">
            Porte confirmado
          </label>
          <select
            id="d-porte"
            className="selecao"
            value={rascunho.porte ?? ""}
            onChange={(e) => mudar("porte", e.target.value)}
          >
            <option value="">Não confirmado</option>
            {listas?.portes.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          {sugestao?.calculavel && rascunho.porte !== sugestao.porte && (
            <button
              type="button"
              className="botao botao-secundario"
              style={{ marginTop: "var(--e1)" }}
              onClick={() => mudar("porte", sugestao.porte ?? "")}
            >
              Usar sugestão ({sugestao.porte})
            </button>
          )}
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="d-porte-por">
            Definido por
          </label>
          <select
            id="d-porte-por"
            className="selecao"
            value={rascunho.porte_definido_por ?? ""}
            onChange={(e) => mudar("porte_definido_por", e.target.value)}
          >
            <option value="">Não informado</option>
            {listas?.captadores.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      {detalhe.porte_definido_em && (
        <p className="campo-ajuda" style={{ margin: 0 }}>
          Confirmado por {detalhe.porte_definido_por ?? "alguém não identificado"} em{" "}
          {dataHora(detalhe.porte_definido_em)}. O instante é gravado pelo servidor — é o que
          vira material para recalibrar a régua depois.
        </p>
      )}
    </div>
  );
}

export function DetalheDaOportunidade({
  id,
  listas,
  situacaoInicial,
  aoFechar,
  aoSalvar,
}: {
  id: number;
  listas: Listas | null;
  /** Pré-seleciona a situação ao abrir — usado pelo arrasto no kanban.
   *
   * O cartão do kanban não carrega `data_aceite` (só o detalhe traz); soltar
   * em "Aceita" não tem como decidir sozinho se falta a data. Em vez de
   * adivinhar, abre aqui com a situação já marcada, e a trava existente —
   * salvar desabilitado sem a data — cuida do resto sem duplicar a regra.
   */
  situacaoInicial?: string;
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const [detalhe, definirDetalhe] = useState<OportunidadeDetalhe | null>(null);
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);
  const [rascunho, definirRascunho] = useState<Record<string, string>>({});
  const [convertendoEmContrato, definirConvertendoEmContrato] = useState(false);
  const [avisoDeContrato, definirAvisoDeContrato] = useState<string | null>(null);

  const carregar = () => {
    definirErro(null);
    api
      .oportunidade(id)
      .then((d) => {
        definirDetalhe(d);
        definirRascunho({
          situacao: situacaoInicial ?? d.situacao,
          temperatura: d.temperatura ?? "",
          motivo_recusa: d.motivo_recusa ?? "",
          data_aceite: d.data_aceite ?? "",
          proxima_acao: d.proxima_acao ?? "",
          proxima_acao_em: d.proxima_acao_em ?? "",
          observacao: d.observacao ?? "",
          servico: d.servico ?? "",
          tipo_servico: d.tipo_servico ?? "",
          data_colocacao: d.data_colocacao ?? "",
          preco_mensal: d.preco_mensal ?? "",
          preco_anual: d.preco_anual ?? "",
          complexidade: d.complexidade?.toString() ?? "",
          risco_tecnico: d.risco_tecnico?.toString() ?? "",
          documentos_fiscais_mes: d.documentos_fiscais_mes?.toString() ?? "",
          lancamentos_contabeis_mes: d.lancamentos_contabeis_mes?.toString() ?? "",
          pagamentos_mes: d.pagamentos_mes?.toString() ?? "",
          contas_bancarias: d.contas_bancarias?.toString() ?? "",
          conciliacoes_cartao_mes: d.conciliacoes_cartao_mes?.toString() ?? "",
          empregados_clt: d.empregados_clt?.toString() ?? "",
          admissoes_desligamentos_mes: d.admissoes_desligamentos_mes?.toString() ?? "",
          cnpjs_no_escopo: d.cnpjs_no_escopo?.toString() ?? "",
          tomadores_de_servico: d.tomadores_de_servico?.toString() ?? "",
          servicos_contratados_alem_do_primeiro: d.servicos_contratados_alem_do_primeiro.toString(),
          tem_consolidacao_de_grupo: d.tem_consolidacao_de_grupo ? "sim" : "",
          e_auditada: d.e_auditada ? "sim" : "",
          porte: d.porte ?? "",
          porte_definido_por: d.porte_definido_por ?? "",
        });
      })
      .catch((f) => definirErro(f instanceof ErroDaApi ? f.message : "Falha inesperada."));
  };

  useEffect(carregar, [id]);

  const mudar = (campo: string, valor: string) =>
    definirRascunho((atual) => ({ ...atual, [campo]: valor }));

  const alternar = (campo: string) => (evento: { target: { checked: boolean } }) =>
    definirRascunho((atual) => ({ ...atual, [campo]: evento.target.checked ? "sim" : "" }));

  //  Os dois únicos campos booleanos: "" não é "sem resposta" aqui, é "não" —
  // um checkbox desmarcado precisa virar `false` explícito, não sumir do
  // corpo da requisição como os outros campos vazios fazem.
  const CAMPOS_BOOLEANOS = new Set(["tem_consolidacao_de_grupo", "e_auditada"]);

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      // Campo vazio vira null, não string vazia: no banco a ausência é null.
      const mudancas = Object.fromEntries(
        Object.entries(rascunho).map(([k, v]) =>
          CAMPOS_BOOLEANOS.has(k) ? [k, v === "sim"] : [k, v === "" ? null : v],
        ),
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

  const converterEmContrato = async () => {
    definirConvertendoEmContrato(true);
    definirErro(null);
    definirAvisoDeContrato(null);
    try {
      await api.converterEmContrato(id);
      definirAvisoDeContrato("Contrato criado — confira na tela Contratos.");
      aoSalvar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao converter em contrato.");
    } finally {
      definirConvertendoEmContrato(false);
    }
  };

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
            {detalhe.situacao === "Aceita" && (
              <button
                type="button"
                className="botao botao-secundario"
                onClick={converterEmContrato}
                disabled={convertendoEmContrato}
              >
                {convertendoEmContrato ? "Convertendo…" : "Converter em contrato"}
              </button>
            )}
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
          {avisoDeContrato && (
            <div className="recado" role="status">
              {avisoDeContrato}
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
                <label className="campo-rotulo" htmlFor="d-servico">
                  Serviço
                </label>
                <input
                  id="d-servico"
                  className="entrada"
                  value={rascunho.servico}
                  onChange={(e) => mudar("servico", e.target.value)}
                  placeholder="BPO Contábil"
                />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="d-tipo-servico">
                  Tipo de serviço
                </label>
                <input
                  id="d-tipo-servico"
                  className="entrada"
                  value={rascunho.tipo_servico}
                  onChange={(e) => mudar("tipo_servico", e.target.value)}
                  placeholder="Contabilidade"
                />
              </div>
            </div>

            <div className="formulario-duplo">
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="d-preco-mensal">
                  Preço mensal
                </label>
                <input
                  id="d-preco-mensal"
                  type="number"
                  step="0.01"
                  min="0"
                  className="entrada"
                  value={rascunho.preco_mensal}
                  onChange={(e) => mudar("preco_mensal", e.target.value)}
                />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="d-preco-anual">
                  Preço anual
                </label>
                <input
                  id="d-preco-anual"
                  type="number"
                  step="0.01"
                  min="0"
                  className="entrada"
                  value={rascunho.preco_anual}
                  onChange={(e) => mudar("preco_anual", e.target.value)}
                />
              </div>
            </div>

            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="d-originacao">
                Data de originação
              </label>
              <input
                id="d-originacao"
                type="date"
                className="entrada"
                value={rascunho.data_colocacao}
                onChange={(e) => mudar("data_colocacao", e.target.value)}
              />
            </div>

            <p className="campo-ajuda" style={{ margin: 0 }}>
              Serviço, preço e data de originação agora são editáveis aqui — desde
              22/09/2026 (E4), a proposta pode nascer e ser ajustada direto no CRM.{" "}
              <strong>A mesma trava contra a recarga da planilha vale para eles.</strong>
            </p>

            <VolumetriaEPorte
              detalhe={detalhe}
              rascunho={rascunho}
              mudar={mudar}
              alternar={alternar}
              listas={listas}
            />

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

            <p className="campo-ajuda" style={{ margin: 0 }}>
              O que você mudar em situação, temperatura, motivo e data do aceite{" "}
              <strong>a recarga da planilha não sobrescreve</strong>. Se a planilha
              discordar, a divergência aparece na tela Conferência para você decidir.
            </p>

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
              Editá-los nos dois lugares criaria divergência.
            </div>
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
