/** A faixa de números do funil.
 *
 * Mostra só o que os dados de 2026 sustentam sem definição pendente. Os
 * indicadores que ainda não podem ser calculados aparecem como cartões de
 * pendência, com o motivo e o que falta — nunca como zero e nunca como traço.
 * Zero pareceria medição; traço esconderia que há trabalho a fazer.
 *
 * O rótulo do mensal aceito não diz "MRR" de propósito: o MRR oficial é a
 * receita contratada da carteira inteira, e este número é outra coisa.
 */

import { useId } from "react";
import { api } from "../api/cliente";
import type { Indicadores, TaxaDeConversao } from "../api/tipos";
import { Carregando, Erro } from "./estados";
import { paraConsulta, type EstadoDosFiltros } from "./Filtros";
import { dias, dinheiro, dinheiroCurto, percentual } from "../formato";
import { usarDados } from "../usarDados";

/** O tom da conversão contra a meta e o alerta de Configurações › Metas (padrão: 50% e 30%).
 *
 * Mesma regra do PAD-002 que `Etiqueta` aplica às situações: a palavra vem
 * sempre junto da cor, nunca só a cor sozinha.
 */
function tomDaConversao(tx: TaxaDeConversao): Tom {
  if (!tx.calculavel) return "azul";
  return tx.atingiu_a_meta ? "verde" : tx.abaixo_do_alerta ? "vermelho" : "ambar";
}

function EtiquetaDeConversao({ tx }: { tx: TaxaDeConversao }) {
  if (!tx.calculavel) return null;
  const [texto, tom] = tx.atingiu_a_meta
    ? ["Na meta", "ganho"]
    : tx.abaixo_do_alerta
      ? ["Abaixo do alerta", "perda"]
      : ["Entre o alerta e a meta", "espera"];
  return <span className={`etiqueta etiqueta-${tom}`}>{texto}</span>;
}

type Tom = "azul" | "verde" | "ambar" | "vermelho" | "dourado" | "violeta" | "rosa" | "marinho";

/** Um indicador compacto: rótulo, número e uma linha de apoio. O que explica o número (definição, ressalvas)
 * fica numa janela que abre ao passar o mouse ou ao focar com o teclado (Tab), ao redor do indicador. */
function Cartao({
  rotulo,
  destaque,
  apoio,
  etiqueta,
  tom,
  children,
  pendente = false,
}: {
  rotulo: string;
  destaque?: string;
  apoio?: string;
  etiqueta?: React.ReactNode;
  tom: Tom;
  children?: React.ReactNode;
  pendente?: boolean;
}) {
  const id = useId();
  return (
    <section className={`numero ind ind-${tom} ${pendente ? "numero-pendente" : ""}`} tabIndex={0} aria-describedby={id}>
      <h3 className="numero-rotulo ind-rotulo">{rotulo}</h3>
      {destaque ? <p className="numero-valor ind-valor">{destaque}</p> : <p className="ind-valor ind-valor-pendente">Não calculável</p>}
      {apoio && <p className="ind-apoio">{apoio}</p>}
      {etiqueta}
      <div className="numero-detalhe ind-janela" role="tooltip" id={id}>
        {children}
      </div>
    </section>
  );
}

export function Numeros({ filtros }: { filtros: EstadoDosFiltros }) {
  const { dados, carregando, erro, recarregar } = usarDados<Indicadores>(
    () => api.indicadores(paraConsulta(filtros)),
    [
      filtros.busca,
      filtros.captador,
      filtros.tipo_canal,
      filtros.temperatura,
      filtros.servico,
      filtros.dataTipo,
      filtros.periodo,
      filtros.dataDe,
      filtros.dataAte,
    ],
  );

  if (carregando && !dados) return <Carregando rotulo="Calculando os números" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;

  const {
    em_aberto: aberto,
    aceitas,
    ciclo_medio: ciclo,
    cobertura,
    dependencia_de_canal: dependencia,
    ticket_recorrente: ticket,
  } = dados;

  return (
    <div className="numeros" aria-label="Números do funil">
      <Cartao
        rotulo="Em aberto"
        tom="azul"
        destaque={`${aberto.quantas} proposta${aberto.quantas === 1 ? "" : "s"}`}
        apoio={`${dinheiroCurto(aberto.valor_anual)} ao ano`}
      >
        <p>{dinheiroCurto(aberto.valor_anual)} ao ano</p>
        <p>
          {dinheiro(aberto.valor_mensal)} por mês
          {aberto.sem_preco_mensal > 0 &&
            ` · ${aberto.sem_preco_mensal} sem preço mensal`}
        </p>
      </Cartao>

      <Cartao
        rotulo="Aceitas em 2026"
        tom="verde"
        destaque={`${aceitas.quantas} proposta${aceitas.quantas === 1 ? "" : "s"}`}
        apoio={`${dinheiroCurto(aceitas.valor_anual)} ao ano`}
      >
        <p>{dinheiroCurto(aceitas.valor_anual)} ao ano</p>
        <p>
          {dinheiro(aceitas.valor_mensal)} por mês
          {aceitas.sem_preco_mensal > 0 &&
            `, de ${aceitas.com_preco_mensal} com preço mensal`}
        </p>
        {aceitas.sem_preco_mensal > 0 && (
          <p className="numero-nota">
            {aceitas.sem_preco_mensal} são de valor único e entram só no anual. Este
            valor <strong>não é o MRR</strong> da carteira.
          </p>
        )}
      </Cartao>

      <Cartao
        rotulo="Ticket recorrente aceito"
        tom="dourado"
        destaque={ticket.calculavel ? dinheiro(ticket.ticket_medio) : undefined}
        apoio={ticket.calculavel ? `por mês · mediana ${dinheiro(ticket.mediana)}` : undefined}
        pendente={!ticket.calculavel}
      >
        {ticket.calculavel ? (
          <>
            <p>
              Mediana <strong>{dinheiro(ticket.mediana)}</strong> por mês
            </p>
            <p>
              {ticket.quantas} proposta{ticket.quantas === 1 ? "" : "s"} de {ticket.clientes}{" "}
              cliente{ticket.clientes === 1 ? "" : "s"} · {dinheiro(ticket.valor_mensal)} por mês
            </p>
            <p className="numero-nota">
              O maior contrato ({dinheiro(ticket.maior_valor)}) pesa{" "}
              {percentual(ticket.participacao_do_maior)} do total — por isso a mediana vem junto.
              Só serviços recorrentes, em MRR (a parcela × 13 ÷ 12); consultoria e legalização são
              pontuais e ficam de fora. Não é o ticket médio da carteira.
            </p>
          </>
        ) : (
          <p className="numero-estado">
            Não calculável — nenhuma aceita com preço mensal neste recorte.
          </p>
        )}
      </Cartao>

      <Cartao
        rotulo="Ciclo médio de vendas"
        tom="violeta"
        destaque={ciclo.calculavel ? `${dias(ciclo.dias)} dias` : undefined}
        apoio={ciclo.calculavel ? `amostra de ${ciclo.amostra} proposta${ciclo.amostra === 1 ? "" : "s"}` : undefined}
        pendente={!ciclo.calculavel}
      >
        {ciclo.calculavel ? (
          <>
            <p>Originação até aceite · {ciclo.amostra} proposta{ciclo.amostra === 1 ? "" : "s"}</p>
            {ciclo.aceitas_sem_as_duas_datas > 0 && (
              <p className="numero-nota">
                {ciclo.aceitas_sem_as_duas_datas} aceita
                {ciclo.aceitas_sem_as_duas_datas === 1 ? "" : "s"} sem as duas datas ficaram
                de fora — não contam como zero dias.
              </p>
            )}
          </>
        ) : (
          <p className="numero-estado">
            Não calculável — nenhuma aceita com data de originação e de aceite ainda.
          </p>
        )}
      </Cartao>

      <Cartao
        rotulo="Taxa de conversão"
        tom={tomDaConversao(dados.taxa_de_conversao)}
        apoio={dados.taxa_de_conversao.calculavel ? `${dados.taxa_de_conversao.aceitas} de ${dados.taxa_de_conversao.decididas} decididas` : undefined}
        etiqueta={<EtiquetaDeConversao tx={dados.taxa_de_conversao} />}
        destaque={
          dados.taxa_de_conversao.calculavel
            ? percentual(dados.taxa_de_conversao.percentual)
            : undefined
        }
        pendente={!dados.taxa_de_conversao.calculavel}
      >
        {dados.taxa_de_conversao.calculavel ? (
          <>
            <p>
              {dados.taxa_de_conversao.aceitas} de {dados.taxa_de_conversao.decididas}{" "}
              decididas. Meta {Number(dados.taxa_de_conversao.meta ?? 50).toLocaleString("pt-BR")}%, alerta abaixo de{" "}
              {Number(dados.taxa_de_conversao.alerta ?? 30).toLocaleString("pt-BR")}%.
            </p>
            <p className="numero-nota">
              Só o que já tem desfecho entra na conta — aceita, recusada ou
              perdida. Em aberto fica de fora: ainda pode fechar.
            </p>
          </>
        ) : (
          <p className="numero-estado">
            Não calculável — nenhuma proposta decidida ainda neste recorte.
          </p>
        )}
      </Cartao>

      <Cartao
        rotulo="Cobertura do processo"
        tom="rosa"
        destaque={cobertura.percentual_com_proxima_acao !== null ? percentual(cobertura.percentual_com_proxima_acao) : undefined}
        apoio={cobertura.percentual_com_proxima_acao !== null ? "com próxima ação" : undefined}
        pendente={cobertura.percentual_com_proxima_acao === null}
      >
        {cobertura.percentual_com_proxima_acao !== null ? (
          <p>
            {percentual(cobertura.percentual_com_proxima_acao)} com próxima ação:{" "}
            {cobertura.em_aberto_com_proxima_acao} de {cobertura.em_aberto_total} em aberto
            têm próxima ação definida
          </p>
        ) : (
          <p className="numero-estado">Nenhuma oportunidade em aberto neste recorte.</p>
        )}
        <p>
          {percentual(cobertura.percentual_com_volumetria_completa)} com ficha de
          volumetria completa ({cobertura.com_volumetria_completa} de {cobertura.total})
        </p>
        <p className="numero-nota">
          É "aumentar os pontos de contato" virando número — os dois indicadores de
          cobertura que a base de 2026 já sustenta.
        </p>
      </Cartao>

      <Cartao
        rotulo="Dependência de canal"
        tom="marinho"
        apoio={dependencia.percentual !== null ? "da rede dos sócios" : undefined}
        destaque={
          dependencia.percentual !== null ? percentual(dependencia.percentual) : undefined
        }
        pendente={dependencia.percentual === null}
      >
        {dependencia.percentual !== null ? (
          <p>
            {dependencia.da_rede_de_socios} de {dependencia.total} propostas nasceram da
            rede dos sócios
          </p>
        ) : (
          <p className="numero-estado">Nenhuma oportunidade neste recorte.</p>
        )}
      </Cartao>
    </div>
  );
}
