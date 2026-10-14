/** Configurações › Serviços e contratos (amostra aprovada por Eduardo em 13/10/2026).
 *
 * O tipo (recorrente ou não) e as parcelas saem do catálogo de serviços, aprovado em 27/09/2026, e não se editam
 * aqui. Por serviço, escolhem-se o modelo de contrato e o reajuste. Na conversão da oportunidade em contrato, o
 * tipo do serviço é a sugestão. */

import { useEffect, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ModeloDeContrato, ReajusteDoServico, ServicoNoContrato } from "../api/tipos";
import { usarAcesso } from "../entrada";
import { usarDados } from "../usarDados";
import { Carregando, Erro } from "./estados";

type Escolha = { modelo: ModeloDeContrato; reajuste: ReajusteDoServico };

export function ServicosEContratos() {
  const { pode } = usarAcesso();
  const podeEditar = pode("configuracoes.servicos");
  const { dados, carregando, erro, recarregar } = usarDados<ServicoNoContrato[]>(() => api.servicosEContratos(), []);
  const [linhas, definirLinhas] = useState<ServicoNoContrato[] | null>(null);
  const [escolhas, definirEscolhas] = useState<Record<string, Escolha>>({});
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  useEffect(() => {
    if (dados) definirLinhas(dados);
  }, [dados]);

  const atual = (l: ServicoNoContrato): Escolha => escolhas[l.servico] ?? { modelo: l.modelo, reajuste: l.reajuste };
  const mudou = (linhas ?? []).filter((l) => {
    const e = escolhas[l.servico];
    return e && (e.modelo !== l.modelo || e.reajuste !== l.reajuste);
  });

  const escolher = (l: ServicoNoContrato, mudanca: Partial<Escolha>) => {
    definirEscolhas((anteriores) => ({ ...anteriores, [l.servico]: { ...atual(l), ...mudanca } }));
    definirFeito(null);
  };

  const salvar = async () => {
    if (mudou.length === 0) return definirFalha("Nada mudou.");
    definirOcupado(true);
    definirFalha(null);
    try {
      const novas = await api.gravarServicosEContratos(mudou.map((l) => ({ servico: l.servico, ...atual(l) })));
      definirLinhas(novas);
      definirEscolhas({});
      definirFeito(`${mudou.length} serviço${mudou.length === 1 ? "" : "s"} salvo${mudou.length === 1 ? "" : "s"}.`);
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao salvar.");
    } finally {
      definirOcupado(false);
    }
  };

  if (carregando && !linhas) return <Carregando rotulo="Carregando os serviços" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!linhas) return null;

  return (
    <section aria-labelledby="servicos-contratos-titulo">
      <div className="reajuste-cabecalho">
        <div>
          <h3 className="reajuste-titulo" id="servicos-contratos-titulo">Serviços e contratos</h3>
          <p className="campo-ajuda" style={{ margin: 0 }}>
            O tipo vem do serviço e orienta o contrato. Nome, tipo, parcelas e o roteiro do SDR seguem o catálogo aprovado
            em 27/09/2026.
          </p>
        </div>
        {podeEditar && (
          <button type="button" className="botao botao-primario" disabled={ocupado} onClick={() => void salvar()}>
            {ocupado ? "Salvando…" : "Salvar"}
          </button>
        )}
      </div>
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {falha && <p className="estado-texto estado-erro" role="alert">✗ {falha}</p>}

      <div className="tabela-rolagem">
        <table className="tabela" aria-label="Serviços e contratos">
          <thead>
            <tr>
              <th scope="col">Serviço</th>
              <th scope="col">Tipo</th>
              <th scope="col">Modelo de contrato</th>
              <th scope="col" className="tabela-numero">Parcelas</th>
              <th scope="col">Reajuste</th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((l) => {
              const e = atual(l);
              return (
                <tr key={l.servico}>
                  <td>
                    {l.servico}
                    {l.temas > 0 && <span className="celula-fonte">{l.temas} temas</span>}
                  </td>
                  <td>
                    <span className={`etiqueta etiqueta-${l.linha === "C1" ? "ganho" : "andamento"}`}>{l.tipo}</span>
                  </td>
                  <td>
                    {podeEditar && l.modelos_possiveis.length > 1 ? (
                      <select className="selecao" value={e.modelo} aria-label={`Modelo de contrato de ${l.servico}`}
                        onChange={(ev) => escolher(l, { modelo: ev.target.value as ModeloDeContrato })}>
                        {l.modelos_possiveis.map((m) => <option key={m} value={m}>{m}</option>)}
                      </select>
                    ) : (
                      e.modelo
                    )}
                    <span className={`celula-fonte${l.situacao_do_modelo === "aguardando arquivo" ? " texto-espera" : ""}`}>
                      {l.situacao_do_modelo}
                    </span>
                  </td>
                  <td className="tabela-numero">{l.parcelas ?? "—"}</td>
                  <td>
                    {podeEditar ? (
                      <select className="selecao" value={e.reajuste} aria-label={`Reajuste de ${l.servico}`}
                        onChange={(ev) => escolher(l, { reajuste: ev.target.value as ReajusteDoServico })}>
                        {l.reajustes_possiveis.map((r) => <option key={r} value={r}>{r}</option>)}
                      </select>
                    ) : (
                      e.reajuste
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="campo-ajuda" style={{ marginTop: "var(--e3)" }}>
        "IPCA em julho" entra na tabela do reajuste anual; "Caso a caso" entra como "Você decide"; "Sem reajuste" fica de
        fora. Não recorrente nunca reajusta sozinho. CFO as a Service e BPO Plus esperam a Descoberta do Cliente.
      </p>
    </section>
  );
}
