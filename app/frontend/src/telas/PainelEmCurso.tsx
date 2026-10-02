/** Painel do cliente em curso no Funil do Sucesso do Cliente: as reuniões que a classe pede, o
 * registro da reunião com a ata e o histórico. A ata (aprovada por Eduardo em 02/10/2026) nasce da
 * transcrição do Granola: a IA monta o rascunho, o gestor revisa, escolhe o responsável e o prazo de
 * cada ajuste e registra. Os ajustes vão para a Agenda da área técnica. Uma ação principal só:
 * "Registrar reunião"; montar a ata é secundária e não grava nada. */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type {
  AjusteTecnico, FunilDoSucesso as Funil, GrupoNoFunilDoSucesso as Grupo, ReuniaoDeResultado, ResponsavelPorAjuste, TipoDeReuniao,
} from "../api/tipos";
import { CampoDeData } from "../componentes/CampoDeData";
import { Carregando, Erro } from "../componentes/estados";
import { PainelLateral } from "../componentes/PainelLateral";
import { usarAcesso } from "../entrada";
import { data, dataHora, prazo as quandoVence } from "../formato";
import { usarDados } from "../usarDados";

const MINIMO_DA_TRANSCRICAO = 50;

type AjusteEmEdicao = { chave: number; descricao: string; responsavel_email: string; prazo: string | null };

const nomeDoTipo = (f: Funil, chave: string) => f.tipos.find((t) => t.chave === chave)?.nome ?? chave;
const pautaDe = (t: TipoDeReuniao | undefined) => (t ? t.pauta.map((p) => `• ${p}`).join("\n") : "");
const emTopicos = (itens: string[]) => itens.map((i) => `• ${i}`).join("\n");

function situacaoDoAjuste(a: AjusteTecnico): string {
  if (a.feito_em) return `✓ feito em ${data(a.feito_em)}`;
  const vence = quandoVence(a.prazo);
  if (!a.prazo) return "pendente, sem prazo";
  return vence?.atrasado ? `⚠ pendente, prazo ${data(a.prazo)} (${vence.texto})` : `pendente, prazo ${data(a.prazo)}`;
}

/** O texto da ata para colar no Teams ou num e-mail. */
export function textoDaAta(f: Funil, grupo: string, r: ReuniaoDeResultado): string {
  const partes = [`Ata da reunião ${nomeDoTipo(f, r.tipo).toLowerCase()} · ${grupo} · ${data(r.data)}`];
  if (r.participantes) partes.push(`Participantes: ${r.participantes}`);
  if (r.resumo) partes.push(`Resumo\n${r.resumo}`);
  if (r.decisoes) partes.push(`Decisões do cliente\n${r.decisoes}`);
  if (r.ajustes.length) {
    partes.push(`Ajustes para a área técnica\n${r.ajustes.map((a) =>
      `• ${a.descricao} — ${a.responsavel_nome ?? a.responsavel_email}${a.prazo ? `, até ${data(a.prazo)}` : ""}`).join("\n")}`);
  }
  if (r.pendencias_do_cliente) partes.push(`Pendências do cliente\n${r.pendencias_do_cliente}`);
  if (r.pontos_sensiveis) partes.push(`Pontos sensíveis\n${r.pontos_sensiveis}`);
  if (r.proximos_passos) partes.push(`Próximos passos\n${r.proximos_passos}`);
  if (r.dashboard) partes.push(`Dashboard: ${r.dashboard}`);
  return partes.join("\n\n");
}

function Historico({ f, g }: { f: Funil; g: Grupo }) {
  const historico = usarDados<ReuniaoDeResultado[]>(() => api.reunioesDoGrupo(g.grupo_id), [g.grupo_id, g.reunioes, g.ajustes_pendentes]);
  const [copiada, definirCopiada] = useState<number | null>(null);
  const copiar = async (r: ReuniaoDeResultado) => {
    try {
      await navigator.clipboard.writeText(textoDaAta(f, g.nome, r));
      definirCopiada(r.id);
    } catch {
      definirCopiada(null);
    }
  };
  return (
    <section aria-labelledby="re-historico">
      <h3 className="campo-rotulo" id="re-historico">Reuniões registradas</h3>
      {historico.carregando && !historico.dados ? (
        <Carregando rotulo="Abrindo as reuniões" />
      ) : historico.erro ? (
        <Erro mensagem={historico.erro} aoTentarDeNovo={historico.recarregar} />
      ) : !historico.dados?.length ? (
        <p className="campo-ajuda">Nenhuma reunião registrada ainda.</p>
      ) : (
        <ol className="sucesso-historico">
          {historico.dados.map((r) => (
            <li key={r.id}>
              <div className="sucesso-historico-topo">
                <strong>{nomeDoTipo(f, r.tipo)} · {data(r.data)}</strong>
                <button type="button" className="link-de-tabela" onClick={() => void copiar(r)}>
                  {copiada === r.id ? "✓ Ata copiada" : "Copiar a ata"}
                </button>
              </div>
              {r.participantes && <span className="campo-ajuda">{r.participantes}</span>}
              {r.resumo && <p>{r.resumo}</p>}
              {r.decisoes && <p><b>Decisões do cliente:</b>{"\n"}{r.decisoes}</p>}
              {r.ajustes.length > 0 && (
                <div>
                  <b>Ajustes para a área técnica:</b>
                  <ul className="sucesso-ajustes">
                    {r.ajustes.map((a) => (
                      <li key={a.id}>
                        {a.descricao} — {a.responsavel_nome ?? a.responsavel_email}
                        <span className={`celula-fonte ${!a.feito_em && quandoVence(a.prazo)?.atrasado ? "cartao-prazo-atrasado" : ""}`}>
                          {situacaoDoAjuste(a)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {r.pendencias_do_cliente && <p><b>Pendências do cliente:</b>{"\n"}{r.pendencias_do_cliente}</p>}
              {r.pontos_sensiveis && <p><b>Pontos sensíveis:</b>{"\n"}{r.pontos_sensiveis}</p>}
              {r.proximos_passos && <p><b>Próximos passos:</b>{"\n"}{r.proximos_passos}</p>}
              {r.dashboard && <p><b>Dashboard:</b> {r.dashboard}</p>}
              <span className="campo-ajuda">
                Registrada {r.registrada_por ? `por ${r.registrada_por} ` : ""}em {dataHora(r.criado_em)}
                {r.tem_transcricao ? " · com a transcrição do Granola guardada" : ""}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function PainelEmCurso({
  f, g, tipoPedido = null, titulo, subtitulo, aoFechar, aoMudar,
}: {
  f: Funil; g: Grupo; tipoPedido?: string | null; titulo: string; subtitulo: string; aoFechar: () => void; aoMudar: () => void;
}) {
  const { pode } = usarAcesso();
  const edita = pode("sucesso.editar");
  // Aberto pela coluna de uma reunião, já vem nela; senão, a primeira vencida, senão a primeira da classe.
  const sugerido = tipoPedido ?? g.reunioes.find((r) => r.atrasada)?.tipo ?? g.reunioes[0]?.tipo ?? f.tipos[0].chave;
  const tipoInicial = f.tipos.find((t) => t.chave === sugerido);
  const hoje = new Date().toLocaleDateString("sv");
  const vazio = {
    tipo: sugerido, data: hoje, participantes: tipoInicial?.participantes ?? "", pauta: pautaDe(tipoInicial),
    dashboard: "", transcricao: "", resumo: "", decisoes: "", pendencias_do_cliente: "", pontos_sensiveis: "",
  };
  const [campos, definirCampos] = useState(vazio);
  const [ajustes, definirAjustes] = useState<AjusteEmEdicao[]>([]);
  const [proxima, definirProxima] = useState(1);
  const [montando, definirMontando] = useState(false);
  const [ocupado, definirOcupado] = useState(false);
  const [falha, definirFalha] = useState<string | null>(null);
  const [feito, definirFeito] = useState<string | null>(null);
  const responsaveis = usarDados<ResponsavelPorAjuste[]>(
    () => (edita ? api.responsaveisPorAjuste() : Promise.resolve([])), [edita]);

  const mudar = (campo: keyof typeof campos, valor: string) => {
    definirFeito(null);
    definirCampos((c) => ({ ...c, [campo]: valor }));
  };
  const mudarTipo = (chave: string) => {
    const t = f.tipos.find((x) => x.chave === chave);
    definirFeito(null);
    definirCampos((c) => ({ ...c, tipo: chave, participantes: t?.participantes ?? "", pauta: pautaDe(t) }));
  };
  const novoAjuste = (descricao = "", prazo: string | null = null): AjusteEmEdicao => {
    const chave = proxima;
    definirProxima((n) => n + 1);
    return { chave, descricao, responsavel_email: "", prazo };
  };
  const mudarAjuste = (chave: number, mudanca: Partial<AjusteEmEdicao>) =>
    definirAjustes((lista) => lista.map((a) => (a.chave === chave ? { ...a, ...mudanca } : a)));

  const montarAta = async () => {
    definirMontando(true);
    definirFalha(null);
    definirFeito(null);
    try {
      const ata = await api.montarAta(g.grupo_id, {
        tipo: campos.tipo, data: campos.data, participantes: campos.participantes, transcricao: campos.transcricao,
      });
      definirCampos((c) => ({
        ...c, resumo: ata.resumo, decisoes: emTopicos(ata.decisoes_do_cliente),
        pendencias_do_cliente: emTopicos(ata.pendencias_do_cliente), pontos_sensiveis: emTopicos(ata.pontos_sensiveis),
      }));
      let n = proxima;
      definirAjustes(ata.ajustes.map((a) => ({ chave: n++, descricao: a.descricao, responsavel_email: "", prazo: a.prazo })));
      definirProxima(n);
      definirFeito(
        `Rascunho da ata montado${ata.custo_usd ? ` (custo estimado US$ ${ata.custo_usd.replace(".", ",")})` : ""}. ` +
        "Revise cada campo e escolha o responsável de cada ajuste antes de registrar.",
      );
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui montar a ata. Tente de novo.");
    } finally {
      definirMontando(false);
    }
  };

  const incompletos = ajustes.filter((a) => a.descricao.trim().length < 3 || !a.responsavel_email).length;
  const registrar = async () => {
    definirOcupado(true);
    definirFalha(null);
    try {
      await api.registrarReuniao(g.grupo_id, {
        ...campos,
        ajustes: ajustes.map((a) => ({ descricao: a.descricao.trim(), responsavel_email: a.responsavel_email, prazo: a.prazo || null })),
      });
      definirFeito(
        `Reunião ${nomeDoTipo(f, campos.tipo).toLowerCase()} de ${data(campos.data)} registrada` +
        (ajustes.length ? `, com ${ajustes.length} ${ajustes.length === 1 ? "ajuste enviado" : "ajustes enviados"} à área técnica.` : "."),
      );
      definirCampos({ ...vazio, tipo: campos.tipo, participantes: campos.participantes, pauta: campos.pauta });
      definirAjustes([]);
      aoMudar();
    } catch (e) {
      definirFalha(e instanceof ErroDaApi ? e.message : "Não consegui registrar. Tente de novo.");
    } finally {
      definirOcupado(false);
    }
  };

  const semResponsaveis = responsaveis.dados !== null && responsaveis.dados.length === 0;

  return (
    <PainelLateral
      titulo={titulo} subtitulo={subtitulo} aoFechar={aoFechar}
      rodape={edita ? (
        <>
          <button type="button" className="botao botao-primario" disabled={ocupado || montando || !campos.data || incompletos > 0}
            onClick={() => void registrar()}>
            {ocupado ? "Registrando…" : "Registrar reunião"}
          </button>
          {incompletos > 0 && <span className="campo-ajuda">· cada ajuste precisa de descrição e responsável</span>}
        </>
      ) : undefined}
    >
      {g.situacao === "sem_classe" ? (
        <p className="recado">⚠ Este grupo ainda não tem classe. Avalie o Score na aba Saúde da carteira: é a classe que diz quais reuniões ele recebe.</p>
      ) : (
        <table className="tabela">
          <caption className="campo-rotulo" style={{ textAlign: "left", paddingBottom: "var(--e2)" }}>Reuniões da classe {g.classe}</caption>
          <thead>
            <tr><th>Reunião</th><th>Com quem</th><th>Última</th><th>Próxima</th></tr>
          </thead>
          <tbody>
            {g.reunioes.map((r) => (
              <tr key={r.tipo}>
                <td>{nomeDoTipo(f, r.tipo)}</td>
                <td>{f.tipos.find((t) => t.chave === r.tipo)?.participantes}</td>
                <td>{r.ultima ? data(r.ultima) : "nenhuma"}</td>
                <td className={r.atrasada ? "cartao-prazo-atrasado" : undefined}>
                  {!r.proxima ? "⚠ registre a primeira" : r.atrasada ? `⚠ venceu em ${data(r.proxima)} (${r.dias_de_atraso} d)` : `até ${data(r.proxima)}`}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {(g.ajustes_pendentes > 0 || g.ajustes_feitos > 0) && (
        <p className="campo-ajuda" style={{ margin: 0 }}>
          Ajustes da área técnica: {g.ajustes_pendentes + g.ajustes_feitos} · {g.ajustes_feitos} feito{g.ajustes_feitos === 1 ? "" : "s"}
          {g.ajustes_atrasados > 0 && ` · ⚠ ${g.ajustes_atrasados} atrasado${g.ajustes_atrasados === 1 ? "" : "s"}`}
        </p>
      )}

      {edita && (
        <fieldset className="formulario" disabled={ocupado}>
          <legend className="campo-rotulo">Registrar reunião feita</legend>
          <div className="formulario-duplo">
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="re-tipo">Tipo</label>
              <select id="re-tipo" className="selecao" value={campos.tipo} onChange={(e) => mudarTipo(e.target.value)}>
                {f.tipos.map((t) => <option key={t.chave} value={t.chave}>{t.nome}</option>)}
              </select>
            </div>
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="re-data">Data</label>
              <CampoDeData id="re-data" value={campos.data} aoMudar={(v) => mudar("data", v)} />
            </div>
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-participantes">Participantes</label>
            <input id="re-participantes" className="entrada" maxLength={300} value={campos.participantes} onChange={(e) => mudar("participantes", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-pauta">Pauta</label>
            <textarea id="re-pauta" className="entrada" rows={3} value={campos.pauta} onChange={(e) => mudar("pauta", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-dashboard">Dashboard apresentado (opcional)</label>
            <input id="re-dashboard" className="entrada" maxLength={400} placeholder="Link ou caminho no SharePoint"
              value={campos.dashboard} onChange={(e) => mudar("dashboard", e.target.value)} />
          </div>

          <div className="campo-bloco ata-transcricao">
            <label className="campo-rotulo" htmlFor="re-transcricao">Transcrição do Granola</label>
            <textarea id="re-transcricao" className="entrada" rows={5} placeholder="Cole aqui a transcrição ou as notas da reunião"
              value={campos.transcricao} onChange={(e) => mudar("transcricao", e.target.value)} />
            <div className="perfis-acoes">
              <button type="button" className="botao botao-secundario"
                disabled={montando || campos.transcricao.trim().length < MINIMO_DA_TRANSCRICAO} onClick={() => void montarAta()}>
                {montando ? "Montando a ata…" : "Montar a ata com a IA"}
              </button>
              <span className="campo-ajuda">
                {montando ? "· pode levar até um minuto" : "· a IA só monta o rascunho; nada é gravado até registrar"}
              </span>
            </div>
          </div>

          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-resumo">Resumo</label>
            <textarea id="re-resumo" className="entrada" rows={3} value={campos.resumo} onChange={(e) => mudar("resumo", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-decisoes">Decisões do cliente</label>
            <textarea id="re-decisoes" className="entrada" rows={3} placeholder="O que o cliente decidiu a partir dos números"
              value={campos.decisoes} onChange={(e) => mudar("decisoes", e.target.value)} />
          </div>

          <div className="campo-bloco">
            <span className="campo-rotulo" id="re-ajustes">Ajustes para a área técnica</span>
            {semResponsaveis && (
              <p className="campo-ajuda">⚠ Ninguém ainda pode receber ajustes. Libere a área técnica em Configurações › Perfis e acesso (perfil Área técnica).</p>
            )}
            {ajustes.length === 0 ? (
              <p className="campo-ajuda" style={{ margin: 0 }}>Nenhum ajuste. Monte a ata com a IA ou inclua à mão.</p>
            ) : (
              <ul className="ata-ajustes" aria-labelledby="re-ajustes">
                {ajustes.map((a, i) => (
                  <li key={a.chave}>
                    <textarea className="entrada" rows={2} aria-label={`Ajuste ${i + 1}: o quê`} value={a.descricao}
                      onChange={(e) => mudarAjuste(a.chave, { descricao: e.target.value })} />
                    <div className="ata-ajuste-linha">
                      <select className="selecao" aria-label={`Ajuste ${i + 1}: responsável`} value={a.responsavel_email}
                        onChange={(e) => mudarAjuste(a.chave, { responsavel_email: e.target.value })}>
                        <option value="">Responsável…</option>
                        {(responsaveis.dados ?? []).map((p) => <option key={p.email} value={p.email}>{p.nome ?? p.email}</option>)}
                      </select>
                      <CampoDeData aria-label={`Ajuste ${i + 1}: prazo`} value={a.prazo ?? ""} aoMudar={(v) => mudarAjuste(a.chave, { prazo: v || null })} />
                      <button type="button" className="botao-icone" aria-label={`Tirar o ajuste ${i + 1}`}
                        onClick={() => definirAjustes((lista) => lista.filter((x) => x.chave !== a.chave))}>✕</button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <div>
              <button type="button" className="botao botao-secundario" onClick={() => definirAjustes((l) => [...l, novoAjuste()])}>+ ajuste</button>
            </div>
          </div>

          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-pendencias">Pendências do cliente</label>
            <textarea id="re-pendencias" className="entrada" rows={2} value={campos.pendencias_do_cliente}
              onChange={(e) => mudar("pendencias_do_cliente", e.target.value)} />
          </div>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="re-sensiveis">Pontos sensíveis</label>
            <textarea id="re-sensiveis" className="entrada" rows={2} value={campos.pontos_sensiveis}
              onChange={(e) => mudar("pontos_sensiveis", e.target.value)} />
          </div>
          {falha && <p className="estado estado-erro estado-texto" role="alert">✗ {falha}</p>}
          {feito && <p className="recado" role="status">✓ {feito}</p>}
        </fieldset>
      )}

      <Historico f={f} g={g} />
    </PainelLateral>
  );
}
