/** Campanhas de tráfego pago — amostra aprovada por Eduardo em 13/10/2026.
 *
 * Responde a uma pergunta: em qual campanha pôr o próximo real. Um funil por canal,
 * com a passagem entre etapas e o custo de cada uma, e a decisão por campanha pela
 * régua provisória de `crm.domain.campanhas`. Desde 13/10/2026, o custo por campanha: lido do Meta
 * Ads e, desde 14/10/2026, do Google Ads (botão único "Atualizar dos anúncios"), ou digitado em Custos e mídia. O sucesso da busca (primeira resposta,
 * quem respondeu) vem do painel do SDR, filtrado em tráfego pago.
 *
 * A largura de cada etapa é fixa, para dar a forma de funil: o número é o que vale.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { FunilDoCanal, LinhaDaCampanha, PainelDeCampanhas, PainelDoSdr, ResumoDasConversoes,
  SituacaoDosLeadsDoMeta } from "../api/tipos";
import { Carregando, Erro, VazioSemDados } from "../componentes/estados";
import { dinheiro } from "../formato";
import { mesAtual, nomeDoMes, numero, pct, tempo } from "../sdrFormato";
import { usarDados } from "../usarDados";

const LARGURAS = [100, 86, 72, 58, 46, 36];

/** O custo por etapa no singular: "por lead", "por reunião". */
const POR: Record<string, string> = {
  leads: "por lead", icp: "por lead no ICP", qualificados: "por qualificado",
  reunioes: "por reunião", propostas: "por proposta", contratos: "por contrato",
};

const TOM_DA_DECISAO: Record<string, string> = {
  "Escalar": "ganho",
  "Manter e observar": "neutra",
  "Aguardar volume": "neutra",
  "Ajustar criativo": "espera",
  "Rever campanha": "espera",
  "Rever custo": "espera",
  "Refazer público": "perda",
};

export function Campanhas() {
  const [mes, definirMes] = useState(mesAtual());
  const campanhas = usarDados<PainelDeCampanhas>(() => api.campanhas(mes), [mes]);
  const sdr = usarDados<PainelDoSdr>(() => api.painelDoSdr({ mes, origem: "trafego_pago" }), [mes]);
  const { dados, carregando, erro, recarregar } = campanhas;

  return (
    <div className="sdr">
      <div className="filtros">
        <div className="campo">
          <label className="campo-rotulo" htmlFor="campanhas-mes">Mês de chegada do lead</label>
          <input id="campanhas-mes" type="month" className="entrada" value={mes}
            onChange={(e) => e.target.value && definirMes(e.target.value)} />
        </div>
      </div>

      {carregando && !dados && <Carregando rotulo="Calculando as campanhas" />}
      {erro && <Erro mensagem={erro} aoTentarDeNovo={recarregar} />}
      {!erro && dados && !dados.total && (
        <VazioSemDados
          titulo={`Nenhum lead de tráfego pago em ${nomeDoMes(mes)}`}
          explicacao="O painel acompanha os leads de tráfego pago que chegaram no mês, do formulário ao contrato. Cadastre o lead com o tipo de canal Tráfego pago, o canal (Meta Ads, Google Ads) e a campanha, e lance o investimento do mês em SDR da IA › Custos e mídia."
        />
      )}
      {!erro && dados && <LeadsDoMetaBarra aoBuscar={recarregar} />}
      {!erro && dados && <LeituraDosAnunciosBarra mes={mes} p={dados} aoLer={recarregar} />}
      {!erro && dados?.total && <Conteudo p={dados} sdr={sdr.dados} />}
      {!erro && dados && <ConversoesDevolvidas mes={mes} />}
      {!erro && dados && <Prontidao p={dados} />}
    </div>
  );
}

function Conteudo({ p, sdr }: { p: PainelDeCampanhas; sdr: PainelDoSdr | null }) {
  const t = p.total!;
  const icp = t.etapas[1];
  const reuniao = t.etapas[3];
  return (
    <>
      <section className="sdr-secao" aria-labelledby="camp-s1">
        <div className="sdr-secao-topo">
          <h2 id="camp-s1">Tráfego pago em {nomeDoMes(p.mes)}</h2>
          <p>{numero(p.leads)} {p.leads === 1 ? "lead de tráfego pago chegou" : "leads de tráfego pago chegaram"} no mês</p>
        </div>
        <div className="sdr-kpis">
          <Kpi rotulo="Investimento" valor={t.investimento ? dinheiro(t.investimento) : null}
            apoio={p.canais.filter((c) => c.investimento).map((c) => `${c.canal} ${dinheiro(c.investimento)}`).join(" · ")}
            falta="Sem investimento lançado" />
          <Kpi rotulo="Leads no ICP" valor={`${numero(icp.quantidade)}`}
            apoio={`de ${numero(t.etapas[0].quantidade)} · ${pct(t.etapas[0].passagem!, 0) ?? "—"} no perfil`} />
          <Kpi rotulo="Custo por reunião" valor={reuniao.custo ? dinheiro(reuniao.custo) : null}
            apoio={`${numero(reuniao.quantidade)} reuniões`}
            falta={t.investimento ? "Nenhuma reunião ainda" : "Sem investimento lançado"} />
          <Kpi rotulo="CAC" valor={t.cac ? dinheiro(t.cac) : null}
            apoio={`${numero(t.etapas[5].quantidade)} contratos`}
            falta={t.investimento ? "Nenhum contrato ainda" : "Sem investimento lançado"} />
          <Kpi rotulo="MRR novo" valor={dinheiro(t.mrr_novo)}
            apoio={t.contratos_sem_preco ? `${t.contratos_sem_preco} contrato(s) sem preço mensal` : "parcela × 13 ÷ 12"} />
        </div>
      </section>

      <section className="sdr-secao" aria-labelledby="camp-s2">
        <div className="sdr-secao-topo">
          <h2 id="camp-s2">Funil por canal</h2>
          <p>% que passa para a etapa seguinte · custo de cada etapa</p>
        </div>
        <div className="camp-funis">
          {p.canais.length > 1 && <Funil f={t} total />}
          {p.canais.map((c) => <Funil key={c.canal} f={c} />)}
        </div>
      </section>

      <section className="sdr-secao" aria-labelledby="camp-s3">
        <div className="sdr-secao-topo">
          <h2 id="camp-s3">Decisão por campanha</h2>
          <p>Régua provisória: decide com {p.regua.volume_minimo} leads ou mais · ICP alvo{" "}
            {p.regua.icp_alvo_pct ? `${numero(Number(p.regua.icp_alvo_pct))}%` : "não definido no Plano de MRR"}
            {" "}· meta de {numero(p.regua.qualificados_meta_pct)}% qualificados
            {" "}· rever custo acima de {numero(Number(p.regua.teto_de_custo), 1)} × o R$/reunião do canal</p>
        </div>
        <TabelaDeCampanhas linhas={p.campanhas} />
      </section>

      <section className="sdr-secao" aria-labelledby="camp-s4">
        <div className="sdr-secao-topo">
          <h2 id="camp-s4">Sucesso da busca</h2>
          <p>Do painel do SDR da IA, só tráfego pago</p>
        </div>
        {sdr ? (
          <div className="sdr-grade sdr-grade-3">
            <div className="sdr-mini"><b>{tempo(sdr.primeira_resposta.valor) ?? "—"}</b><span>primeira resposta da IA (mediana)</span></div>
            <div className="sdr-mini"><b>{sdr.leads ? `${numero((100 * sdr.responderam) / sdr.leads, 0)}%` : "—"}</b><span>dos leads responderam</span></div>
            <div className="sdr-mini"><b>{pct(sdr.qualificados_sobre_responderam, 0) ?? "—"}</b><span>dos que responderam foram qualificados</span></div>
          </div>
        ) : <p className="sdr-sem-dado">Sem o painel do SDR neste mês.</p>}
      </section>
    </>
  );
}

/** "Atualizar dos anúncios" (14/10/2026): lê toda plataforma ligada; a leitura só grava valor lido, o digitado
 * fica. Uma plataforma que falha não impede a outra, e cada uma diz o seu resultado. */
function LeituraDosAnunciosBarra({ mes, p, aoLer }: { mes: string; p: PainelDeCampanhas; aoLer: () => void }) {
  const [lendo, definirLendo] = useState(false);
  const [avisos, definirAvisos] = useState<{ ok: boolean; texto: string }[]>([]);
  const ler = async () => {
    definirLendo(true);
    definirAvisos([]);
    try {
      const r = await api.atualizarDosAnuncios(mes);
      definirAvisos(r.plataformas.map((x) => x.ok
        ? { ok: true, texto: `${x.canal}: ${x.gravadas} campanha(s) atualizada(s).${x.digitadas_mantidas.length
            ? ` Valor digitado mantido em: ${x.digitadas_mantidas.join(", ")}.` : ""}` }
        : { ok: false, texto: `${x.canal}: ${x.erro}` }));
      aoLer();
    } catch (falha) {
      definirAvisos([{ ok: false, texto: falha instanceof ErroDaApi ? falha.message : "Não consegui ler os anúncios." }]);
    } finally {
      definirLendo(false);
    }
  };
  const quando = (a: PainelDeCampanhas["anuncios"][number]) => !a.configurada
    ? `${a.canal}: leitura desligada em Configurações › Integrações`
    : a.lido_em
      ? `${a.canal} lido em ${new Date(a.lido_em).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}`
      : `${a.canal} ainda não lido neste mês`;
  const algumaLigada = p.anuncios.some((a) => a.configurada);
  return (
    <div className="camp-leitura">
      <span>{p.anuncios.map(quando).join(" · ")}</span>
      {algumaLigada && (
        <button type="button" className="botao botao-secundario" onClick={ler} disabled={lendo}>
          {lendo ? "Lendo os anúncios…" : "Atualizar dos anúncios"}
        </button>
      )}
      {avisos.map((a) => (
        <p key={a.texto} role={a.ok ? "status" : "alert"} className={a.ok ? "camp-aviso" : "camp-aviso camp-aviso-falha"}>{a.texto}</p>
      ))}
    </div>
  );
}

function Kpi({ rotulo, valor, apoio, falta }: { rotulo: string; valor: string | null; apoio?: string; falta?: string }) {
  return (
    <article className="sdr-bloco sdr-kpi">
      <span className="sdr-kpi-rotulo">{rotulo}</span>
      {valor ? <span className="sdr-kpi-valor camp-kpi-valor">{valor}</span> : <p className="sdr-sem-dado">{falta}</p>}
      {apoio && <span className="sdr-apoio">{apoio}</span>}
    </article>
  );
}

function Funil({ f, total = false }: { f: FunilDoCanal; total?: boolean }) {
  const passagens = f.etapas.filter((e) => e.passagem?.valor != null && e.quantidade > 0).map((e) => e.passagem!.valor!);
  const pior = passagens.length ? Math.min(...passagens) : null;
  return (
    <figure className={`camp-funil${total ? " camp-funil-total" : ""}`} aria-label={`Funil de ${f.canal}`}>
      <figcaption className="camp-funil-cab">
        <strong>{f.canal}</strong>
        <span>{f.investimento ? dinheiro(f.investimento) : "sem investimento"} · {pct(f.lead_a_contrato) ?? "—"} lead → contrato</span>
      </figcaption>
      <ol className="camp-etapas">
        {f.etapas.map((e, i) => {
          const a = LARGURAS[i];
          const b = LARGURAS[i + 1] ?? a - 10;
          const recuo = Math.round(((a - b) / 2 / a) * 10000) / 100;
          const valor = e.passagem?.valor ?? null;
          const ePior = valor !== null && valor === pior && e.quantidade > 0;
          return (
            <li key={e.chave}>
              <div className="camp-etapa" style={{ width: `${a}%`, clipPath: `polygon(0 0, 100% 0, ${100 - recuo}% 100%, ${recuo}% 100%)` }}>
                <b>{numero(e.quantidade)}</b><span>{e.rotulo}</span>
              </div>
              <p className="camp-custo">{e.custo ? `${dinheiro(e.custo)} ${POR[e.chave]}` : " "}</p>
              {e.passagem && (
                <p className={`camp-passagem${ePior ? " camp-pior" : ""}`}>
                  {ePior ? "! " : "↓ "}{pct(e.passagem, 0) ?? "—"}{ePior && <span> · pior passagem</span>}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </figure>
  );
}

function TabelaDeCampanhas({ linhas }: { linhas: LinhaDaCampanha[] }) {
  return (
    <div className="tabela-rolagem">
      <table className="tabela" aria-label="Decisão por campanha">
        <thead>
          <tr>
            <th>Campanha</th><th className="tabela-numero">Invest.</th><th className="tabela-numero">Leads</th>
            <th className="tabela-numero">No ICP</th><th className="tabela-numero">Qualificados</th>
            <th className="tabela-numero">Reuniões</th><th className="tabela-numero">R$/lead ICP</th>
            <th className="tabela-numero">R$/reunião</th><th className="tabela-numero">Contratos</th>
            <th>O que mais descarta</th><th>Decisão</th>
          </tr>
        </thead>
        <tbody>
          {linhas.map((l) => (
            <tr key={`${l.canal}|${l.campanha}`}>
              <td>{l.campanha}<br /><span className="sdr-fraco">{l.canal}{l.fonte ? ` · ${l.fonte}` : ""}</span></td>
              <td className="tabela-numero">{l.investimento ? dinheiro(l.investimento) : "—"}</td>
              <td className="tabela-numero">{numero(l.leads)}</td>
              <td className="tabela-numero">{pct(l.no_icp, 0) ?? "—"}</td>
              <td className="tabela-numero">{pct(l.qualificados, 0) ?? "—"}</td>
              <td className="tabela-numero">{numero(l.reunioes)}</td>
              <td className="tabela-numero">{l.custo_por_lead_icp ? dinheiro(l.custo_por_lead_icp) : "—"}</td>
              <td className="tabela-numero">{l.custo_por_reuniao ? dinheiro(l.custo_por_reuniao) : "—"}</td>
              <td className="tabela-numero">{numero(l.contratos)}</td>
              <td>{l.descartes[0] ? `${l.descartes[0].nome} (${l.descartes[0].quantidade})` : "—"}</td>
              <td>
                <span className={`etiqueta etiqueta-${TOM_DA_DECISAO[l.decisao] ?? "neutra"}`}>{l.decisao}</span>
                <br /><span className="sdr-fraco">{l.porque}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Prontidao({ p }: { p: PainelDeCampanhas }) {
  return (
    <section className="sdr-secao" aria-labelledby="camp-s5">
      <div className="sdr-secao-topo"><h2 id="camp-s5">Prontidão dos dados</h2></div>
      <ul className="camp-prontidao">
        {p.prontidao.map((x) => (
          <li key={x.texto} className={x.ok ? "camp-ok" : "camp-falta"}>
            <span aria-hidden="true">{x.ok ? "✓" : "!"}</span>
            <span className="sr">{x.ok ? "Pronto: " : "Falta: "}</span>{x.texto}
          </li>
        ))}
      </ul>
    </section>
  );
}

const HORA = (iso: string) => new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });

/** Conversões devolvidas ao Meta e ao Google (amostra aprovada em 14/10/2026): o que saiu, o que foi recusado e
 * o que não tem como ser reconhecido. O envio é automático a cada 10 minutos; "Enviar agora" roda uma vez já. */
function ConversoesDevolvidas({ mes }: { mes: string }) {
  const { dados, carregando, erro, recarregar } = usarDados<ResumoDasConversoes>(() => api.conversoes(mes), [mes]);
  const [enviando, definirEnviando] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const enviar = async () => {
    definirEnviando(true);
    definirFalha(null);
    try {
      await api.enviarConversoes();
      recarregar();
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui enviar as conversões.");
    } finally {
      definirEnviando(false);
    }
  };
  if (carregando && !dados) return <Carregando rotulo="Contando as conversões" />;
  if (erro) return <Erro mensagem={erro} aoTentarDeNovo={recarregar} />;
  if (!dados) return null;
  const plataformas = Object.keys(dados.ligadas);
  const algumaLigada = plataformas.some((p) => dados.ligadas[p]);
  const celula = (evento: string, p: string) => {
    const l = dados.linhas.find((x) => x.evento === evento && x.plataforma === p);
    if (!l) return "—";
    const partes = [`${numero(l.enviados)} enviado${l.enviados === 1 ? "" : "s"}`];
    if (l.valor_enviado) partes[0] += ` · ${dinheiro(l.valor_enviado)}`;
    if (l.sem_identificador) partes.push(`${numero(l.sem_identificador)} sem ${p === "Google Ads" ? "gclid" : "e-mail, telefone ou fbclid"}`);
    if (l.recusados) partes.push(`${numero(l.recusados)} recusado${l.recusados === 1 ? "" : "s"}`);
    if (l.falhas) partes.push(`${numero(l.falhas)} a reenviar`);
    return partes.join(" · ");
  };
  const eventos = [...new Map(dados.linhas.map((l) => [l.evento, l.rotulo])).entries()];
  const ultima = dados.ultima_rodada;
  return (
    <section className="sdr-secao" aria-labelledby="camp-s6">
      <div className="sdr-secao-topo">
        <h2 id="camp-s6">Conversões devolvidas</h2>
        <p>{plataformas.map((p) => `${p}: ${dados.ligadas[p] ? "ligada" : "desligada"}`).join(" · ")}</p>
      </div>
      <div className="camp-leitura">
        <span>
          {algumaLigada ? "Envio automático a cada 10 minutos" : "Devolução desligada em Configurações › Integrações"}
          {algumaLigada && ultima ? ` · última rodada em ${HORA(ultima.em)}` : ""}
        </span>
        {algumaLigada && (
          <button type="button" className="botao botao-secundario" onClick={enviar} disabled={enviando}>
            {enviando ? "Enviando…" : "Enviar agora"}
          </button>
        )}
        {falha && <p role="alert" className="camp-aviso camp-aviso-falha">{falha}</p>}
        {ultima?.plataformas.filter((p) => p.aviso).map((p) => (
          <p key={p.plataforma} role="alert" className="camp-aviso camp-aviso-falha">{p.plataforma}: {p.aviso}</p>
        ))}
      </div>
      <div className="tabela-rolagem">
        <table className="tabela" aria-label="Conversões devolvidas">
          <thead><tr><th>Evento do CRM</th>{plataformas.map((p) => <th key={p}>{p}</th>)}</tr></thead>
          <tbody>
            {eventos.map(([evento, rotulo]) => (
              <tr key={evento}>
                <td>{rotulo}{evento === "contrato_fechado" && <span className="sdr-fraco"> (valor = MRR)</span>}</td>
                {plataformas.map((p) => <td key={p}>{celula(evento, p)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {dados.recusas.length > 0 && (
        <ul className="camp-prontidao" aria-label="Recusas">
          {dados.recusas.map((r) => (
            <li key={`${r.lead}-${r.evento}-${r.plataforma}`} className="camp-falta">
              <span aria-hidden="true">!</span><span className="sr">Recusado: </span>
              {r.lead} · {r.evento} · {r.plataforma}: {r.motivo}
            </li>
          ))}
        </ul>
      )}
      <p className="sdr-nota">
        Cada evento sai uma vez só. E-mail e telefone saem só criptografados (SHA-256). Lead que pediu para não ser
        contatado nunca é enviado.
      </p>
    </section>
  );
}

/** Leads do formulário do Meta (amostra aprovada em 14/10/2026): entram sozinhos a cada 10 minutos; "Buscar leads
 * agora" roda uma vez já e recarrega o painel. */
function LeadsDoMetaBarra({ aoBuscar }: { aoBuscar: () => void }) {
  const { dados, recarregar } = usarDados<SituacaoDosLeadsDoMeta>(() => api.leadsDoMeta(), []);
  const [buscando, definirBuscando] = useState(false);
  const [aviso, definirAviso] = useState<{ ok: boolean; texto: string } | null>(null);
  if (!dados) return null;
  const buscar = async () => {
    definirBuscando(true);
    definirAviso(null);
    try {
      const r = await api.buscarLeadsDoMeta();
      definirAviso(r.erro ? { ok: false, texto: r.erro }
        : { ok: true, texto: `${numero(r.novos)} lead${r.novos === 1 ? "" : "s"} novo${r.novos === 1 ? "" : "s"} do Meta.` });
      recarregar();
      aoBuscar();
    } catch (falha) {
      definirAviso({ ok: false, texto: falha instanceof ErroDaApi ? falha.message : "Não consegui buscar os leads do Meta." });
    } finally {
      definirBuscando(false);
    }
  };
  const u = dados.ultima;
  const texto = !dados.ligada
    ? "Leads do Meta: entrada desligada em Configurações › Integrações"
    : `Leads do Meta: busca automática a cada 10 minutos${u ? ` · última em ${HORA(u.em)}, ${numero(u.novos)} novo${u.novos === 1 ? "" : "s"}` : ""}`;
  return (
    <div className="camp-leitura">
      <span>{texto}</span>
      {dados.ligada && (
        <button type="button" className="botao botao-secundario" onClick={buscar} disabled={buscando}>
          {buscando ? "Buscando…" : "Buscar leads agora"}
        </button>
      )}
      {u?.erro && !aviso && <p role="alert" className="camp-aviso camp-aviso-falha">{u.erro}</p>}
      {aviso && <p role={aviso.ok ? "status" : "alert"} className={aviso.ok ? "camp-aviso" : "camp-aviso camp-aviso-falha"}>{aviso.texto}</p>}
    </div>
  );
}
