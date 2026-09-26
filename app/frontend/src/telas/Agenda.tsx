/** A agenda de follow-up — Etapa 2 (25/09/2026).
 *
 * O que pede uma ação agora, por urgência. O balde que mais importa hoje é
 * **"Sem próxima ação"**: das propostas em aberto, nenhuma tinha próxima ação
 * definida (cobertura do processo em 0%), e é definindo-a que esse número sobe.
 * Por isso a linha permite **escrever a próxima ação ali mesmo**, sem abrir o painel.
 *
 * Lembrete aqui é tela, não notificação: a API do WhatsApp continua pendente.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { Agenda as DadosDaAgenda, BaldeDaAgenda, ItemDaAgenda, Listas } from "../api/tipos";
import { Etiqueta } from "../componentes/Etiqueta";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { data, dinheiroCurto } from "../formato";
import { usarDados } from "../usarDados";
import { DetalheDaOportunidade } from "./DetalheDaOportunidade";

const BALDES: { chave: BaldeDaAgenda; rotulo: string; explicacao: string }[] = [
  { chave: "atrasada", rotulo: "Atrasadas", explicacao: "A data da próxima ação já passou." },
  { chave: "hoje", rotulo: "Hoje", explicacao: "Ação marcada para hoje." },
  { chave: "proximos_7_dias", rotulo: "Próximos 7 dias", explicacao: "Ação marcada para esta semana." },
  { chave: "depois", rotulo: "Depois", explicacao: "Ação marcada para além de 7 dias." },
  { chave: "sem_data", rotulo: "Sem data", explicacao: "Tem a ação escrita, mas ninguém disse quando." },
  {
    chave: "sem_acao",
    rotulo: "Sem próxima ação",
    explicacao:
      "Em aberto e sem próxima ação. Não é falha de ninguém: é por aqui que a cobertura do processo sobe.",
  },
];

function Linha({
  item,
  aoAbrir,
  aoSalvar,
}: {
  item: ItemDaAgenda;
  aoAbrir: () => void;
  aoSalvar: () => void;
}) {
  const [acao, definirAcao] = useState(item.proxima_acao ?? "");
  const [quando, definirQuando] = useState(item.proxima_acao_em ?? "");
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const podeSalvar = item.tipo === "oportunidade" && acao.trim() !== "" && !salvando;

  const salvar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      await api.editarOportunidade(item.id, {
        proxima_acao: acao.trim(),
        proxima_acao_em: quando || null,
      });
      aoSalvar();
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao salvar.");
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <li className="agenda-linha">
      <div className="agenda-quem">
        <button type="button" className="link-de-tabela" onClick={aoAbrir}>
          {item.titulo}
        </button>
        {item.subtitulo && <span className="numero-nota">{item.subtitulo}</span>}
        <span className="agenda-etiquetas">
          <Etiqueta texto={item.tipo === "lead" ? "Lead" : item.tipo === "contrato" ? "Contrato" : item.situacao} tipo="neutra" />
          <Etiqueta texto={item.temperatura} tipo="temperatura" />
          {item.captador && <Etiqueta texto={item.captador} tipo="neutra" />}
        </span>
        <span className="numero-nota">
          {item.valor_anual ? `${dinheiroCurto(item.valor_anual)} ao ano` : "sem valor anual"}
          {item.dias_desde_o_envio !== null && ` · enviada há ${item.dias_desde_o_envio} dias`}
          {item.dias_de_atraso > 0 && ` · ${item.dias_de_atraso} dia${item.dias_de_atraso === 1 ? "" : "s"} de atraso`}
        </span>
      </div>

      {item.tipo === "oportunidade" ? (
        <div className="agenda-acao">
          <input
            className="entrada"
            aria-label={`Próxima ação de ${item.titulo}`}
            placeholder="Ligar para o decisor…"
            maxLength={200}
            value={acao}
            onChange={(e) => definirAcao(e.target.value)}
          />
          <input
            className="entrada"
            type="date"
            aria-label={`Quando, para ${item.titulo}`}
            value={quando}
            onChange={(e) => definirQuando(e.target.value)}
          />
          <button type="button" className="botao botao-primario" disabled={!podeSalvar} onClick={salvar}>
            {salvando ? "Salvando…" : "Salvar"}
          </button>
          {erro && <p role="alert" className="estado-texto">{erro}</p>}
        </div>
      ) : (
        <div className="agenda-acao">
          <span className="numero-nota">
            {item.proxima_acao
              ? `${item.proxima_acao} · ${data(item.proxima_acao_em)}`
              : "Defina a próxima ação na tela Leads."}
            {item.tipo === "contrato" && " · abra em Contratos para renovar."}
          </span>
        </div>
      )}
    </li>
  );
}

export function Agenda({
  listas,
  aoAbrirLeads,
  aoAbrirContratos = () => {},
}: {
  listas: Listas | null;
  aoAbrirLeads: () => void;
  aoAbrirContratos?: () => void;
}) {
  const [balde, definirBalde] = useState<BaldeDaAgenda | null>(null);
  const [aberta, definirAberta] = useState<number | null>(null);
  const { dados, carregando, erro, recarregar } = usarDados<DadosDaAgenda>(() => api.agenda(), []);

  if (carregando && !dados) return <Carregando rotulo="Montando a agenda" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;

  // Sem escolha, abre no primeiro balde que tem gente: o que mais urge.
  const atual = balde ?? BALDES.find((b) => dados.contagens[b.chave] > 0)?.chave ?? "sem_acao";
  const doBalde = dados.itens.filter((i) => i.balde === atual);
  const info = BALDES.find((b) => b.chave === atual)!;

  return (
    <>
      <div className="abas" role="tablist" aria-label="Baldes da agenda">
        {BALDES.map((b) => (
          <button
            key={b.chave}
            type="button"
            role="tab"
            className="aba"
            aria-selected={atual === b.chave}
            onClick={() => definirBalde(b.chave)}
          >
            {b.rotulo}
            <span className="aba-contagem">{dados.contagens[b.chave]}</span>
          </button>
        ))}
      </div>

      <div className="recado">{info.explicacao}</div>

      {doBalde.length === 0 ? (
        <VazioSemDados titulo={`Nada em “${info.rotulo}”`} explicacao="Nenhuma oportunidade ou lead neste balde agora." />
      ) : (
        <ul className="agenda">
          {doBalde.map((item) => (
            <Linha
              key={`${item.tipo}-${item.id}`}
              item={item}
              aoAbrir={() =>
                item.tipo === "lead" ? aoAbrirLeads() : item.tipo === "contrato" ? aoAbrirContratos() : definirAberta(item.id)
              }
              aoSalvar={recarregar}
            />
          ))}
        </ul>
      )}

      {aberta !== null && (
        <DetalheDaOportunidade
          id={aberta}
          listas={listas}
          aoFechar={() => definirAberta(null)}
          aoSalvar={recarregar}
        />
      )}
    </>
  );
}
