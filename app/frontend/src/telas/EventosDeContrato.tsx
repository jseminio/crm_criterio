/** Eventos do contrato: aditivo, reajuste, expansão, contração, renovação, encerramento.
 *
 * **A vigência começa na assinatura** (decisão de 25/09/2026), então só contrato
 * assinado recebe evento. Cada evento é um **fato imutável**: depois de registrado
 * não se edita nem se apaga — errou, registra outro. Por isso o registro pede
 * confirmação em dois passos, e o painel deixa claro o que vai mudar no contrato.
 */

import { useState } from "react";
import { api, ErroDaApi } from "../api/cliente";
import type { ContratoDetalhe, EventoDeContrato } from "../api/tipos";
import { data, dataHora, dinheiro } from "../formato";
import { CampoDeData } from "../componentes/CampoDeData";
import { motivoDaAlcada } from "../alcada";
import { usarAcesso } from "../entrada";

type Tipo = EventoDeContrato["tipo"];
const TIPOS: { valor: Tipo; ajuda: string }[] = [
  { valor: "Reajuste", ajuda: "Troca o preço (para cima ou para baixo), por correção ou negociação." },
  { valor: "Expansão", ajuda: "O cliente contrata mais: o novo preço não pode ser menor." },
  { valor: "Contração", ajuda: "O cliente reduz o escopo: o novo preço não pode ser maior." },
  { valor: "Aditivo", ajuda: "Qualquer alteração contratual. Descreva o que mudou; escopo e preço são opcionais." },
  { valor: "Renovação", ajuda: "Estende a vigência: informe a nova data de fim." },
  { valor: "Correção", ajuda: "Corrige um valor lançado errado, com o motivo. Não conta como expansão nem contração no MRR." },
  { valor: "Encerramento", ajuda: "O cliente anunciou a saída. Até a saída efetiva o contrato segue ativo, faturando e no MRR; na saída o MRR cai, o churn conta e ele paga a 13ª proporcional." },
  { valor: "Desistência da saída", ajuda: "O cliente em aviso de saída decidiu ficar: desfaz o encerramento anunciado." },
];

/** Prazo do aviso: 30 ou 60 dias da data do anúncio, ou outra data negociada (10/10/2026). */
function maisDias(iso: string, dias: number): string {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + dias);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const hojeIso = () => maisDias(new Date().toISOString().slice(0, 10), 0);

const PRECOS: Tipo[] = ["Reajuste", "Expansão", "Contração", "Aditivo", "Correção"];

function Efeito({ e }: { e: EventoDeContrato }) {
  const partes: string[] = [];
  if (e.preco_mensal_novo !== null)
    partes.push(`mensal ${dinheiro(e.preco_mensal_anterior)} → ${dinheiro(e.preco_mensal_novo)}`);
  if (e.preco_anual_novo !== null)
    partes.push(`anual ${dinheiro(e.preco_anual_anterior)} → ${dinheiro(e.preco_anual_novo)}`);
  if (e.escopo_novo !== null) partes.push(`escopo “${e.escopo_anterior ?? "—"}” → “${e.escopo_novo}”`);
  if (e.data_fim_nova !== null)
    partes.push(`fim ${e.data_fim_anterior ? data(e.data_fim_anterior) : "—"} → ${data(e.data_fim_nova)}`);
  return <>{partes.length ? partes.join(" · ") : "sem mudança de valores"}</>;
}

export function EventosDeContrato({
  contrato,
  aoRegistrar,
  motivos = [],
  iniciativas = ["Cliente", "Critério"],
}: {
  contrato: ContratoDetalhe;
  aoRegistrar: (atualizado: ContratoDetalhe) => void;
  /** A lista de categorias de motivo de encerramento, vinda de `/api/listas`. */
  motivos?: string[];
  /** Quem pode decidir encerrar, vindo de `/api/listas` (Cliente, Critério). */
  iniciativas?: string[];
}) {
  const assinado = contrato.situacao === "Ativo" || contrato.situacao === "Suspenso";
  const emAviso = assinado && !!contrato.saida_em;
  // Em aviso de saída, só Correção, novo Encerramento (troca a saída) ou a Desistência.
  const tiposPossiveis = TIPOS.filter((t) =>
    emAviso ? ["Encerramento", "Desistência da saída", "Correção"].includes(t.valor) : t.valor !== "Desistência da saída");
  const [tipo, definirTipo] = useState<Tipo>(emAviso ? "Desistência da saída" : "Reajuste");
  const [prazo, definirPrazo] = useState<"30" | "60" | "outra">("30");
  const [campos, definirCampos] = useState<Record<string, string>>({});
  const [confirmando, definirConfirmando] = useState(false);
  const [salvando, definirSalvando] = useState(false);
  const [erro, definirErro] = useState<string | null>(null);
  const [enviado, definirEnviado] = useState<string | null>(null);
  const { eu, pode } = usarAcesso();
  const pendente = contrato.aprovacao_pendente ?? null;

  const mudar = (campo: string, valor: string) => {
    definirCampos((c) => ({ ...c, [campo]: valor }));
    definirConfirmando(false);
  };
  const ajuda = TIPOS.find((t) => t.valor === tipo)!.ajuda;
  const pedeMotivo = tipo === "Encerramento";
  const categoriaOutro = pedeMotivo && campos.motivo_categoria === "Outro";
  // Aditivo sempre descreve; no encerramento o texto só é obrigatório quando a
  // categoria é "Outro" — nas demais, a categoria já diz o porquê.
  const pedeDescricao = tipo === "Aditivo" || tipo === "Correção" || categoriaOutro;
  // Alçada (02/10/2026): sem login não há alçada; quem aprova registra direto.
  const alcada = eu.modo !== "local" && !pode("contratos.aprovar") ? motivoDaAlcada(contrato, tipo, campos) : null;
  const anuncio = campos.data_do_evento || hojeIso();
  const saida = prazo === "outra" ? campos.data_da_saida ?? "" : maisDias(anuncio, Number(prazo));
  const faltaDado =
    (pedeMotivo && (!campos.iniciativa || !campos.motivo_categoria || !saida || saida < anuncio)) ||
    (pedeDescricao && (campos.descricao ?? "").trim().length < 3) ||
    (tipo === "Renovação" && !campos.data_fim_nova) ||
    (["Reajuste", "Expansão", "Contração", "Correção"].includes(tipo) && !campos.preco_mensal_novo && !campos.preco_anual_novo);

  const registrar = async () => {
    definirSalvando(true);
    definirErro(null);
    try {
      const corpo: Record<string, unknown> = { tipo, data_do_evento: campos.data_do_evento || null };
      for (const k of ["descricao", "motivo_categoria", "iniciativa", "escopo_novo", "preco_mensal_novo", "preco_anual_novo", "data_fim_nova"]) {
        if (campos[k]) corpo[k] = campos[k];
      }
      if (tipo === "Encerramento") corpo.data_da_saida = saida;
      const atualizado = await api.registrarEventoDeContrato(contrato.id, corpo);
      definirCampos({});
      definirConfirmando(false);
      definirEnviado(atualizado.aprovacao_pendente ? `Pedido de ${tipo.toLowerCase()} enviado para aprovação: o contrato muda quando alguém aprovar.` : null);
      aoRegistrar(atualizado);
    } catch (falha) {
      definirErro(falha instanceof ErroDaApi ? falha.message : "Falha ao registrar.");
      definirConfirmando(false);
    } finally {
      definirSalvando(false);
    }
  };

  return (
    <div className="formulario">
      <h3 style={{ fontSize: 14, marginBottom: "var(--e2)" }}>Eventos do contrato</h3>

      {contrato.eventos.length === 0 ? (
        <p className="campo-ajuda" style={{ margin: 0 }}>Nenhum evento registrado desde a assinatura.</p>
      ) : (
        <ul className="eventos">
          {contrato.eventos.map((ev) => (
            <li key={ev.id} className="evento">
              <div>
                <strong>{ev.tipo}</strong> · {ev.tipo === "Encerramento" ? "anunciado em " : ""}{data(ev.data_do_evento)}
                {ev.tipo === "Encerramento" && ev.data_da_saida && <> · <strong>saída efetiva {data(ev.data_da_saida)}</strong></>}
                <span className="numero-nota"> · registrado em {dataHora(ev.registrado_em)}</span>
              </div>
              <div className="numero-nota"><Efeito e={ev} /></div>
              {ev.iniciativa && <div>Quem decidiu: <strong>{ev.iniciativa}</strong></div>}
              {ev.motivo_categoria && <div>Motivo: <strong>{ev.motivo_categoria}</strong></div>}
              {ev.descricao && <div>{ev.descricao}</div>}
            </li>
          ))}
        </ul>
      )}

      {enviado && <p className="recado" role="status">✓ {enviado}</p>}

      {pendente ? (
        <div className="recado recado-alcada" role="note">
          <strong>⏳ {pendente.tipo} aguardando aprovação</strong>, pedida por {pendente.pedido_por} em {dataHora(pendente.pedido_em)}
          {" "}({pendente.motivo}).
          {pendente.preco_mensal_novo !== null && ` Mensal ${dinheiro(pendente.preco_mensal_anterior)} → ${dinheiro(pendente.preco_mensal_novo)}.`}
          {pendente.preco_anual_novo !== null && ` Anual ${dinheiro(pendente.preco_anual_anterior)} → ${dinheiro(pendente.preco_anual_novo)}.`}
          {pendente.escopo_novo !== null && ` Escopo “${pendente.escopo_anterior ?? "—"}” → “${pendente.escopo_novo}”.`}
          {" "}Até a decisão, o contrato não recebe outro evento.
          {pode("contratos.aprovar") && " Aprove ou recuse na Agenda › Aprovações."}
        </div>
      ) : !assinado ? (
        <div className="recado">
          {contrato.situacao === "Encerrado"
            ? "Contrato encerrado: não recebe mais eventos."
            : "A vigência começa na assinatura. Informe a data da assinatura e ative o contrato para registrar eventos."}
        </div>
      ) : (
        <>
          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ev-tipo">Registrar evento</label>
            <select id="ev-tipo" className="selecao" value={tipo} onChange={(e) => { definirTipo(e.target.value as Tipo); definirConfirmando(false); }}>
              {tiposPossiveis.map((t) => <option key={t.valor} value={t.valor}>{t.valor}</option>)}
            </select>
            <p className="campo-ajuda">{ajuda}</p>
          </div>

          {emAviso && (
            <div className="recado" role="note">
              <strong>Em aviso de saída</strong> · sai em {data(contrato.saida_em)}. Até lá segue ativo e faturando; na saída,
              passa a Encerrado sozinho.
            </div>
          )}

          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ev-data">
              {pedeMotivo ? "Data do anúncio (o cliente avisou; vazio = hoje)" : "Data do evento (vazio = hoje)"}
            </label>
            <CampoDeData id="ev-data" value={campos.data_do_evento ?? ""} aoMudar={(v) => mudar("data_do_evento", v)} />
          </div>

          {pedeMotivo && (
            <div className="campo-bloco">
              <span className="campo-rotulo" id="ev-prazo">Prazo até a saída efetiva</span>
              <div className="opcoes-em-linha" role="radiogroup" aria-labelledby="ev-prazo">
                {(["30", "60", "outra"] as const).map((p) => (
                  <label key={p} className="opcao-em-linha">
                    <input type="radio" name="ev-prazo" checked={prazo === p} onChange={() => { definirPrazo(p); definirConfirmando(false); }} />
                    {p === "outra" ? "Outra data" : `${p} dias`}
                  </label>
                ))}
              </div>
              {prazo === "outra" ? (
                <>
                  <label className="campo-rotulo" htmlFor="ev-saida">Data da saída efetiva (último dia da Critério)</label>
                  <CampoDeData id="ev-saida" value={campos.data_da_saida ?? ""} aoMudar={(v) => mudar("data_da_saida", v)} />
                </>
              ) : null}
              <p className="campo-ajuda">
                {saida && saida >= anuncio
                  ? <>Saída efetiva em <strong>{data(saida)}</strong>. Até lá o contrato segue ativo, faturando e no MRR; na saída o MRR cai, o churn conta e o cliente paga a 13ª proporcional.</>
                  : "A saída efetiva não pode ser antes do anúncio."}
              </p>
            </div>
          )}

          {PRECOS.includes(tipo) && (
            <div className="formulario-duplo">
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ev-mensal">Novo preço mensal</label>
                <input id="ev-mensal" type="number" step="0.01" min="0" className="entrada" value={campos.preco_mensal_novo ?? ""} onChange={(e) => mudar("preco_mensal_novo", e.target.value)} placeholder={contrato.preco_mensal ?? ""} />
              </div>
              <div className="campo-bloco">
                <label className="campo-rotulo" htmlFor="ev-anual">Novo preço anual</label>
                <input id="ev-anual" type="number" step="0.01" min="0" className="entrada" value={campos.preco_anual_novo ?? ""} onChange={(e) => mudar("preco_anual_novo", e.target.value)} placeholder={contrato.preco_anual ?? ""} />
              </div>
            </div>
          )}

          {tipo === "Aditivo" && (
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ev-escopo">Novo escopo (opcional)</label>
              <input id="ev-escopo" className="entrada" maxLength={200} value={campos.escopo_novo ?? ""} onChange={(e) => mudar("escopo_novo", e.target.value)} placeholder={contrato.escopo ?? ""} />
            </div>
          )}

          {tipo === "Renovação" && (
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ev-fim">Nova data de fim</label>
              <CampoDeData id="ev-fim" value={campos.data_fim_nova ?? ""} aoMudar={(v) => mudar("data_fim_nova", v)} />
              <p className="campo-ajuda">Hoje o contrato termina em {contrato.data_fim ? data(contrato.data_fim) : "— (sem data de fim)"}.</p>
            </div>
          )}

          {pedeMotivo && (
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ev-iniciativa">Quem decidiu encerrar?</label>
              <select id="ev-iniciativa" className="selecao" value={campos.iniciativa ?? ""} onChange={(e) => mudar("iniciativa", e.target.value)}>
                <option value="">Escolha</option>
                {iniciativas.map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
              <p className="campo-ajuda">Separa saída do cliente (churn) de saída da Critério (saída organizada).</p>
            </div>
          )}

          {pedeMotivo && (
            <div className="campo-bloco">
              <label className="campo-rotulo" htmlFor="ev-categoria">Motivo do encerramento</label>
              <select id="ev-categoria" className="selecao" value={campos.motivo_categoria ?? ""} onChange={(e) => mudar("motivo_categoria", e.target.value)}>
                <option value="">Escolha a categoria</option>
                {motivos.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
              <p className="campo-ajuda">Alimenta a análise de saída (churn). A lista é uma proposta, ainda a aprovar.</p>
            </div>
          )}

          <div className="campo-bloco">
            <label className="campo-rotulo" htmlFor="ev-desc">
              {pedeMotivo ? (categoriaOutro ? "Descreva o motivo" : "Detalhe (opcional)") : tipo === "Correção" ? "Motivo da correção" : pedeDescricao ? "O que foi aditado" : "Motivo (opcional)"}
            </label>
            <input id="ev-desc" className="entrada" maxLength={500} value={campos.descricao ?? ""} onChange={(e) => mudar("descricao", e.target.value)} placeholder={pedeMotivo ? "ex.: o cliente migrou de contador" : "ex.: reajuste anual pelo IPCA"} />
          </div>

          {erro && <p role="alert" className="estado-texto">{erro}</p>}

          {confirmando ? (
            <>
              {alcada ? (
                <div className="recado recado-alcada" role="note">
                  <strong>⚠ Precisa de aprovação:</strong> {alcada}, acima da alçada do seu perfil (reduções de até 10% entram
                  direto). O evento fica <strong>aguardando aprovação</strong> e o contrato só muda quando um Administrador aprovar.
                </div>
              ) : (
                <div className="recado">
                  <strong>Isto não se edita nem se apaga depois.</strong> Se errar, registre outro evento.
                  {tipo === "Encerramento" && (saida <= hojeIso()
                    ? " A saída já chegou: o contrato passa a Encerrado e não recebe mais eventos."
                    : ` O contrato fica em aviso de saída até ${data(saida)} e então passa a Encerrado.`)}
                </div>
              )}
              <button type="button" className="botao botao-primario" disabled={salvando} onClick={registrar}>
                {salvando ? "Registrando…" : alcada ? "Enviar para aprovação" : `Confirmar ${tipo.toLowerCase()}`}
              </button>
            </>
          ) : (
            <button type="button" className="botao botao-secundario" disabled={faltaDado} onClick={() => definirConfirmando(true)}>
              Registrar {tipo.toLowerCase()}
            </button>
          )}
        </>
      )}
    </div>
  );
}
