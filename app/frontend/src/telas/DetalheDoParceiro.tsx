/** O painel do parceiro (19/10/2026): o cadastro (PF ou PJ, nível, acordo, sócio responsável, perfil pedido), as
 * indicações com a validação e o vínculo de 12 meses, ligar uma oportunidade nova e os fees do parceiro. No acordo
 * informal, a regra prometida fica registrada com quem combinou e quando: é a base da regularização. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { CadastroDoParceiro, IndicacaoDoParceiro, OportunidadeParaIndicar, ParceiroDetalhe } from "../api/tipos";
import { CampoDeData } from "../componentes/CampoDeData";
import { Etiqueta } from "../componentes/Etiqueta";
import { PainelLateral } from "../componentes/PainelLateral";
import { RegistrarIndicacao } from "../componentes/RegistrarIndicacao";
import { abrirParaImprimir, mesPadrao } from "../relatorioDoParceiro";
import { Carregando, Erro } from "../componentes/estados";
import { usarAcesso } from "../entrada";
import { data, dinheiro, hojeIso } from "../formato";
import { usarDados } from "../usarDados";
import { ACORDOS, ETAPAS_MANUAIS, NIVEIS } from "../componentes/ParceirosApoio";

const MOTIVOS = ["Já é cliente", "Já estava em negociação", "Já apresentada por outro parceiro", "Fora do perfil"];

const EM_BRANCO: CadastroDoParceiro = {
  nome: "", tipo_pessoa: "PJ", documento: null, tipo: null, nivel: "Indicador", etapa_manual: "Mapeado",
  acordo: "Sem acordo", contrato_assinado_em: null, regra_combinada: null, combinado_por: null, combinado_em: null,
  socio_responsavel: null, perfil_pedido: null, contato: null, observacao: null,
};

function cadastroDe(p: ParceiroDetalhe): CadastroDoParceiro {
  const { nome, tipo_pessoa, documento, tipo, nivel, etapa_manual, acordo, contrato_assinado_em, regra_combinada,
    combinado_por, combinado_em, socio_responsavel, perfil_pedido, contato, observacao } = p;
  return { nome, tipo_pessoa, documento, tipo, nivel, etapa_manual, acordo, contrato_assinado_em, regra_combinada,
    combinado_por, combinado_em, socio_responsavel, perfil_pedido, contato, observacao };
}

export function DetalheDoParceiro({ id, aoFechar, aoSalvar }: {
  id: number | null;
  aoFechar: () => void;
  aoSalvar: (id: number) => void;
}) {
  const { dados, carregando, erro, recarregar } = usarDados<ParceiroDetalhe | null>(
    () => (id === null ? Promise.resolve(null) : api.parceiro(id)), [id],
  );
  if (id !== null && carregando && !dados) {
    return <PainelLateral titulo="Parceiro" aoFechar={aoFechar}><Carregando rotulo="Carregando o parceiro" /></PainelLateral>;
  }
  if (id !== null && erro) {
    return <PainelLateral titulo="Parceiro" aoFechar={aoFechar}><Erro mensagem={erro} aoTentarDeNovo={recarregar} /></PainelLateral>;
  }
  return <Formulario key={dados?.id ?? "novo"} parceiro={dados} aoFechar={aoFechar} aoSalvar={(p) => {
    recarregar();
    aoSalvar(p.id);
  }} />;
}

function Formulario({ parceiro, aoFechar, aoSalvar }: {
  parceiro: ParceiroDetalhe | null;
  aoFechar: () => void;
  aoSalvar: (p: ParceiroDetalhe) => void;
}) {
  const { pode } = usarAcesso();
  const editavel = pode("parceiros.editar");
  const [campos, definirCampos] = useState<CadastroDoParceiro>(parceiro ? cadastroDe(parceiro) : EM_BRANCO);
  const [salvando, definirSalvando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [atual, definirAtual] = useState<ParceiroDetalhe | null>(parceiro);

  const mudar = <K extends keyof CadastroDoParceiro>(campo: K, valor: CadastroDoParceiro[K]) =>
    definirCampos((c) => ({ ...c, [campo]: valor }));
  const texto = (campo: keyof CadastroDoParceiro, rotulo: string, extra: { placeholder?: string; ajuda?: string } = {}) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`p-${campo}`}>{rotulo}</label>
      <input id={`p-${campo}`} className="entrada" value={(campos[campo] as string | null) ?? ""} disabled={!editavel}
        placeholder={extra.placeholder} onChange={(e) => mudar(campo, (e.target.value || null) as never)} />
      {extra.ajuda && <p className="campo-ajuda">{extra.ajuda}</p>}
    </div>
  );
  const escolha = (campo: keyof CadastroDoParceiro, rotulo: string, opcoes: string[]) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`p-${campo}`}>{rotulo}</label>
      <select id={`p-${campo}`} className="selecao" value={campos[campo] as string} disabled={!editavel}
        onChange={(e) => mudar(campo, e.target.value as never)}>
        {opcoes.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </div>
  );
  const dataDe = (campo: "contrato_assinado_em" | "combinado_em", rotulo: string) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`p-${campo}`}>{rotulo}</label>
      <CampoDeData id={`p-${campo}`} value={campos[campo]} disabled={!editavel} aoMudar={(v) => mudar(campo, v || null)} />
    </div>
  );

  async function salvar() {
    definirSalvando(true);
    definirFalha(null);
    try {
      const salvo = atual ? await api.editarParceiro(atual.id, campos) : await api.criarParceiro(campos);
      definirAtual(salvo);
      aoSalvar(salvo);
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui salvar.");
    } finally {
      definirSalvando(false);
    }
  }

  return (
    <PainelLateral
      titulo={atual ? atual.nome : "Novo parceiro"}
      subtitulo={atual ? `${atual.etapa} · ${atual.nivel} · ${atual.acordo}` : "Quem indica clientes à Critério"}
      aoFechar={aoFechar}
      rodape={editavel ? (
        <>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>Fechar</button>
          <button type="button" className="botao botao-primario" onClick={salvar} disabled={salvando || campos.nome.trim() === ""}>
            {salvando ? "Salvando…" : atual ? "Salvar" : "Cadastrar parceiro"}
          </button>
        </>
      ) : undefined}
    >
      {falha && <div className="estado estado-erro" role="alert"><p className="estado-texto">{falha}</p></div>}

      <div className="formulario">
        {texto("nome", "Nome", { placeholder: "Ficus Advocacia" })}
        <div className="formulario-duplo">
          {escolha("tipo_pessoa", "Pessoa", ["PJ", "PF"])}
          {texto("documento", campos.tipo_pessoa === "PF" ? "CPF" : "CNPJ")}
        </div>
        <div className="formulario-duplo">
          {texto("tipo", "Tipo", { placeholder: "Advocacia tributária" })}
          {texto("socio_responsavel", "Sócio responsável", { placeholder: "Eduardo" })}
        </div>
        <div className="formulario-duplo">
          {escolha("nivel", "Nível", NIVEIS)}
          {escolha("etapa_manual", "Etapa marcada à mão", ETAPAS_MANUAIS)}
        </div>
        <p className="campo-ajuda">
          Formalizado, Ativado, Produtivo e Dormente saem dos dados: contrato assinado, indicação validada, proposta enviada
          e seis meses sem indicação. Estratégico marcado à mão vale sobre tudo.
        </p>
        <div className="formulario-duplo">
          {escolha("acordo", "Acordo", ACORDOS)}
          {campos.acordo === "Contrato assinado" && dataDe("contrato_assinado_em", "Assinado em")}
        </div>
        {campos.acordo === "Informal, com fee" && (
          <>
            {texto("regra_combinada", "Fee combinado", { placeholder: "1ª parcela de cada contrato recorrente",
              ajuda: "Com as palavras de quem combinou. É a base da regularização." })}
            <div className="formulario-duplo">
              {texto("combinado_por", "Combinado por")}
              {dataDe("combinado_em", "Combinado em")}
            </div>
          </>
        )}
        {texto("perfil_pedido", "Perfil de cliente pedido", { placeholder: "Porte Médio a Extra Grande, fora de apostas" })}
        {texto("contato", "Contato", { placeholder: "E-mail ou telefone de quem fala pelo parceiro" })}
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="p-observacao">Observação</label>
          <textarea id="p-observacao" className="entrada" rows={3} value={campos.observacao ?? ""} disabled={!editavel}
            onChange={(e) => mudar("observacao", e.target.value || null)} />
        </div>
      </div>

      {atual && <RelatorioDoMes parceiroId={atual.id} />}
      {atual && <Indicacoes parceiro={atual} editavel={editavel} aoMudar={(p) => { definirAtual(p); aoSalvar(p); }} />}
      {atual && atual.fees.length > 0 && (
        <section className="secao-do-painel">
          <h3>Fees</h3>
          <ul className="lista-de-indicacoes">
            {atual.fees.map((f) => (
              <li key={f.id}>
                <div className="indicacao-topo">
                  <strong>{f.grupo ?? f.oportunidade}</strong>
                  <Etiqueta texto={f.situacao} />
                </div>
                <span className="indicacao-detalhe">
                  {f.regra} · competência {data(f.competencia)} · {dinheiro(f.valor_aprovado ?? f.calculado)}
                  {f.pago_em ? ` · pago em ${data(f.pago_em)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {atual && atual.textos_do_canal.length > 0 && (
        <p className="campo-ajuda">Ligado pela conferência aos textos de canal: {atual.textos_do_canal.join(", ")}.</p>
      )}
    </PainelLateral>
  );
}

function Indicacoes({ parceiro, editavel, aoMudar }: {
  parceiro: ParceiroDetalhe;
  editavel: boolean;
  aoMudar: (p: ParceiroDetalhe) => void;
}) {
  const [falha, definirFalha] = useState<string | null>(null);
  const [registrando, definirRegistrando] = useState(false);
  async function agir(acao: () => Promise<ParceiroDetalhe>) {
    definirFalha(null);
    try {
      aoMudar(await acao());
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui salvar.");
    }
  }
  return (
    <section className="secao-do-painel">
      <div className="indicacao-topo">
        <h3>Indicações ({parceiro.indicacoes.length})</h3>
        {editavel && (
          <button type="button" className="botao botao-secundario" onClick={() => definirRegistrando(true)}>
            Registrar indicação
          </button>
        )}
      </div>
      {registrando && (
        <RegistrarIndicacao parceiro={parceiro} aoFechar={() => definirRegistrando(false)}
          aoRegistrar={(p) => {
            definirRegistrando(false);
            aoMudar(p);
          }} />
      )}
      {falha && <div className="estado estado-erro" role="alert"><p className="estado-texto">{falha}</p></div>}
      {parceiro.indicacoes.length === 0 ? (
        <p className="campo-ajuda">Nenhuma indicação ligada ainda.</p>
      ) : (
        <ul className="lista-de-indicacoes">
          {parceiro.indicacoes.map((i) => (
            <ItemDaIndicacao key={i.oportunidade_id} indicacao={i} editavel={editavel} agir={agir} />
          ))}
        </ul>
      )}
      {editavel && <LigarOportunidade parceiro={parceiro} agir={agir} />}
    </section>
  );
}

function ItemDaIndicacao({ indicacao: i, editavel, agir }: {
  indicacao: IndicacaoDoParceiro;
  editavel: boolean;
  agir: (acao: () => Promise<ParceiroDetalhe>) => Promise<void>;
}) {
  return (
    <li>
      <div className="indicacao-topo">
        <strong>{i.grupo ?? i.nome}</strong>
        {i.recusada ? <Etiqueta texto="Recusado" /> : <Etiqueta texto={i.situacao} />}
      </div>
      <span className="indicacao-detalhe">{i.nome}{Number(i.mrr) ? ` · ${dinheiro(i.mrr)}/mês de MRR` : ""}</span>
      <span className="indicacao-detalhe">
        Indicada em {data(i.recebida_em)} · {i.recusada ? `recusada: ${i.recusada}`
          : i.validada_em ? `validada em ${data(i.validada_em)} · vínculo até ${data(i.vinculo_ate)}` : "a validar"}
      </span>
      {editavel && (
        <div className="indicacao-acoes">
          {!i.validada_em && !i.recusada && (
            <button type="button" className="botao botao-secundario"
              onClick={() => agir(() => api.editarIndicacao(i.oportunidade_id, { validada_em: hojeIso() }))}>Validar hoje</button>
          )}
          {!i.recusada && (
            <select className="selecao" aria-label={`Recusar a indicação ${i.nome}`} value=""
              onChange={(e) => e.target.value && agir(() => api.editarIndicacao(i.oportunidade_id, { recusada: e.target.value }))}>
              <option value="">Recusar…</option>
              {MOTIVOS.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          )}
          {i.recusada && (
            <button type="button" className="botao botao-secundario"
              onClick={() => agir(() => api.editarIndicacao(i.oportunidade_id, { recusada: null }))}>Desfazer recusa</button>
          )}
          <button type="button" className="botao botao-secundario"
            onClick={() => agir(() => api.desligarIndicacao(i.oportunidade_id))}>Desligar</button>
        </div>
      )}
    </li>
  );
}

function LigarOportunidade({ parceiro, agir }: {
  parceiro: ParceiroDetalhe;
  agir: (acao: () => Promise<ParceiroDetalhe>) => Promise<void>;
}) {
  const [busca, definirBusca] = useState("");
  const [achadas, definirAchadas] = useState<OportunidadeParaIndicar[] | null>(null);
  const [recebida, definirRecebida] = useState(hojeIso());
  async function buscar() {
    if (busca.trim().length < 2) return;
    definirAchadas(await api.buscarOportunidadesParaIndicar(busca.trim()));
  }
  return (
    <div className="formulario" style={{ marginTop: "var(--e3)" }}>
      <div className="campo-bloco">
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="p-ligar">Ligar uma oportunidade do funil</label>
          <input id="p-ligar" className="entrada" placeholder="Nome da oportunidade ou do grupo" value={busca}
            onChange={(e) => definirBusca(e.target.value)} onKeyDown={(e) => e.key === "Enter" && buscar()} />
        </div>
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="p-recebida">Indicada em</label>
          <CampoDeData id="p-recebida" value={recebida} aoMudar={definirRecebida} />
        </div>
      </div>
      <button type="button" className="botao botao-secundario" onClick={buscar} disabled={busca.trim().length < 2}>Buscar</button>
      {achadas && achadas.length === 0 && (
        <p className="campo-ajuda">
          Nenhuma oportunidade com esse nome. Crie a oportunidade no Funil comercial, com Tipo de canal Parceiros e o nome
          do parceiro em Canal, e ligue aqui.
        </p>
      )}
      {achadas && achadas.length > 0 && (
        <ul className="lista-simples">
          {achadas.map((o) => (
            <li key={o.id}>
              <span>{o.grupo ?? "—"} · {o.nome} · {o.situacao}{o.parceiro ? ` · indicada por ${o.parceiro}` : ""}</span>{" "}
              {o.parceiro !== parceiro.nome && (
                <button type="button" className="botao botao-secundario" disabled={o.parceiro !== null}
                  onClick={() => agir(() => api.ligarIndicacao(parceiro.id, { oportunidade_id: o.id, recebida_em: recebida || null }))
                    .then(() => definirAchadas(null))}>
                  Ligar
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RelatorioDoMes({ parceiroId }: { parceiroId: number }) {
  const [mes, definirMes] = useState(mesPadrao());
  const [aviso, definirAviso] = useState<string | null>(null);
  async function emitir() {
    definirAviso(null);
    try {
      const relatorio = await api.relatorioDoParceiro(parceiroId, mes);
      if (!abrirParaImprimir([relatorio])) definirAviso("Não consegui preparar a impressão do relatório.");
    } catch (e) {
      definirAviso(e instanceof ErroDaApi ? e.message : "Não consegui montar o relatório.");
    }
  }
  return (
    <section className="secao-do-painel">
      <h3>Relatório ao parceiro</h3>
      <div className="indicacao-acoes">
        <input className="entrada" type="month" aria-label="Mês do relatório" value={mes} style={{ width: "auto" }}
          onChange={(e) => definirMes(e.target.value)} />
        <button type="button" className="botao botao-secundario" onClick={emitir} disabled={!mes}>Relatório do mês (PDF)</button>
      </div>
      <p className="campo-ajuda">Abre a página pronta para imprimir: escolha "Salvar como PDF". Quem envia ao parceiro é você.</p>
      {aviso && <p className="campo-ajuda" role="status">{aviso}</p>}
    </section>
  );
}
