/** O detalhe de um grupo econômico: as propostas dele e o que já foi juntado nele.
 *
 * Existe para o reagrupamento ser auditável. Juntar dois grupos move tudo para
 * um deles e marca o outro como fundido — sem esta tela, o resultado da junção
 * só se veria de longe, na contagem da lista.
 *
 * Também reúne os PDFs do cliente (seção Documentos, 19/10/2026).
 */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { GrupoResumo, Listas, OportunidadeResumo, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { ThOrdenavel, ordenar, usarOrdenacao } from "../componentes/Ordenacao";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { data, dinheiro } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";
import { AvisoDeLacuna, QuadroDeLacunas, irAoCampo, marcasDeLacuna, usarLacunas } from "../componentes/Lacunas";
import type { Lacuna } from "../api/tipos";
import { CardDaLacuna, CardDoContrato, lacunaTemCard } from "./CardDaLacuna";
import { DocumentosDoGrupo } from "./DocumentosDoGrupo";

function FormularioDeGrupo({
  grupo,
  aoSalvar,
  aoCancelar,
  marcas,
}: {
  grupo: GrupoResumo;
  aoSalvar: (corpo: Record<string, unknown>) => Promise<void>;
  aoCancelar: () => void;
  marcas: ReturnType<typeof marcasDeLacuna>;
}) {
  const [nome, definirNome] = useState(grupo.nome);
  const [responsavelCs, definirResponsavelCs] = useState(grupo.responsavel_cs ?? "");
  const [observacao, definirObservacao] = useState(grupo.observacao ?? "");
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await aoSalvar({
        nome: nome.trim(),
        responsavel_cs: responsavelCs.trim() === "" ? null : responsavelCs.trim(),
        observacao: observacao.trim() === "" ? null : observacao.trim(),
      });
    } catch (f) {
      definirErro(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <div className="formulario">
      <div className="formulario-duplo">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="grupo-nome">Nome</label>
          <input id="grupo-nome" className="entrada" maxLength={200} value={nome} onChange={(e) => definirNome(e.target.value)} />
        </div>
        <div className={`campo-bloco ${marcas.classe("responsavel_cs")}`} id={marcas.id("responsavel_cs")}>
          <label className="campo-rotulo" htmlFor="grupo-responsavel">Responsável CS</label>
          <input id="grupo-responsavel" className="entrada" maxLength={10} value={responsavelCs} onChange={(e) => definirResponsavelCs(e.target.value)} />
          {marcas.aviso("responsavel_cs")}
        </div>
      </div>
      <div className="campo-bloco">
        <label className="campo-rotulo" htmlFor="grupo-observacao">Observação</label>
        <input id="grupo-observacao" className="entrada" value={observacao} onChange={(e) => definirObservacao(e.target.value)} />
      </div>
      {erro && <p role="alert" className="estado-texto">{erro}</p>}
      <div className="sugestao-acoes">
        <button type="button" className="botao botao-secundario" onClick={aoCancelar}>Cancelar</button>
        <button type="button" className="botao botao-primario" disabled={salvando || nome.trim() === ""} onClick={salvar}>
          {salvando ? "Salvando…" : "Salvar grupo"}
        </button>
      </div>
    </div>
  );
}

export function DetalheDoGrupo({
  grupo,
  listas,
  foco,
  aoFechar,
  aoMudar,
}: {
  grupo: GrupoResumo;
  listas: Listas | null;
  /** Abre já nesta lacuna do cliente (a chave), vindo da Integralidade (18/10/2026). */
  foco?: string;
  aoFechar: () => void;
  aoMudar: () => void;
}) {
  const [grupoAtual, definirGrupoAtual] = useState(grupo);
  const [editando, definirEditando] = useState(false);
  const [aberta, definirAberta] = useState<number | null>(null);
  const [contratoAberto, definirContratoAberto] = useState<number | null>(null);
  const { ordenacao, alternar: alternarOrdenacao } = usarOrdenacao();

  // O que falta no cadastro do grupo inteiro (18/10/2026): cliente, oportunidades, contratos, empresas e contatos.
  // "ir ao campo" abre o card do registro já no campo; o do cliente é o formulário daqui.
  const [versaoDasLacunas, definirVersaoDasLacunas] = useState(0);
  const { lacunas } = usarLacunas({ grupo_id: grupo.id }, versaoDasLacunas);
  const marcas = marcasDeLacuna(lacunas, "Cliente", grupo.id);
  const [lacunaAberta, definirLacunaAberta] = useState<Lacuna | null>(null);
  const irPara = (l: Pick<Lacuna, "cadastro" | "chave">) => {
    if (l.cadastro === "Cliente") {
      definirEditando(true);
      window.setTimeout(() => irAoCampo(marcas.id(l.chave)), 60);
    } else if (lacunas) {
      const alvo = lacunas.find((x) => x.cadastro === l.cadastro && x.chave === l.chave);
      if (alvo) definirLacunaAberta(alvo);
    }
  };
  const prontoParaFoco = lacunas !== null;
  useEffect(() => {
    if (foco === "responsavel_cs" && prontoParaFoco) irPara({ cadastro: "Cliente", chave: foco });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [foco, prontoParaFoco]);

  const salvarGrupo = async (corpo: Record<string, unknown>) => {
    const atualizado = await api.editarGrupo(grupoAtual.id, corpo);
    definirGrupoAtual(atualizado);
    definirEditando(false);
    definirVersaoDasLacunas((v) => v + 1);
    aoMudar();
  };

  const propostas = usarDados<Pagina<OportunidadeResumo>>(
    () => api.oportunidades({ grupo_id: grupo.id }),
    [grupo.id],
  );

  // Os grupos fundidos continuam no banco, apontando para quem os absorveu.
  const todos = usarDados<Pagina<GrupoResumo>>(
    () => api.grupos({ incluir_fundidos: true, limite: 500 }),
    [grupo.id],
  );
  const juntados = todos.dados?.itens.filter((g) => g.fundido_em_id === grupo.id) ?? [];

  return (
    <>
      <PainelLateral
        titulo={grupoAtual.nome}
        subtitulo="Grupo econômico"
        aoFechar={aoFechar}
      >
        <QuadroDeLacunas lacunas={lacunas} comRegistro grupoNome={grupoAtual.nome} aoIr={(l) => (l.cadastro === "Cliente" ? irPara(l) : definirLacunaAberta(l))}
          semCampo={(l) => (l.cadastro === "Cliente" && l.chave === "classificacao" ? "Na Saúde da carteira: avalie o grupo."
            : l.cadastro === "Cliente" && l.chave === "porte" ? "Na Saúde da carteira: confirme o porte do grupo."
              : l.cadastro !== "Cliente" && !lacunaTemCard(l) ? "Sem card para abrir: a pessoa não tem empresa." : null)} />

        <div className="secao-do-painel">
          {editando ? (
            <FormularioDeGrupo grupo={grupoAtual} aoSalvar={salvarGrupo} aoCancelar={() => definirEditando(false)} marcas={marcas} />
          ) : (
            <>
              <div className="cartao-linha">
                <Etiqueta texto={grupoAtual.situacao} />
                <Etiqueta texto={grupoAtual.origem} tipo="neutra" />
                {grupoAtual.data_entrada && (
                  <span className="campo-ajuda">Cliente desde {data(grupoAtual.data_entrada)}</span>
                )}
              </div>
              {grupoAtual.responsavel_cs && (
                <p className="campo-ajuda" style={{ marginTop: "var(--e2)" }}>Responsável CS: {grupoAtual.responsavel_cs}</p>
              )}
              {marcas.tem("responsavel_cs") && (
                <p style={{ margin: "var(--e2) 0 0" }}><AvisoDeLacuna obrigatorio texto="Obrigatório em falta: responsável de CS" /></p>
              )}
              {grupoAtual.observacao && <p className="campo-ajuda">{grupoAtual.observacao}</p>}
              <button type="button" className="botao botao-secundario" style={{ marginTop: "var(--e2)" }} onClick={() => definirEditando(true)}>
                Editar
              </button>
            </>
          )}
        </div>

        <div className="secao-do-painel">
          <h3>Propostas</h3>
          {propostas.carregando && <Carregando rotulo="Carregando as propostas" />}
          {propostas.erro && (
            <Erro mensagem={propostas.erro} aoTentarDeNovo={propostas.recarregar} />
          )}
          {!propostas.carregando && !propostas.erro && propostas.dados?.total === 0 && (
            <VazioSemDados
              titulo="Nenhuma proposta neste grupo"
              explicacao="Um grupo sem proposta costuma ser o que sobrou de uma junção."
            />
          )}
          {!propostas.carregando && (propostas.dados?.total ?? 0) > 0 && (
            <table className="mini-tabela">
              <thead>
                <tr>
                  <ThOrdenavel coluna="nome" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Proposta</ThOrdenavel>
                  <ThOrdenavel coluna="situacao" ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Situação</ThOrdenavel>
                  <ThOrdenavel coluna="anual" numerico ordenacao={ordenacao} aoAlternar={alternarOrdenacao}>Anual</ThOrdenavel>
                </tr>
              </thead>
              <tbody>
                {ordenar(propostas.dados!.itens, ordenacao, {
                  nome: (o) => o.nome,
                  situacao: (o) => o.situacao,
                  anual: (o) => (o.preco_anual ? Number(o.preco_anual) : null),
                }).map((o) => (
                  <tr key={o.id}>
                    <td>
                      <button
                        type="button"
                        className="link-de-tabela"
                        onClick={() => definirAberta(o.id)}
                      >
                        {o.nome}
                      </button>
                      <div className="campo-ajuda">
                        {[o.servico, o.tipo_servico].filter(Boolean).join(" · ") || "—"}
                        {o.data_colocacao && ` · ${data(o.data_colocacao)}`}
                      </div>
                    </td>
                    <td>
                      <Etiqueta texto={o.situacao} />
                    </td>
                    <td className="tabela-numero">{dinheiro(o.preco_anual)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <DocumentosDoGrupo grupoId={grupo.id} propostas={propostas.dados?.itens ?? []}
          aoAbrirContrato={definirContratoAberto} aoAbrirOportunidade={definirAberta} />

        {juntados.length > 0 && (
          <div className="secao-do-painel">
            <h3>Juntados neste grupo</h3>
            <p className="campo-ajuda" style={{ marginTop: 0 }}>
              Continuam no banco, marcados como fundidos. Nada foi apagado.
            </p>
            <table className="mini-tabela">
              <tbody>
                {juntados.map((g) => (
                  <tr key={g.id}>
                    <td>{g.nome}</td>
                    <td>
                      <Etiqueta texto={g.situacao} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </PainelLateral>

      {aberta !== null && (
        <DetalheDaOportunidade
          id={aberta}
          listas={listas}
          aoFechar={() => definirAberta(null)}
          aoSalvar={propostas.recarregar}
        />
      )}
      {contratoAberto !== null && (
        <CardDoContrato contratoId={contratoAberto} listas={listas} aoFechar={() => definirContratoAberto(null)} />
      )}
      {lacunaAberta && (
        <CardDaLacuna lacuna={lacunaAberta} listas={listas}
          aoFechar={() => { definirLacunaAberta(null); definirVersaoDasLacunas((v) => v + 1); propostas.recarregar(); }} />
      )}
    </>
  );
}
