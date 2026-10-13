/** Sucesso do Cliente › Reajuste anual (amostra aprovada por Eduardo em 13/10/2026).
 *
 * Julho, pelo IPCA desde a última definição do preço até junho. O CRM calcula e sugere; uma pessoa confirma
 * ou altera cada valor, e o evento de Reajuste guarda quem autorizou. Quem não completou 12 meses aparece como
 * "Adiado"; não recorrente longo e contrato em IGP-M, como "Você decide" (desmarcados). */

import { useMemo, useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { LinhaDoReajuste, MesDoIpca, ReajusteDoAno } from "../api/tipos";
import { CampoDeValor } from "../componentes/CampoDeValor";
import { Etiqueta } from "../componentes/Etiqueta";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { usarAcesso } from "../entrada";
import { data, dataHora, dinheiro } from "../formato";
import { usarDados } from "../usarDados";

const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

function mes(iso: string | null): string {
  if (!iso) return "—";
  const [a, m] = iso.split("-");
  return `${MESES[Number(m) - 1]}/${a.slice(2)}`;
}

function mesLongo(iso: string | null): string {
  if (!iso) return "—";
  const [a, m] = iso.split("-");
  return `${MESES[Number(m) - 1]}/${a}`;
}

function pct(valor: string | null): string {
  if (valor === null) return "—";
  return `${Number(valor).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
}

/** O valor que a linha reajusta: o mensal no recorrente; o total no projeto sem mensal. */
function campo(l: LinhaDoReajuste): "mensal" | "anual" {
  return l.preco_mensal !== null ? "mensal" : "anual";
}

function Base({ l }: { l: LinhaDoReajuste }) {
  if (l.situacao === "Adiado") {
    return (
      <>
        {l.meses} {l.meses === 1 ? "mês" : "meses"}
        <span className="celula-fonte">fica para jul/{l.adiado_para}</span>
      </>
    );
  }
  if (!l.de) return <>{l.base ? `desde ${data(l.base)}` : "—"}</>;
  return (
    <>
      {mes(l.de)} a {mes(l.ate)}
      <span className="celula-fonte">
        {l.meses} meses{l.base_presumida ? " · presumido" : ""}
        {l.meses_faltando.length > 0 && ` · falta ${l.meses_faltando.map(mesLongo).join(", ")}`}
      </span>
    </>
  );
}

function HistoricoDoIpca({ aoAtualizar }: { aoAtualizar: () => void }) {
  const [aberto, definirAberto] = useState(false);
  const [serie, definirSerie] = useState<MesDoIpca[] | null>(null);
  const [estado, definirEstado] = useState<string | null>(null);
  const [ocupado, definirOcupado] = useState(false);
  const desde = `${new Date().getFullYear() - 2}-01-01`;

  const carregar = async () => {
    try {
      definirSerie(await api.ipca(desde));
    } catch (f) {
      definirEstado(f instanceof ErroDaApi ? f.message : "Falha ao ler o IPCA.");
    }
  };
  const atualizar = async () => {
    definirOcupado(true);
    definirEstado(null);
    try {
      const s = await api.atualizarIpca();
      definirEstado(`IPCA atualizado: último mês ${mesLongo(s.ultimo_mes)}.`);
      await carregar();
      aoAtualizar();
    } catch (f) {
      definirEstado(f instanceof ErroDaApi ? f.message : "Falha ao atualizar o IPCA.");
    } finally {
      definirOcupado(false);
    }
  };

  return (
    <details
      className="historico-do-ipca"
      onToggle={(e) => {
        const abriu = (e.target as HTMLDetailsElement).open;
        definirAberto(abriu);
        if (abriu && serie === null) void carregar();
      }}
    >
      <summary>Histórico do IPCA guardado no CRM</summary>
      {aberto && (
        <div style={{ marginTop: "var(--e2)" }}>
          <p className="campo-ajuda">
            Variação mensal do IPCA (IBGE), série 433 do Banco Central. O CRM completa sozinho quando falta o último mês.{" "}
            <button type="button" className="link-de-tabela" disabled={ocupado} onClick={() => void atualizar()}>
              {ocupado ? "Atualizando…" : "Atualizar agora"}
            </button>
          </p>
          {estado && <p className="campo-ajuda" role="status">{estado}</p>}
          {serie === null && !estado && <Carregando rotulo="Carregando o IPCA" />}
          {serie !== null && serie.length === 0 && <p className="campo-ajuda">Nenhum mês guardado ainda.</p>}
          {serie !== null && serie.length > 0 && (
            <div className="tabela-rolagem">
              <table className="tabela" aria-label="IPCA por mês">
                <thead>
                  <tr><th scope="col">Mês</th><th scope="col" className="tabela-numero">IPCA no mês</th></tr>
                </thead>
                <tbody>
                  {serie.map((m) => (
                    <tr key={m.mes}><td>{mesLongo(m.mes)}</td><td className="tabela-numero">{pct(m.variacao)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </details>
  );
}

export function ReajusteAnual() {
  const { eu, pode } = usarAcesso();
  const hoje = new Date();
  const [ano, definirAno] = useState(hoje.getFullYear());
  const { dados, carregando, erro, recarregar } = usarDados<ReajusteDoAno>(() => api.reajuste(ano), [ano]);
  const podeAprovar = pode("contratos.aprovar");

  const [escolhidos, definirEscolhidos] = useState<Set<number> | null>(null);
  const [valores, definirValores] = useState<Record<number, string | null>>({});
  const [autorizador, definirAutorizador] = useState("");
  const [confirmando, definirConfirmando] = useState(false);
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);

  const linhas = dados?.linhas ?? [];
  const padrao = useMemo(
    () => new Set(linhas.filter((l) => l.aprovavel && l.situacao === "Reajustar").map((l) => l.contrato_id)),
    [linhas],
  );
  const marcados = escolhidos ?? padrao;
  const conta = (s: string) => linhas.filter((l) => l.situacao === s).length;

  const valorDe = (l: LinhaDoReajuste): string | null =>
    l.contrato_id in valores ? valores[l.contrato_id] : campo(l) === "mensal" ? l.mensal_sugerido : l.anual_sugerido;

  const trocarAno = (novo: number) => {
    definirAno(novo);
    definirEscolhidos(null);
    definirValores({});
    definirConfirmando(false);
    definirFalha(null);
    definirFeito(null);
  };

  const alternar = (id: number) => {
    const novo = new Set(marcados);
    if (novo.has(id)) novo.delete(id);
    else novo.add(id);
    definirEscolhidos(novo);
    definirConfirmando(false);
  };

  const aprovar = async () => {
    const itens = [];
    for (const l of linhas.filter((x) => marcados.has(x.contrato_id))) {
      const valor = valorDe(l);
      if (!valor) {
        definirFalha(`${l.grupo}: informe o valor reajustado.`);
        definirConfirmando(false);
        return;
      }
      if (campo(l) === "mensal") {
        // O anual acompanha o mensal pelas parcelas do contrato (13 por padrão): sugerido anual ÷ sugerido mensal.
        const parcelas = l.anual_sugerido && l.mensal_sugerido ? Math.round(Number(l.anual_sugerido) / Number(l.mensal_sugerido)) : null;
        const anual = parcelas ? ((Math.round(Number(valor) * 100) * parcelas) / 100).toFixed(2) : null;
        itens.push({ contrato_id: l.contrato_id, preco_mensal_novo: valor, preco_anual_novo: anual });
      } else {
        itens.push({ contrato_id: l.contrato_id, preco_anual_novo: valor });
      }
    }
    definirOcupado(true);
    definirFalha(null);
    try {
      const r = await api.aprovarReajuste(dados?.ano ?? ano, itens, eu.modo === "local" ? autorizador.trim() : undefined);
      definirFeito(`${r.aplicados} reajuste${r.aplicados === 1 ? "" : "s"} aplicado${r.aplicados === 1 ? "" : "s"}, autorizado${r.aplicados === 1 ? "" : "s"} por ${r.autorizado_por}.`);
      definirEscolhidos(null);
      definirValores({});
      recarregar();
    } catch (f) {
      definirFalha(f instanceof ErroDaApi ? f.message : "Falha ao aplicar o reajuste.");
    } finally {
      definirOcupado(false);
      definirConfirmando(false);
    }
  };

  const anos = [];
  for (let a = Math.max(2026, hoje.getFullYear() - 3); a <= hoje.getFullYear() + 1; a++) anos.push(a);

  return (
    <section aria-labelledby="reajuste-titulo">
      <div className="reajuste-cabecalho">
        <div>
          <h3 className="reajuste-titulo" id="reajuste-titulo">Reajuste anual · julho/{ano}</h3>
          <p className="campo-ajuda" style={{ margin: 0 }}>
            IPCA do Banco Central (série 433)
            {dados?.ipca.ultimo_mes && ` · último mês guardado: ${mesLongo(dados.ipca.ultimo_mes)}`}
            {dados?.ipca.buscado_em && ` · buscado em ${dataHora(dados.ipca.buscado_em)}`}
          </p>
        </div>
        <div className="reajuste-acoes">
          <label className="campo-rotulo" htmlFor="reajuste-ano">Ano</label>
          <select id="reajuste-ano" className="selecao" value={ano} onChange={(e) => trocarAno(Number(e.target.value))}>
            {anos.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
          {podeAprovar && dados?.ipca_completo && (
            confirmando ? (
              <>
                <button type="button" className="botao botao-primario" disabled={ocupado} onClick={() => void aprovar()}>
                  {ocupado ? "Aplicando…" : `Confirmar ${marcados.size} reajuste${marcados.size === 1 ? "" : "s"}`}
                </button>
                <button type="button" className="botao botao-secundario" onClick={() => definirConfirmando(false)}>Voltar</button>
              </>
            ) : (
              <button
                type="button"
                className="botao botao-primario"
                onClick={() => {
                  if (marcados.size === 0) return definirFalha("Marque ao menos um contrato.");
                  if (eu.modo === "local" && autorizador.trim().length < 3) return definirFalha("Informe quem autoriza o reajuste.");
                  definirFalha(null);
                  definirConfirmando(true);
                }}
              >
                Aprovar selecionados
              </button>
            )
          )}
        </div>
      </div>

      {dados?.ipca.aviso && <p className="recado recado-alcada" role="status">{dados.ipca.aviso}</p>}
      {dados && !dados.ipca_completo && (
        <p className="recado" role="status">
          O IPCA de junho/{ano} ainda não está guardado (o IBGE publica por volta de 10 de julho). Os valores abaixo são
          prévia, com os meses que já saíram; a aprovação abre quando junho sair.
        </p>
      )}
      {confirmando && (
        <p className="recado recado-alcada" role="status">
          Cada reajuste vira um evento de Reajuste em 01/07/{ano}, com o IPCA, o valor sugerido, o aprovado e quem autorizou.
          O evento não se apaga: se algo sair errado, registra-se uma Correção no contrato.
        </p>
      )}
      {feito && <p className="recado" role="status">✓ {feito}</p>}
      {falha && <p className="estado-texto estado-erro" role="alert">✗ {falha}</p>}

      {podeAprovar && eu.modo === "local" && (
        <div className="campo" style={{ maxWidth: 320, marginBottom: "var(--e3)" }}>
          <label className="campo-rotulo" htmlFor="reajuste-autorizador">Quem autoriza</label>
          <input id="reajuste-autorizador" className="entrada" value={autorizador} maxLength={200}
            onChange={(e) => definirAutorizador(e.target.value)} placeholder="Seu nome" />
        </div>
      )}

      {carregando && <Carregando rotulo="Montando o reajuste" />}
      {erro && !carregando && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {!carregando && !erro && linhas.length === 0 && (
        <VazioSemDados
          titulo={`Nenhum contrato no reajuste de julho/${ano}`}
          explicacao="Entram os contratos ativos assinados antes de julho. Contrato em aviso de saída não entra."
        />
      )}

      {!carregando && !erro && linhas.length > 0 && (
        <>
          <div className="numeros numeros-tres">
            <div className="numero"><span className="numero-rotulo">A reajustar</span><p className="numero-valor">{conta("Reajustar")}</p></div>
            <div className="numero"><span className="numero-rotulo">Adiados (menos de 12 meses)</span><p className="numero-valor">{conta("Adiado")}</p></div>
            <div className="numero"><span className="numero-rotulo">Você decide</span><p className="numero-valor">{conta("Você decide")}</p></div>
          </div>

          <div className="tabela-rolagem">
            <table className="tabela" aria-label={`Reajuste de julho/${ano}`}>
              <thead>
                <tr>
                  {podeAprovar && <th scope="col"><span className="visualmente-oculto">Aprovar</span></th>}
                  <th scope="col">Cliente</th>
                  <th scope="col">Base do cálculo</th>
                  <th scope="col" className="tabela-numero">IPCA</th>
                  <th scope="col" className="tabela-numero">Atual</th>
                  <th scope="col" className="tabela-numero">Novo</th>
                  <th scope="col">Situação</th>
                </tr>
              </thead>
              <tbody>
                {linhas.map((l) => {
                  const atual = campo(l) === "mensal" ? l.preco_mensal : l.preco_anual;
                  const editavel = podeAprovar && l.aprovavel;
                  return (
                    <tr key={l.contrato_id}>
                      {podeAprovar && (
                        <td>
                          {l.aprovavel && (
                            <input type="checkbox" checked={marcados.has(l.contrato_id)} onChange={() => alternar(l.contrato_id)}
                              aria-label={`Aprovar o reajuste de ${l.grupo}`} />
                          )}
                        </td>
                      )}
                      <td>
                        {l.grupo}
                        <span className="celula-fonte">{[l.escopo, l.empresa].filter(Boolean).join(" · ") || "—"}</span>
                      </td>
                      <td><Base l={l} /></td>
                      <td className="tabela-numero">{l.de ? pct(l.ipca) : "—"}</td>
                      <td className="tabela-numero">
                        {dinheiro(atual)}
                        <span className="celula-fonte">{campo(l) === "mensal" ? "mensal" : "total"}</span>
                      </td>
                      <td className="tabela-numero">
                        {editavel ? (
                          <CampoDeValor
                            className="entrada entrada-do-reajuste"
                            value={valorDe(l)}
                            aoMudar={(v) => {
                              definirValores((anterior) => ({ ...anterior, [l.contrato_id]: v }));
                              definirConfirmando(false);
                            }}
                            aria-label={`Valor reajustado de ${l.grupo}`}
                          />
                        ) : l.situacao === "Reajustar" || l.situacao === "Você decide" ? (
                          dinheiro(campo(l) === "mensal" ? l.mensal_sugerido : l.anual_sugerido)
                        ) : (
                          <span className="numero-nota">{dinheiro(atual)}</span>
                        )}
                      </td>
                      <td>
                        <Etiqueta texto={l.situacao} />
                        {(l.reajustado || l.observacao) && <span className="celula-fonte">{l.reajustado ?? l.observacao}</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="campo-ajuda" style={{ marginTop: "var(--e3)" }}>
            Ao aprovar, o CRM grava no histórico do contrato o valor anterior, o IPCA usado, o valor final, se foi alterado à
            mão, quem autorizou e quando. "Você decide" vem desmarcado: marque só o que for reajustar.
          </p>
        </>
      )}

      <HistoricoDoIpca aoAtualizar={recarregar} />
    </section>
  );
}
