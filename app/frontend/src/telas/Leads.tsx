/** A fila de leads — a porta de entrada que a planilha nunca teve.
 *
 * Desde 27/09/2026 mora dentro da tela do SDR de IA. Só o lead qualificado
 * vira oportunidade: o funil continua medindo proposta, não contato.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ConversaDoSdr, LeadResumo, Listas, Pagina } from "../api/tipos";
import { EscolhaDeServico } from "../componentes/CatalogoDeServicos";
import { Etiqueta } from "../componentes/Etiqueta";
import { PainelLateral } from "../componentes/PainelLateral";
import { PrimeiroContato, type RascunhoDoPrimeiroContato } from "../componentes/PrimeiroContato";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { data, dataHora, prazo } from "../formato";
import { usarDados } from "../usarDados";
import { CampoDeData } from "../componentes/CampoDeData";

const CAMPOS_VAZIOS = {
  nome: "",
  empresa_texto: "",
  email: "",
  telefone: "",
  tipo_canal: "",
  canal: "",
  captador: "",
  interesse: "",
  temperatura: "",
  proxima_acao: "",
  proxima_acao_em: "",
  observacao: "",
};

function FormularioDeLead({
  listas,
  aoFechar,
  aoCriar,
}: {
  listas: Listas | null;
  aoFechar: () => void;
  aoCriar: () => void;
}) {
  const [campos, definirCampos] = useState(CAMPOS_VAZIOS);
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);

  const mudar = (campo: string, valor: string) =>
    definirCampos((atual) => ({ ...atual, [campo]: valor }));

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const corpo = Object.fromEntries(
        Object.entries(campos).filter(([, v]) => v !== ""),
      );
      await api.criarLead(corpo);
      aoCriar();
      aoFechar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  const campo = (id: string, rotulo: string, extra?: Record<string, unknown>) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`l-${id}`}>
        {rotulo}
      </label>
      <input
        id={`l-${id}`}
        className="entrada"
        value={campos[id as keyof typeof campos]}
        onChange={(e) => mudar(id, e.target.value)}
        {...extra}
      />
    </div>
  );

  const seletor = (id: string, rotulo: string, opcoes: string[] | undefined, vazio: string) => (
    <div className="campo-bloco">
      <label className="campo-rotulo" htmlFor={`l-${id}`}>
        {rotulo}
      </label>
      <select
        id={`l-${id}`}
        className="selecao"
        value={campos[id as keyof typeof campos]}
        onChange={(e) => mudar(id, e.target.value)}
      >
        <option value="">{vazio}</option>
        {opcoes?.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );

  return (
    <PainelLateral
      titulo="Cadastrar lead"
      subtitulo="Só o nome é obrigatório"
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
            disabled={salvando || campos.nome.trim() === ""}
          >
            {salvando ? "Salvando…" : "Salvar lead"}
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
        {campo("nome", "Nome do contato", { placeholder: "Quem procurou ou foi indicado" })}
        {campo("empresa_texto", "Empresa", { placeholder: "Como a pessoa falou" })}

        <div className="formulario-duplo">
          {campo("email", "E-mail", { type: "email" })}
          {campo("telefone", "Telefone")}
        </div>

        <div className="formulario-duplo">
          {seletor("tipo_canal", "Tipo de canal", listas?.tipos_de_canal, "Não informado")}
          {campo("canal", "Canal", { placeholder: "Nome de quem indicou" })}
        </div>

        <div className="formulario-duplo">
          {seletor("captador", "Captador", listas?.captadores, "Não informado")}
          {seletor("temperatura", "Temperatura", listas?.temperaturas, "Não informada")}
        </div>

        {campo("interesse", "Interesse", { placeholder: "BPO Financeiro, consultoria…" })}

        <div className="formulario-duplo">
          {campo("proxima_acao", "Próxima ação")}
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="l-proxima_acao_em">Quando</label>
            <CampoDeData id="l-proxima_acao_em" value={campos.proxima_acao_em} aoMudar={(v) => mudar("proxima_acao_em", v)} />
          </div>
        </div>
      </div>

      <div className="recado">
        A <strong>origem em duas camadas</strong> — tipo de canal e canal — é o que permite medir
        de onde vêm os negócios que fecham, não só os que entram.
      </div>
    </PainelLateral>
  );
}

function Conversao({
  lead,
  aoFechar,
  aoConverter,
}: {
  lead: LeadResumo;
  aoFechar: () => void;
  aoConverter: () => void;
}) {
  const [nomeDoGrupo, definirNomeDoGrupo] = useState(lead.empresa_texto ?? lead.nome);
  // O serviço de interesse que a qualificação registrou já vem escolhido.
  const [servico, definirServico] = useState(lead.interesse ?? "");
  const [servicoDescricao, definirServicoDescricao] = useState(lead.interesse_descricao ?? "");
  const [servicoTema, definirServicoTema] = useState(lead.interesse_tema ?? "");
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);

  const converter = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await api.converterLead(lead.id, {
        nome_do_grupo: nomeDoGrupo || undefined,
        servico: servico || undefined,
        servico_descricao: servicoDescricao || undefined,
        servico_tema: servicoTema || undefined,
      });
      aoConverter();
      aoFechar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao converter.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <PainelLateral
      titulo="Converter em oportunidade"
      subtitulo={lead.nome}
      aoFechar={aoFechar}
      rodape={
        <>
          <button type="button" className="botao botao-secundario" onClick={aoFechar}>
            Cancelar
          </button>
          <button
            type="button"
            className="botao botao-primario"
            onClick={converter}
            disabled={salvando}
          >
            {salvando ? "Convertendo…" : "Converter em oportunidade"}
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
          <label className="campo-rotulo" htmlFor="c-grupo">
            Grupo econômico
          </label>
          <input
            id="c-grupo"
            className="entrada"
            value={nomeDoGrupo}
            onChange={(e) => definirNomeDoGrupo(e.target.value)}
          />
        </div>
        <EscolhaDeServico
          id="c-servico"
          rotulo="Serviço"
          valor={servico}
          descricao={servicoDescricao}
          tema={servicoTema}
          aoEscolher={(nome, texto, tema) => {
            definirServico(nome);
            definirServicoDescricao(texto);
            definirServicoTema(tema);
          }}
        />
      </div>
      <div className="recado">
        A oportunidade nasce em <strong>Enviar proposta</strong> e carrega a origem do lead —
        tipo de canal, canal e captador viajam junto.
      </div>
    </PainelLateral>
  );
}

function EdicaoDeLead({
  lead,
  listas,
  aoFechar,
  aoSalvar,
}: {
  lead: LeadResumo;
  listas: Listas | null;
  aoFechar: () => void;
  aoSalvar: () => void;
}) {
  const convertido = lead.convertido_em_id !== null;
  const [rascunho, definirRascunho] = useState({
    situacao: lead.situacao,
    temperatura: lead.temperatura ?? "",
    interesse: lead.interesse ?? "",
    interesse_descricao: lead.interesse_descricao ?? "",
    interesse_tema: lead.interesse_tema ?? "",
    proxima_acao: lead.proxima_acao ?? "",
    proxima_acao_em: lead.proxima_acao_em ?? "",
    observacao: lead.observacao ?? "",
    cnpj: lead.cnpj ?? "",
    porte_estimado: lead.porte_estimado ?? "",
    motivo_descarte: lead.motivo_descarte ?? "",
    reuniao_marcada_para: paraCampoLocal(lead.reuniao_marcada_para),
  });
  const [naoContatar, definirNaoContatar] = useState(Boolean(lead.nao_contatar));
  const contatoSugerido = !lead.primeiro_contato_em && Boolean(lead.primeiro_contato_pelo_sdr);
  const contatoInicial: RascunhoDoPrimeiroContato = {
    primeiro_contato_em: paraCampoLocal(lead.primeiro_contato_em ?? lead.primeiro_contato_pelo_sdr),
    aderencia: lead.aderencia ?? "",
    aderencia_sobre: lead.aderencia_sobre ?? [],
    aderencia_esperava: lead.aderencia_esperava ?? "",
  };
  const [contato, definirContato] = useState(contatoInicial);
  const qualificando = !convertido && rascunho.situacao === "Qualificado";
  const descartando = !convertido && rascunho.situacao === "Descartado";
  // As mesmas exigências da API, ditas antes de salvar: qualificar pede o
  // porte, descartar pede o motivo.
  const falta = qualificando && !rascunho.porte_estimado
    ? "Para qualificar, escolha o porte estimado."
    : descartando && !rascunho.motivo_descarte
      ? "Para descartar, escolha o motivo."
      : null;
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
      mudancas.reuniao_marcada_para = rascunho.reuniao_marcada_para
        ? new Date(rascunho.reuniao_marcada_para).toISOString()
        : null;
      // O motivo só vai junto quando o lead fica descartado: a API recusa
      // motivo em lead aberto.
      if (!descartando) delete mudancas.motivo_descarte;
      if (naoContatar !== Boolean(lead.nao_contatar)) mudancas.nao_contatar = naoContatar;
      // Primeiro contato e aderência: só vai o que mudou (a sugestão do SDR, ao salvar, fica gravada).
      if (contato.primeiro_contato_em !== paraCampoLocal(lead.primeiro_contato_em)) {
        mudancas.primeiro_contato_em = contato.primeiro_contato_em ? new Date(contato.primeiro_contato_em).toISOString() : null;
      }
      if (contato.aderencia !== (lead.aderencia ?? "")) mudancas.aderencia = contato.aderencia || null;
      const comDetalhe = contato.aderencia === "Em parte" || contato.aderencia === "Não bate";
      if (comDetalhe) {
        mudancas.aderencia_sobre = contato.aderencia_sobre;
        mudancas.aderencia_esperava = contato.aderencia_esperava.trim() || null;
      }
      // Lead convertido tem a situação decidida pela oportunidade: não a enviamos.
      if (convertido) delete mudancas.situacao;
      await api.editarLead(lead.id, mudancas);
      aoSalvar();
      aoFechar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  // "Convertido" fica de fora: só a conversão leva a esse estado, porque ele
  // pressupõe a oportunidade que o sustenta.
  const situacoes = listas?.situacoes_de_lead.filter((s) => s !== "Convertido") ?? [];

  return (
    <PainelLateral
      titulo={lead.nome}
      subtitulo={lead.empresa_texto ?? undefined}
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
            disabled={salvando || falta !== null}
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
          <label className="campo-rotulo" htmlFor="e-situacao">
            Situação
          </label>
          {convertido ? (
            <div>
              <Etiqueta texto={lead.situacao} />
              <p className="campo-ajuda">
                Este lead já virou oportunidade — a situação passou a ser a dela.
              </p>
            </div>
          ) : (
            <select
              id="e-situacao"
              className="selecao"
              value={rascunho.situacao}
              onChange={(e) => mudar("situacao", e.target.value)}
            >
              {situacoes.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          )}
        </div>

        <PrimeiroContato lead={lead} listas={listas} rascunho={contato} aoMudar={definirContato} sugerido={contatoSugerido} />

        {qualificando && (
          <div className="formulario-duplo">
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="e-porte">
                Porte estimado
              </label>
              <select
                id="e-porte"
                className="selecao"
                value={rascunho.porte_estimado}
                onChange={(e) => mudar("porte_estimado", e.target.value)}
              >
                <option value="">Escolha</option>
                {listas?.portes.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="e-reuniao">
                Reunião marcada para
              </label>
              <input
                id="e-reuniao"
                type="datetime-local"
                className="entrada"
                value={rascunho.reuniao_marcada_para}
                onChange={(e) => mudar("reuniao_marcada_para", e.target.value)}
              />
            </div>
          </div>
        )}

        {descartando && (
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="e-motivo">
              Motivo do descarte
            </label>
            <select
              id="e-motivo"
              className="selecao"
              value={rascunho.motivo_descarte}
              onChange={(e) => mudar("motivo_descarte", e.target.value)}
            >
              <option value="">Escolha</option>
              {listas?.motivos_de_descarte?.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        )}

        {falta && <p className="campo-ajuda">{falta}</p>}

        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="e-cnpj">
            CNPJ
          </label>
          <input
            id="e-cnpj"
            className="entrada"
            value={rascunho.cnpj}
            onChange={(e) => mudar("cnpj", e.target.value)}
          />
        </div>

        <label className="campo-marcar">
          <input
            type="checkbox"
            checked={naoContatar}
            onChange={(e) => definirNaoContatar(e.target.checked)}
          />{" "}
          Pediu para não ser contatado. Nenhuma mensagem da IA ou da equipe sai para este lead.
        </label>

        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="e-temperatura">
              Temperatura
            </label>
            <select
              id="e-temperatura"
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
          <EscolhaDeServico
            id="e-interesse"
            rotulo="Serviço de interesse"
            valor={rascunho.interesse}
            descricao={rascunho.interesse_descricao}
            tema={rascunho.interesse_tema}
            aoEscolher={(nome, texto, tema) => {
              mudar("interesse", nome);
              mudar("interesse_descricao", texto);
              mudar("interesse_tema", tema);
            }}
          />
        </div>

        <div className="formulario-duplo">
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="e-acao">
              Próxima ação
            </label>
            <input
              id="e-acao"
              className="entrada"
              value={rascunho.proxima_acao}
              onChange={(e) => mudar("proxima_acao", e.target.value)}
            />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="e-acao-em">
              Quando
            </label>
            <CampoDeData
              id="e-acao-em"
              value={rascunho.proxima_acao_em}
              aoMudar={(v) => mudar("proxima_acao_em", v)}
            />
          </div>
        </div>

        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="e-obs">
            Observação
          </label>
          <textarea
            id="e-obs"
            className="entrada"
            rows={3}
            value={rascunho.observacao}
            onChange={(e) => mudar("observacao", e.target.value)}
          />
        </div>
      </div>

      <ConversasComAIA leadId={lead.id} />
    </PainelLateral>
  );
}

/** O `datetime-local` quer a hora local sem fuso; a API guarda em UTC. */
function paraCampoLocal(iso: string | null | undefined): string {
  if (!iso) return "";
  const momento = new Date(iso);
  const local = new Date(momento.getTime() - momento.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

/** O que a IA e o lead disseram. Só leitura: quem registra é a integração do canal. */
function ConversasComAIA({ leadId }: { leadId: number }) {
  const { dados, carregando, erro, recarregar } = usarDados<ConversaDoSdr[]>(
    () => api.conversasDoLead(leadId),
    [leadId],
  );

  return (
    <section className="sdr-conversas" aria-labelledby="t-conversas">
      <h3 className="bloco-titulo" id="t-conversas">
        Conversas com a IA
      </h3>
      {carregando && <Carregando rotulo="Carregando as conversas" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {!carregando && !erro && dados?.length === 0 && (
        <p className="campo-ajuda">
          Nenhuma conversa registrada. Elas aparecem aqui quando a integração do WhatsApp ou do
          e-mail estiver ligada.
        </p>
      )}
      {!carregando &&
        !erro &&
        dados?.map((conversa) => (
          <div key={conversa.id} className="sdr-conversa">
            <p className="sdr-conversa-topo">
              {conversa.canal} · começou {dataHora(conversa.iniciada_em)}{" "}
              {conversa.desfecho ? (
                <Etiqueta texto={conversa.desfecho} tipo="neutra" />
              ) : (
                <span className="etiqueta etiqueta-andamento">Em andamento</span>
              )}
            </p>
            <ol className="sdr-mensagens">
              {conversa.mensagens.map((m) => (
                <li
                  key={m.id}
                  className={`sdr-mensagem sdr-mensagem-${m.autor === "Lead" ? "lead" : "criterio"}`}
                >
                  <span className="sdr-mensagem-autor">
                    {m.autor} · {dataHora(m.enviada_em)}
                    {m.fallback && " · não entendeu"}
                  </span>
                  {m.texto}
                </li>
              ))}
            </ol>
          </div>
        ))}
    </section>
  );
}

const ORIGENS = [
  { valor: "", rotulo: "Todas as origens" },
  { valor: "Tráfego pago", rotulo: "Tráfego pago" },
  { valor: "Prospecção ativa", rotulo: "Leads frios (prospecção ativa)" },
];

export function Leads({ listas }: { listas: Listas | null }) {
  const [apenasAbertos, definirApenasAbertos] = useState(true);
  const [busca, definirBusca] = useState("");
  const [origem, definirOrigem] = useState("");
  const [cadastrando, definirCadastrando] = useState(false);
  const [convertendo, definirConvertendo] = useState<LeadResumo | null>(null);
  const [editando, definirEditando] = useState<LeadResumo | null>(null);

  const { dados, carregando, erro, recarregar } = usarDados<Pagina<LeadResumo>>(
    () =>
      api.leads({
        apenas_abertos: apenasAbertos,
        busca: busca || undefined,
        tipo_canal: origem || undefined,
      }),
    [apenasAbertos, busca, origem],
  );

  // Uma ação primária por tela — regra 2 do PAD-002. Com a fila vazia, a ação
  // mora dentro do estado vazio, junto da explicação; o botão da barra sairia
  // repetido e competiria com ela.
  const filaVazia = !carregando && !erro && dados?.total === 0;

  return (
    <>
      <div className="filtros">
        <div className="campo">
          <label className="campo-rotulo" htmlFor="l-busca">
            Buscar
          </label>
          <input
            id="l-busca"
            className="entrada entrada-busca"
            placeholder="Nome ou empresa"
            value={busca}
            onChange={(e) => definirBusca(e.target.value)}
          />
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="l-abertos">
            Mostrar
          </label>
          <select
            id="l-abertos"
            className="selecao"
            value={apenasAbertos ? "abertos" : "todos"}
            onChange={(e) => definirApenasAbertos(e.target.value === "abertos")}
          >
            <option value="abertos">Só os abertos</option>
            <option value="todos">Todos</option>
          </select>
        </div>
        <div className="campo">
          <label className="campo-rotulo" htmlFor="l-origem">
            Origem
          </label>
          <select
            id="l-origem"
            className="selecao"
            value={origem}
            onChange={(e) => definirOrigem(e.target.value)}
          >
            {ORIGENS.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.rotulo}
              </option>
            ))}
          </select>
        </div>
        {!filaVazia && (
          <div style={{ marginLeft: "auto" }}>
            <button
              type="button"
              className="botao botao-primario"
              onClick={() => definirCadastrando(true)}
            >
              Cadastrar lead
            </button>
          </div>
        )}
      </div>

      {carregando && <Carregando rotulo="Carregando os leads" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}

      {filaVazia && (
        <VazioSemDados
          titulo="Nenhum lead na fila"
          explicacao="O lead é a porta de entrada do funil. A planilha de 2026 começava direto na proposta enviada, então não há histórico para carregar aqui."
          acao={
            <button
              type="button"
              className="botao botao-primario"
              onClick={() => definirCadastrando(true)}
            >
              Cadastrar o primeiro lead
            </button>
          }
        />
      )}

      {!carregando && !erro && (dados?.total ?? 0) > 0 && (
        <table className="tabela tabela-em-cartoes">
          <thead>
            <tr>
              <th scope="col">Contato</th>
              <th scope="col">Empresa</th>
              <th scope="col">Situação</th>
              <th scope="col">Qualificação</th>
              <th scope="col">Origem</th>
              <th scope="col">Captador</th>
              <th scope="col">Próxima ação</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {dados!.itens.map((lead) => {
              const quando = prazo(lead.proxima_acao_em);
              return (
                <tr key={lead.id}>
                  <td className="cartao-titulo">{lead.nome}</td>
                  <td data-rotulo="Empresa">{lead.empresa_texto ?? "—"}</td>
                  <td data-rotulo="Situação">
                    <Etiqueta texto={lead.situacao} />{" "}
                    {lead.nao_contatar && (
                      <span className="etiqueta etiqueta-perda">Não contatar</span>
                    )}
                  </td>
                  <td className="sdr-qualificacao" data-rotulo="Qualificação">
                    {lead.porte_estimado ? `Porte ${lead.porte_estimado}` : ""}
                    {lead.situacao === "Descartado" && lead.motivo_descarte}
                    {lead.reuniao_marcada_para && (
                      <span> · reunião {dataHora(lead.reuniao_marcada_para)}</span>
                    )}
                  </td>
                  <td data-rotulo="Origem">
                    <Etiqueta texto={lead.tipo_canal} tipo="neutra" />{" "}
                    {lead.canal && (
                      <span style={{ fontSize: 12, color: "var(--texto-medio)" }}>
                        {lead.canal}
                      </span>
                    )}
                  </td>
                  <td data-rotulo="Captador">{lead.captador ?? "—"}</td>
                  <td data-rotulo="Próxima ação">
                    {lead.proxima_acao ?? "—"}
                    {quando && (
                      <span
                        style={{
                          fontSize: 12,
                          color: quando.atrasado ? "var(--perda)" : "var(--texto-medio)",
                        }}
                      >
                        {" "}
                        · {quando.texto} ({data(lead.proxima_acao_em)})
                      </span>
                    )}
                  </td>
                  <td className="cartao-acoes" style={{ whiteSpace: "nowrap" }}>
                    <button
                      type="button"
                      className="botao botao-secundario"
                      onClick={() => definirEditando(lead)}
                    >
                      Abrir
                    </button>{" "}
                    {lead.convertido_em_id === null ? (
                      lead.situacao === "Qualificado" ? (
                        <button
                          type="button"
                          className="botao botao-secundario"
                          onClick={() => definirConvertendo(lead)}
                        >
                          Converter
                        </button>
                      ) : (
                        <span style={{ fontSize: 12, color: "var(--texto-medio)" }}>
                          Qualifique para converter
                        </span>
                      )
                    ) : (
                      <span style={{ fontSize: 12, color: "var(--texto-medio)" }}>
                        Virou oportunidade
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {cadastrando && (
        <FormularioDeLead
          listas={listas}
          aoFechar={() => definirCadastrando(false)}
          aoCriar={recarregar}
        />
      )}
      {editando && (
        <EdicaoDeLead
          lead={editando}
          listas={listas}
          aoFechar={() => definirEditando(null)}
          aoSalvar={recarregar}
        />
      )}
      {convertendo && (
        <Conversao
          lead={convertendo}
          aoFechar={() => definirConvertendo(null)}
          aoConverter={recarregar}
        />
      )}
    </>
  );
}
