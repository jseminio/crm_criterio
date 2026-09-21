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

import { api } from "../api/cliente";
import type { Indicadores } from "../api/tipos";
import { Carregando, Erro } from "./estados";
import { paraConsulta, type EstadoDosFiltros } from "./Filtros";
import { dinheiro, dinheiroCurto } from "../formato";
import { usarDados } from "../usarDados";

function Cartao({
  rotulo,
  destaque,
  children,
  pendente = false,
}: {
  rotulo: string;
  destaque?: string;
  children?: React.ReactNode;
  pendente?: boolean;
}) {
  return (
    <section className={`numero ${pendente ? "numero-pendente" : ""}`}>
      <h3 className="numero-rotulo">{rotulo}</h3>
      {destaque && <p className="numero-valor">{destaque}</p>}
      <div className="numero-detalhe">{children}</div>
    </section>
  );
}

export function Numeros({ filtros }: { filtros: EstadoDosFiltros }) {
  const { dados, carregando, erro, recarregar } = usarDados<Indicadores>(
    () => api.indicadores(paraConsulta(filtros)),
    [filtros.busca, filtros.captador, filtros.tipo_canal, filtros.temperatura],
  );

  if (carregando && !dados) return <Carregando rotulo="Calculando os números" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;

  const { em_aberto: aberto, aceitas } = dados;
  const semData = aceitas.quantas - dados.aceitas_com_data_de_aceite;

  return (
    <div className="numeros" aria-label="Números do funil">
      <Cartao
        rotulo="Em aberto"
        destaque={`${aberto.quantas} proposta${aberto.quantas === 1 ? "" : "s"}`}
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
        destaque={`${aceitas.quantas} proposta${aceitas.quantas === 1 ? "" : "s"}`}
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

      <Cartao rotulo="Ciclo médio de vendas" pendente>
        <p className="numero-estado">Não calculável</p>
        <p>{dados.ciclo_medio.motivo}</p>
        {semData > 0 && (
          <p className="numero-nota">
            Preencher a data do aceite libera este indicador.
          </p>
        )}
      </Cartao>

      <Cartao rotulo="Taxa de conversão" pendente>
        <p className="numero-estado">Aguardando definição</p>
        <p>{dados.taxa_de_conversao.motivo}</p>
      </Cartao>
    </div>
  );
}
