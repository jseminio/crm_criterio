/** A fila de leads — a porta de entrada que a planilha nunca teve. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { LeadResumo, Listas, Pagina } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { PainelLateral } from "../componentes/PainelLateral";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { data, prazo } from "../formato";
import { usarDados } from "../usarDados";

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
          {campo("proxima_acao_em", "Quando", { type: "date" })}
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
  const [servico, definirServico] = useState("");
  const [erro, definirErro] = useState<string | null>(null);
  const [salvando, definirSalvando] = useState(false);

  const converter = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await api.converterLead(lead.id, {
        nome_do_grupo: nomeDoGrupo || undefined,
        servico: servico || undefined,
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
        <div className="campo-bloco">
          <label className="campo-rotulo" htmlFor="c-servico">
            Serviço
          </label>
          <input
            id="c-servico"
            className="entrada"
            value={servico}
            onChange={(e) => definirServico(e.target.value)}
            placeholder="BPO Contábil, Consultoria…"
          />
        </div>
      </div>
      <div className="recado">
        A oportunidade nasce em <strong>Enviar proposta</strong> e carrega a origem do lead —
        tipo de canal, canal e captador viajam junto.
      </div>
    </PainelLateral>
  );
}

export function Leads({ listas }: { listas: Listas | null }) {
  const [apenasAbertos, definirApenasAbertos] = useState(true);
  const [busca, definirBusca] = useState("");
  const [cadastrando, definirCadastrando] = useState(false);
  const [convertendo, definirConvertendo] = useState<LeadResumo | null>(null);

  const { dados, carregando, erro, recarregar } = usarDados<Pagina<LeadResumo>>(
    () => api.leads({ apenas_abertos: apenasAbertos, busca: busca || undefined }),
    [apenasAbertos, busca],
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
        <table className="tabela">
          <thead>
            <tr>
              <th scope="col">Contato</th>
              <th scope="col">Empresa</th>
              <th scope="col">Situação</th>
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
                  <td>{lead.nome}</td>
                  <td>{lead.empresa_texto ?? "—"}</td>
                  <td>
                    <Etiqueta texto={lead.situacao} />
                  </td>
                  <td>
                    <Etiqueta texto={lead.tipo_canal} tipo="neutra" />{" "}
                    {lead.canal && (
                      <span style={{ fontSize: 12, color: "var(--texto-medio)" }}>
                        {lead.canal}
                      </span>
                    )}
                  </td>
                  <td>{lead.captador ?? "—"}</td>
                  <td>
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
                  <td>
                    {lead.convertido_em_id === null ? (
                      <button
                        type="button"
                        className="botao botao-secundario"
                        onClick={() => definirConvertendo(lead)}
                      >
                        Converter
                      </button>
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
