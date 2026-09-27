/** O pop-up do catálogo de serviços — amostra aprovada por Eduardo em 27/09/2026.
 *
 * Aparece na Nova oportunidade, na conversão do lead e na qualificação do lead.
 * À direita, o roteiro do serviço: o que perguntar, quando fica fora do perfil e
 * para quem a IA passa a conversa. **Sem preço**: a IA não informa preço.
 *
 * O catálogo vem de `GET /api/servicos` (a fonte é `crm.domain.servicos`). A linha
 * C1/C2 não é escolhida aqui: o servidor a tira do serviço.
 */

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api } from "../api/cliente";
import type { ServicoDoCatalogo } from "../api/tipos";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";

const DESCRICAO_DA_LINHA: Record<string, string> = { C1: "Recorrente", C2: "Não recorrente" };

function semAcento(texto: string): string {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLocaleLowerCase("pt-BR");
}

export function EtiquetaDaLinha({ linha }: { linha: string }) {
  return (
    <span className={`etiqueta etiqueta-${linha === "C1" ? "andamento" : "ganho"}`}>
      {linha} · {DESCRICAO_DA_LINHA[linha] ?? linha}
    </span>
  );
}

/** O botão do formulário: mostra o serviço escolhido e abre o catálogo. */
export function EscolhaDeServico({
  id,
  rotulo,
  valor,
  aoEscolher,
}: {
  id: string;
  rotulo: string;
  valor: string;
  aoEscolher: (nome: string) => void;
}) {
  const [aberto, definirAberto] = useState(false);
  const { dados } = usarDados<ServicoDoCatalogo[]>(() => api.servicos(), []);
  const doCatalogo = dados?.find((s) => s.nome === valor);
  const botao = useRef<HTMLButtonElement>(null);

  const fechar = () => {
    definirAberto(false);
    botao.current?.focus();
  };

  return (
    <div className="campo-bloco">
      <span className="campo-rotulo" id={`${id}-rotulo`}>
        {rotulo}
      </span>
      <button
        ref={botao}
        id={id}
        type="button"
        className="escolha-servico"
        aria-labelledby={`${id}-rotulo ${id}-valor`}
        aria-haspopup="dialog"
        onClick={() => definirAberto(true)}
      >
        <span id={`${id}-valor`} className={valor ? undefined : "escolha-servico-vazia"}>
          {valor || "Escolha no catálogo"}{" "}
          {doCatalogo && <EtiquetaDaLinha linha={doCatalogo.linha} />}
          {valor && dados && !doCatalogo && (
            <span className="etiqueta etiqueta-espera">fora do catálogo</span>
          )}
        </span>
        <span className="escolha-servico-seta">{valor ? "Trocar ▸" : "Abrir catálogo ▸"}</span>
      </button>
      {aberto && (
        <CatalogoDeServicos
          inicial={valor}
          aoFechar={fechar}
          aoEscolher={(nome) => {
            aoEscolher(nome);
            fechar();
          }}
        />
      )}
    </div>
  );
}

export function CatalogoDeServicos({
  inicial,
  aoFechar,
  aoEscolher,
}: {
  inicial?: string;
  aoFechar: () => void;
  aoEscolher: (nome: string) => void;
}) {
  const { dados, carregando, erro, recarregar } = usarDados<ServicoDoCatalogo[]>(
    () => api.servicos(),
    [],
  );
  const [busca, definirBusca] = useState("");
  const [selecionado, definirSelecionado] = useState<string | null>(inicial || null);
  const campoDeBusca = useRef<HTMLInputElement>(null);

  useEffect(() => {
    campoDeBusca.current?.focus();
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && aoFechar();
    document.addEventListener("keydown", tecla);
    return () => document.removeEventListener("keydown", tecla);
  }, [aoFechar]);

  const termo = semAcento(busca.trim());
  const achados = (dados ?? []).filter((s) =>
    semAcento(`${s.nome} ${s.nome_por_extenso ?? ""} ${s.nomes_antigos.join(" ")}`).includes(termo),
  );
  const atual = dados?.find((s) => s.nome === selecionado) ?? achados[0] ?? null;

  return createPortal(
    <div className="catalogo-cortina" onClick={(e) => e.target === e.currentTarget && aoFechar()}>
      <div className="catalogo" role="dialog" aria-modal="true" aria-labelledby="catalogo-titulo">
        <div className="catalogo-cab">
          <div>
            <h2 id="catalogo-titulo">Catálogo de serviços</h2>
            <p>Escolha o serviço. À direita, o roteiro que a equipe e o SDR de IA seguem para qualificar.</p>
          </div>
          <button type="button" className="botao-icone" aria-label="Fechar o catálogo" onClick={aoFechar}>
            ×
          </button>
        </div>

        <div className="catalogo-corpo">
          <div className="catalogo-lista">
            <label className="campo-rotulo" htmlFor="catalogo-busca">
              Buscar serviço
            </label>
            <input
              ref={campoDeBusca}
              id="catalogo-busca"
              className="entrada"
              placeholder="BPO, folha, auditoria…"
              value={busca}
              onChange={(e) => definirBusca(e.target.value)}
            />
            {carregando && <Carregando rotulo="Carregando o catálogo" />}
            {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
            {!carregando && !erro && dados && achados.length === 0 && (
              <div className="estado">
                <p className="estado-texto">Nenhum serviço com esse nome.</p>
                <button type="button" className="botao botao-secundario" onClick={() => definirBusca("")}>
                  Limpar a busca
                </button>
              </div>
            )}
            {!carregando &&
              !erro &&
              ["C1", "C2"].map((linha) => {
                const itens = achados.filter((s) => s.linha === linha);
                if (!itens.length) return null;
                return (
                  <div key={linha} className="catalogo-grupo">
                    <h3>
                      <EtiquetaDaLinha linha={linha} />
                    </h3>
                    <ul role="listbox" aria-label={`${linha} · ${DESCRICAO_DA_LINHA[linha]}`}>
                      {itens.map((s) => (
                        <li key={s.nome}>
                          <button
                            type="button"
                            role="option"
                            className="catalogo-item"
                            aria-selected={atual?.nome === s.nome}
                            onClick={() => definirSelecionado(s.nome)}
                          >
                            {s.nome}
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
          </div>

          <div className="catalogo-detalhe" aria-live="polite">
            {atual && <Roteiro servico={atual} />}
          </div>
        </div>

        <div className="catalogo-rodape">
          <p>C1 é recorrente. C2 não é recorrente. A linha sai do serviço escolhido.</p>
          <div>
            <button type="button" className="botao botao-secundario" onClick={aoFechar}>
              Cancelar
            </button>
            <button
              type="button"
              className="botao botao-primario"
              disabled={!atual}
              onClick={() => atual && aoEscolher(atual.nome)}
            >
              Usar este serviço
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function Roteiro({ servico: s }: { servico: ServicoDoCatalogo }) {
  return (
    <>
      <div className="catalogo-titulo-servico">
        <h3>{s.nome}</h3>
        <EtiquetaDaLinha linha={s.linha} />
        {s.nome_por_extenso && <span className="etiqueta etiqueta-neutra">{s.nome_por_extenso}</span>}
      </div>
      <p className="catalogo-para-quem">
        {s.para_quem}
        {s.rascunho && <span className="catalogo-rascunho">texto em rascunho</span>}
      </p>
      <div className="catalogo-bloco">
        <h4>O que perguntar para qualificar</h4>
        <ul>
          {s.perguntas.map((p) => (
            <li key={p.texto}>
              {p.texto}
              {p.direcionador && <span className="catalogo-regua">régua de porte</span>}
            </li>
          ))}
        </ul>
      </div>
      <div className="catalogo-duas">
        <div className="catalogo-bloco">
          <h4>Fica fora do perfil se</h4>
          {s.fora_do_perfil.length ? (
            <ul>
              {s.fora_do_perfil.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          ) : (
            <p className="campo-ajuda">A escrever.</p>
          )}
        </div>
        <div className="catalogo-bloco">
          <h4>Se a IA não resolver, passa para</h4>
          <p>{s.transbordo}</p>
        </div>
      </div>
      <div className="recado">
        <strong>Sem preço.</strong> Se o lead perguntar o valor, a IA explica que o preço sai da
        volumetria e passa a conversa para a equipe.
      </div>
    </>
  );
}
